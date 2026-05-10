"""Framework-independent tag lifecycle mutation services."""
from dataclasses import dataclass, field
import json
from pathlib import Path

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
