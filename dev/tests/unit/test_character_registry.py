import pytest
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import core.character_registry as character_registry
from core.character_registry import (
    bulk_set_character_mappings,
    collect_character_candidates,
    create_character,
    deactivate_character,
    delete_characters,
    delete_entry_character_turns,
    get_all_characters,
    get_character_display_for_entries,
    get_character_display_for_entry,
    get_character_usage_counts,
    get_character_by_slug,
    get_inactive_characters,
    get_entries_for_character,
    get_entry_character_turns,
    normalize_character_name,
    normalize_known_character_roles,
    reactivate_character,
    set_entry_character_turns,
    update_character,
    upsert_character_mappings,
)
from core.loreforge_meta import LOREFORGE_META_KEY
from core.models import Base, Character, EntryCharacterTurn


@pytest.fixture
def character_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'characters.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(character_registry, "SessionLocal", session_factory)
    return session_factory


def test_character_table_is_created_with_unique_slug(character_db):
    inspector = sa_inspect(character_db.kw["bind"])

    assert "characters" in inspector.get_table_names()
    assert "entry_character_turns" in inspector.get_table_names()
    constraints = inspector.get_unique_constraints("characters")
    assert any(
        constraint["name"] == "uq_character_slug"
        and constraint["column_names"] == ["slug"]
        for constraint in constraints
    )
    turn_constraints = inspector.get_unique_constraints("entry_character_turns")
    assert any(
        constraint["name"] == "uq_entry_character_turn"
        and constraint["column_names"] == ["entry_uuid", "turn_index"]
        for constraint in turn_constraints
    )


def test_normalize_character_name_reuses_tag_normalization():
    assert normalize_character_name("  Scott Summers  ") == (
        "scott_summers",
        "Scott Summers",
    )


def _candidate_entry(entry_uuid, roles):
    return {
        LOREFORGE_META_KEY: {"native": True, "entry_uuid": entry_uuid},
        "messages": [
            {"role": role, "content": f"{role} says hi"}
            for role in roles
        ],
        "tags": [],
    }


def test_collect_character_candidates_returns_empty_for_standard_roles():
    report = collect_character_candidates([
        _candidate_entry("entry-1", ["system", "user", "assistant"]),
        _candidate_entry("entry-2", ["System", "Human", "GPT"]),
    ])

    assert report.has_candidates is False
    assert report.candidates == ()
    assert report.pattern_summary is None


def test_collect_character_candidates_groups_custom_roles_by_location():
    report = collect_character_candidates([
        _candidate_entry("entry-1", ["system", "Scott", "Emma", "Scott"]),
        _candidate_entry("entry-2", ["system", "Scott", "Emma"]),
    ])

    assert report.has_candidates is True
    candidates = {candidate.source_role_label: candidate for candidate in report.candidates}
    assert set(candidates) == {"Emma", "Scott"}
    assert candidates["Scott"].suggested_slug == "scott"
    assert candidates["Scott"].suggested_display_name == "Scott"
    assert candidates["Scott"].entry_uuids == ("entry-1", "entry-2")
    assert candidates["Scott"].turn_locations == (
        {"entry_uuid": "entry-1", "turn_index": 1},
        {"entry_uuid": "entry-1", "turn_index": 3},
        {"entry_uuid": "entry-2", "turn_index": 1},
    )
    assert candidates["Scott"].occurrence_count == 3
    assert candidates["Emma"].occurrence_count == 2


def test_collect_character_candidates_suggests_alternating_training_roles():
    report = collect_character_candidates([
        _candidate_entry("entry-1", ["Scott", "Emma", "Scott", "Emma"]),
    ])

    candidates = {candidate.source_role_label: candidate for candidate in report.candidates}
    assert candidates["Scott"].suggested_training_role == "user"
    assert candidates["Emma"].suggested_training_role == "assistant"
    assert report.pattern_summary == (
        "Custom role names detected - likely maps to standard roles: "
        "Scott appears to be 'user', Emma appears to be 'assistant'."
    )


