from dev.tests.service.dataset_service_test_helpers import (
    _assert_stamped,
    _backup_recorder,
    _entry,
    _fail_if_backup_called,
    _force_backup_failure,
    _read_entries,
    _without_rolethread_meta,
    _write_dataset,
    copy,
    dataset_service,
    json,
    replace_system_prompt_bulk_service,
    save_dataset,
    save_full_edit_service,
    save_repaired_entries_service,
)


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
    assert _without_rolethread_meta(result.entries[2]) == entries[2]
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
    assert _without_rolethread_meta(result.entries) == [
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

