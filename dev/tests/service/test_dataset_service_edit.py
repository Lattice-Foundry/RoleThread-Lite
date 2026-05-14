from dev.tests.service.dataset_service_test_helpers import (
    SimpleNamespace,
    _assert_stamped,
    _backup_recorder,
    _entry,
    _fail_if_backup_called,
    _force_backup_failure,
    _malformed_entry,
    _multi_turn_entry,
    _read_entries,
    _registry_session_factory,
    _without_loreforge_meta,
    _write_dataset,
    copy,
    create_character,
    get_entry_character_turns,
    get_entry_uuid,
    save_full_edit_service,
    save_quick_edit_service,
    set_entry_character_turns,
    stamp_entries,
    tag_resolution,
)


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

def test_save_full_edit_service_group_mode_replaces_character_mappings(
    tmp_path,
    monkeypatch,
):
    _registry_session_factory(tmp_path, monkeypatch)
    create_character("Scott")
    create_character("Emma")
    create_character("Kai")
    entries = stamp_entries([_entry(tags=["old"])], dataset_uuid="dataset-uuid")
    path = _write_dataset(tmp_path, entries)
    entry_uuid = get_entry_uuid(entries[0])
    set_entry_character_turns(
        entry_uuid,
        [
            {
                "turn_index": 1,
                "character_slug": "kai",
                "training_role": "user",
                "source_role_label": "Kai",
            },
        ],
    )

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=_entry(user="Edited", assistant="Saved", tags=["new"]),
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

    mappings = get_entry_character_turns(entry_uuid)
    assert result.ok is True
    assert [(mapping.turn_index, mapping.training_role) for mapping in mappings] == [
        (1, "user"),
        (2, "assistant"),
    ]

def test_save_full_edit_service_standard_mode_clears_character_mappings(
    tmp_path,
    monkeypatch,
):
    _registry_session_factory(tmp_path, monkeypatch)
    create_character("Scott")
    entries = stamp_entries([_entry(tags=["old"])], dataset_uuid="dataset-uuid")
    path = _write_dataset(tmp_path, entries)
    entry_uuid = get_entry_uuid(entries[0])
    set_entry_character_turns(
        entry_uuid,
        [
            {
                "turn_index": 1,
                "character_slug": "scott",
                "training_role": "user",
                "source_role_label": "Scott",
            },
        ],
    )

    result = save_full_edit_service(
        dataset_path=str(path),
        entries=entries,
        entry_index=0,
        updated_entry=_entry(user="Edited", assistant="Saved", tags=["new"]),
        clear_character_mappings=True,
        backup_enabled=False,
    )

    assert result.ok is True
    assert get_entry_character_turns(entry_uuid) == []

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