def test_collect_character_candidates_handles_mixed_standard_and_custom_roles():
    report = collect_character_candidates([
        _candidate_entry("entry-1", ["system", "user", "assistant"]),
        _candidate_entry("entry-2", ["system", "Kai", "assistant"]),
    ])

    assert [candidate.source_role_label for candidate in report.candidates] == ["Kai"]
    assert report.candidates[0].suggested_training_role is None


def test_normalize_known_character_roles_uses_existing_source_labels(character_db):
    create_character("Scott")
    set_entry_character_turns(
        "existing-entry",
        [{"turn_index": 1, "character_slug": "scott", "training_role": "user", "source_role_label": "Scott"}],
    )
    entry = _candidate_entry("new-entry", ["system", "Scott", "assistant"])

    result = normalize_known_character_roles([entry])

    assert result.changed_entries == 1
    assert result.changed_turns == 1
    assert result.entries[0]["messages"][1]["role"] == "user"
    assert result.mapping_payload == (
        {
            "entry_uuid": "new-entry",
            "turns": [
                {
                    "turn_index": 1,
                    "character_slug": "scott",
                    "training_role": "user",
                    "source_role_label": "Scott",
                }
            ],
        },
    )


def test_normalize_known_character_roles_skips_ambiguous_training_roles(character_db):
    create_character("Scott")
    set_entry_character_turns(
        "entry-user",
        [{"turn_index": 1, "character_slug": "scott", "training_role": "user", "source_role_label": "Scott"}],
    )
    set_entry_character_turns(
        "entry-assistant",
        [{"turn_index": 2, "character_slug": "scott", "training_role": "assistant", "source_role_label": "Scott"}],
    )
    entry = _candidate_entry("new-entry", ["system", "Scott", "assistant"])

    result = normalize_known_character_roles([entry])

    assert result.changed_entries == 0
    assert result.changed_turns == 0
    assert result.entries[0]["messages"][1]["role"] == "Scott"
    assert result.mapping_payload == ()


def test_create_character_normalizes_and_persists(character_db):
    character = create_character("  Scott Summers  ", description="Cyclops")

    assert character.slug == "scott_summers"
    assert character.display_name == "Scott Summers"
    assert character.description == "Cyclops"
    assert character.is_active is True
    assert character.created_at is not None
    assert character.updated_at is not None

    session = character_db()
    try:
        stored = session.query(Character).filter_by(slug="scott_summers").one()
        assert stored.display_name == "Scott Summers"
    finally:
        session.close()


def test_create_character_rejects_empty_and_duplicate_names(character_db):
    with pytest.raises(ValueError, match="cannot be empty"):
        create_character(" ")

    create_character("Emma Frost")

    with pytest.raises(ValueError, match="already exists"):
        create_character("emma_frost")


def test_database_rejects_duplicate_character_slugs(character_db):
    session = character_db()
    try:
        session.add_all([
            Character(slug="duplicate", display_name="Duplicate"),
            Character(slug="duplicate", display_name="Duplicate Again"),
        ])
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_get_all_characters_returns_active_ordered(character_db):
    create_character("Yuki")
    create_character("Kai")
    create_character("Emma")
    deactivate_character("kai")

    characters = get_all_characters()

    assert [character.slug for character in characters] == ["emma", "yuki"]


def test_get_character_by_slug_normalizes_and_excludes_inactive(character_db):
    create_character("Scott Summers")

    character = get_character_by_slug("Scott Summers")

    assert character is not None
    assert character.slug == "scott_summers"

    assert deactivate_character("scott_summers") is True
    assert get_character_by_slug("Scott Summers") is None


def test_update_character_changes_display_metadata_not_slug(character_db):
    create_character("Scott Summers", description="Old")

    updated = update_character(
        "scott_summers",
        display_name="Cyclops",
        description="Team leader",
    )

    assert updated.slug == "scott_summers"
    assert updated.display_name == "Cyclops"
    assert updated.description == "Team leader"


def test_update_character_rejects_missing_or_empty_display_name(character_db):
    create_character("Scott")

    with pytest.raises(ValueError, match="display name"):
        update_character("scott", display_name=" ")
    with pytest.raises(ValueError, match="not found"):
        update_character("missing", display_name="Missing")


