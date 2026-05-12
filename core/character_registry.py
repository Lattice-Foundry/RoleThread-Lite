"""DB-backed character registry helpers."""
from __future__ import annotations

from core.db import SessionLocal
from core.models import Character, EntryCharacterTurn
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


def set_entry_character_turns(entry_uuid: str, turns: list[dict]) -> list[EntryCharacterTurn]:
    """Replace all character turn mappings for one entry UUID."""

    if not entry_uuid:
        raise ValueError("Entry UUID is required.")

    session = SessionLocal()
    try:
        session.query(EntryCharacterTurn).filter_by(entry_uuid=entry_uuid).delete()
        mappings: list[EntryCharacterTurn] = []
        for turn in turns:
            turn_index = turn.get("turn_index")
            character_slug = turn.get("character_slug")
            training_role = turn.get("training_role")
            if not isinstance(turn_index, int) or turn_index < 0:
                raise ValueError("Turn index must be a non-negative integer.")
            if not isinstance(training_role, str) or not training_role.strip():
                raise ValueError("Training role is required.")

            normalized_slug, _display_name = normalize_character_name(character_slug or "")
            character = (
                session.query(Character)
                .filter_by(slug=normalized_slug, is_active=True)
                .first()
            )
            if character is None:
                raise ValueError(f"Character not found: {character_slug}")

            mapping = EntryCharacterTurn(
                entry_uuid=entry_uuid,
                turn_index=turn_index,
                character_id=character.id,
                training_role=training_role.strip(),
                source_role_label=turn.get("source_role_label"),
            )
            session.add(mapping)
            mappings.append(mapping)

        session.commit()
        for mapping in mappings:
            session.refresh(mapping)
            session.expunge(mapping)
        return sorted(mappings, key=lambda mapping: mapping.turn_index)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_entry_character_turns(entry_uuid: str) -> list[EntryCharacterTurn]:
    """Return turn mappings for one entry UUID ordered by turn index."""

    session = SessionLocal()
    try:
        mappings = (
            session.query(EntryCharacterTurn)
            .join(Character)
            .filter(EntryCharacterTurn.entry_uuid == entry_uuid)
            .order_by(EntryCharacterTurn.turn_index)
            .all()
        )
        for mapping in mappings:
            session.expunge(mapping)
        return mappings
    finally:
        session.close()


def get_character_display_for_entry(entry_uuid: str) -> dict[int, str]:
    """Return ``{turn_index: display_name}`` for one entry UUID."""

    session = SessionLocal()
    try:
        rows = (
            session.query(EntryCharacterTurn.turn_index, Character.display_name)
            .join(Character)
            .filter(EntryCharacterTurn.entry_uuid == entry_uuid)
            .order_by(EntryCharacterTurn.turn_index)
            .all()
        )
        return {turn_index: display_name for turn_index, display_name in rows}
    finally:
        session.close()


def get_entries_for_character(character_slug: str) -> list[str]:
    """Return entry UUIDs that have mappings for one active character."""

    normalized_slug, _display_name = normalize_character_name(character_slug)
    if not normalized_slug:
        return []

    session = SessionLocal()
    try:
        rows = (
            session.query(EntryCharacterTurn.entry_uuid)
            .join(Character)
            .filter(
                Character.slug == normalized_slug,
                Character.is_active.is_(True),
            )
            .distinct()
            .order_by(EntryCharacterTurn.entry_uuid)
            .all()
        )
        return [entry_uuid for (entry_uuid,) in rows]
    finally:
        session.close()


def delete_entry_character_turns(entry_uuid: str) -> int:
    """Remove all character turn mappings for one entry UUID."""

    session = SessionLocal()
    try:
        deleted_count = (
            session.query(EntryCharacterTurn)
            .filter_by(entry_uuid=entry_uuid)
            .delete()
        )
        session.commit()
        return deleted_count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def bulk_set_character_mappings(mappings: list[dict]) -> dict[str, int]:
    """Replace character turn mappings for many entries."""

    applied_entries = 0
    applied_turns = 0
    for mapping in mappings:
        entry_uuid = mapping.get("entry_uuid")
        turns = mapping.get("turns", [])
        created = set_entry_character_turns(entry_uuid, turns)
        applied_entries += 1
        applied_turns += len(created)
    return {"entries": applied_entries, "turns": applied_turns}
