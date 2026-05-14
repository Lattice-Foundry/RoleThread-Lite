from dev.tests.service.dataset_service_test_helpers import (
    _backup_recorder,
    _entry,
    _multi_turn_entry,
    _read_entries,
    _registry_session_factory,
    _write_dataset,
    create_character,
    get_entry_character_turns,
    get_entry_uuid,
    join_entries_service,
    read_sidecar,
    set_entry_character_turns,
    sidecar_path_for_dataset,
    split_entry_service,
    stamp_entries,
)


def test_split_entry_service_splits_into_two_with_backup(tmp_path, monkeypatch):
    entries = stamp_entries([_multi_turn_entry(tags=["shared"])])
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)
    entry_uuid = get_entry_uuid(entries[0])

    result = split_entry_service(
        dataset_path=str(path),
        entry_uuid=entry_uuid,
        split_points=[1],
        entries=entries,
    )

    assert result.ok is True
    assert result.affected_count == 2
    assert len(backups) == 1
    assert len(result.entries) == 2
    assert [entry["tags"] for entry in result.entries] == [["shared"], ["shared"]]
    assert [len(entry["messages"]) for entry in result.entries] == [3, 3]
    assert result.entries[0]["messages"][0]["content"] == "System"
    assert result.entries[1]["messages"][0]["content"] == "System"
    assert get_entry_uuid(result.entries[0]) != entry_uuid
    assert get_entry_uuid(result.entries[1]) != entry_uuid
    assert _read_entries(path) == result.entries

def test_split_entry_service_splits_into_three_or_more(tmp_path, monkeypatch):
    entry = {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "U1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "U2"},
            {"role": "assistant", "content": "A2"},
            {"role": "user", "content": "U3"},
            {"role": "assistant", "content": "A3"},
        ],
        "tags": ["shared"],
    }
    entries = stamp_entries([entry])
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = split_entry_service(
        dataset_path=str(path),
        entry_uuid=get_entry_uuid(entries[0]),
        split_points=[1, 2],
        entries=entries,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert len(result.entries) == 3
    assert [
        [message["content"] for message in entry["messages"][1:]]
        for entry in result.entries
    ] == [["U1", "A1"], ["U2", "A2"], ["U3", "A3"]]

def test_split_entry_service_reindexes_character_mappings(tmp_path, monkeypatch):
    _registry_session_factory(tmp_path, monkeypatch)
    create_character("Scott")
    create_character("Emma")
    entries = stamp_entries([_multi_turn_entry(tags=["shared"])])
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
            {
                "turn_index": 2,
                "character_slug": "emma",
                "training_role": "assistant",
                "source_role_label": "Emma",
            },
            {
                "turn_index": 3,
                "character_slug": "scott",
                "training_role": "user",
                "source_role_label": "Scott",
            },
            {
                "turn_index": 4,
                "character_slug": "emma",
                "training_role": "assistant",
                "source_role_label": "Emma",
            },
        ],
    )
    path = _write_dataset(tmp_path, entries)

    result = split_entry_service(
        dataset_path=str(path),
        entry_uuid=entry_uuid,
        split_points=[1],
        entries=entries,
        backup_enabled=False,
    )

    assert result.ok is True
    first_mappings = get_entry_character_turns(get_entry_uuid(result.entries[0]))
    second_mappings = get_entry_character_turns(get_entry_uuid(result.entries[1]))
    assert [(m.turn_index, m.character.slug) for m in first_mappings] == [
        (1, "scott"),
        (2, "emma"),
    ]
    assert [(m.turn_index, m.character.slug) for m in second_mappings] == [
        (1, "scott"),
        (2, "emma"),
    ]
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert len(sidecar.entry_character_mappings) == 2

def test_join_entries_service_joins_two_entries_with_backup(tmp_path, monkeypatch):
    entries = stamp_entries([
        _entry(system="First system", user="U1", assistant="A1", tags=["first"]),
        _entry(system="First system", user="U2", assistant="A2", tags=["second"]),
    ])
    path = _write_dataset(tmp_path, entries)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = join_entries_service(
        dataset_path=str(path),
        entry_uuids=[get_entry_uuid(entries[0]), get_entry_uuid(entries[1])],
        entries=entries,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert len(result.entries) == 1
    joined = result.entries[0]
    assert joined["messages"][0]["content"] == "First system"
    assert [message["content"] for message in joined["messages"][1:]] == [
        "U1",
        "A1",
        "U2",
        "A2",
    ]
    assert joined["tags"] == ["first", "second"]
    assert get_entry_uuid(joined) not in {
        get_entry_uuid(entries[0]),
        get_entry_uuid(entries[1]),
    }

def test_join_entries_service_joins_three_and_uses_first_system_prompt(
    tmp_path,
    monkeypatch,
):
    entries = stamp_entries([
        _entry(system="First system", user="U1", assistant="A1", tags=["first"]),
        _entry(system="Second system", user="U2", assistant="A2", tags=["second"]),
        _entry(system="Third system", user="U3", assistant="A3", tags=["third"]),
    ])
    path = _write_dataset(tmp_path, entries)
    _backup_recorder(monkeypatch, tmp_path)

    result = join_entries_service(
        dataset_path=str(path),
        entry_uuids=[get_entry_uuid(entry) for entry in entries],
        entries=entries,
    )

    assert result.ok is True
    assert len(result.entries) == 1
    assert result.entries[0]["messages"][0]["content"] == "First system"
    assert result.entries[0]["tags"] == ["first", "second", "third"]
    assert result.warnings == [
        "System prompts differed; the first selected system prompt was used."
    ]

def test_join_entries_service_reindexes_character_mappings(tmp_path, monkeypatch):
    _registry_session_factory(tmp_path, monkeypatch)
    create_character("Scott")
    create_character("Emma")
    entries = stamp_entries([
        _entry(system="System", user="U1", assistant="A1", tags=["first"]),
        _entry(system="System", user="U2", assistant="A2", tags=["second"]),
    ])
    for entry in entries:
        set_entry_character_turns(
            get_entry_uuid(entry),
            [
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
        )
    path = _write_dataset(tmp_path, entries)

    result = join_entries_service(
        dataset_path=str(path),
        entry_uuids=[get_entry_uuid(entry) for entry in entries],
        entries=entries,
        backup_enabled=False,
    )

    assert result.ok is True
    mappings = get_entry_character_turns(get_entry_uuid(result.entries[0]))
    assert [(m.turn_index, m.character.slug) for m in mappings] == [
        (1, "scott"),
        (2, "emma"),
        (3, "scott"),
        (4, "emma"),
    ]
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert len(sidecar.entry_character_mappings) == 1
    assert len(sidecar.entry_character_mappings[0].turns) == 4
