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


def test_default_new_dataset_filename_is_timestamped():
    assert (
        load_section._default_new_dataset_filename(datetime(2026, 5, 13, 8, 9, 10))
        == "dataset_20260513_080910.jsonl"
    )


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
        }
    ]
    assert flashes == [("success", "Dataset renamed to `new_name`.")]
