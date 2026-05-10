"""Framework-independent tag lifecycle mutation services."""
from dataclasses import dataclass, field
import copy
import json
from pathlib import Path

from core.backups import create_dataset_backup
from core.dataset import get_entry_tags, normalize_dataset_tags, save_dataset, set_entry_tags
import core.tag_registry as tag_registry
from core.models import (
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    Tag,
    TagCategory,
    TagLifecycleMetadata,
)
from core.tag_normalization import normalize_tag


@dataclass
class TagLifecycleOperationResult:
    """Structured result returned by tag lifecycle services."""

    ok: bool
    message: str
    errors: list[str] = field(default_factory=list)
    affected_count: int = 0
    tag_slugs: list[str] = field(default_factory=list)
    category_slug: str | None = None
    db_backup_path: str | None = None
    dataset_backup_path: str | None = None
    entries: list[dict] | None = None
    old_slug: str | None = None
    new_slug: str | None = None
    old_display_name: str | None = None
    new_display_name: str | None = None


def _normalized_unique_slugs(tag_slugs: list[str]) -> tuple[list[str], list[str]]:
    normalized_slugs: list[str] = []
    errors: list[str] = []
    seen: set[str] = set()

    for raw_slug in tag_slugs:
        normalized = normalize_tag(raw_slug)
        if not normalized.slug:
            errors.append("Selected tags include an invalid tag slug.")
            continue
        if normalized.slug not in seen:
            seen.add(normalized.slug)
            normalized_slugs.append(normalized.slug)

    if not normalized_slugs:
        errors.append("No archived tags selected.")
    return normalized_slugs, errors


def _current_metadata(session, slug: str) -> dict:
    history = (
        session.query(TagLifecycleMetadata)
        .filter(
            TagLifecycleMetadata.old_slug == slug,
            TagLifecycleMetadata.action.in_(tag_registry.TAG_CURRENT_METADATA_ACTIONS),
        )
        .order_by(TagLifecycleMetadata.id.desc())
        .first()
    )
    if history is None or not history.metadata_json:
        return {}
    try:
        metadata = json.loads(history.metadata_json)
    except json.JSONDecodeError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _is_imported_archived_tag(session, tag: Tag) -> bool:
    metadata = _current_metadata(session, tag.slug)
    archive_origin = metadata.get("archive_origin")
    if archive_origin is None and tag.category_id is None:
        archive_origin = tag_registry.ARCHIVE_ORIGIN_IMPORTED
    return archive_origin == tag_registry.ARCHIVE_ORIGIN_IMPORTED


def _tag_label(tag: Tag | None, slug: str) -> str:
    """Return a user-facing tag label for service messages."""
    return tag.name if tag is not None else tag_registry.prettify_tag_name(slug)


def _validate_dataset_path(dataset_path: str) -> list[str]:
    if not dataset_path:
        return ["No dataset loaded. Please load or create a dataset before saving."]
    if not Path(dataset_path).is_file():
        return ["Dataset file was not found."]
    return []


def _rewrite_entry_tag_slug(
    entries: list[dict],
    *,
    old_slug: str,
    new_slug: str,
) -> tuple[list[dict], int]:
    """Return entries with one canonical tag slug replaced and deduplicated."""
    proposed_entries = copy.deepcopy(entries)
    changed_entries = 0

    for entry in proposed_entries:
        if not isinstance(entry, dict):
            continue
        tags = get_entry_tags(entry)
        if old_slug not in tags:
            continue
        changed_entries += 1
        rewritten_tags = [new_slug if tag == old_slug else tag for tag in tags]
        set_entry_tags(entry, rewritten_tags)

    normalized = normalize_dataset_tags(proposed_entries).entries
    return normalized, changed_entries


