"""Pure registry sidecar schema, serialization, and validation helpers."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from core.version import ROLETHREAD_VERSION


SIDECAR_SCHEMA_VERSION = 1
SIDECAR_KIND = "rolethread.tag_registry"
SIDECAR_APP_NAME = "RoleThread Lite"
SIDECAR_APP_VERSION = ROLETHREAD_VERSION
_MISSING = object()


@dataclass(frozen=True)
class SidecarMetadata:
    """Metadata identifying a RoleThread registry sidecar."""

    schema_version: int = SIDECAR_SCHEMA_VERSION
    kind: str = SIDECAR_KIND
    exported_at: str = ""
    app_name: str = SIDECAR_APP_NAME
    app_version: str = SIDECAR_APP_VERSION


@dataclass(frozen=True)
class SidecarDatasetInfo:
    """Dataset details useful for matching sidecars to JSONL files.

    ``tag_usage_counts`` is exported as diagnostic snapshot metadata only.
    Importers must recompute usage from entries rather than trust these counts
    as source-of-truth registry data.
    """

    dataset_uuid: str
    filename: str
    entry_count: int = 0
    tag_usage_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SidecarCategory:
    """Serializable tag category record."""

    slug: str
    name: str
    sort_order: int = 0
    is_active: bool = True
    is_builtin: bool = False


@dataclass(frozen=True)
class SidecarTag:
    """Serializable tag record."""

    slug: str
    name: str
    category_slug: str | None = None
    sort_order: int = 0
    status: str = "active"
    is_active: bool = True
    is_builtin: bool = False
    lifecycle: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SidecarAlias:
    """Serializable resolver alias record."""

    old_slug: str
    new_slug: str | None
    action: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SidecarCharacter:
    """Serializable character record."""

    slug: str
    display_name: str
    description: str | None = None
    is_active: bool = True


@dataclass(frozen=True)
class SidecarSystemPrompt:
    """Serializable system prompt template record."""

    slug: str
    name: str
    content: str
    description: str | None = None
    is_active: bool = True


@dataclass(frozen=True)
class SidecarEntryCharacterMapping:
    """Serializable per-entry character turn mappings."""

    entry_uuid: str
    turns: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class SidecarRegistry:
    """Complete portable tag registry sidecar."""

    metadata: SidecarMetadata
    dataset_info: SidecarDatasetInfo
    categories: tuple[SidecarCategory, ...] = ()
    tags: tuple[SidecarTag, ...] = ()
    aliases: tuple[SidecarAlias, ...] = ()
    characters: tuple[SidecarCharacter, ...] = ()
    entry_character_mappings: tuple[SidecarEntryCharacterMapping, ...] = ()
    system_prompts: tuple[SidecarSystemPrompt, ...] = ()


class SidecarValidationError(ValueError):
    """Raised when a registry sidecar cannot be parsed or validated."""


def build_sidecar_registry(
    *,
    categories,
    tags,
    aliases,
    dataset_uuid: str,
    dataset_filename: str,
    entry_count: int,
    tag_usage_counts: dict[str, int],
    characters=(),
    entry_character_mappings=(),
    system_prompts=(),
) -> SidecarRegistry:
    """Build a registry sidecar from already-queried registry data."""

    if not isinstance(dataset_uuid, str) or not dataset_uuid:
        raise SidecarValidationError("Missing or invalid 'dataset_uuid' string.")
    return SidecarRegistry(
        metadata=SidecarMetadata(exported_at=_utc_timestamp()),
        dataset_info=SidecarDatasetInfo(
            dataset_uuid=str(dataset_uuid),
            filename=str(dataset_filename),
            entry_count=int(entry_count),
            # Snapshot/diagnostic metadata only. Entry tags remain authoritative.
            tag_usage_counts={str(k): int(v) for k, v in tag_usage_counts.items()},
        ),
        categories=tuple(_coerce_category(category) for category in categories),
        tags=tuple(_coerce_tag(tag) for tag in tags),
        aliases=tuple(_coerce_alias(alias) for alias in aliases),
        characters=tuple(_coerce_character(character) for character in characters),
        entry_character_mappings=tuple(
            _coerce_entry_character_mapping(mapping)
            for mapping in entry_character_mappings
        ),
        system_prompts=tuple(
            _coerce_system_prompt(prompt)
            for prompt in system_prompts
        ),
    )


def sidecar_to_dict(registry: SidecarRegistry) -> dict[str, Any]:
    """Convert a sidecar registry dataclass tree to a JSON-ready dict."""

    return {
        "metadata": asdict(registry.metadata),
        "dataset": asdict(registry.dataset_info),
        "categories": [asdict(category) for category in registry.categories],
        "tags": [asdict(tag) for tag in registry.tags],
        "aliases": [asdict(alias) for alias in registry.aliases],
        "characters": [asdict(character) for character in registry.characters],
        "entry_character_mappings": [
            {
                "entry_uuid": mapping.entry_uuid,
                "turns": [dict(turn) for turn in mapping.turns],
            }
            for mapping in registry.entry_character_mappings
        ],
        "system_prompts": [asdict(prompt) for prompt in registry.system_prompts],
    }


def write_sidecar(registry: SidecarRegistry, path: Path) -> None:
    """Write a registry sidecar JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(sidecar_to_dict(registry), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_sidecar(path: Path) -> SidecarRegistry:
    """Read, parse, and validate a registry sidecar JSON file."""

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return parse_sidecar_dict(data)


def parse_sidecar_dict(data: dict) -> SidecarRegistry:
    """Parse an already-loaded sidecar dict into frozen dataclasses."""

    if not isinstance(data, dict):
        raise SidecarValidationError("Registry sidecar must be a JSON object.")

    metadata_data = _required_mapping(data, "metadata")
    metadata = _parse_metadata(metadata_data)

    dataset_data = _required_mapping(data, "dataset")
    dataset_info = SidecarDatasetInfo(
        dataset_uuid=_required_str(dataset_data, "dataset_uuid"),
        filename=_required_str(dataset_data, "filename"),
        entry_count=_optional_int(dataset_data, "entry_count", 0),
        tag_usage_counts=_coerce_usage_counts(
            dataset_data.get("tag_usage_counts", {})
        ),
    )

    categories = tuple(
        _parse_category(item)
        for item in _optional_list(data, "categories")
    )
    tags = tuple(_parse_tag(item) for item in _optional_list(data, "tags"))
    aliases = tuple(_parse_alias(item) for item in _optional_list(data, "aliases"))
    characters = tuple(
        _parse_character(item)
        for item in _optional_list(data, "characters")
    )
    entry_character_mappings = tuple(
        _parse_entry_character_mapping(item)
        for item in _optional_list(data, "entry_character_mappings")
    )
    system_prompts = tuple(
        _parse_system_prompt(item)
        for item in _optional_list(data, "system_prompts")
    )

    return SidecarRegistry(
        metadata=metadata,
        dataset_info=dataset_info,
        categories=categories,
        tags=tags,
        aliases=aliases,
        characters=characters,
        entry_character_mappings=entry_character_mappings,
        system_prompts=system_prompts,
    )


def sidecar_path_for_dataset(dataset_path: Path) -> Path:
    """Return the sibling registry sidecar path for one dataset JSONL path."""

    return dataset_path.with_name(f"{dataset_path.stem}.registry.json")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_category(category) -> SidecarCategory:
    if isinstance(category, SidecarCategory):
        return category
    return SidecarCategory(
        slug=str(_get_value(category, "slug")),
        name=str(_get_value(category, "name")),
        sort_order=int(_get_value(category, "sort_order", 0)),
        is_active=bool(_get_value(category, "is_active", True)),
        is_builtin=bool(_get_value(category, "is_builtin", False)),
    )


def _coerce_tag(tag) -> SidecarTag:
    if isinstance(tag, SidecarTag):
        return tag
    category_slug = _get_value(tag, "category_slug", None)
    return SidecarTag(
        slug=str(_get_value(tag, "slug")),
        name=str(_get_value(tag, "name")),
        category_slug=str(category_slug) if category_slug is not None else None,
        sort_order=int(_get_value(tag, "sort_order", 0)),
        status=str(_get_value(tag, "status", "active")),
        is_active=bool(_get_value(tag, "is_active", True)),
        is_builtin=bool(_get_value(tag, "is_builtin", False)),
        lifecycle=_copy_mapping(_get_value(tag, "lifecycle", {})),
    )


def _coerce_alias(alias) -> SidecarAlias:
    if isinstance(alias, SidecarAlias):
        return alias
    new_slug = _get_value(alias, "new_slug", None)
    return SidecarAlias(
        old_slug=str(_get_value(alias, "old_slug")),
        new_slug=str(new_slug) if new_slug is not None else None,
        action=str(_get_value(alias, "action")),
        metadata=_copy_mapping(_get_value(alias, "metadata", {})),
    )


def _coerce_character(character) -> SidecarCharacter:
    if isinstance(character, SidecarCharacter):
        return character
    description = _get_value(character, "description", None)
    return SidecarCharacter(
        slug=str(_get_value(character, "slug")),
        display_name=str(_get_value(character, "display_name")),
        description=str(description) if description is not None else None,
        is_active=bool(_get_value(character, "is_active", True)),
    )


def _coerce_entry_character_mapping(mapping) -> SidecarEntryCharacterMapping:
    if isinstance(mapping, SidecarEntryCharacterMapping):
        return mapping
    return SidecarEntryCharacterMapping(
        entry_uuid=str(_get_value(mapping, "entry_uuid")),
        turns=tuple(dict(turn) for turn in _get_value(mapping, "turns", ())),
    )


def _coerce_system_prompt(prompt) -> SidecarSystemPrompt:
    if isinstance(prompt, SidecarSystemPrompt):
        return prompt
    description = _get_value(prompt, "description", None)
    return SidecarSystemPrompt(
        slug=str(_get_value(prompt, "slug")),
        name=str(_get_value(prompt, "name")),
        content=str(_get_value(prompt, "content")),
        description=str(description) if description is not None else None,
        is_active=bool(_get_value(prompt, "is_active", True)),
    )


def _parse_metadata(data: dict) -> SidecarMetadata:
    schema_version = _required_int(data, "schema_version")
    kind = _required_str(data, "kind")
    if kind != SIDECAR_KIND:
        raise SidecarValidationError(f"Unsupported sidecar kind: {kind}")
    if schema_version != SIDECAR_SCHEMA_VERSION:
        raise SidecarValidationError(
            f"Unsupported registry sidecar schema_version: {schema_version}"
        )
    return SidecarMetadata(
        schema_version=schema_version,
        kind=kind,
        exported_at=_required_str(data, "exported_at"),
        app_name=_optional_str(data, "app_name", SIDECAR_APP_NAME),
        app_version=_optional_str(data, "app_version", SIDECAR_APP_VERSION),
    )


def _parse_category(data: dict) -> SidecarCategory:
    if not isinstance(data, dict):
        raise SidecarValidationError("Each category must be an object.")
    return SidecarCategory(
        slug=_required_str(data, "slug"),
        name=_required_str(data, "name"),
        sort_order=_optional_int(data, "sort_order", 0),
        is_active=_optional_bool(data, "is_active", True),
        is_builtin=_optional_bool(data, "is_builtin", False),
    )


def _parse_tag(data: dict) -> SidecarTag:
    if not isinstance(data, dict):
        raise SidecarValidationError("Each tag must be an object.")
    category_slug = data.get("category_slug")
    if category_slug is not None and not isinstance(category_slug, str):
        raise SidecarValidationError("Tag category_slug must be a string or null.")
    return SidecarTag(
        slug=_required_str(data, "slug"),
        name=_required_str(data, "name"),
        category_slug=category_slug,
        sort_order=_optional_int(data, "sort_order", 0),
        status=_optional_str(data, "status", "active"),
        is_active=_optional_bool(data, "is_active", True),
        is_builtin=_optional_bool(data, "is_builtin", False),
        lifecycle=_copy_mapping(data.get("lifecycle", {})),
    )


def _parse_alias(data: dict) -> SidecarAlias:
    if not isinstance(data, dict):
        raise SidecarValidationError("Each alias must be an object.")
    new_slug = data.get("new_slug")
    if new_slug is not None and not isinstance(new_slug, str):
        raise SidecarValidationError("Alias new_slug must be a string or null.")
    return SidecarAlias(
        old_slug=_required_str(data, "old_slug"),
        new_slug=new_slug,
        action=_required_str(data, "action"),
        metadata=_copy_mapping(data.get("metadata", {})),
    )


def _parse_character(data: dict) -> SidecarCharacter:
    if not isinstance(data, dict):
        raise SidecarValidationError("Each character must be an object.")
    description = data.get("description")
    if description is not None and not isinstance(description, str):
        raise SidecarValidationError("Character description must be a string or null.")
    return SidecarCharacter(
        slug=_required_str(data, "slug"),
        display_name=_required_str(data, "display_name"),
        description=description,
        is_active=_optional_bool(data, "is_active", True),
    )


def _parse_entry_character_mapping(data: dict) -> SidecarEntryCharacterMapping:
    if not isinstance(data, dict):
        raise SidecarValidationError("Each entry character mapping must be an object.")
    turns = _optional_list(data, "turns")
    return SidecarEntryCharacterMapping(
        entry_uuid=_required_str(data, "entry_uuid"),
        turns=tuple(_parse_character_turn(turn) for turn in turns),
    )


def _parse_system_prompt(data: dict) -> SidecarSystemPrompt:
    if not isinstance(data, dict):
        raise SidecarValidationError("Each system prompt must be an object.")
    description = data.get("description")
    if description is not None and not isinstance(description, str):
        raise SidecarValidationError(
            "System prompt description must be a string or null."
        )
    return SidecarSystemPrompt(
        slug=_required_str(data, "slug"),
        name=_required_str(data, "name"),
        content=_required_str(data, "content"),
        description=description,
        is_active=_optional_bool(data, "is_active", True),
    )


def _parse_character_turn(data: dict) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SidecarValidationError("Each character turn mapping must be an object.")
    turn_index = _required_int(data, "turn_index")
    character_slug = _required_str(data, "character_slug")
    training_role = _required_str(data, "training_role")
    source_role_label = data.get("source_role_label")
    if source_role_label is not None and not isinstance(source_role_label, str):
        raise SidecarValidationError("source_role_label must be a string or null.")
    return {
        "turn_index": turn_index,
        "character_slug": character_slug,
        "training_role": training_role,
        "source_role_label": source_role_label,
    }


def _required_mapping(data: dict, key: str) -> dict:
    value = data.get(key)
    if not isinstance(value, dict):
        raise SidecarValidationError(f"Missing or invalid '{key}' object.")
    return value


def _required_str(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise SidecarValidationError(f"Missing or invalid '{key}' string.")
    return value


def _required_int(data: dict, key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise SidecarValidationError(f"Missing or invalid '{key}' integer.")
    return value


def _optional_str(data: dict, key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise SidecarValidationError(f"Invalid '{key}' string.")
    return value


def _optional_int(data: dict, key: str, default: int) -> int:
    value = data.get(key, default)
    if not isinstance(value, int):
        raise SidecarValidationError(f"Invalid '{key}' integer.")
    return value


def _optional_bool(data: dict, key: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise SidecarValidationError(f"Invalid '{key}' boolean.")
    return value


def _optional_list(data: dict, key: str) -> list:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise SidecarValidationError(f"Invalid '{key}' list.")
    return value


def _coerce_usage_counts(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise SidecarValidationError("Invalid 'tag_usage_counts' object.")
    return {str(key): int(count) for key, count in value.items()}


def _copy_mapping(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SidecarValidationError("Expected metadata object.")
    return dict(value)


def _get_value(record, key: str, default: Any = _MISSING) -> Any:
    if isinstance(record, dict):
        if key in record:
            return record[key]
        if default is not _MISSING:
            return default
        raise SidecarValidationError(f"Missing required field: {key}")

    if hasattr(record, key):
        return getattr(record, key)
    if default is not _MISSING:
        return default
    raise SidecarValidationError(f"Missing required field: {key}")

