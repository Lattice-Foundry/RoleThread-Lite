import copy
import inspect
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from core.dataset import load_dataset, save_dataset
from core.loreforge_meta import LOREFORGE_META_KEY, get_entry_uuid
from core.version import LOREFORGE_VERSION
import core.tag_registry as tag_registry
from services import dataset_service
from services.dataset_service import (
    clear_tags_bulk_service,
    create_entry_service,
    delete_entries_service,
    normalize_dataset_service,
    replace_single_entry_tags_service,
    replace_system_prompt_bulk_service,
    replace_tags_bulk_service,
    save_repaired_entries_service,
    save_full_edit_service,
    save_merged_entries_service,
    save_quick_edit_service,
)


def _entry(*, system="System", user="Hi", assistant="Hello", tags=None, metadata=None):
    entry = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "tags": list(tags or []),
    }
    if metadata:
        entry.update(metadata)
    return entry


def _multi_turn_entry(*, tags=None):
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "Doing well."},
        ],
        "tags": list(tags or []),
    }


def _malformed_entry():
    return {"messages": [{"role": "system", "content": "Only system"}], "tags": ["bad"]}


def _dataset_path(tmp_path):
    return tmp_path / "dataset.jsonl"


def _write_dataset(tmp_path, entries):
    path = _dataset_path(tmp_path)
    save_dataset(str(path), entries)
    return path


def _read_entries(path):
    entries, errors = load_dataset(str(path))
    assert errors == []
    return entries


def _without_loreforge_meta(value):
    if isinstance(value, list):
        return [_without_loreforge_meta(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _without_loreforge_meta(item)
            for key, item in value.items()
            if key != LOREFORGE_META_KEY
        }
    return value


def _assert_stamped(entries):
    assert entries
    for entry in entries:
        assert entry[LOREFORGE_META_KEY]["version"] == LOREFORGE_VERSION
        assert entry[LOREFORGE_META_KEY]["native"] is True
        assert entry[LOREFORGE_META_KEY]["validated_at"].endswith("Z")
        assert get_entry_uuid(entry) is not None


def _backup_recorder(monkeypatch, tmp_path):
    backup_paths = []
    backup_root = tmp_path / "backups"

    def fake_create_dataset_backup(dataset_path, reason):
        source = Path(dataset_path)
        if not source.is_file():
            return None
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_path = backup_root / f"{len(backup_paths):03d}_{reason}.jsonl"
        shutil.copyfile(source, backup_path)
        backup_paths.append(backup_path)
        return backup_path

    monkeypatch.setattr(dataset_service, "create_dataset_backup", fake_create_dataset_backup)
    return backup_paths


def _fail_if_backup_called(monkeypatch):
    def fail_backup(_dataset_path, _reason):
        raise AssertionError("backup should not be created")

    monkeypatch.setattr(dataset_service, "create_dataset_backup", fail_backup)


def _force_backup_failure(monkeypatch):
    def fail_backup(_dataset_path, _reason):
        raise RuntimeError("backup failed")

    monkeypatch.setattr(dataset_service, "create_dataset_backup", fail_backup)


def test_dataset_service_has_no_streamlit_import_or_session_state_usage():
    source = inspect.getsource(dataset_service)

    assert "import streamlit" not in source
    assert "from streamlit" not in source
    assert "st.session_state" not in source


def test_create_entry_service_appends_valid_entry_and_preserves_metadata(tmp_path):
    existing = [_entry(tags=["existing"])]
    path = _write_dataset(tmp_path, existing)
    new_entry = _entry(tags=["custom"], metadata={"source": "manual"})
    original_entries = copy.deepcopy(existing)

    result = create_entry_service(
        dataset_path=str(path),
        entries=existing,
        new_entry=new_entry,
    )

    assert result.ok is True
    assert result.affected_count == 1
    assert _without_loreforge_meta(result.entries) == existing + [new_entry]
    _assert_stamped(result.entries)
    assert existing == original_entries
    assert _read_entries(path) == result.entries


def test_create_entry_service_auto_corrects_role_typos_before_validation(tmp_path):
    existing = [_entry(tags=["existing"])]
    path = _write_dataset(tmp_path, existing)

    result = create_entry_service(
        dataset_path=str(path),
        entries=existing,
        new_entry={
            "messages": [
                {"role": "context", "content": "System"},
                {"role": "prompt", "content": "Hi"},
                {"role": "completion", "content": "Hello"},
            ],
            "tags": ["custom"],
        },
    )

    assert result.ok is True
    assert result.entries[-1]["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]
    assert _read_entries(path)[-1]["messages"] == result.entries[-1]["messages"]


def test_create_entry_service_invalid_entry_blocks_save_and_preserves_disk(tmp_path):
    existing = [_entry(tags=["existing"])]
    path = _write_dataset(tmp_path, existing)

    result = create_entry_service(
        dataset_path=str(path),
        entries=existing,
        new_entry=_malformed_entry(),
    )

    assert result.ok is False
    assert result.entries is None
    assert result.errors
    assert _read_entries(path) == existing


def test_create_entry_service_missing_dataset_path_fails_safely():
    result = create_entry_service(
        dataset_path="",
        entries=[],
        new_entry=_entry(),
    )

    assert result.ok is False
    assert result.entries is None


def test_save_quick_edit_service_saves_valid_messages_and_does_not_mutate_input(tmp_path):
    entries = [_entry(tags=["one"]), _entry(user="Old", assistant="Old answer", tags=["two"])]
    path = _write_dataset(tmp_path, entries)
    original_entries = copy.deepcopy(entries)
    updated_messages = [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "New user"},
        {"role": "assistant", "content": "New assistant"},
    ]

    result = save_quick_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=1,
        updated_messages=updated_messages,
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.affected_count == 1
    assert result.entries[1]["messages"] == updated_messages
    assert entries == original_entries
    assert _read_entries(path) == result.entries


def test_save_quick_edit_service_invalid_edit_does_not_modify_disk_or_input(tmp_path):
    entries = [_entry()]
    path = _write_dataset(tmp_path, entries)
    original_entries = copy.deepcopy(entries)

    result = save_quick_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_messages=[
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Missing assistant"},
        ],
        backup_enabled=False,
    )

    assert result.ok is False
    assert result.entries is None
    assert result.errors
    assert entries == original_entries
    assert _read_entries(path) == original_entries


