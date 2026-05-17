"""Character display-name helpers for conversation previews."""
from __future__ import annotations

from core.character_registry import (
    get_character_display_for_entries,
    get_character_display_for_entry,
)
from core.rolethread_meta import get_entry_uuid

_ROLE_LABELS = {
    "system": "System",
    "user": "User",
    "assistant": "Assistant",
}


def build_character_display_cache(entries: list[dict]) -> dict[str, dict[int, str]]:
    """Return character display mappings for the given entries in one DB query."""

    entry_uuids = {
        entry_uuid
        for entry in entries
        if isinstance(entry, dict) and (entry_uuid := get_entry_uuid(entry))
    }
    return get_character_display_for_entries(entry_uuids)


def get_turn_display_names(
    entry: dict,
    user_default: str,
    assistant_default: str,
    character_display_cache: dict[str, dict[int, str]] | None = None,
) -> dict[int, str]:
    """Return display labels for every message turn in an entry."""

    if not isinstance(entry, dict):
        return {}

    entry_uuid = get_entry_uuid(entry)
    character_names = _character_names_for_entry(entry_uuid, character_display_cache)
    messages = entry.get("messages")
    if not isinstance(messages, list):
        return {}

    return {
        turn_index: _display_name_for_turn(
            message,
            turn_index,
            character_names,
            user_default,
            assistant_default,
        )
        for turn_index, message in enumerate(messages)
        if isinstance(message, dict)
    }


def _character_names_for_entry(
    entry_uuid: str | None,
    character_display_cache: dict[str, dict[int, str]] | None,
) -> dict[int, str]:
    if not entry_uuid:
        return {}
    if character_display_cache is not None:
        return character_display_cache.get(entry_uuid, {})
    return get_character_display_for_entry(entry_uuid)


def _display_name_for_turn(
    message: dict,
    turn_index: int,
    character_names: dict[int, str],
    user_default: str,
    assistant_default: str,
) -> str:
    if turn_index in character_names:
        return character_names[turn_index]

    role = str(message.get("role", "") or "").strip()
    role_key = role.lower()
    if role_key == "user":
        return user_default or _ROLE_LABELS["user"]
    if role_key == "assistant":
        return assistant_default or _ROLE_LABELS["assistant"]
    return _ROLE_LABELS.get(role_key, role or "?")

