import copy
import inspect
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.dataset import load_dataset, save_dataset
from core.loreforge_meta import (
    LOREFORGE_META_KEY,
    get_dataset_uuid_for_entries,
    get_entry_uuid,
    stamp_entries,
)
from core.registry_sidecar import (
    SidecarAlias,
    SidecarCategory,
    SidecarCharacter,
    SidecarDatasetInfo,
    SidecarEntryCharacterMapping,
    SidecarMetadata,
    SidecarRegistry,
    SidecarTag,
    read_sidecar,
    sidecar_path_for_dataset,
    write_sidecar,
)
from core.models import Base, Character, EntryCharacterTurn, Tag, TagCategory
import core.tag_registry as tag_registry
from core.version import LOREFORGE_VERSION
import core.tag_resolution as tag_resolution
import services.registry_sidecar_service as registry_sidecar_service
from services import dataset_service
from services.dataset_service import (
    clear_tags_bulk_service,
    create_entry_service,
    delete_entries_service,
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
    assert get_dataset_uuid_for_entries(entries) is not None


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


def _registry_session_factory(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'merge_registry.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(tag_registry, "engine", engine)
    monkeypatch.setattr(tag_registry, "SessionLocal", session_factory)
    monkeypatch.setattr(registry_sidecar_service, "engine", engine)
    monkeypatch.setattr(registry_sidecar_service, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_resolution, "SessionLocal", session_factory)
    monkeypatch.setattr(
        registry_sidecar_service,
        "create_db_backup",
        lambda *, engine: tmp_path / "db_backup.sqlite",
    )
    return session_factory


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
        backup_enabled=False,
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
        backup_enabled=False,
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
        backup_enabled=False,
    )

    assert result.ok is False
    assert result.entries is None
    assert result.errors
    assert _read_entries(path) == existing


def test_create_entry_service_creates_backup_before_append(tmp_path, monkeypatch):
    existing = [_entry(tags=["existing"])]
    path = _write_dataset(tmp_path, existing)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = create_entry_service(
        dataset_path=str(path),
        entries=existing,
        new_entry=_entry(tags=["custom"]),
    )

    assert result.ok is True
    assert len(backups) == 1
    assert result.backup_path == str(backups[0])
    assert _read_entries(backups[0]) == existing
    assert _read_entries(path) == result.entries
    assert len(result.entries) == 2


def test_create_entry_service_backup_failure_blocks_append(tmp_path, monkeypatch):
    existing = [_entry(tags=["existing"])]
    path = _write_dataset(tmp_path, existing)
    original_entries = copy.deepcopy(existing)
    _force_backup_failure(monkeypatch)

    monkeypatch.setattr(
        dataset_service,
        "_write_registry_sidecar",
        lambda *_args: (_ for _ in ()).throw(AssertionError("sidecar should not write")),
    )

    result = create_entry_service(
        dataset_path=str(path),
        entries=existing,
        new_entry=_entry(tags=["custom"]),
    )

    assert result.ok is False
    assert result.entries is None
    assert result.backup_path is None
    assert "Failed to create dataset backup" in result.message
    assert _read_entries(path) == original_entries


def test_create_entry_service_first_entry_into_empty_dataset_creates_dataset_uuid_and_sidecar(
    tmp_path,
):
    path = _write_dataset(tmp_path, [])

    result = create_entry_service(
        dataset_path=str(path),
        entries=[],
        new_entry=_entry(tags=[]),
        backup_enabled=False,
    )

    dataset_uuid = get_dataset_uuid_for_entries(result.entries)
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert result.ok is True
    assert dataset_uuid is not None
    assert sidecar.dataset_info.dataset_uuid == dataset_uuid
    assert sidecar.dataset_info.entry_count == 1
    assert _read_entries(path) == result.entries


def test_create_entry_service_first_entry_into_empty_dataset_uses_existing_sidecar_uuid(
    tmp_path,
):
    path = _write_dataset(tmp_path, [])
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00+00:00"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="empty-sidecar-uuid",
                filename=path.name,
            ),
        ),
        sidecar_path_for_dataset(path),
    )

    result = create_entry_service(
        dataset_path=str(path),
        entries=[],
        new_entry=_entry(tags=[]),
        backup_enabled=False,
    )

    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert result.ok is True
    assert get_dataset_uuid_for_entries(result.entries) == "empty-sidecar-uuid"
    assert sidecar.dataset_info.dataset_uuid == "empty-sidecar-uuid"
    assert sidecar.dataset_info.entry_count == 1


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
    assert result.sidecar_ok is False
    assert result.sidecar_message == "Registry sidecar could not be updated."


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
        tag_resolution,
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


