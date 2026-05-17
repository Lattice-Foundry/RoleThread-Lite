from dev.tests.service.dataset_service_test_helpers import (
    _backup_recorder,
    _entry,
    _fail_if_backup_called,
    _force_backup_failure,
    _malformed_entry,
    _read_entries,
    _without_rolethread_meta,
    _write_dataset,
    clear_tags_bulk_service,
    copy,
    delete_entries_service,
    replace_single_entry_tags_service,
    replace_tags_bulk_service,
    save_dataset,
)


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
    assert _without_rolethread_meta(result.entries[0]) == entries[0]
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
    assert _without_rolethread_meta(result.entries[1]) == entries[1]
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
    assert _without_rolethread_meta(result.entries) == [entries[0], entries[3]]
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
    assert _without_rolethread_meta(result.entries) == [entries[0], _entry(tags=["also_good"])]
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

