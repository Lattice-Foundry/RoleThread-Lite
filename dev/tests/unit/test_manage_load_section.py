import json
from datetime import datetime
from types import SimpleNamespace

import ui.manage.load_section as load_section
from core.registry_sidecar import (
    build_sidecar_registry,
    sidecar_path_for_dataset,
    write_sidecar,
)


class FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _fake_streamlit(state: FakeSessionState):
    return SimpleNamespace(
        session_state=state,
        error=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        success=lambda *args, **kwargs: None,
        rerun=lambda: None,
    )


class _TrackingColumn:
    def __init__(self, fake, name: str):
        self.fake = fake
        self.name = name

    def __enter__(self):
        self.fake.active_column = self.name
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.fake.active_column = None
        return False


class FakeLayoutStreamlit:
    def __init__(self):
        self.session_state = FakeSessionState(
            prefs={},
            loaded_path="",
            working_copy_summary=None,
        )
        self.active_column = None
        self.clicked_buttons = {"Load"}

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [
            _TrackingColumn(self, f"col_{index}")
            for index in range(count)
        ]

    def button(self, label, **_kwargs):
        return label in self.clicked_buttons


class FakeRecentStreamlit:
    def __init__(self, recent_paths: list[str]):
        self.session_state = FakeSessionState(
            prefs={load_section.RECENT_DATASETS_KEY: recent_paths},
        )
        self.button_calls: list[dict] = []
        self.clicked_buttons: set[str] = set()
        self.markdowns: list[str] = []
        self.rerun_count = 0

    def markdown(self, message):
        self.markdowns.append(message)

    def button(self, label, **kwargs):
        self.button_calls.append({"label": label, **kwargs})
        return kwargs.get("key") in self.clicked_buttons

    def rerun(self):
        self.rerun_count += 1

    def container(self, *, key=None):
        self.container_key = key
        return _TrackingColumn(self, "container")


def test_foreign_load_updates_manage_path_to_working_copy(monkeypatch, tmp_path):
    state = FakeSessionState(
        prefs={},
        tag_normalization_summary={"changed_entries": 0},
        normalization_pending=False,
    )
    monkeypatch.setattr(load_section, "st", _fake_streamlit(state))

    original_path = tmp_path / "source" / "dataset.jsonl"
    working_path = tmp_path / "training_data" / "dataset" / "dataset.jsonl"
    normalization = SimpleNamespace(entries=[{"messages": [], "tags": []}])

    monkeypatch.setattr(
        load_section,
        "load_dataset_with_summary",
        lambda path, *, auto_normalize: (normalization, []),
    )
    monkeypatch.setattr(
        load_section,
        "render_load_errors",
        lambda normalization, errors, entries: False,
    )
    monkeypatch.setattr(
        load_section,
        "set_loaded_entries",
        lambda entries, normalization_summary, dataset_path: str(working_path),
    )
    monkeypatch.setattr(load_section, "clear_selected_entries", lambda: None)
    monkeypatch.setattr(
        load_section,
        "should_persist_loaded_normalization",
        lambda *, parse_errors, normalization_pending: False,
    )
    monkeypatch.setattr(load_section, "update_prefs", lambda updates: None)
    monkeypatch.setattr(load_section, "render_load_format_summary", lambda *args, **kwargs: None)

    load_section._load_dataset(str(original_path))

    assert state.loaded_path == str(working_path)
    assert state["manage_load_path_pending"] == str(working_path)


def test_load_path_guard_blocks_active_working_copy_source(tmp_path):
    original_path = tmp_path / "source" / "dataset.jsonl"
    working_path = tmp_path / "training_data" / "dataset" / "dataset.jsonl"
    other_path = tmp_path / "source" / "other.jsonl"

    assert load_section._is_load_path_already_active(
        str(working_path),
        str(working_path),
        {"original_path": str(original_path)},
    )
    assert load_section._is_load_path_already_active(
        str(original_path),
        str(working_path),
        {"original_path": str(original_path)},
    )
    assert not load_section._is_load_path_already_active(
        str(other_path),
        str(working_path),
        {"original_path": str(original_path)},
    )


