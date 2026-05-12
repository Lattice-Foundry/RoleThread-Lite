import pytest
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import core.character_registry as character_registry
from core.character_registry import (
    create_character,
    deactivate_character,
    delete_characters,
    get_all_characters,
    get_character_by_slug,
    normalize_character_name,
)
from core.models import Base, Character


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
    constraints = inspector.get_unique_constraints("characters")
    assert any(
        constraint["name"] == "uq_character_slug"
        and constraint["column_names"] == ["slug"]
        for constraint in constraints
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