def _alias_slug_is_reserved(session, slug: str, *, old_slug: str) -> bool:
    """Return True when slug is already an alias key for another lifecycle map."""
    if slug == old_slug:
        return False
    return (
        session.query(TagLifecycleMetadata)
        .filter(
            TagLifecycleMetadata.old_slug == slug,
            TagLifecycleMetadata.action.in_(tag_registry.TAG_ALIAS_METADATA_ACTIONS),
        )
        .first()
        is not None
    )


def assign_archived_imported_tags_to_category(
    *,
    tag_slugs: list[str],
    category_slug: str,
) -> TagLifecycleOperationResult:
    """Activate archived/imported tags under an active category."""
    normalized_tag_slugs, errors = _normalized_unique_slugs(tag_slugs)
    normalized_category = normalize_tag(category_slug).slug
    if not normalized_category:
        errors.append("Selected category does not exist or is inactive.")

    if errors:
        return TagLifecycleOperationResult(
            ok=False,
            message="Could not assign archived tags.",
            errors=errors,
            tag_slugs=normalized_tag_slugs,
            category_slug=normalized_category or None,
        )

    session = tag_registry.SessionLocal()
    try:
        category = (
            session.query(TagCategory)
            .filter_by(slug=normalized_category, is_active=True)
            .first()
        )
        if category is None:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not assign archived tags.",
                errors=["Selected category does not exist or is inactive."],
                tag_slugs=normalized_tag_slugs,
                category_slug=normalized_category,
            )

        tags: list[Tag] = []
        validation_errors: list[str] = []
        for slug in normalized_tag_slugs:
            tag = session.query(Tag).filter_by(slug=slug).order_by(Tag.id).first()
            if tag is None:
                validation_errors.append(f"Tag not found: {_tag_label(None, slug)}")
                continue
            tag_label = _tag_label(tag, slug)

            conflicting_active = (
                session.query(Tag)
                .join(TagCategory, Tag.category_id == TagCategory.id)
                .filter(
                    Tag.slug == slug,
                    Tag.id != tag.id,
                    Tag.status == TAG_STATUS_ACTIVE,
                    Tag.is_active.is_(True),
                    TagCategory.is_active.is_(True),
                )
                .first()
            )
            if conflicting_active is not None:
                validation_errors.append(
                    f"An active tag already exists for: {tag_label}"
                )
                continue

            if tag.status != TAG_STATUS_ARCHIVED:
                validation_errors.append(f"Tag is not archived: {tag_label}")
                continue
            if not _is_imported_archived_tag(session, tag):
                validation_errors.append(
                    f"Tag is not an imported archived tag: {tag_label}"
                )
                continue

            tags.append(tag)

        if validation_errors:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not assign archived tags.",
                errors=validation_errors,
                tag_slugs=normalized_tag_slugs,
                category_slug=normalized_category,
            )

        try:
            db_backup_path = tag_registry.create_db_backup(engine=tag_registry.engine)
        except Exception as exc:
            return TagLifecycleOperationResult(
                ok=False,
                message=f"Could not create database backup: {exc}",
                tag_slugs=normalized_tag_slugs,
                category_slug=normalized_category,
            )

        max_order = (
            session.query(Tag)
            .filter_by(category_id=category.id)
            .order_by(Tag.sort_order.desc())
            .first()
        )
        next_sort_order = (max_order.sort_order if max_order is not None else 0) + 1

        for offset, tag in enumerate(tags):
            tag.status = TAG_STATUS_ACTIVE
            tag.is_active = True
            tag.category_id = category.id
            tag.sort_order = next_sort_order + offset
            tag_registry.clear_or_replace_tag_lifecycle_metadata(
                action=tag_registry.TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
                old_slug=tag.slug,
                old_display_name=tag.name,
                old_category_slug=None,
                new_slug=tag.slug,
                new_display_name=tag.name,
                new_category_slug=category.slug,
                metadata=tag_registry.build_active_assigned_metadata(category.slug),
                session=session,
            )

        session.commit()
        return TagLifecycleOperationResult(
            ok=True,
            message=f"Assigned {len(tags)} archived tag(s) to {category.name}.",
            affected_count=len(tags),
            tag_slugs=[tag.slug for tag in tags],
            category_slug=category.slug,
            db_backup_path=str(Path(db_backup_path)),
        )
    except Exception as exc:
        session.rollback()
        return TagLifecycleOperationResult(
            ok=False,
            message=f"Database error: {exc}",
            tag_slugs=normalized_tag_slugs,
            category_slug=normalized_category,
        )
    finally:
        session.close()