def test_load_controls_run_selected_action_after_button_columns(monkeypatch):
    fake = FakeLayoutStreamlit()
    action_columns: list[str | None] = []
    monkeypatch.setattr(load_section, "st", fake)
    monkeypatch.setattr(load_section, "path_input", lambda *args, **kwargs: "dataset.jsonl")
    monkeypatch.setattr(load_section, "_render_rename_panel", lambda: None)
    monkeypatch.setattr(
        load_section,
        "_load_dataset",
        lambda _path: action_columns.append(fake.active_column),
    )

    load_section._render_load_controls()

    assert action_columns == [None]


def test_recent_datasets_render_as_full_width_borderless_rows(monkeypatch, tmp_path):
    recent_path = tmp_path / "a" / "very" / "long" / "dataset" / "path.jsonl"
    recent_path.parent.mkdir(parents=True)
    recent_path.write_text("{}", encoding="utf-8")
    fake = FakeRecentStreamlit([str(recent_path)])
    monkeypatch.setattr(load_section, "st", fake)

    load_section._render_recent_datasets()

    assert fake.markdowns == ["**Recent Datasets**"]
    assert fake.container_key == "recent_dataset_list"
    assert fake.button_calls == [
        {
            "label": str(recent_path),
            "key": "btn_recent_dataset_0",
            "disabled": False,
            "type": "tertiary",
        }
    ]


def test_recent_dataset_click_queues_load_for_next_render(monkeypatch, tmp_path):
    recent_path = tmp_path / "dataset.jsonl"
    recent_path.write_text("{}", encoding="utf-8")
    fake = FakeRecentStreamlit([str(recent_path)])
    fake.clicked_buttons.add("btn_recent_dataset_0")
    load_calls: list[str] = []
    monkeypatch.setattr(load_section, "st", fake)
    monkeypatch.setattr(load_section, "_load_dataset", load_calls.append)

    load_section._render_recent_datasets()

    assert fake.session_state[load_section.PENDING_RECENT_DATASET_LOAD_KEY] == str(
        recent_path
    )
    assert fake.rerun_count == 1
    assert load_calls == []


def test_pending_recent_dataset_load_renders_before_recent_list(monkeypatch):
    state = FakeSessionState(
        {load_section.PENDING_RECENT_DATASET_LOAD_KEY: "queued.jsonl"}
    )
    fake = _fake_streamlit(state)
    load_calls: list[str] = []
    monkeypatch.setattr(load_section, "st", fake)
    monkeypatch.setattr(load_section, "_load_dataset", load_calls.append)

    load_section._render_pending_recent_dataset_load()

    assert load_calls == ["queued.jsonl"]
    assert load_section.PENDING_RECENT_DATASET_LOAD_KEY not in state


def test_open_and_close_rename_dataset_panel(monkeypatch, tmp_path):
    loaded_path = tmp_path / "training_data" / "dataset" / "dataset.jsonl"
    state = FakeSessionState(loaded_path=str(loaded_path))
    monkeypatch.setattr(load_section, "st", _fake_streamlit(state))

    load_section._open_rename_dataset_panel()

    assert state[load_section.RENAME_DATASET_PANEL_KEY] is True
    assert state[load_section.RENAME_DATASET_SOURCE_KEY] == str(loaded_path)
    assert state[load_section.RENAME_DATASET_NAME_KEY] == "dataset"

    load_section._close_rename_dataset_panel()

    assert state[load_section.RENAME_DATASET_PANEL_KEY] is False
    assert load_section.RENAME_DATASET_SOURCE_KEY not in state
    assert load_section.RENAME_DATASET_NAME_KEY not in state


def test_default_new_dataset_filename_is_timestamped():
    assert (
        load_section._default_new_dataset_filename(datetime(2026, 5, 13, 8, 9, 10))
        == "dataset_20260513_080910.jsonl"
    )


def test_update_recent_dataset_paths_promotes_and_deduplicates(tmp_path):
    first = str(tmp_path / "first.jsonl")
    second = str(tmp_path / "second.jsonl")
    third = str(tmp_path / "third.jsonl")

    recent = load_section.update_recent_dataset_paths(
        [first, second, first, third],
        second,
        limit=3,
    )

    assert recent == [second, first, third]


