import json
import shutil
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.character_registry as character_registry
from core.dataset import save_dataset
from core.rolethread_meta import get_entry_uuid
from core.models import Base
from services import character_mapping_service, dataset_service
from services.character_mapping_service import apply_character_mapping_service


def _entry():
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "Scott", "content": "Hi."},
            {"role": "Emma", "content": "Hello."},
        ],
        "tags": [],
    }


def _read_entries(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _setup_character_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'characters.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(character_registry, "SessionLocal", session_factory)
    return session_factory


def _backup_recorder(monkeypatch, tmp_path):
    backup_paths = []
    backup_root = tmp_path / "backups"

    def fake_create_dataset_backup(dataset_path, reason):
        backup_root.mkdir(parents=True, exist_ok=True)
        backup_path = backup_root / f"{len(backup_paths):03d}_{reason}.jsonl"
        shutil.copyfile(dataset_path, backup_path)
        backup_paths.append(backup_path)
        return backup_path

    monkeypatch.setattr(dataset_service, "create_dataset_backup", fake_create_dataset_backup)
    return backup_paths


def test_apply_character_mapping_rewrites_roles_and_persists_mappings(tmp_path, monkeypatch):
    session_factory = _setup_character_db(tmp_path, monkeypatch)
    backups = _backup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(dataset_service, "_write_registry_sidecar", lambda *_args: None)
    sidecar_calls = []
    monkeypatch.setattr(
        character_mapping_service,
        "_write_sidecar_after_mapping",
        lambda dataset_path, entries: sidecar_calls.append((dataset_path, entries)),
    )
    path = tmp_path / "dataset.jsonl"
    save_dataset(str(path), [_entry()])

    result = apply_character_mapping_service(
        dataset_path=str(path),
        entries=[_entry()],
        role_mappings={"Scott": "user", "Emma": "assistant"},
    )

    assert result.ok is True
    assert result.backup_path == str(backups[0])
    assert result.characters_created == ["scott", "emma"]
    assert result.mapped_entries == 1
    assert result.mapped_turns == 2
    assert result.entries[0]["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi."},
        {"role": "assistant", "content": "Hello."},
    ]
    entry_uuid = get_entry_uuid(result.entries[0])
    assert entry_uuid is not None
    assert _read_entries(path) == result.entries
    assert sidecar_calls == [(str(path), result.entries)]

    session = session_factory()
    try:
        rows = character_registry.get_entry_character_turns(entry_uuid)
        assert [
            (row.turn_index, row.training_role, row.source_role_label)
            for row in rows
        ] == [
            (1, "user", "Scott"),
            (2, "assistant", "Emma"),
        ]
    finally:
        session.close()


def test_apply_character_mapping_reuses_existing_character(tmp_path, monkeypatch):
    _setup_character_db(tmp_path, monkeypatch)
    _backup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(dataset_service, "_write_registry_sidecar", lambda *_args: None)
    monkeypatch.setattr(character_mapping_service, "_write_sidecar_after_mapping", lambda *_args: None)
    character_registry.create_character("Scott")
    path = tmp_path / "dataset.jsonl"
    save_dataset(str(path), [_entry()])

    result = apply_character_mapping_service(
        dataset_path=str(path),
        entries=[_entry()],
        role_mappings={"Scott": "user"},
    )

    assert result.ok is True
    assert result.characters_created == []
    assert result.mapped_turns == 1


def test_apply_character_mapping_twice_replaces_existing_turn_mappings(
    tmp_path,
    monkeypatch,
):
    session_factory = _setup_character_db(tmp_path, monkeypatch)
    _backup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(dataset_service, "_write_registry_sidecar", lambda *_args: None)
    monkeypatch.setattr(character_mapping_service, "_write_sidecar_after_mapping", lambda *_args: None)
    path = tmp_path / "dataset.jsonl"
    entries = [_entry()]
    save_dataset(str(path), entries)

    first = apply_character_mapping_service(
        dataset_path=str(path),
        entries=entries,
        role_mappings={"Scott": "user", "Emma": "assistant"},
    )
    second_input = [_entry()]
    second_input[0]["_rolethread"] = dict(first.entries[0]["_rolethread"])
    second = apply_character_mapping_service(
        dataset_path=str(path),
        entries=second_input,
        role_mappings={"Scott": "user", "Emma": "assistant"},
    )

    assert first.ok is True
    assert second.ok is True
    assert second.characters_created == []
    entry_uuid = get_entry_uuid(second.entries[0])
    session = session_factory()
    try:
        rows = character_registry.get_entry_character_turns(entry_uuid)
        assert len(rows) == 2
        assert [
            (row.turn_index, row.training_role, row.source_role_label)
            for row in rows
        ] == [
            (1, "user", "Scott"),
            (2, "assistant", "Emma"),
        ]
    finally:
        session.close()


def test_character_mapping_remains_addressable_by_entry_uuid_after_reload(
    tmp_path,
    monkeypatch,
):
    _setup_character_db(tmp_path, monkeypatch)
    _backup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(dataset_service, "_write_registry_sidecar", lambda *_args: None)
    monkeypatch.setattr(character_mapping_service, "_write_sidecar_after_mapping", lambda *_args: None)
    path = tmp_path / "dataset.jsonl"
    save_dataset(str(path), [_entry()])

    result = apply_character_mapping_service(
        dataset_path=str(path),
        entries=[_entry()],
        role_mappings={"Scott": "user", "Emma": "assistant"},
    )
    reloaded_entries = _read_entries(path)
    reloaded_uuid = get_entry_uuid(reloaded_entries[0])

    assert result.ok is True
    assert reloaded_uuid == get_entry_uuid(result.entries[0])
    assert character_registry.get_character_display_for_entry(reloaded_uuid) == {
        1: "Scott",
        2: "Emma",
    }


def test_apply_character_mapping_rejects_invalid_training_role(tmp_path, monkeypatch):
    _setup_character_db(tmp_path, monkeypatch)
    path = tmp_path / "dataset.jsonl"
    entries = [_entry()]
    save_dataset(str(path), entries)

    result = apply_character_mapping_service(
        dataset_path=str(path),
        entries=entries,
        role_mappings={"Scott": "system"},
    )

    assert result.ok is False
    assert "Invalid training role" in result.errors[0]
    assert _read_entries(path) == entries

