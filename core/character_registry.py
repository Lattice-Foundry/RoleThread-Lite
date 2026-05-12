"""DB-backed character registry helpers."""
from __future__ import annotations

from dataclasses import dataclass

from core.db import SessionLocal
from core.format_conversion import detect_custom_role_pattern
from core.loreforge_meta import get_entry_uuid
from core.models import Character, EntryCharacterTurn
from core.role_normalization import normalize_role
from core.tag_normalization import normalize_tag

_STANDARD_ROLES = {"user", "assistant", "system"}


@dataclass(frozen=True)
class CharacterCandidate:
    """Detected non-standard role name that may represent a character."""

    source_role_label: str
    suggested_slug: str
    suggested_display_name: str
    suggested_training_role: str | None
    entry_uuids: tuple[str, ...]
    turn_locations: tuple[dict, ...]
    occurrence_count: int


@dataclass(frozen=True)
class CharacterCandidateReport:
    """Grouped character candidates detected in loaded entries."""

    candidates: tuple[CharacterCandidate, ...]
    has_candidates: bool
    pattern_summary: str | None = None


def normalize_character_name(name: str) -> tuple[str, str]:
    """Return ``(slug, display_name)`` for one character name."""

    normalized = normalize_tag(name)
    return normalized.slug, normalized.display_name


def collect_character_candidates(entries: list[dict]) -> CharacterCandidateReport:
    """Collect non-standard message roles as potential character candidates."""

    pattern_summary = _detect_entry_role_pattern(entries)
    suggested_mapping = pattern_summary.suggested_mapping if pattern_summary.detected else {}
    findings: dict[str, dict] = {}

    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        entry_uuid = get_entry_uuid(entry) or f"entry_index:{entry_index}"
        messages = entry.get("messages")
        if not isinstance(messages, list):
            continue
        for turn_index, message in enumerate(messages):
            if not isinstance(message, dict):
                continue
            raw_role = message.get("role")
            if raw_role is None:
                continue
            role = str(raw_role).strip()
            if not role or _is_standard_or_known_variant(role):
                continue

            normalized_slug, display_name = normalize_character_name(role)
            if not normalized_slug:
                continue
            finding = findings.setdefault(
                role,
                {
                    "entry_uuids": [],
                    "seen_entry_uuids": set(),
                    "turn_locations": [],
                    "occurrence_count": 0,
                    "suggested_slug": normalized_slug,
                    "suggested_display_name": display_name,
                },
            )
            if entry_uuid not in finding["seen_entry_uuids"]:
                finding["seen_entry_uuids"].add(entry_uuid)
                finding["entry_uuids"].append(entry_uuid)
            finding["turn_locations"].append({
                "entry_uuid": entry_uuid,
                "turn_index": turn_index,
            })
            finding["occurrence_count"] += 1

    candidates = tuple(
        CharacterCandidate(
            source_role_label=role,
            suggested_slug=finding["suggested_slug"],
            suggested_display_name=finding["suggested_display_name"],
            suggested_training_role=suggested_mapping.get(role),
            entry_uuids=tuple(finding["entry_uuids"]),
            turn_locations=tuple(finding["turn_locations"]),
            occurrence_count=finding["occurrence_count"],
        )
        for role, finding in sorted(findings.items(), key=lambda item: item[0].lower())
    )
    return CharacterCandidateReport(
        candidates=candidates,
        has_candidates=bool(candidates),
        pattern_summary=pattern_summary.message if pattern_summary.detected else None,
    )


def _is_standard_or_known_variant(role: str) -> bool:
    normalized_role, changed = normalize_role(role)
    return normalized_role in _STANDARD_ROLES and (changed or role in _STANDARD_ROLES)


def _detect_entry_role_pattern(entries: list[dict]):
    records = []
    for entry in entries:
        messages = entry.get("messages") if isinstance(entry, dict) else None
        if not isinstance(messages, list):
            continue
        records.append({
            "conversations": [
                {"from": message.get("role"), "value": message.get("content", "")}
                for message in messages
                if isinstance(message, dict)
            ]
        })
    return detect_custom_role_pattern(records)


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


def get_inactive_characters() -> list[Character]:
    """Return inactive characters ordered by display name."""

    session = SessionLocal()
    try:
        characters = (
            session.query(Character)
            .filter_by(is_active=False)
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


def update_character(
    slug: str,
    *,
    display_name: str,
    description: str | None = None,
) -> Character:
    """Update a character's display metadata without changing its slug."""

    normalized_slug, _display_name = normalize_character_name(slug)
    if not normalized_slug:
        raise ValueError("Character slug cannot be empty.")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError("Character display name cannot be empty.")

    session = SessionLocal()
    try:
        character = (
            session.query(Character)
            .filter_by(slug=normalized_slug, is_active=True)
            .first()
        )
        if character is None:
            raise ValueError(f"Character not found: {slug}")
        character.display_name = display_name.strip()
        character.description = description.strip() if isinstance(description, str) else None
        session.commit()
        session.refresh(character)
        session.expunge(character)
        return character
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reactivate_character(slug: str) -> bool:
    """Reactivate one inactive character by normalized slug."""

    normalized_slug, _display_name = normalize_character_name(slug)
    if not normalized_slug:
        return False

    session = SessionLocal()
    try:
        character = (
            session.query(Character)
            .filter_by(slug=normalized_slug, is_active=False)
            .first()
        )
        if character is None:
            return False
        character.is_active = True
        session.commit()
        return True
    except Exception:
        session.rollback()
        raise
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
        character_ids = [character.id for character in characters]
        if character_ids:
            session.query(EntryCharacterTurn).filter(
                EntryCharacterTurn.character_id.in_(character_ids)
            ).delete(synchronize_session=False)
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


def get_character_usage_counts(slugs: list[str]) -> dict[str, int]:
    """Return entry usage counts for active characters by slug."""

    normalized_slugs = {
        normalized_slug
        for slug in slugs
        if (normalized_slug := normalize_character_name(slug)[0])
    }
    if not normalized_slugs:
        return {}

    session = SessionLocal()
    try:
        rows = (
            session.query(Character.slug, EntryCharacterTurn.entry_uuid)
            .join(EntryCharacterTurn)
            .filter(
                Character.slug.in_(normalized_slugs),
                Character.is_active.is_(True),
            )
            .distinct()
            .all()
        )
        counts: dict[str, int] = {slug: 0 for slug in normalized_slugs}
        for slug, _entry_uuid in rows:
            counts[slug] = counts.get(slug, 0) + 1
        return counts
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


def get_character_display_for_entries(entry_uuids: set[str]) -> dict[str, dict[int, str]]:
    """Return ``{entry_uuid: {turn_index: display_name}}`` for many entries."""

    if not entry_uuids:
        return {}

    session = SessionLocal()
    try:
        rows = (
            session.query(
                EntryCharacterTurn.entry_uuid,
                EntryCharacterTurn.turn_index,
                Character.display_name,
            )
            .join(Character)
            .filter(
                EntryCharacterTurn.entry_uuid.in_(entry_uuids),
                Character.is_active.is_(True),
            )
            .order_by(EntryCharacterTurn.entry_uuid, EntryCharacterTurn.turn_index)
            .all()
        )
        display_by_entry: dict[str, dict[int, str]] = {}
        for entry_uuid, turn_index, display_name in rows:
            display_by_entry.setdefault(entry_uuid, {})[turn_index] = display_name
        return display_by_entry
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
