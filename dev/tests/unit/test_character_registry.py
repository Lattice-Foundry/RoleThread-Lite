import pytest
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import core.character_registry as character_registry
from core.character_registry import (
    bulk_set_character_mappings,
    create_character,
    deactivate_character,
    delete_characters,
    delete_entry_character_turns,
    get_all_characters,
    get_character_display_for_entry,
    get_character_by_slug,
    get_entries_for_character,
    get_entry_character_turns,
    normalize_character_name,
    set_entry_character_turns,
)
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
    assert get_character_display_for_entry("entry-1") == {
        1: "Scott",
        2: "Emma",
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
