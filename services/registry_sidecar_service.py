"""Framework-independent registry sidecar export service."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import traceback
from uuid import uuid4

from core.dataset import TAGS, get_entry_tags
from core.rolethread_meta import get_dataset_uuid_for_entries, get_entry_uuid
from core.models import (
    Character,
    EntryCharacterTurn,
    SystemPromptTemplate,
    Tag,
    TagCategory,
    TagLifecycleMetadata,
)
from core.registry_sidecar import (
    SidecarRegistry,
    build_sidecar_registry,
    read_sidecar,
    sidecar_path_for_dataset,
    write_sidecar,
)
from core.tag_constants import (
    ARCHIVE_ORIGIN_DELETED,
    ARCHIVE_ORIGIN_IMPORTED,
    TAG_ALIAS_METADATA_ACTIONS,
    TAG_CURRENT_METADATA_ACTIONS,
    TAG_LIFECYCLE_METADATA_ARCHIVE,
    TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
    TAG_LIFECYCLE_METADATA_HIDE,
    TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
    TAG_LIFECYCLE_METADATA_MERGE,
    TAG_LIFECYCLE_METADATA_RENAME,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
)
from core.tag_normalization import normalize_tag
from core.tag_resolution import resolve_tag_lifecycle
from core.text_helpers import count_phrase
from core.tag_registry import SessionLocal, create_db_backup, engine


@dataclass
class RegistrySidecarExportResult:
    """Structured result returned by registry sidecar export."""

    ok: bool
    message: str
    path: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class RegistrySidecarImportResult:
    """Structured result returned by registry sidecar import."""

    ok: bool
    message: str
    categories_created: list[str] = field(default_factory=list)
    tags_created: list[str] = field(default_factory=list)
    tags_promoted: list[str] = field(default_factory=list)
    aliases_imported: list[str] = field(default_factory=list)
    characters_created: list[str] = field(default_factory=list)
    character_mappings_imported: list[str] = field(default_factory=list)
    system_prompts_created: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    db_backup_path: str | None = None


def export_registry_sidecar(
    *,
    dataset_path: str,
    entries: list[dict],
    dataset_uuid: str | None = None,
    extra_character_slugs: set[str] | None = None,
) -> RegistrySidecarExportResult:
    """Export the current DB tag registry as a sidecar next to a dataset path."""
    if not dataset_path:
        return RegistrySidecarExportResult(
            ok=False,
            message="Could not export registry sidecar.",
            errors=["No export dataset path was provided."],
        )

    try:
        output_path = sidecar_path_for_dataset(Path(dataset_path))
        resolved_dataset_uuid = (
            dataset_uuid
            or get_dataset_uuid_for_entries(entries)
            or _existing_sidecar_dataset_uuid(output_path)
            or str(uuid4())
        )
        usage_counts = _tag_usage_counts(entries)
        included_slugs = set(usage_counts)
        raw_slugs = _raw_tag_slugs(entries)
        entry_uuids = _entry_uuids(entries)
        character_mappings = _query_entry_character_mappings(entry_uuids)
        character_slugs = {
            turn["character_slug"]
            for mapping in character_mappings
            for turn in mapping["turns"]
        }
        character_slugs.update(extra_character_slugs or set())
        tags = _query_tags()
        tags = [tag for tag in tags if tag["slug"] in included_slugs]
        category_slugs = {
            tag["category_slug"]
            for tag in tags
            if tag.get("category_slug")
        }
        registry = build_sidecar_registry(
            categories=[
                category
                for category in _query_categories()
                if category["slug"] in category_slugs
            ],
            tags=tags,
            aliases=[
                alias
                for alias in _query_aliases()
                if alias.get("old_slug") in raw_slugs
                or alias.get("new_slug") in included_slugs
            ],
            characters=[
                character
                for character in _query_characters()
                if character["slug"] in character_slugs
            ],
            entry_character_mappings=character_mappings,
            system_prompts=_query_system_prompts(),
            dataset_uuid=resolved_dataset_uuid,
            dataset_filename=Path(dataset_path).name,
            entry_count=len(entries),
            tag_usage_counts=usage_counts,
        )
        write_sidecar(registry, output_path)
        return RegistrySidecarExportResult(
            ok=True,
            message=f"Registry sidecar written to {output_path.name}.",
            path=str(output_path),
        )
    except Exception as exc:
        traceback.print_exc()
        return RegistrySidecarExportResult(
            ok=False,
            message=f"Could not export registry sidecar: {exc}",
            errors=[str(exc)],
        )


def import_registry_sidecar(
    *,
    sidecar_path: str | Path | None = None,
    registry: SidecarRegistry | None = None,
    entries: list[dict] | None = None,
    include_entry_character_mappings: bool = True,
    valid_entry_uuids: set[str] | None = None,
) -> RegistrySidecarImportResult:
    """Merge a registry sidecar into the current DB registry."""
    if registry is None:
        if sidecar_path is None:
            return RegistrySidecarImportResult(
                ok=False,
                message="Could not import registry sidecar.",
                errors=["No registry sidecar path was provided."],
            )
        try:
            registry = read_sidecar(Path(sidecar_path))
        except Exception as exc:
            traceback.print_exc()
            return RegistrySidecarImportResult(
                ok=False,
                message=f"Could not import registry sidecar: {exc}",
                errors=[str(exc)],
            )

    if entries is not None:
        entry_dataset_uuid = get_dataset_uuid_for_entries(entries)
        if entry_dataset_uuid and registry.dataset_info.dataset_uuid != entry_dataset_uuid:
            return RegistrySidecarImportResult(
                ok=False,
                message="Could not import registry sidecar.",
                errors=[
                    "Sidecar dataset UUID does not match the loaded dataset "
                    f"({registry.dataset_info.dataset_uuid} != {entry_dataset_uuid})."
                ],
            )

    session = SessionLocal()
    result = RegistrySidecarImportResult(
        ok=False,
        message="Could not import registry sidecar.",
    )
    try:
        try:
            backup_path = create_db_backup(engine=engine)
            result.db_backup_path = str(backup_path)
        except Exception as exc:
            traceback.print_exc()
            result.errors.append(f"Could not create database backup: {exc}")
            return result

        _merge_categories(session, registry, result)
        _merge_tags(session, registry, result)
        session.flush()
        _merge_aliases(session, registry, result)
        _merge_characters(session, registry, result)
        _merge_system_prompts(session, registry, result)
        session.flush()
        if include_entry_character_mappings:
            mapping_valid_entry_uuids = valid_entry_uuids
            if mapping_valid_entry_uuids is None and entries is not None:
                mapping_valid_entry_uuids = _entry_uuids(entries)
            _merge_character_mappings(
                session,
                registry,
                result,
                valid_entry_uuids=mapping_valid_entry_uuids,
            )

        session.commit()
        result.ok = not result.errors
        result.message = _import_success_message(result) if result.ok else result.message
        return result
    except Exception as exc:
        traceback.print_exc()
        session.rollback()
        result.ok = False
        result.message = f"Could not import registry sidecar: {exc}"
        result.errors.append(str(exc))
        return result
    finally:
        session.close()


def _query_categories() -> list[dict]:
    default_slugs = {normalize_tag(category_name).slug for category_name in TAGS}
    session = SessionLocal()
    try:
        categories = (
            session.query(TagCategory)
            .order_by(TagCategory.sort_order, TagCategory.name, TagCategory.slug)
            .all()
        )
        return [
            {
                "slug": category.slug,
                "name": category.name,
                "sort_order": category.sort_order,
                "is_active": category.is_active,
                "is_builtin": category.slug in default_slugs,
            }
            for category in categories
        ]
    finally:
        session.close()


def _query_tags() -> list[dict]:
    session = SessionLocal()
    try:
        tags = (
            session.query(Tag)
            .outerjoin(TagCategory, Tag.category_id == TagCategory.id)
            .order_by(Tag.sort_order, Tag.name, Tag.slug)
            .all()
        )
        metadata_by_slug = _current_metadata_by_slug(session)
        return [
            {
                "slug": tag.slug,
                "name": tag.name,
                "category_slug": tag.category.slug if tag.category is not None else None,
                "sort_order": tag.sort_order,
                "status": tag.status,
                "is_active": tag.is_active,
                "is_builtin": tag.is_builtin,
                "lifecycle": metadata_by_slug.get(tag.slug, {}),
            }
            for tag in tags
        ]
    finally:
        session.close()


def _query_aliases() -> list[dict]:
    session = SessionLocal()
    try:
        rows = (
            session.query(TagLifecycleMetadata)
            .filter(TagLifecycleMetadata.action.in_(TAG_ALIAS_METADATA_ACTIONS))
            .order_by(TagLifecycleMetadata.id)
            .all()
        )
        return [
            {
                "old_slug": row.old_slug or "",
                "new_slug": row.new_slug,
                "action": row.action,
                "metadata": _parse_metadata(row.metadata_json),
            }
            for row in rows
            if row.old_slug
        ]
    finally:
        session.close()


def _query_characters() -> list[dict]:
    session = SessionLocal()
    try:
        characters = (
            session.query(Character)
            .filter_by(is_active=True)
            .order_by(Character.display_name, Character.slug)
            .all()
        )
        return [
            {
                "slug": character.slug,
                "display_name": character.display_name,
                "description": character.description,
                "is_active": character.is_active,
            }
            for character in characters
        ]
    finally:
        session.close()


def _query_entry_character_mappings(entry_uuids: set[str]) -> list[dict]:
    if not entry_uuids:
        return []

    session = SessionLocal()
    try:
        rows = (
            session.query(EntryCharacterTurn)
            .join(Character)
            .filter(
                EntryCharacterTurn.entry_uuid.in_(entry_uuids),
                Character.is_active.is_(True),
            )
            .order_by(EntryCharacterTurn.entry_uuid, EntryCharacterTurn.turn_index)
            .all()
        )
        mappings_by_uuid: dict[str, list[dict]] = {}
        for row in rows:
            mappings_by_uuid.setdefault(row.entry_uuid, []).append({
                "turn_index": row.turn_index,
                "character_slug": row.character.slug,
                "training_role": row.training_role,
                "source_role_label": row.source_role_label,
            })
        return [
            {"entry_uuid": entry_uuid, "turns": turns}
            for entry_uuid, turns in mappings_by_uuid.items()
        ]
    finally:
        session.close()


def _query_system_prompts() -> list[dict]:
    session = SessionLocal()
    try:
        prompts = (
            session.query(SystemPromptTemplate)
            .filter_by(is_active=True)
            .order_by(SystemPromptTemplate.name, SystemPromptTemplate.slug)
            .all()
        )
        return [
            {
                "slug": prompt.slug,
                "name": prompt.name,
                "content": prompt.content,
                "description": prompt.description,
                "is_active": prompt.is_active,
            }
            for prompt in prompts
        ]
    finally:
        session.close()


def _current_metadata_by_slug(session) -> dict[str, dict]:
    rows = (
        session.query(TagLifecycleMetadata)
        .filter(TagLifecycleMetadata.action.in_(TAG_CURRENT_METADATA_ACTIONS))
        .order_by(TagLifecycleMetadata.id.desc())
        .all()
    )
    metadata_by_slug: dict[str, dict] = {}
    for row in rows:
        if not row.old_slug or row.old_slug in metadata_by_slug:
            continue
        metadata_by_slug[row.old_slug] = _parse_metadata(row.metadata_json)
    return metadata_by_slug


def _parse_metadata(metadata_json: str | None) -> dict:
    if not metadata_json:
        return {}
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _tag_usage_counts(entries: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        seen_for_entry: set[str] = set()
        for tag in get_entry_tags(entry):
            canonical_slug = _canonical_tag_slug(tag)
            if not canonical_slug or canonical_slug in seen_for_entry:
                continue
            seen_for_entry.add(canonical_slug)
            counts[canonical_slug] = counts.get(canonical_slug, 0) + 1
    return counts


def _raw_tag_slugs(entries: list[dict]) -> set[str]:
    return {
        tag
        for entry in entries
        for tag in get_entry_tags(entry)
        if tag
    }


def _entry_uuids(entries: list[dict] | None) -> set[str]:
    return {
        entry_uuid
        for entry in (entries or [])
        if (entry_uuid := get_entry_uuid(entry))
    }


def _existing_sidecar_dataset_uuid(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return read_sidecar(path).dataset_info.dataset_uuid
    except Exception:
        return None


def _canonical_tag_slug(tag: str) -> str:
    resolution = resolve_tag_lifecycle(tag)
    if resolution.should_rewrite_slug and resolution.resolved_slug:
        return resolution.resolved_slug
    return resolution.resolved_slug or normalize_tag(tag).slug


def _merge_categories(
    session,
    registry: SidecarRegistry,
    result: RegistrySidecarImportResult,
) -> None:
    default_slugs = {normalize_tag(category_name).slug for category_name in TAGS}
    for category in registry.categories:
        existing = session.query(TagCategory).filter_by(slug=category.slug).first()
        if existing is not None:
            if existing.name != category.name:
                result.warnings.append(
                    f"Category '{category.slug}' already exists as "
                    f"'{existing.name}'; sidecar name '{category.name}' was skipped."
                )
            continue

        if category.is_builtin and category.slug not in default_slugs:
            result.warnings.append(
                f"Built-in category '{category.name}' is not a current RoleThread "
                "default and was skipped."
            )
            continue

        session.add(
            TagCategory(
                name=category.name,
                slug=category.slug,
                sort_order=category.sort_order,
                is_active=category.is_active,
            )
        )
        result.categories_created.append(category.slug)
    session.flush()


def _merge_tags(
    session,
    registry: SidecarRegistry,
    result: RegistrySidecarImportResult,
) -> None:
    categories_by_slug = {
        category.slug: category
        for category in session.query(TagCategory).all()
    }
    sidecar_categories = {
        category.slug: category
        for category in registry.categories
    }

    for sidecar_tag in registry.tags:
        category = _ensure_tag_category(
            session,
            sidecar_tag,
            categories_by_slug,
            sidecar_categories,
            result,
        )
        if sidecar_tag.status == TAG_STATUS_ACTIVE and category is None:
            result.conflicts.append(
                f"Tag '{sidecar_tag.slug}' is active in the sidecar but has no usable category."
            )
            continue

        existing = session.query(Tag).filter_by(slug=sidecar_tag.slug).first()
        if existing is None:
            _create_tag_from_sidecar(session, sidecar_tag, category, result)
            continue

        existing_category_slug = (
            existing.category.slug if existing.category is not None else None
        )
        if (
            existing.status == sidecar_tag.status
            and existing_category_slug == sidecar_tag.category_slug
        ):
            continue

        if (
            existing.status == TAG_STATUS_ACTIVE
            and sidecar_tag.status == TAG_STATUS_ACTIVE
            and existing_category_slug != sidecar_tag.category_slug
        ):
            result.conflicts.append(
                f"Active tag '{sidecar_tag.slug}' is already in category "
                f"'{existing_category_slug}', not '{sidecar_tag.category_slug}'."
            )
            continue

        if (
            existing.status == TAG_STATUS_ARCHIVED
            and sidecar_tag.status == TAG_STATUS_ACTIVE
            and _is_imported_archived_tag(session, existing)
        ):
            existing.status = TAG_STATUS_ACTIVE
            existing.is_active = True
            existing.category_id = category.id
            existing.sort_order = sidecar_tag.sort_order
            existing.name = sidecar_tag.name
            existing.is_builtin = sidecar_tag.is_builtin
            _write_current_metadata(session, sidecar_tag)
            result.tags_promoted.append(sidecar_tag.slug)
            continue

        result.conflicts.append(
            f"Tag '{sidecar_tag.slug}' already exists with status "
            f"'{existing.status}' and was not overwritten."
        )


def _merge_aliases(
    session,
    registry: SidecarRegistry,
    result: RegistrySidecarImportResult,
) -> None:
    for alias in registry.aliases:
        if not alias.new_slug:
            result.warnings.append(
                f"Alias '{alias.old_slug}' has no target and was skipped."
            )
            continue
        target = session.query(Tag).filter_by(slug=alias.new_slug).first()
        if target is None:
            result.warnings.append(
                f"Alias '{alias.old_slug}' -> '{alias.new_slug}' was skipped "
                "because the target tag does not exist."
            )
            continue
        if _alias_exists(session, alias):
            continue

        session.add(
            TagLifecycleMetadata(
                action=alias.action,
                old_slug=alias.old_slug,
                old_display_name=None,
                old_category_slug=None,
                new_slug=alias.new_slug,
                new_display_name=target.name,
                new_category_slug=target.category.slug if target.category else None,
                metadata_json=_metadata_json(alias.metadata),
            )
        )
        result.aliases_imported.append(alias.old_slug)


def _merge_characters(
    session,
    registry: SidecarRegistry,
    result: RegistrySidecarImportResult,
) -> None:
    for character in registry.characters:
        existing = session.query(Character).filter_by(slug=character.slug).first()
        if existing is not None:
            continue
        session.add(
            Character(
                slug=character.slug,
                display_name=character.display_name,
                description=character.description,
                is_active=character.is_active,
            )
        )
        result.characters_created.append(character.slug)


def _merge_system_prompts(
    session,
    registry: SidecarRegistry,
    result: RegistrySidecarImportResult,
) -> None:
    for prompt in registry.system_prompts:
        existing = (
            session.query(SystemPromptTemplate)
            .filter_by(slug=prompt.slug)
            .first()
        )
        if existing is not None:
            result.warnings.append(
                f"System prompt template '{prompt.slug}' already exists and was skipped."
            )
            continue
        session.add(
            SystemPromptTemplate(
                slug=prompt.slug,
                name=prompt.name,
                content=prompt.content,
                description=prompt.description,
                is_active=prompt.is_active,
            )
        )
        result.system_prompts_created.append(prompt.slug)


def _merge_character_mappings(
    session,
    registry: SidecarRegistry,
    result: RegistrySidecarImportResult,
    *,
    valid_entry_uuids: set[str] | None,
) -> None:
    characters_by_slug = {
        character.slug: character
        for character in session.query(Character).all()
    }
    for mapping in registry.entry_character_mappings:
        if valid_entry_uuids is not None and mapping.entry_uuid not in valid_entry_uuids:
            result.warnings.append(
                f"Character mapping for entry '{mapping.entry_uuid}' was skipped "
                "because that entry is not loaded."
            )
            continue

        session.query(EntryCharacterTurn).filter_by(
            entry_uuid=mapping.entry_uuid
        ).delete()
        imported_turns = 0
        for turn in mapping.turns:
            character_slug = turn.get("character_slug")
            character = characters_by_slug.get(character_slug)
            if character is None:
                result.warnings.append(
                    f"Character mapping for entry '{mapping.entry_uuid}' turn "
                    f"{turn.get('turn_index')} was skipped because character "
                    f"'{character_slug}' does not exist."
                )
                continue
            session.add(
                EntryCharacterTurn(
                    entry_uuid=mapping.entry_uuid,
                    turn_index=turn["turn_index"],
                    character_id=character.id,
                    training_role=turn["training_role"],
                    source_role_label=turn.get("source_role_label"),
                )
            )
            imported_turns += 1
        if imported_turns:
            result.character_mappings_imported.append(mapping.entry_uuid)


def _ensure_tag_category(
    session,
    sidecar_tag,
    categories_by_slug: dict[str, TagCategory],
    sidecar_categories,
    result: RegistrySidecarImportResult,
) -> TagCategory | None:
    if not sidecar_tag.category_slug:
        return None
    category = categories_by_slug.get(sidecar_tag.category_slug)
    if category is not None:
        return category

    sidecar_category = sidecar_categories.get(sidecar_tag.category_slug)
    if sidecar_category is not None:
        category_name = sidecar_category.name
        sort_order = sidecar_category.sort_order
        is_active = sidecar_category.is_active
    else:
        normalized = normalize_tag(sidecar_tag.category_slug)
        category_name = normalized.display_name
        sort_order = 0
        is_active = True

    category = TagCategory(
        name=category_name,
        slug=sidecar_tag.category_slug,
        sort_order=sort_order,
        is_active=is_active,
    )
    session.add(category)
    session.flush()
    categories_by_slug[category.slug] = category
    result.categories_created.append(category.slug)
    return category


def _create_tag_from_sidecar(
    session,
    sidecar_tag,
    category: TagCategory | None,
    result: RegistrySidecarImportResult,
) -> None:
    tag = Tag(
        category_id=category.id if category is not None else None,
        name=sidecar_tag.name,
        slug=sidecar_tag.slug,
        sort_order=sidecar_tag.sort_order,
        is_active=sidecar_tag.is_active,
        is_builtin=sidecar_tag.is_builtin,
        status=sidecar_tag.status,
    )
    session.add(tag)
    _write_current_metadata(session, sidecar_tag)
    result.tags_created.append(sidecar_tag.slug)


def _write_current_metadata(session, sidecar_tag) -> None:
    metadata = dict(sidecar_tag.lifecycle or {})
    action = _metadata_action_for_tag(sidecar_tag)
    if action is None:
        return
    session.add(
        TagLifecycleMetadata(
            action=action,
            old_slug=sidecar_tag.slug,
            old_display_name=sidecar_tag.name,
            old_category_slug=sidecar_tag.category_slug,
            new_slug=sidecar_tag.slug,
            new_display_name=sidecar_tag.name,
            new_category_slug=sidecar_tag.category_slug,
            metadata_json=_metadata_json(metadata),
        )
    )


def _metadata_action_for_tag(sidecar_tag) -> str | None:
    if sidecar_tag.status == TAG_STATUS_ACTIVE:
        return TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY
    if sidecar_tag.status == TAG_STATUS_HIDDEN:
        return TAG_LIFECYCLE_METADATA_HIDE
    if sidecar_tag.status != TAG_STATUS_ARCHIVED:
        return None
    origin = (sidecar_tag.lifecycle or {}).get("archive_origin")
    if origin == ARCHIVE_ORIGIN_DELETED:
        return TAG_LIFECYCLE_METADATA_ARCHIVE
    if origin == ARCHIVE_ORIGIN_IMPORTED or origin is None:
        return TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED
    return TAG_LIFECYCLE_METADATA_ARCHIVE


def _is_imported_archived_tag(session, tag: Tag) -> bool:
    metadata = _current_metadata_by_slug(session).get(tag.slug, {})
    archive_origin = metadata.get("archive_origin")
    if archive_origin is None and tag.category_id is None:
        archive_origin = ARCHIVE_ORIGIN_IMPORTED
    return archive_origin == ARCHIVE_ORIGIN_IMPORTED


def _alias_exists(session, alias) -> bool:
    metadata_json = _metadata_json(alias.metadata)
    return (
        session.query(TagLifecycleMetadata)
        .filter_by(
            action=alias.action,
            old_slug=alias.old_slug,
            new_slug=alias.new_slug,
            metadata_json=metadata_json,
        )
        .first()
        is not None
    )


def _metadata_json(metadata: dict) -> str:
    return json.dumps(metadata or {}, sort_keys=True, separators=(",", ":"))


def _import_success_message(result: RegistrySidecarImportResult) -> str:
    changed = (
        len(result.categories_created)
        + len(result.tags_created)
        + len(result.tags_promoted)
        + len(result.aliases_imported)
        + len(result.characters_created)
        + len(result.character_mappings_imported)
        + len(result.system_prompts_created)
    )
    if changed == 0:
        return "Registry sidecar already matches the current registry."
    return (
        "Imported registry sidecar: "
        f"{count_phrase(len(result.categories_created), 'category', 'categories')}, "
        f"{count_phrase(len(result.tags_created), 'tag')}, "
        f"{count_phrase(len(result.tags_promoted), 'promoted tag')}, "
        f"{count_phrase(len(result.aliases_imported), 'alias', 'aliases')}, "
        f"{count_phrase(len(result.characters_created), 'character')}, "
        f"{count_phrase(len(result.character_mappings_imported), 'entry mapping')}, "
        f"{count_phrase(len(result.system_prompts_created), 'system prompt template')}."
    )