def test_save_merged_entries_service_forces_new_dataset_uuid_for_single_source_dataset(
    tmp_path,
):
    path = tmp_path / "merged.jsonl"
    source_uuid = "source-dataset-uuid"
    entries = stamp_entries([_entry(tags=["merged"])], dataset_uuid=source_uuid)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=entries,
        backup_enabled=False,
    )

    assert result.ok is True
    merged_uuid = get_dataset_uuid_for_entries(result.entries)
    assert merged_uuid is not None
    assert merged_uuid != source_uuid
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert sidecar.dataset_info.dataset_uuid == merged_uuid


def test_save_merged_entries_service_forces_new_dataset_uuid_for_multiple_sources(
    tmp_path,
):
    path = tmp_path / "merged.jsonl"
    source_one = stamp_entries([_entry(user="One", tags=["one"])], dataset_uuid="source-one")
    source_two = stamp_entries([_entry(user="Two", tags=["two"])], dataset_uuid="source-two")

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=source_one + source_two,
        backup_enabled=False,
    )

    assert result.ok is True
    merged_uuid = get_dataset_uuid_for_entries(result.entries)
    assert merged_uuid is not None
    assert merged_uuid not in {"source-one", "source-two"}
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert sidecar.dataset_info.dataset_uuid == merged_uuid


def test_save_merged_entries_service_does_not_reuse_existing_output_sidecar_uuid(
    tmp_path,
):
    path = tmp_path / "merged.jsonl"
    existing_sidecar_uuid = "existing-output-sidecar-uuid"
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid=existing_sidecar_uuid,
                filename=path.name,
            ),
        ),
        sidecar_path_for_dataset(path),
    )

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["merged"])],
        backup_enabled=False,
    )

    assert result.ok is True
    merged_uuid = get_dataset_uuid_for_entries(result.entries)
    assert merged_uuid is not None
    assert merged_uuid != existing_sidecar_uuid
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert sidecar.dataset_info.dataset_uuid == merged_uuid


def test_save_merged_entries_service_canonicalizes_alias_tags(tmp_path, monkeypatch):
    path = tmp_path / "merged.jsonl"

    def fake_resolve_tag_lifecycle(tag):
        if tag == "old_tag":
            return SimpleNamespace(should_rewrite_slug=True, resolved_slug="new_tag")
        return SimpleNamespace(should_rewrite_slug=False, resolved_slug=tag)

    monkeypatch.setattr(tag_resolution, "resolve_tag_lifecycle", fake_resolve_tag_lifecycle)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["old_tag", "new_tag", "kept_tag"])],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.entries[0]["tags"] == ["new_tag", "kept_tag"]
    assert _read_entries(path)[0]["tags"] == ["new_tag", "kept_tag"]


