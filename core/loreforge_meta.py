"""LoreForge entry metadata helpers."""

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
