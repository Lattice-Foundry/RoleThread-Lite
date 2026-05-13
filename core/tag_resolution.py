"""Tag lifecycle resolver and alias mapping logic."""
from core.db import SessionLocal
from core.models import Tag, TagCategory, TagLifecycleMetadata
from core.tag_constants import (
    TAG_LIFECYCLE_METADATA_ARCHIVE,
    TAG_LIFECYCLE_METADATA_DELETE,
    TAG_LIFECYCLE_METADATA_HIDE,
    TAG_LIFECYCLE_METADATA_MERGE,
    TAG_LIFECYCLE_METADATA_RENAME,
    TAG_RESOLUTION_ACTIVE,
    TAG_RESOLUTION_ALIAS_MAPPED,
    TAG_RESOLUTION_ARCHIVED,
    TAG_RESOLUTION_HIDDEN,
    TAG_RESOLUTION_RETIRED,
    TAG_RESOLUTION_UNKNOWN,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
    TAG_STATUS_UNCATEGORIZED,
    TagResolutionResult,
)
from core.tag_normalization import normalize_tag


def _get_active_tag(session, slug: str) -> Tag | None:
    """Return an active tag only when it belongs to an active category."""
    return (
        session.query(Tag)
        .join(TagCategory, Tag.category_id == TagCategory.id)
        .filter(
            Tag.slug == slug,
            Tag.status == TAG_STATUS_ACTIVE,
            Tag.is_active.is_(True),
            TagCategory.is_active.is_(True),
        )
        .first()
    )


def _resolve_alias_mapping(session, slug: str) -> tuple[str, str] | None:
    """Follow rename/merge history to an active target slug."""
    seen: set[str] = set()
    current_slug = slug

    for _ in range(20):
        if current_slug in seen:
            return None
        seen.add(current_slug)

        history = (
            session.query(TagLifecycleMetadata)
            .filter(
                TagLifecycleMetadata.old_slug == current_slug,
                TagLifecycleMetadata.action.in_([TAG_LIFECYCLE_METADATA_RENAME, TAG_LIFECYCLE_METADATA_MERGE]),
                TagLifecycleMetadata.new_slug.isnot(None),
                TagLifecycleMetadata.new_slug != "",
            )
            .order_by(TagLifecycleMetadata.id.desc())
            .first()
        )
        if history is None:
            return None

        target_slug = normalize_tag(history.new_slug).slug
        if not target_slug:
            return None
        if _get_active_tag(session, target_slug) is not None:
            return target_slug, history.action
        current_slug = target_slug

    return None


def _has_retired_history(session, slug: str) -> bool:
    """Return True when history says a slug should not be recreated."""
    retired_actions = [TAG_LIFECYCLE_METADATA_ARCHIVE, TAG_LIFECYCLE_METADATA_HIDE, TAG_LIFECYCLE_METADATA_DELETE]
    histories = (
        session.query(TagLifecycleMetadata)
        .filter(
            TagLifecycleMetadata.old_slug == slug,
            TagLifecycleMetadata.action.in_(retired_actions),
        )
        .order_by(TagLifecycleMetadata.id.desc())
        .all()
    )
    for history in histories:
        target_slug = normalize_tag(history.new_slug).slug if history.new_slug else ""
        if not target_slug or _get_active_tag(session, target_slug) is None:
            return True
    return False


def resolve_tag_lifecycle(raw_tag: str) -> TagResolutionResult:
    """Resolve an imported tag against active tags, lifecycle rows, and history."""
    normalized = normalize_tag(raw_tag)
    if not normalized.slug:
        return TagResolutionResult(
            raw=normalized.raw,
            normalized_slug="",
            normalized_display_name="",
            resolved_slug="",
            result_type=TAG_RESOLUTION_UNKNOWN,
            should_skip_creation=True,
            reason="invalid_tag",
        )

    session = SessionLocal()
    try:
        active_tag = _get_active_tag(session, normalized.slug)
        if active_tag is not None:
            return TagResolutionResult(
                raw=normalized.raw,
                normalized_slug=normalized.slug,
                normalized_display_name=normalized.display_name,
                resolved_slug=normalized.slug,
                result_type=TAG_RESOLUTION_ACTIVE,
                reason="active_tag",
            )

        alias = _resolve_alias_mapping(session, normalized.slug)
        if alias is not None:
            target_slug, action = alias
            return TagResolutionResult(
                raw=normalized.raw,
                normalized_slug=normalized.slug,
                normalized_display_name=normalized.display_name,
                resolved_slug=target_slug,
                result_type=TAG_RESOLUTION_ALIAS_MAPPED,
                should_rewrite_slug=target_slug != normalized.slug,
                target_slug=target_slug,
                reason=action,
            )

        existing_tag = (
            session.query(Tag)
            .filter_by(slug=normalized.slug)
            .order_by(Tag.id)
            .first()
        )
        if existing_tag is not None:
            status_to_result = {
                TAG_STATUS_UNCATEGORIZED: TAG_RESOLUTION_ARCHIVED,
                TAG_STATUS_ARCHIVED: TAG_RESOLUTION_ARCHIVED,
                TAG_STATUS_HIDDEN: TAG_RESOLUTION_HIDDEN,
            }
            result_type = status_to_result.get(existing_tag.status)
            if result_type is not None:
                return TagResolutionResult(
                    raw=normalized.raw,
                    normalized_slug=normalized.slug,
                    normalized_display_name=normalized.display_name,
                    resolved_slug=normalized.slug,
                    result_type=result_type,
                    should_skip_creation=True,
                    reason=f"existing_{existing_tag.status}",
                )

        if _has_retired_history(session, normalized.slug):
            return TagResolutionResult(
                raw=normalized.raw,
                normalized_slug=normalized.slug,
                normalized_display_name=normalized.display_name,
                resolved_slug=normalized.slug,
                result_type=TAG_RESOLUTION_RETIRED,
                should_skip_creation=True,
                reason="retired_history",
            )

        return TagResolutionResult(
            raw=normalized.raw,
            normalized_slug=normalized.slug,
            normalized_display_name=normalized.display_name,
            resolved_slug=normalized.slug,
            result_type=TAG_RESOLUTION_UNKNOWN,
            should_create_archived=True,
            reason="unknown_tag",
        )
    finally:
        session.close()