def test_save_quick_edit_service_backup_enabled_creates_backup(tmp_path, monkeypatch):
    entries = [_entry()]
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = save_quick_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_messages=[
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Edited"},
            {"role": "assistant", "content": "Saved"},
        ],
        backup_enabled=True,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert result.backup_path == str(backups[0])


def test_save_quick_edit_service_backup_disabled_creates_no_backup(tmp_path, monkeypatch):
    entries = [_entry()]
    path = _write_dataset(tmp_path, entries)
    _fail_if_backup_called(monkeypatch)

    result = save_quick_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_messages=[
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Edited"},
            {"role": "assistant", "content": "Saved"},
        ],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.backup_path is None


def test_save_quick_edit_service_backup_failure_aborts_save(tmp_path, monkeypatch):
    entries = [_entry()]
    path = _write_dataset(tmp_path, entries)
    original_entries = copy.deepcopy(entries)
    _force_backup_failure(monkeypatch)

    result = save_quick_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_messages=[
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Edited"},
            {"role": "assistant", "content": "Saved"},
        ],
        backup_enabled=True,
    )

    assert result.ok is False
    assert result.entries is None
    assert _read_entries(path) == original_entries


def test_save_quick_edit_service_does_not_validate_unrelated_malformed_entries(tmp_path):
    entries = [_entry(), _malformed_entry()]
    path = _write_dataset(tmp_path, entries)

    result = save_quick_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_messages=[
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Edited"},
            {"role": "assistant", "content": "Saved"},
        ],
        backup_enabled=False,
    )

    assert result.ok is True
    assert _without_loreforge_meta(result.entries[1]) == entries[1]


def test_save_quick_edit_service_normalizes_role_variants_before_validation(tmp_path):
    entries = [
        {
            "messages": [
                {"role": "System", "content": "System"},
                {"role": "human", "content": "Hi"},
                {"role": "GPT", "content": "Hello"},
            ],
            "tags": ["slow burn", 7, ""],
        }
    ]
    path = _write_dataset(tmp_path, entries)

    result = save_quick_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_messages=[
            {"role": "System", "content": "System"},
            {"role": "user", "content": "Edited"},
            {"role": "assistant", "content": "Saved"},
        ],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.entries[0]["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Edited"},
        {"role": "assistant", "content": "Saved"},
    ]
    assert result.entries[0]["tags"] == ["slow_burn"]