def test_deactivate_character_and_bulk_delete_soft_delete(character_db):
    create_character("Scott")
    create_character("Emma")
    create_character("Kai")

    assert deactivate_character("Scott") is True
    assert deactivate_character("Missing") is False
    assert delete_characters(["Emma", "Kai", "Missing"]) == ["emma", "kai"]
    assert get_all_characters() == []

    session = character_db()
    try:
        stored = {character.slug: character for character in session.query(Character)}
        assert stored["scott"].is_active is False
        assert stored["emma"].is_active is False
        assert stored["kai"].is_active is False
    finally:
        session.close()


def test_inactive_characters_and_reactivation(character_db):
    create_character("Scott")
    create_character("Emma")
    delete_characters(["Scott"])

    assert [character.slug for character in get_inactive_characters()] == ["scott"]
    assert reactivate_character("Scott") is True
    assert reactivate_character("Missing") is False
    assert [character.slug for character in get_all_characters()] == ["emma", "scott"]


def test_set_and_get_entry_character_turns(character_db):
    create_character("Scott")
    create_character("Emma")

    mappings = set_entry_character_turns(
        "entry-1",
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

    assert [mapping.turn_index for mapping in mappings] == [1, 2]
    stored = get_entry_character_turns("entry-1")
    assert [(mapping.turn_index, mapping.training_role) for mapping in stored] == [
        (1, "user"),
        (2, "assistant"),
    ]
    assert [mapping.character.slug for mapping in stored] == ["scott", "emma"]
    assert get_character_display_for_entry("entry-1") == {
        1: "Scott",
        2: "Emma",
    }


def test_get_character_display_for_entries_bulk(character_db):
    create_character("Scott")
    create_character("Emma")
    set_entry_character_turns(
        "entry-1",
        [{"turn_index": 1, "character_slug": "scott", "training_role": "user"}],
    )
    set_entry_character_turns(
        "entry-2",
        [{"turn_index": 2, "character_slug": "emma", "training_role": "assistant"}],
    )

    assert get_character_display_for_entries({"entry-1", "entry-2"}) == {
        "entry-1": {1: "Scott"},
        "entry-2": {2: "Emma"},
    }


def test_set_entry_character_turns_replaces_existing_mappings(character_db):
    create_character("Scott")
    create_character("Emma")
    set_entry_character_turns(
        "entry-1",
        [
            {
                "turn_index": 1,
                "character_slug": "scott",
                "training_role": "user",
            }
        ],
    )

    set_entry_character_turns(
        "entry-1",
        [
            {
                "turn_index": 2,
                "character_slug": "emma",
                "training_role": "assistant",
            }
        ],
    )

    stored = get_entry_character_turns("entry-1")
    assert [(mapping.turn_index, mapping.training_role) for mapping in stored] == [
        (2, "assistant")
    ]


def test_entry_character_turn_unique_constraint(character_db):
    character = create_character("Scott")
    session = character_db()
    try:
        session.add_all([
            EntryCharacterTurn(
                entry_uuid="entry-1",
                turn_index=1,
                character_id=character.id,
                training_role="user",
            ),
            EntryCharacterTurn(
                entry_uuid="entry-1",
                turn_index=1,
                character_id=character.id,
                training_role="assistant",
            ),
        ])
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_get_entries_for_character_returns_distinct_entry_uuids(character_db):
    create_character("Scott")
    create_character("Emma")
    set_entry_character_turns(
        "entry-2",
        [
            {"turn_index": 1, "character_slug": "scott", "training_role": "user"},
            {"turn_index": 2, "character_slug": "emma", "training_role": "assistant"},
        ],
    )
    set_entry_character_turns(
        "entry-1",
        [
            {"turn_index": 1, "character_slug": "scott", "training_role": "user"},
        ],
    )

    assert get_entries_for_character("Scott") == ["entry-1", "entry-2"]


def test_get_character_usage_counts_returns_distinct_entry_counts(character_db):
    create_character("Scott")
    create_character("Emma")
    set_entry_character_turns(
        "entry-1",
        [
            {"turn_index": 1, "character_slug": "scott", "training_role": "user"},
            {"turn_index": 2, "character_slug": "scott", "training_role": "user"},
            {"turn_index": 3, "character_slug": "emma", "training_role": "assistant"},
        ],
    )
    set_entry_character_turns(
        "entry-2",
        [{"turn_index": 1, "character_slug": "scott", "training_role": "user"}],
    )

    assert get_character_usage_counts(["Scott", "Emma", "Missing"]) == {
        "scott": 2,
        "emma": 1,
        "missing": 0,
    }


def test_soft_delete_character_removes_turn_mappings(character_db):
    create_character("Scott")
    set_entry_character_turns(
        "entry-1",
        [{"turn_index": 1, "character_slug": "scott", "training_role": "user"}],
    )

    assert delete_characters(["Scott"]) == ["scott"]
    assert get_entry_character_turns("entry-1") == []
    assert get_entries_for_character("Scott") == []


def test_delete_entry_character_turns(character_db):
    create_character("Scott")
    set_entry_character_turns(
        "entry-1",
        [
            {"turn_index": 1, "character_slug": "scott", "training_role": "user"},
            {"turn_index": 2, "character_slug": "scott", "training_role": "assistant"},
        ],
    )

    assert delete_entry_character_turns("entry-1") == 2
    assert get_entry_character_turns("entry-1") == []
    assert delete_entry_character_turns("entry-1") == 0


def test_bulk_set_character_mappings(character_db):
    create_character("Scott")
    create_character("Emma")

    result = bulk_set_character_mappings([
        {
            "entry_uuid": "entry-1",
            "turns": [
                {"turn_index": 1, "character_slug": "scott", "training_role": "user"},
            ],
        },
        {
            "entry_uuid": "entry-2",
            "turns": [
                {"turn_index": 2, "character_slug": "emma", "training_role": "assistant"},
            ],
        },
    ])

    assert result == {"entries": 2, "turns": 2}
    assert get_character_display_for_entry("entry-1") == {1: "Scott"}
    assert get_character_display_for_entry("entry-2") == {2: "Emma"}


def test_upsert_character_mappings_updates_turn_without_deleting_others(character_db):
    create_character("Scott")
    create_character("Emma")
    set_entry_character_turns(
        "entry-1",
        [
            {"turn_index": 1, "character_slug": "scott", "training_role": "user"},
            {"turn_index": 2, "character_slug": "emma", "training_role": "assistant"},
        ],
    )

    result = upsert_character_mappings([
        {
            "entry_uuid": "entry-1",
            "turns": [
                {
                    "turn_index": 1,
                    "character_slug": "emma",
                    "training_role": "assistant",
                    "source_role_label": "Emma",
                }
            ],
        }
    ])

    assert result == {"entries": 1, "turns": 1}
    stored = get_entry_character_turns("entry-1")
    assert [(mapping.turn_index, mapping.training_role) for mapping in stored] == [
        (1, "assistant"),
        (2, "assistant"),
    ]
    assert len(stored) == 2


def test_set_entry_character_turns_validates_inputs(character_db):
    create_character("Scott")

    with pytest.raises(ValueError, match="Entry UUID"):
        set_entry_character_turns("", [])
    with pytest.raises(ValueError, match="Turn index"):
        set_entry_character_turns(
            "entry-1",
            [{"turn_index": -1, "character_slug": "scott", "training_role": "user"}],
        )
    with pytest.raises(ValueError, match="Training role"):
        set_entry_character_turns(
            "entry-1",
            [{"turn_index": 1, "character_slug": "scott", "training_role": ""}],
        )
    with pytest.raises(ValueError, match="Character not found"):
        set_entry_character_turns(
            "entry-1",
            [{"turn_index": 1, "character_slug": "missing", "training_role": "user"}],
        )


def test_character_hard_delete_cascades_turn_mappings(character_db):
    create_character("Scott")
    set_entry_character_turns(
        "entry-1",
        [
            {"turn_index": 1, "character_slug": "scott", "training_role": "user"},
        ],
    )

    session = character_db()
    try:
        character = session.query(Character).filter_by(slug="scott").one()
        session.delete(character)
        session.commit()
    finally:
        session.close()

    assert get_entry_character_turns("entry-1") == []