def test_save_merged_entries_service_imports_source_sidecar_registry_metadata(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "merged.jsonl"
    source_entries = [_entry(tags=["slowburn"])]
    save_dataset(str(source_path), source_entries)
    source_sidecar_path = sidecar_path_for_dataset(source_path)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="source-dataset-uuid",
                filename=source_path.name,
            ),
            categories=(
                SidecarCategory(
                    slug="behavior",
                    name="Behavior",
                    sort_order=0,
                    is_builtin=True,
                ),
            ),
            tags=(
                SidecarTag(
                    slug="slow_burn",
                    name="Slow Burn",
                    category_slug="behavior",
                    status="active",
                ),
            ),
            aliases=(
                SidecarAlias(
                    old_slug="slowburn",
                    new_slug="slow_burn",
                    action="rename",
                    metadata={"resolver_behavior": "map_to_target"},
                ),
            ),
            characters=(
                SidecarCharacter(slug="scott", display_name="Scott"),
            ),
        ),
        source_sidecar_path,
    )
    original_source_text = source_path.read_text(encoding="utf-8")
    original_sidecar_text = source_sidecar_path.read_text(encoding="utf-8")

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.source_sidecar_summary.found_count == 1
    assert result.source_sidecar_summary.imported_count == 1
    assert result.source_sidecar_summary.categories_created == ["behavior"]
    assert result.source_sidecar_summary.tags_created == ["slow_burn"]
    assert result.source_sidecar_summary.aliases_imported == ["slowburn"]
    assert result.source_sidecar_summary.characters_created == ["scott"]
    assert result.source_sidecar_summary.character_mappings_imported == []
    assert result.entries[0]["tags"] == ["slow_burn"]
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert [category.slug for category in output_sidecar.categories] == ["behavior"]
    assert [tag.slug for tag in output_sidecar.tags] == ["slow_burn"]
    assert [alias.old_slug for alias in output_sidecar.aliases] == ["slowburn"]
    assert [character.slug for character in output_sidecar.characters] == ["scott"]
    assert output_sidecar.entry_character_mappings == ()
    assert source_path.read_text(encoding="utf-8") == original_source_text
    assert source_sidecar_path.read_text(encoding="utf-8") == original_sidecar_text

    session = session_factory()
    try:
        assert session.query(TagCategory).filter_by(slug="behavior").count() == 1
        assert session.query(Tag).filter_by(slug="slow_burn").count() == 1
        assert session.query(Character).filter_by(slug="scott").count() == 1
        assert session.query(EntryCharacterTurn).count() == 0
    finally:
        session.close()


def test_save_merged_entries_service_preserves_source_character_mapping_for_survivor(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "merged.jsonl"
    source_entries = stamp_entries(
        [_entry(user="Scott speaks", tags=[])],
        dataset_uuid="source-dataset-uuid",
    )
    source_entry_uuid = get_entry_uuid(source_entries[0])
    save_dataset(str(source_path), source_entries)
    source_sidecar_path = sidecar_path_for_dataset(source_path)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="source-dataset-uuid",
                filename=source_path.name,
            ),
            characters=(SidecarCharacter(slug="scott", display_name="Scott"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid=source_entry_uuid,
                    turns=(
                        {
                            "turn_index": 1,
                            "character_slug": "scott",
                            "training_role": "user",
                            "source_role_label": "Scott",
                        },
                    ),
                ),
            ),
        ),
        source_sidecar_path,
    )
    original_source_text = source_path.read_text(encoding="utf-8")
    original_sidecar_text = source_sidecar_path.read_text(encoding="utf-8")

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.source_sidecar_summary.character_mappings_imported == [
        source_entry_uuid
    ]
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert len(output_sidecar.entry_character_mappings) == 1
    mapping = output_sidecar.entry_character_mappings[0]
    assert mapping.entry_uuid == source_entry_uuid
    assert mapping.turns == (
        {
            "turn_index": 1,
            "character_slug": "scott",
            "training_role": "user",
            "source_role_label": "Scott",
        },
    )
    assert [character.slug for character in output_sidecar.characters] == ["scott"]
    assert source_path.read_text(encoding="utf-8") == original_source_text
    assert source_sidecar_path.read_text(encoding="utf-8") == original_sidecar_text

    session = session_factory()
    try:
        mappings = session.query(EntryCharacterTurn).all()
        assert len(mappings) == 1
        assert mappings[0].entry_uuid == source_entry_uuid
        assert mappings[0].character.slug == "scott"
    finally:
        session.close()


def test_save_merged_entries_service_skips_character_mapping_for_discarded_duplicate(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    survivor_path = tmp_path / "survivor.jsonl"
    discarded_path = tmp_path / "discarded.jsonl"
    output_path = tmp_path / "merged.jsonl"
    survivor_entries = stamp_entries(
        [_entry(user="Same conversation", tags=[])],
        dataset_uuid="survivor-dataset-uuid",
    )
    discarded_entries = stamp_entries(
        [_entry(user="Same conversation", tags=[])],
        dataset_uuid="discarded-dataset-uuid",
    )
    survivor_uuid = get_entry_uuid(survivor_entries[0])
    discarded_uuid = get_entry_uuid(discarded_entries[0])
    save_dataset(str(survivor_path), survivor_entries)
    save_dataset(str(discarded_path), discarded_entries)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="discarded-dataset-uuid",
                filename=discarded_path.name,
            ),
            characters=(SidecarCharacter(slug="emma", display_name="Emma"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid=discarded_uuid,
                    turns=(
                        {
                            "turn_index": 2,
                            "character_slug": "emma",
                            "training_role": "assistant",
                            "source_role_label": "Emma",
                        },
                    ),
                ),
            ),
        ),
        sidecar_path_for_dataset(discarded_path),
    )

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=survivor_entries,
        source_paths=[str(survivor_path), str(discarded_path)],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.source_sidecar_summary.character_mappings_imported == []
    assert any(
        discarded_uuid in warning
        for warning in result.source_sidecar_summary.warnings
    )
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert output_sidecar.entry_character_mappings == ()
    assert get_entry_uuid(result.entries[0]) == survivor_uuid

    session = session_factory()
    try:
        assert session.query(EntryCharacterTurn).filter_by(
            entry_uuid=discarded_uuid
        ).count() == 0
    finally:
        session.close()