def test_save_full_edit_service_saves_valid_full_edit_and_multiturn(tmp_path):
    entries = [_entry(tags=["old"])]
    path = _write_dataset(tmp_path, entries)
    updated_entry = _multi_turn_entry(tags=["new", "unknown"])
    original_entries = copy.deepcopy(entries)

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=updated_entry,
        backup_enabled=False,
    )

    assert result.ok is True
    assert _without_loreforge_meta(result.entries) == [updated_entry]
    _assert_stamped(result.entries)
    assert result.entries[0]["tags"] == ["new", "unknown"]
    assert entries == original_entries
    assert _read_entries(path) == result.entries


def test_dataset_save_services_auto_write_registry_sidecar(tmp_path, monkeypatch):
    entries = [_entry(tags=["old"])]
    path = _write_dataset(tmp_path, entries)
    sidecar_calls = []

    monkeypatch.setattr(
        dataset_service,
        "_write_registry_sidecar",
        lambda dataset_path, saved_entries: sidecar_calls.append(
            (dataset_path, copy.deepcopy(saved_entries))
        ),
    )

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=_entry(tags=["new"]),
        backup_enabled=False,
    )

    assert result.ok is True
    assert sidecar_calls == [(str(path), result.entries)]


def test_dataset_save_services_do_not_fail_when_sidecar_write_fails(tmp_path, monkeypatch):
    entries = [_entry(tags=["old"])]
    path = _write_dataset(tmp_path, entries)

    def fail_sidecar(_dataset_path, _saved_entries):
        raise RuntimeError("sidecar disk full")

    monkeypatch.setattr(dataset_service, "_write_registry_sidecar", fail_sidecar)

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=_entry(tags=["new"]),
        backup_enabled=False,
    )

    assert result.ok is True
    assert _read_entries(path) == result.entries


def test_dataset_save_migrates_flat_training_data_file_to_subfolder(
    tmp_path,
    monkeypatch,
):
    training_dir = tmp_path / "training_data"
    training_dir.mkdir()
    path = training_dir / "dataset.jsonl"
    entries = [_entry(tags=["old"])]
    save_dataset(str(path), entries)
    sidecar_path = path.with_name("dataset.registry.json")
    sidecar_path.write_text('{"metadata": {}}', encoding="utf-8")
    monkeypatch.setattr(
        dataset_service,
        "get_default_training_data_dir",
        lambda: training_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "core.working_copy.get_default_training_data_dir",
        lambda: training_dir,
    )

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=_entry(tags=["new"]),
        backup_enabled=False,
    )

    expected_path = training_dir / "dataset" / "dataset.jsonl"
    expected_sidecar = training_dir / "dataset" / "dataset.registry.json"
    assert result.ok is True
    assert result.dataset_path == str(expected_path.resolve())
    assert expected_path.exists()
    assert expected_sidecar.exists()
    assert not path.exists()
    assert not sidecar_path.exists()


def test_save_full_edit_service_auto_corrects_role_typos_before_validation(tmp_path):
    entries = [_entry(tags=["old"])]
    path = _write_dataset(tmp_path, entries)

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry={
            "messages": [
                {"role": "sytem", "content": "System"},
                {"role": "uesr", "content": "Hi"},
                {"role": "ASSITANT", "content": "Hello"},
            ],
            "tags": ["old"],
        },
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.entries[0]["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]


def test_save_full_edit_service_rewrites_stale_alias_tags(tmp_path, monkeypatch):
    entries = [_entry(tags=["old_tag", "active_tag"])]
    path = _write_dataset(tmp_path, entries)

    monkeypatch.setattr(
        tag_registry,
        "resolve_tag_lifecycle",
        lambda slug: SimpleNamespace(
            should_rewrite_slug=slug == "old_tag",
            resolved_slug="active_tag" if slug == "old_tag" else slug,
        ),
    )

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=_entry(tags=["old_tag", "active_tag"]),
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.entries[0]["tags"] == ["active_tag"]
    assert _read_entries(path)[0]["tags"] == ["active_tag"]


def test_save_full_edit_service_invalid_entry_blocks_save(tmp_path):
    entries = [_entry()]
    path = _write_dataset(tmp_path, entries)
    original_entries = copy.deepcopy(entries)

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=_malformed_entry(),
        backup_enabled=False,
    )

    assert result.ok is False
    assert result.entries is None
    assert result.errors
    assert entries == original_entries
    assert _read_entries(path) == original_entries


