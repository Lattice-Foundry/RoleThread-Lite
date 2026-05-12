"""DB-backed character registry helpers."""
from __future__ import annotations

from core.db import SessionLocal
from core.models import Character
from core.tag_normalization import normalize_tag


def normalize_character_name(name: str) -> tuple[str, str]:
    """Return ``(slug, display_name)`` for one character name."""

    normalized = normalize_tag(name)
    return normalized.slug, normalized.display_name


def create_character(name: str, description: str | None = None) -> Character:
    """Create an active character with a normalized unique slug."""

    slug, display_name = normalize_character_name(name)
    if not slug:
        raise ValueError("Character name cannot be empty.")

    session = SessionLocal()
    try:
        existing = session.query(Character).filter_by(slug=slug).first()
        if existing is not None:
            raise ValueError(f"Character already exists: {display_name}")

        character = Character(
            slug=slug,
            display_name=display_name,
            description=description,
            is_active=True,
        )
        session.add(character)
        session.commit()
        session.refresh(character)
        session.expunge(character)
        return character
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_all_characters() -> list[Character]:
    """Return active characters ordered by display name."""

    session = SessionLocal()
    try:
        characters = (
            session.query(Character)
            .filter_by(is_active=True)
            .order_by(Character.display_name, Character.slug)
            .all()
        )
        for character in characters:
            session.expunge(character)
        return characters
    finally:
        session.close()


def get_character_by_slug(slug: str) -> Character | None:
    """Return one active character by normalized slug."""

    normalized_slug, _display_name = normalize_character_name(slug)
    if not normalized_slug:
        return None

    session = SessionLocal()
    try:
        character = (
            session.query(Character)
            .filter_by(slug=normalized_slug, is_active=True)
            .first()
        )
        if character is not None:
            session.expunge(character)
        return character
    finally:
        session.close()


def deactivate_character(slug: str) -> bool:
    """Soft-delete one character by normalized slug."""

    return bool(delete_characters([slug]))


def delete_characters(slugs: list[str]) -> list[str]:
    """Soft-delete active characters and return their normalized slugs."""

    normalized_slugs: set[str] = set()
    for slug in slugs:
        normalized_slug, _display_name = normalize_character_name(slug)
        if normalized_slug:
            normalized_slugs.add(normalized_slug)
    if not normalized_slugs:
        return []

    session = SessionLocal()
    try:
        characters = (
            session.query(Character)
            .filter(
                Character.slug.in_(normalized_slugs),
                Character.is_active.is_(True),
            )
            .all()
        )
        deactivated: list[str] = []
        for character in characters:
            character.is_active = False
            deactivated.append(character.slug)
        session.commit()
        return sorted(deactivated)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