def assign_archived_imported_tag_to_category(
    *,
    tag_slug: str,
    category_slug: str,
) -> TagLifecycleOperationResult:
    """Activate one archived/imported tag under an active category."""
    return assign_archived_imported_tags_to_category(
        tag_slugs=[tag_slug],
        category_slug=category_slug,
    )


def rename_active_tag(
    *,
    old_slug: str,
    new_display_name: str,
    dataset_path: str,
    entries: list[dict],
) -> TagLifecycleOperationResult:
    """Rename one custom active tag and rewrite loaded dataset entries."""
    normalized_old = normalize_tag(old_slug).slug
    normalized_new = normalize_tag(new_display_name)
    errors = _validate_dataset_path(dataset_path)

    if not normalized_old:
        errors.append("Selected tag is invalid.")
    if not normalized_new.slug:
        errors.append("Tag name cannot be empty.")
    if not isinstance(entries, list):
        errors.append("Loaded entries must be a list.")

    if errors:
        return TagLifecycleOperationResult(
            ok=False,
            message="Could not rename tag.",
            errors=errors,
            old_slug=normalized_old or None,
            new_slug=normalized_new.slug or None,
            new_display_name=normalized_new.display_name or None,
        )

    session = tag_registry.SessionLocal()
    try:
        tag = session.query(Tag).filter_by(slug=normalized_old).order_by(Tag.id).first()
        if tag is None:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not rename tag.",
                errors=[f"Tag not found: {tag_registry.prettify_tag_name(normalized_old)}"],
                old_slug=normalized_old,
                new_slug=normalized_new.slug,
                new_display_name=normalized_new.display_name,
            )

        old_display_name = tag.name
        category = tag.category
        validation_errors: list[str] = []
        if tag.status != TAG_STATUS_ACTIVE or not tag.is_active or category is None or not category.is_active:
            validation_errors.append(f"Tag is not an active custom tag: {old_display_name}")
        if tag.is_builtin:
            validation_errors.append(f"Built-in tags cannot be renamed: {old_display_name}")

        if normalized_new.slug == tag.slug:
            return TagLifecycleOperationResult(
                ok=True,
                message="Rename canceled; tag name is unchanged.",
                affected_count=0,
                tag_slugs=[tag.slug],
                category_slug=category.slug if category is not None else None,
                entries=copy.deepcopy(entries),
                old_slug=tag.slug,
                new_slug=tag.slug,
                old_display_name=old_display_name,
                new_display_name=tag.name,
            )

        conflicting_tag = (
            session.query(Tag)
            .filter(Tag.slug == normalized_new.slug, Tag.id != tag.id)
            .order_by(Tag.id)
            .first()
        )
        if conflicting_tag is not None:
            validation_errors.append(
                f"A tag named {conflicting_tag.name} already exists."
            )
        if _alias_slug_is_reserved(session, normalized_new.slug, old_slug=tag.slug):
            validation_errors.append(
                f"Canonical ID is reserved by lifecycle metadata: {normalized_new.display_name}"
            )

        if validation_errors:
            return TagLifecycleOperationResult(
                ok=False,
                message="Could not rename tag.",
                errors=validation_errors,
                old_slug=tag.slug,
                new_slug=normalized_new.slug,
                old_display_name=old_display_name,
                new_display_name=normalized_new.display_name,
            )

        proposed_entries, changed_entries = _rewrite_entry_tag_slug(
            entries,
            old_slug=tag.slug,
            new_slug=normalized_new.slug,
        )

        try:
            dataset_backup = create_dataset_backup(dataset_path, "before_tag_rename")
            if dataset_backup is None:
                raise FileNotFoundError(
                    "Could not create dataset backup because the dataset file was not found."
                )
        except Exception as exc:
            return TagLifecycleOperationResult(
                ok=False,
                message=f"Failed to create dataset backup: {exc}",
                old_slug=tag.slug,
                new_slug=normalized_new.slug,
                old_display_name=old_display_name,
                new_display_name=normalized_new.display_name,
            )

        try:
            db_backup = tag_registry.create_db_backup(engine=tag_registry.engine)
        except Exception as exc:
            return TagLifecycleOperationResult(
                ok=False,
                message=f"Could not create database backup: {exc}",
                dataset_backup_path=str(Path(dataset_backup)),
                old_slug=tag.slug,
                new_slug=normalized_new.slug,
                old_display_name=old_display_name,
                new_display_name=normalized_new.display_name,
            )

        category_slug = category.slug
        tag.slug = normalized_new.slug
        tag.name = normalized_new.display_name
        tag.status = TAG_STATUS_ACTIVE
        tag.is_active = True

        tag_registry.clear_current_tag_lifecycle_metadata(normalized_old, session=session)
        tag_registry.clear_or_replace_tag_lifecycle_metadata(
            action=tag_registry.TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
            old_slug=normalized_new.slug,
            old_display_name=normalized_new.display_name,
            old_category_slug=category_slug,
            new_slug=normalized_new.slug,
            new_display_name=normalized_new.display_name,
            new_category_slug=category_slug,
            metadata={
                "lifecycle_state": tag_registry.LIFECYCLE_STATE_ACTIVE,
                "activation_origin": "tag_rename",
                "assigned_category_slug": category_slug,
                "visible_badge": None,
            },
            session=session,
        )
        tag_registry.upsert_tag_lifecycle_metadata(
            action=tag_registry.TAG_LIFECYCLE_METADATA_RENAME,
            old_slug=normalized_old,
            old_display_name=old_display_name,
            old_category_slug=category_slug,
            new_slug=normalized_new.slug,
            new_display_name=normalized_new.display_name,
            new_category_slug=category_slug,
            metadata=tag_registry.build_rename_alias_metadata(
                old_slug=normalized_old,
                new_slug=normalized_new.slug,
            ),
            session=session,
        )

        try:
            save_dataset(dataset_path, proposed_entries)
        except Exception as exc:
            session.rollback()
            return TagLifecycleOperationResult(
                ok=False,
                message=f"Failed to save dataset: {exc}",
                dataset_backup_path=str(Path(dataset_backup)),
                db_backup_path=str(Path(db_backup)),
                old_slug=normalized_old,
                new_slug=normalized_new.slug,
                old_display_name=old_display_name,
                new_display_name=normalized_new.display_name,
            )

        session.commit()
        return TagLifecycleOperationResult(
            ok=True,
            message=(
                f'Renamed tag "{old_display_name}" to '
                f'"{normalized_new.display_name}".'
            ),
            affected_count=changed_entries,
            tag_slugs=[normalized_new.slug],
            category_slug=category_slug,
            db_backup_path=str(Path(db_backup)),
            dataset_backup_path=str(Path(dataset_backup)),
            entries=proposed_entries,
            old_slug=normalized_old,
            new_slug=normalized_new.slug,
            old_display_name=old_display_name,
            new_display_name=normalized_new.display_name,
        )
    except Exception as exc:
        session.rollback()
        return TagLifecycleOperationResult(
            ok=False,
            message=f"Database error: {exc}",
            old_slug=normalized_old,
            new_slug=normalized_new.slug,
            new_display_name=normalized_new.display_name,
        )
    finally:
        session.close()