def test_save_merged_entries_service_skips_character_mapping_for_absent_entry_uuid(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "merged.jsonl"
    source_entries = stamp_entries(
        [_entry(user="Present", tags=[])],
        dataset_uuid="source-dataset-uuid",
    )
    save_dataset(str(source_path), source_entries)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="source-dataset-uuid",
                filename=source_path.name,
            ),
            characters=(SidecarCharacter(slug="kai", display_name="Kai"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid="absent-entry-uuid",
                    turns=(
                        {
                            "turn_index": 1,
                            "character_slug": "kai",
                            "training_role": "user",
                            "source_role_label": "Kai",
                        },
                    ),
                ),
            ),
        ),
        sidecar_path_for_dataset(source_path),
    )

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.source_sidecar_summary.character_mappings_imported == []
    assert any(
        "absent-entry-uuid" in warning
        for warning in result.source_sidecar_summary.warnings
    )
    assert (
        read_sidecar(sidecar_path_for_dataset(output_path)).entry_character_mappings
        == ()
    )
    session = session_factory()
    try:
        assert session.query(EntryCharacterTurn).filter_by(
            entry_uuid="absent-entry-uuid"
        ).count() == 0
    finally:
        session.close()


def test_save_merged_entries_service_character_mapping_import_is_idempotent(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "merged.jsonl"
    source_entries = stamp_entries(
        [_entry(user="Scott speaks", tags=[])],
        dataset_uuid="source-dataset-uuid",
    )
    source_entry_uuid = get_entry_uuid(source_entries[0])
    save_dataset(str(source_path), source_entries)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="source-dataset-uuid",
                filename=source_path.name,
            ),
            characters=(SidecarCharacter(slug="scott", display_name="Scott"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid=source_entry_uuid,
                    turns=(
                        {
                            "turn_index": 1,
                            "character_slug": "scott",
                            "training_role": "user",
                            "source_role_label": "Scott",
                        },
                    ),
                ),
            ),
        ),
        sidecar_path_for_dataset(source_path),
    )

    first = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )
    second = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )

    assert first.ok is True
    assert second.ok is True
    assert second.source_sidecar_summary.character_mappings_imported == [
        source_entry_uuid
    ]
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert len(output_sidecar.entry_character_mappings) == 1
    session = session_factory()
    try:
        mappings = session.query(EntryCharacterTurn).filter_by(
            entry_uuid=source_entry_uuid
        ).all()
        assert len(mappings) == 1
    finally:
        session.close()


def test_save_merged_entries_service_skips_missing_and_bad_source_sidecars(
    tmp_path,
    monkeypatch,
):
    _registry_session_factory(tmp_path, monkeypatch)
    missing_source = tmp_path / "missing_sidecar.jsonl"
    bad_source = tmp_path / "bad_sidecar.jsonl"
    output_path = tmp_path / "merged.jsonl"
    entries = [_entry(tags=["merged"])]
    save_dataset(str(missing_source), entries)
    save_dataset(str(bad_source), entries)
    bad_sidecar_path = sidecar_path_for_dataset(bad_source)
    bad_sidecar_path.write_text("{not valid json}", encoding="utf-8")

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=entries,
        source_paths=[str(missing_source), str(bad_source)],
        backup_enabled=False,
    )

    assert result.ok is True
    summary = result.source_sidecar_summary
    assert summary.source_count == 2
    assert summary.found_count == 1
    assert summary.imported_count == 0
    assert summary.missing_paths == [str(sidecar_path_for_dataset(missing_source))]
    assert summary.failed_paths == [str(bad_sidecar_path)]
    assert summary.errors


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