def test_save_full_edit_service_backup_enabled_disabled_and_failure_paths(tmp_path, monkeypatch):
    entries = [_entry()]
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=_entry(user="Edited", assistant="Saved"),
        backup_enabled=True,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert result.backup_path == str(backups[0])

    _fail_if_backup_called(monkeypatch)
    result = save_full_edit_service(
        dataset_path=str(path),
        entries=result.entries,
        entry_index=0,
        updated_entry=_entry(user="Edited again", assistant="Saved again"),
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.backup_path is None

    disk_before_failure = _read_entries(path)
    _force_backup_failure(monkeypatch)
    result = save_full_edit_service(
        dataset_path=str(path),
        entries=disk_before_failure,
        entry_index=0,
        updated_entry=_entry(user="Will not save", assistant="Nope"),
        backup_enabled=True,
    )

    assert result.ok is False
    assert _read_entries(path) == disk_before_failure


def test_replace_single_entry_tags_service_updates_only_target_and_preserves_unknown_tags(tmp_path):
    entries = [_entry(tags=["first"]), _entry(tags=["second"])]
    path = _write_dataset(tmp_path, entries)
    original_entries = copy.deepcopy(entries)

    result = replace_single_entry_tags_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=1,
        tags=["unknown", "reviewed"],
        backup_enabled=False,
    )

    assert result.ok is True
    assert _without_loreforge_meta(result.entries[0]) == entries[0]
    assert result.entries[1]["tags"] == ["unknown", "reviewed"]
    assert entries == original_entries
    assert _read_entries(path) == result.entries


def test_replace_single_entry_tags_service_invalid_tags_fail_safely(tmp_path):
    entries = [_entry(tags=["first"])]
    path = _write_dataset(tmp_path, entries)

    result = replace_single_entry_tags_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        tags=["ok", 7],
        backup_enabled=False,
    )

    assert result.ok is False
    assert result.entries is None
    assert _read_entries(path) == entries


def test_replace_tags_bulk_service_updates_only_selected_entries(tmp_path):
    entries = [_entry(tags=["first"]), _entry(tags=["second"]), _entry(tags=["third"])]
    path = _write_dataset(tmp_path, entries)
    original_entries = copy.deepcopy(entries)

    result = replace_tags_bulk_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[0, 2],
        tags=["bulk", "unknown"],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.affected_count == 2
    assert result.entries[0]["tags"] == ["bulk", "unknown"]
    assert _without_loreforge_meta(result.entries[1]) == entries[1]
    assert result.entries[2]["tags"] == ["bulk", "unknown"]
    assert entries == original_entries
    assert _read_entries(path) == result.entries


def test_clear_tags_bulk_service_clears_only_selected_entries(tmp_path):
    entries = [_entry(tags=["first"]), _entry(tags=["second"]), _entry(tags=["third"])]
    path = _write_dataset(tmp_path, entries)

    result = clear_tags_bulk_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[1],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.entries[0]["tags"] == ["first"]
    assert result.entries[1]["tags"] == []
    assert result.entries[2]["tags"] == ["third"]
    assert _read_entries(path) == result.entries


def test_bulk_tag_service_invalid_tags_fail_safely(tmp_path):
    entries = [_entry(tags=["first"])]
    path = _write_dataset(tmp_path, entries)

    result = replace_tags_bulk_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[0],
        tags=["ok", object()],
        backup_enabled=False,
    )

    assert result.ok is False
    assert result.entries is None
    assert _read_entries(path) == entries