def test_replace_recent_dataset_path_preserves_order_without_duplicates(tmp_path):
    old_path = str(tmp_path / "old.jsonl")
    new_path = str(tmp_path / "new.jsonl")
    other_path = str(tmp_path / "other.jsonl")

    recent = load_section.replace_recent_dataset_path(
        [other_path, old_path, new_path],
        old_path,
        new_path,
    )

    assert recent == [other_path, new_path]


def test_create_new_dataset_writes_current_sidecar_schema(monkeypatch, tmp_path):
    state = FakeSessionState(prefs={})
    monkeypatch.setattr(load_section, "st", _fake_streamlit(state))

    requested_path = tmp_path / "training_data" / "dataset.jsonl"
    canonical_path = tmp_path / "training_data" / "dataset" / "dataset.jsonl"

    def fake_export_registry_sidecar(*, dataset_path, entries):
        registry = build_sidecar_registry(
            categories=[],
            tags=[],
            aliases=[],
            characters=[],
            entry_character_mappings=[],
            dataset_uuid="dataset-uuid",
            dataset_filename=canonical_path.name,
            entry_count=len(entries),
            tag_usage_counts={},
        )
        write_sidecar(registry, sidecar_path_for_dataset(canonical_path))
        return SimpleNamespace(ok=True, message="Sidecar written.")

    monkeypatch.setattr(
        load_section,
        "canonical_training_dataset_path",
        lambda path: canonical_path,
    )
    monkeypatch.setattr(load_section, "export_registry_sidecar", fake_export_registry_sidecar)
    monkeypatch.setattr(load_section, "set_loaded_entries", lambda entries: None)
    monkeypatch.setattr(load_section, "clear_selected_entries", lambda: None)
    monkeypatch.setattr(load_section, "update_prefs", lambda updates: None)

    load_section._create_new_dataset(str(requested_path))

    assert canonical_path.exists()
    sidecar_data = json.loads(sidecar_path_for_dataset(canonical_path).read_text(encoding="utf-8"))
    assert sidecar_data != {}
    assert sidecar_data["metadata"]["kind"] == "loreforge.tag_registry"
    assert sidecar_data["dataset"]["dataset_uuid"] == "dataset-uuid"


def test_rename_loaded_dataset_updates_session_paths(monkeypatch, tmp_path):
    old_path = tmp_path / "training_data" / "old_name" / "old_name.jsonl"
    new_path = tmp_path / "training_data" / "new_name" / "new_name.jsonl"
    state = FakeSessionState(
        prefs={},
        loaded_path=str(old_path),
        working_copy_summary={
            "original_path": str(tmp_path / "source" / "old_name.jsonl"),
            "working_path": str(old_path),
            "sidecar_path": str(old_path.with_name("old_name.registry.json")),
        },
    )
    monkeypatch.setattr(load_section, "st", _fake_streamlit(state))
    monkeypatch.setattr(
        load_section,
        "rename_working_dataset",
        lambda loaded_path, new_name: SimpleNamespace(
            old_path=str(old_path),
            new_path=str(new_path),
            new_sidecar_path=str(new_path.with_name("new_name.registry.json")),
        ),
    )
    prefs_updates = []
    monkeypatch.setattr(load_section, "update_prefs", lambda updates: prefs_updates.append(updates))
    flashes = []
    monkeypatch.setattr(load_section, "enqueue_flash", lambda level, message: flashes.append((level, message)))

    load_section._rename_loaded_dataset("new_name")

    assert state.loaded_path == str(new_path)
    assert state["manage_load_path_pending"] == str(new_path)
    assert state["entry_search_dataset_identifier"] == str(new_path)
    assert state.working_copy_summary["working_path"] == str(new_path)
    assert state.working_copy_summary["sidecar_path"] == str(new_path.with_name("new_name.registry.json"))
    assert prefs_updates == [
        {
            "last_loaded_dataset_path": str(new_path),
            "last_open_directory": str(new_path.parent),
            "recent_dataset_paths": [str(new_path)],
        }
    ]
    assert flashes == [("success", "Dataset renamed to `new_name`.")]
