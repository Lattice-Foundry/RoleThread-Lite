"""LoreForge entry metadata helpers."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from core.version import LOREFORGE_VERSION

LOREFORGE_META_KEY = "_loreforge"


def get_loreforge_meta(entry: dict) -> dict | None:
    """Return LoreForge metadata for an entry if present and well-shaped."""

    if not isinstance(entry, dict):
        return None
    metadata = entry.get(LOREFORGE_META_KEY)
    return metadata if isinstance(metadata, dict) else None


def is_native_entry(entry: dict) -> bool:
    """Return True when an entry carries LoreForge's native signature."""

    metadata = get_loreforge_meta(entry)
    return bool(metadata and metadata.get("native") is True)


def is_native_dataset(entries: list[dict]) -> bool:
    """Return True only when all loaded entries are signed as native."""

    return bool(entries) and all(is_native_entry(entry) for entry in entries)


def get_entry_uuid(entry: dict) -> str | None:
    """Return an entry's stable LoreForge UUID if present."""

    metadata = get_loreforge_meta(entry)
    entry_uuid = metadata.get("entry_uuid") if metadata else None
    return entry_uuid if isinstance(entry_uuid, str) and entry_uuid else None


def ensure_entry_uuid(entry: dict) -> dict:
    """Return a copy of entry with a stable LoreForge UUID."""

    entry_with_uuid = deepcopy(entry)
    metadata = entry_with_uuid.get(LOREFORGE_META_KEY)
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(metadata.get("entry_uuid"), str) or not metadata["entry_uuid"]:
        metadata["entry_uuid"] = str(uuid4())
    entry_with_uuid[LOREFORGE_META_KEY] = metadata
    return entry_with_uuid


def stamp_entry(entry: dict) -> dict:
    """Return a copy of entry stamped as written by LoreForge."""

    stamped = ensure_entry_uuid(entry)
    entry_uuid = get_entry_uuid(stamped)
    stamped[LOREFORGE_META_KEY] = {
        "version": LOREFORGE_VERSION,
        "native": True,
        "validated_at": _utc_timestamp(),
        "entry_uuid": entry_uuid,
    }
    return stamped


def stamp_entries(entries: list[dict]) -> list[dict]:
    """Return copies of entries stamped as written by LoreForge."""

    return [
        stamp_entry(entry) if isinstance(entry, dict) else deepcopy(entry)
        for entry in entries
    ]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
