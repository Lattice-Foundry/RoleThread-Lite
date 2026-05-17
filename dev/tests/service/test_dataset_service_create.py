from dev.tests.service.dataset_service_test_helpers import (
    SidecarDatasetInfo,
    SidecarMetadata,
    SidecarRegistry,
    _assert_stamped,
    _backup_recorder,
    _entry,
    _force_backup_failure,
    _malformed_entry,
    _read_entries,
    _registry_session_factory,
    _without_rolethread_meta,
    _write_dataset,
    copy,
    create_character,
    create_entry_service,
    dataset_service,
    duplicate_entry_service,
    get_dataset_uuid_for_entries,
    get_entry_character_turns,
    get_entry_uuid,
    inspect,
    read_sidecar,
    sidecar_path_for_dataset,
    stamp_entries,
    write_sidecar,
)


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
    assert _without_rolethread_meta(result.entries) == existing + [new_entry]
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

def test_create_entry_service_group_mode_saves_character_mappings(tmp_path, monkeypatch):
    _registry_session_factory(tmp_path, monkeypatch)
    create_character("Scott")
    create_character("Emma")
    existing = [_entry(tags=["existing"])]
    path = _write_dataset(tmp_path, existing)

    result = create_entry_service(
        dataset_path=str(path),
        entries=existing,
        new_entry=_entry(tags=["custom"]),
        character_turns=[
            {
                "turn_index": 1,
                "character_slug": "scott",
                "training_role": "user",
                "source_role_label": "Scott",
            },
            {
                "turn_index": 2,
                "character_slug": "emma",
                "training_role": "assistant",
                "source_role_label": "Emma",
            },
        ],
        backup_enabled=False,
    )

    entry_uuid = get_entry_uuid(result.entries[-1])
    mappings = get_entry_character_turns(entry_uuid)
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert result.ok is True
    assert [(mapping.turn_index, mapping.training_role) for mapping in mappings] == [
        (1, "user"),
        (2, "assistant"),
    ]
    assert sidecar.entry_character_mappings[0].entry_uuid == entry_uuid
    assert sidecar.entry_character_mappings[0].turns == (
        {
            "turn_index": 1,
            "character_slug": "scott",
            "training_role": "user",
            "source_role_label": "Scott",
        },
        {
            "turn_index": 2,
            "character_slug": "emma",
            "training_role": "assistant",
            "source_role_label": "Emma",
        },
    )

def test_create_entry_service_mapping_write_failure_is_non_fatal(tmp_path, monkeypatch):
    existing = [_entry(tags=["existing"])]
    path = _write_dataset(tmp_path, existing)

    def fail_mapping(_entry_uuid, _turns):
        raise RuntimeError("mapping db unavailable")

    monkeypatch.setattr(dataset_service, "set_entry_character_turns", fail_mapping)

    result = create_entry_service(
        dataset_path=str(path),
        entries=existing,
        new_entry=_entry(tags=["custom"]),
        character_turns=[
            {
                "turn_index": 1,
                "character_slug": "scott",
                "training_role": "user",
                "source_role_label": "Scott",
            },
        ],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.warnings == [
        "Character mappings could not be updated: mapping db unavailable"
    ]
    assert _read_entries(path) == result.entries

def test_create_entry_service_missing_dataset_path_fails_safely():
    result = create_entry_service(
        dataset_path="",
        entries=[],
        new_entry=_entry(),
    )

    assert result.ok is False
    assert result.entries is None

def test_duplicate_entry_service_appends_fresh_uuid_with_backup(tmp_path, monkeypatch):
    original_entries = stamp_entries([_entry(tags=["alpha"])], dataset_uuid="dataset-uuid")
    original_uuid = get_entry_uuid(original_entries[0])
    path = _write_dataset(tmp_path, original_entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = duplicate_entry_service(
        dataset_path=str(path),
        entries=original_entries,
        entry_index=0,
        backup_enabled=True,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert result.backup_path == str(backups[0])
    assert result.entries is not None
    assert len(result.entries) == 2
    assert get_entry_uuid(result.entries[0]) == original_uuid
    assert get_entry_uuid(result.entries[1]) != original_uuid
    assert _without_rolethread_meta(result.entries[1]) == _without_rolethread_meta(
        original_entries[0]
    )

