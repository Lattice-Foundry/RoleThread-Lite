"""LoreForge entry metadata helpers."""
from copy import deepcopy
from datetime import datetime, timezone

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


def stamp_entry(entry: dict) -> dict:
    """Return a copy of entry stamped as written by LoreForge."""

    stamped = deepcopy(entry)
    stamped[LOREFORGE_META_KEY] = {
        "version": LOREFORGE_VERSION,
        "native": True,
        "validated_at": _utc_timestamp(),
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
