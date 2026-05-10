import json
import shutil
from types import SimpleNamespace

from services import dataset_service
import ui.session_state as session_state
from core.dataset import load_dataset_with_summary
from services.dataset_service import DatasetOperationResult


class FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _entry_without_tags():
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
    }


def _patch_state(monkeypatch):
    fake_state = FakeSessionState()
    monkeypatch.setattr(session_state, "st", SimpleNamespace(session_state=fake_state))
    monkeypatch.setattr(
        session_state,
        "ensure_tags_exist_for_dataset",
        lambda entries: SimpleNamespace(created_count=0, created_slugs=[]),
    )
    return fake_state


def test_set_loaded_entries_tracks_pending_structural_normalization(monkeypatch):
    state = _patch_state(monkeypatch)

    normalization, errors = _load_entries_with_summary([_entry_without_tags()])

    assert errors == []
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert state.loaded_entries[0]["tags"] == []
    assert state.normalization_pending is True
    assert state.tag_normalization_summary["tag_metadata_added_count"] == 1
    assert state.tag_normalization_summary["structural_changed_entries"] == 1


def test_set_loaded_entries_canonicalizes_tags_even_without_pending_structural_cleanup(monkeypatch):
    state = _patch_state(monkeypatch)
    entry = _entry_without_tags()
    entry["tags"] = ["sLow burn"]

    session_state.set_loaded_entries([entry])

    assert state.loaded_entries[0]["tags"] == ["slow_burn"]
    assert state.normalization_pending is False


def test_persist_loaded_normalization_clears_pending_state_on_success(monkeypatch):
    state = _patch_state(monkeypatch)
    normalization, _ = _load_entries_with_summary([_entry_without_tags()])
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    def fake_normalize_dataset_service(dataset_path, entries):
        return DatasetOperationResult(
            ok=True,
            message="Dataset normalized.",
            entries=entries,
            backup_path="backup.jsonl",
            affected_count=len(entries),
        )

    monkeypatch.setattr(
        session_state,
        "normalize_dataset_service",
        fake_normalize_dataset_service,
    )

    result = session_state.persist_loaded_normalization("dataset.jsonl")

    assert result.ok is True
    assert state.normalization_pending is False
    assert state.tag_normalization_summary["tag_metadata_added_count"] == 0
    assert state.tag_normalization_summary["structural_changed_entries"] == 0


def _load_entries_with_summary(entries):
    from tempfile import TemporaryDirectory
    from pathlib import Path

    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "dataset.jsonl"
        path.write_text(
            "\n".join(json.dumps(entry) for entry in entries) + "\n",
            encoding="utf-8",
        )
        return load_dataset_with_summary(str(path))


def test_auto_normalize_enabled_explicit_load_can_persist_missing_tag_metadata(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "legacy.jsonl"
    legacy_entries = [_entry_without_tags(), _entry_without_tags()]
    path.write_text(
        "\n".join(json.dumps(entry) for entry in legacy_entries) + "\n",
        encoding="utf-8",
    )
    backup_path = tmp_path / "backup.jsonl"
    monkeypatch.setattr(
        dataset_service,
        "create_dataset_backup",
        lambda dataset_path, reason: shutil.copyfile(dataset_path, backup_path) or backup_path,
    )

    normalization, errors = load_dataset_with_summary(str(path))
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=errors,
        normalization_pending=state.normalization_pending,
    ) is True

    result = session_state.persist_loaded_normalization(str(path))
    saved_text = path.read_text(encoding="utf-8")

    assert result.ok is True
    assert state.normalization_pending is False
    assert '"tags": []' in saved_text


def test_auto_normalize_disabled_explicit_load_keeps_disk_unchanged_and_pending(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "legacy.jsonl"
    legacy_entry = _entry_without_tags()
    original_text = json.dumps(legacy_entry) + "\n"
    path.write_text(original_text, encoding="utf-8")

    normalization, errors = load_dataset_with_summary(str(path))
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": False},
        parse_errors=errors,
        normalization_pending=state.normalization_pending,
    ) is False
    assert state.loaded_entries[0]["tags"] == []
    assert state.normalization_pending is True
    assert path.read_text(encoding="utf-8") == original_text


def test_startup_reload_can_track_pending_without_persisting(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "legacy.jsonl"
    legacy_entry = _entry_without_tags()
    original_text = json.dumps(legacy_entry) + "\n"
    path.write_text(original_text, encoding="utf-8")

    normalization, errors = load_dataset_with_summary(str(path))
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert errors == []
    assert state.loaded_entries[0]["tags"] == []
    assert state.normalization_pending is True
    assert path.read_text(encoding="utf-8") == original_text


def test_should_auto_normalize_loaded_dataset_respects_setting_errors_and_pending_state():
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=[],
        normalization_pending=True,
    ) is True
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": False},
        parse_errors=[],
        normalization_pending=True,
    ) is False
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=["Line 2: bad json"],
        normalization_pending=True,
    ) is False
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=[],
        normalization_pending=False,
    ) is False


def test_should_auto_normalize_loaded_dataset_prefers_live_session_value():
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": False},
        parse_errors=[],
        normalization_pending=True,
        auto_normalize_on_load=True,
    ) is True
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=[],
        normalization_pending=True,
        auto_normalize_on_load=False,
    ) is False