def test_bulk_tag_service_backup_enabled_disabled_and_failure_paths(tmp_path, monkeypatch):
    entries = [_entry(tags=["first"]), _entry(tags=["second"])]
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = replace_tags_bulk_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[0],
        tags=["changed"],
        backup_enabled=True,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert result.backup_path == str(backups[0])

    _fail_if_backup_called(monkeypatch)
    result = clear_tags_bulk_service(
        dataset_path=str(path),
        entries=result.entries,
        entry_indices=[1],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.backup_path is None

    disk_before_failure = _read_entries(path)
    _force_backup_failure(monkeypatch)
    result = replace_tags_bulk_service(
        dataset_path=str(path),
        entries=disk_before_failure,
        entry_indices=[0],
        tags=["will-not-save"],
        backup_enabled=True,
    )

    assert result.ok is False
    assert _read_entries(path) == disk_before_failure


def test_replace_system_prompt_bulk_service_replaces_or_inserts_system_prompt(tmp_path):
    no_system = {
        "messages": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": ["no-system"],
    }
    entries = [_entry(tags=["selected"]), no_system, _entry(tags=["unselected"])]
    path = _write_dataset(tmp_path, entries)
    original_entries = copy.deepcopy(entries)

    result = replace_system_prompt_bulk_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[0, 1],
        system_prompt="New system",
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.entries[0]["messages"][0] == {"role": "system", "content": "New system"}
    assert result.entries[1]["messages"][0] == {"role": "system", "content": "New system"}
    assert result.entries[1]["messages"][1:] == no_system["messages"]
    assert result.entries[0]["tags"] == ["selected"]
    assert result.entries[1]["tags"] == ["no_system"]
    assert _without_loreforge_meta(result.entries[2]) == entries[2]
    assert entries == original_entries
    assert _read_entries(path) == result.entries


def test_replace_system_prompt_bulk_service_backup_enabled_disabled_and_failure_paths(tmp_path, monkeypatch):
    entries = [_entry()]
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = replace_system_prompt_bulk_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[0],
        system_prompt="Backed up",
        backup_enabled=True,
    )

    assert result.ok is True
    assert len(backups) == 1

    _fail_if_backup_called(monkeypatch)
    result = replace_system_prompt_bulk_service(
        dataset_path=str(path),
        entries=result.entries,
        entry_indices=[0],
        system_prompt="No backup",
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.backup_path is None

    disk_before_failure = _read_entries(path)
    _force_backup_failure(monkeypatch)
    result = replace_system_prompt_bulk_service(
        dataset_path=str(path),
        entries=disk_before_failure,
        entry_indices=[0],
        system_prompt="Will not save",
        backup_enabled=True,
    )

    assert result.ok is False
    assert _read_entries(path) == disk_before_failure


def test_delete_entries_service_removes_selected_entries_and_preserves_order(tmp_path):
    entries = [
        _entry(user="One", tags=["one"]),
        _entry(user="Two", tags=["two"]),
        _entry(user="Three", tags=["three"]),
        _entry(user="Four", tags=["four"]),
    ]
    path = _write_dataset(tmp_path, entries)
    original_entries = copy.deepcopy(entries)

    result = delete_entries_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[2, 1, 1],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.affected_count == 2
    assert _without_loreforge_meta(result.entries) == [entries[0], entries[3]]
    assert entries == original_entries
    assert _read_entries(path) == result.entries


def test_delete_entries_service_invalid_indices_fail_safely(tmp_path):
    entries = [_entry()]
    path = _write_dataset(tmp_path, entries)

    result = delete_entries_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[3],
        backup_enabled=False,
    )

    assert result.ok is False
    assert result.entries is None
    assert _read_entries(path) == entries


def test_delete_entries_service_can_delete_malformed_selected_entries(tmp_path):
    entries = [_entry(tags=["good"]), _malformed_entry(), _entry(tags=["also-good"])]
    path = _write_dataset(tmp_path, entries)

    result = delete_entries_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[1],
        backup_enabled=False,
    )

    assert result.ok is True
    assert _without_loreforge_meta(result.entries) == [entries[0], _entry(tags=["also_good"])]
    assert _read_entries(path) == result.entries


def test_delete_entries_service_backup_enabled_disabled_and_failure_paths(tmp_path, monkeypatch):
    entries = [_entry(user="One"), _entry(user="Two")]
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = delete_entries_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[0],
        backup_enabled=True,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert result.backup_path == str(backups[0])

    _fail_if_backup_called(monkeypatch)
    result = delete_entries_service(
        dataset_path=str(path),
        entries=result.entries,
        entry_indices=[0],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.backup_path is None

    save_dataset(str(path), entries)
    _force_backup_failure(monkeypatch)
    result = delete_entries_service(
        dataset_path=str(path),
        entries=entries,
        entry_indices=[0],
        backup_enabled=True,
    )

    assert result.ok is False
    assert _read_entries(path) == entries


def test_save_merged_entries_service_saves_new_output_and_preserves_metadata(tmp_path):
    path = tmp_path / "merged.jsonl"
    entries = [_entry(tags=["merged"], metadata={"source": "merge"})]
    original_entries = copy.deepcopy(entries)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=entries,
        backup_enabled=True,
    )

    assert result.ok is True
    assert result.backup_path is None
    assert _without_loreforge_meta(result.entries) == entries
    _assert_stamped(result.entries)
    assert entries == original_entries
    assert _read_entries(path) == result.entries


