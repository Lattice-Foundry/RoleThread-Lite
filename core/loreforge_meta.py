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
    """Return True only when all entries are signed and share dataset identity."""

    return (
        bool(entries)
        and all(is_native_entry(entry) for entry in entries)
        and get_dataset_uuid_for_entries(entries) is not None
    )


def get_entry_uuid(entry: dict) -> str | None:
    """Return an entry's stable LoreForge UUID if present."""

    metadata = get_loreforge_meta(entry)
    entry_uuid = metadata.get("entry_uuid") if metadata else None
    return entry_uuid if isinstance(entry_uuid, str) and entry_uuid else None


def get_dataset_uuid(entry: dict) -> str | None:
    """Return the dataset UUID stored on an entry if present."""

    metadata = get_loreforge_meta(entry)
    dataset_uuid = metadata.get("dataset_uuid") if metadata else None
    return dataset_uuid if isinstance(dataset_uuid, str) and dataset_uuid else None


def get_dataset_uuid_for_entries(entries: list[dict]) -> str | None:
    """Return the single dataset UUID shared by entries, if one is present."""

    dataset_uuids = {
        dataset_uuid
        for entry in entries
        if isinstance(entry, dict)
        if (dataset_uuid := get_dataset_uuid(entry))
    }
    if len(dataset_uuids) == 1:
        return next(iter(dataset_uuids))
    return None


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


def stamp_entry(entry: dict, *, dataset_uuid: str | None = None) -> dict:
    """Return a copy of entry stamped as written by LoreForge."""

    stamped = ensure_entry_uuid(entry)
    entry_uuid = get_entry_uuid(stamped)
    resolved_dataset_uuid = dataset_uuid or get_dataset_uuid(stamped) or str(uuid4())
    stamped[LOREFORGE_META_KEY] = {
        "version": LOREFORGE_VERSION,
        "native": True,
        "validated_at": _utc_timestamp(),
        "entry_uuid": entry_uuid,
        "dataset_uuid": resolved_dataset_uuid,
    }
    return stamped


def stamp_entries(entries: list[dict], *, dataset_uuid: str | None = None) -> list[dict]:
    """Return copies of entries stamped as written by LoreForge."""

    resolved_dataset_uuid = (
        dataset_uuid
        or get_dataset_uuid_for_entries([entry for entry in entries if isinstance(entry, dict)])
        or str(uuid4())
    )
    return [
        stamp_entry(entry, dataset_uuid=resolved_dataset_uuid)
        if isinstance(entry, dict)
        else deepcopy(entry)
        for entry in entries
    ]


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
