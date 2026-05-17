import copy
import inspect
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.dataset import load_dataset, merge_datasets, save_dataset
from core.rolethread_meta import (
    ROLETHREAD_META_KEY,
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
import core.character_registry as character_registry
from core.version import ROLETHREAD_VERSION
import core.tag_resolution as tag_resolution
import services.registry_sidecar_service as registry_sidecar_service
from services import dataset_service
from services.dataset_service import (
    clear_tags_bulk_service,
    create_entry_service,
    delete_entries_service,
    duplicate_entry_service,
    replace_single_entry_tags_service,
    replace_system_prompt_bulk_service,
    replace_tags_bulk_service,
    save_repaired_entries_service,
    save_full_edit_service,
    save_merged_entries_service,
    save_quick_edit_service,
    split_entry_service,
    join_entries_service,
)
from core.character_registry import (
    create_character,
    get_entry_character_turns,
    set_entry_character_turns,
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


def _without_rolethread_meta(value):
    if isinstance(value, list):
        return [_without_rolethread_meta(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _without_rolethread_meta(item)
            for key, item in value.items()
            if key != ROLETHREAD_META_KEY
        }
    return value


def _assert_stamped(entries):
    assert entries
    for entry in entries:
        assert entry[ROLETHREAD_META_KEY]["version"] == ROLETHREAD_VERSION
        assert entry[ROLETHREAD_META_KEY]["native"] is True
        assert entry[ROLETHREAD_META_KEY]["validated_at"].endswith("Z")
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
    monkeypatch.setattr(character_registry, "SessionLocal", session_factory)
    monkeypatch.setattr(registry_sidecar_service, "engine", engine)
    monkeypatch.setattr(registry_sidecar_service, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_resolution, "SessionLocal", session_factory)
    monkeypatch.setattr(
        registry_sidecar_service,
        "create_db_backup",
        lambda *, engine: tmp_path / "db_backup.sqlite",
    )
    return session_factory