def test_save_merged_entries_service_overwrite_backup_enabled_and_disabled(tmp_path, monkeypatch):
    path = tmp_path / "merged.jsonl"
    original = [_entry(tags=["old"])]
    save_dataset(str(path), original)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["new"])],
        backup_enabled=True,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert result.backup_path == str(backups[0])

    _fail_if_backup_called(monkeypatch)
    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["newer"])],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.backup_path is None
    assert _read_entries(path) == result.entries


def test_save_merged_entries_service_invalid_path_fails_safely():
    result = save_merged_entries_service(
        dataset_path="",
        entries=[],
        backup_enabled=False,
    )

    assert result.ok is False
    assert result.entries is None


def test_save_merged_entries_service_backup_failure_aborts_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "merged.jsonl"
    existing = [_entry(tags=["existing"])]
    save_dataset(str(path), existing)
    _force_backup_failure(monkeypatch)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["replacement"])],
        backup_enabled=True,
    )

    assert result.ok is False
    assert _read_entries(path) == existing


def test_normalize_dataset_service_persists_structural_metadata_and_creates_backup(tmp_path, monkeypatch):
    entries = [{"messages": _entry()["messages"]}, _entry(tags=["sLow burn"])]
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = normalize_dataset_service(
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is True
    assert result.backup_path is not None
    assert len(backups) == 1
    assert result.entries[0]["tags"] == []
    assert result.entries[1]["tags"] == ["slow_burn"]
    assert _read_entries(path) == result.entries


def test_normalize_dataset_service_backup_failure_aborts_save(tmp_path, monkeypatch):
    entries = [{"messages": _entry()["messages"]}]
    path = _write_dataset(tmp_path, entries)
    before = path.read_text(encoding="utf-8")
    _force_backup_failure(monkeypatch)

    result = normalize_dataset_service(dataset_path=str(path), entries=entries)

    assert result.ok is False
    assert "backup" in result.message.lower()
    assert path.read_text(encoding="utf-8") == before


def test_save_repaired_entries_service_auto_corrects_role_typos_with_backup(
    tmp_path,
    monkeypatch,
):
    original = [_entry(tags=["original"])]
    path = _write_dataset(tmp_path, original)
    backups = _backup_recorder(monkeypatch, tmp_path)
    repaired_entries = [
        {
            "messages": [
                {"role": "SYSTEM", "content": " System "},
                {"role": "Human", "content": " Hi "},
                {"role": "GPT", "content": " Hello "},
            ],
            "tags": ["slow burn", 7],
        }
    ]

    result = save_repaired_entries_service(
        dataset_path=str(path),
        repaired_entries=repaired_entries,
        backup_reason="before_validation_test",
    )
    written = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert result.ok is True
    assert result.message == "Repaired entries saved."
    assert result.backup_path == str(backups[0])
    assert result.affected_count == 1
    assert _without_loreforge_meta(result.entries) == [
        {
            "messages": [
                {"role": "system", "content": " System "},
                {"role": "user", "content": " Hi "},
                {"role": "assistant", "content": " Hello "},
            ],
            "tags": ["slow burn", 7],
        }
    ]
    _assert_stamped(result.entries)
    assert result.entries is not repaired_entries
    assert written == result.entries
    assert _read_entries(backups[0]) == original


def test_save_repaired_entries_service_backup_failure_aborts_save(tmp_path, monkeypatch):
    original = [_entry(tags=["original"])]
    path = _write_dataset(tmp_path, original)
    before = path.read_text(encoding="utf-8")
    _force_backup_failure(monkeypatch)

    result = save_repaired_entries_service(
        dataset_path=str(path),
        repaired_entries=[_entry(tags=["replacement"])],
    )

    assert result.ok is False
    assert "backup" in result.message.lower()
    assert path.read_text(encoding="utf-8") == before


def test_save_repaired_entries_service_rejects_invalid_inputs(tmp_path):
    missing_path = tmp_path / "missing.jsonl"

    result = save_repaired_entries_service(
        dataset_path=str(missing_path),
        repaired_entries=[],
    )

    assert result.ok is False
    assert result.entries is None
    assert "Dataset file was not found." in result.errors
