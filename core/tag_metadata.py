"""Tag lifecycle metadata helpers."""
import json

from core.db import SessionLocal
from core.models import TagLifecycleMetadata
from core.tag_constants import (
    ACTIVATION_ORIGIN_IMPORTED_ASSIGNMENT,
    ARCHIVE_BADGE_DELETED,
    ARCHIVE_BADGE_IMPORTED,
    ARCHIVE_ORIGIN_DELETED,
    ARCHIVE_ORIGIN_IMPORTED,
    ARCHIVE_REASON_UNKNOWN_IMPORT,
    ARCHIVE_REASON_USER_SOFT_DELETE,
    HIDE_REASON_HIDDEN_FROM_ARCHIVE,
    LIFECYCLE_STATE_ACTIVE,
    LIFECYCLE_STATE_ARCHIVED,
    LIFECYCLE_STATE_HIDDEN,
    RESOLVER_BEHAVIOR_MAP_TO_TARGET,
    TAG_ALIAS_METADATA_ACTIONS,
    TAG_CURRENT_METADATA_ACTIONS,
    TAG_LIFECYCLE_METADATA_MERGE,
    TAG_LIFECYCLE_METADATA_RENAME,
)
from core.tag_normalization import normalize_tag


def _metadata_json(metadata: dict) -> str:
    """Serialize lifecycle metadata compactly and consistently."""
    return json.dumps(metadata, sort_keys=True, separators=(",", ":"))


def build_imported_archive_metadata() -> dict:
    """Return current metadata for an imported archived tag."""
    return {
        "lifecycle_state": LIFECYCLE_STATE_ARCHIVED,
        "archive_origin": ARCHIVE_ORIGIN_IMPORTED,
        "archive_reason": ARCHIVE_REASON_UNKNOWN_IMPORT,
        "visible_badge": ARCHIVE_BADGE_IMPORTED,
    }


def build_active_assigned_metadata(assigned_category_slug: str) -> dict:
    """Return current metadata for an imported tag assigned to a category."""
    return {
        "lifecycle_state": LIFECYCLE_STATE_ACTIVE,
        "activation_origin": ACTIVATION_ORIGIN_IMPORTED_ASSIGNMENT,
        "assigned_category_slug": assigned_category_slug,
        "visible_badge": None,
    }


def build_deleted_archive_metadata(previous_category_slug: str) -> dict:
    """Return current metadata for a soft-deleted archived tag."""
    return {
        "lifecycle_state": LIFECYCLE_STATE_ARCHIVED,
        "archive_origin": ARCHIVE_ORIGIN_DELETED,
        "archive_reason": ARCHIVE_REASON_USER_SOFT_DELETE,
        "previous_category_slug": previous_category_slug,
        "visible_badge": ARCHIVE_BADGE_DELETED,
    }


def build_hidden_metadata() -> dict:
    """Return current metadata for a hidden history-only tag."""
    return {
        "lifecycle_state": LIFECYCLE_STATE_HIDDEN,
        "hide_reason": HIDE_REASON_HIDDEN_FROM_ARCHIVE,
        "visible_badge": None,
    }


def build_rename_alias_metadata(
    old_slug: str | None = None,
    new_slug: str | None = None,
) -> dict:
    """Return resolver metadata for a hidden rename alias."""
    metadata = {
        "lifecycle_state": LIFECYCLE_STATE_HIDDEN,
        "alias_type": TAG_LIFECYCLE_METADATA_RENAME,
        "resolver_behavior": RESOLVER_BEHAVIOR_MAP_TO_TARGET,
    }
    if old_slug is not None:
        metadata["old_slug"] = normalize_tag(old_slug).slug
    if new_slug is not None:
        metadata["new_slug"] = normalize_tag(new_slug).slug
    return metadata


def build_merge_alias_metadata() -> dict:
    """Return resolver metadata for a hidden merge alias."""
    return {
        "lifecycle_state": LIFECYCLE_STATE_HIDDEN,
        "alias_type": TAG_LIFECYCLE_METADATA_MERGE,
        "resolver_behavior": RESOLVER_BEHAVIOR_MAP_TO_TARGET,
    }


def upsert_tag_lifecycle_metadata(
    *,
    action: str,
    old_slug: str,
    old_display_name: str | None = None,
    old_category_slug: str | None = None,
    new_slug: str | None = None,
    new_display_name: str | None = None,
    new_category_slug: str | None = None,
    metadata: dict | None = None,
    session=None,
) -> TagLifecycleMetadata:
    """Create or replace the current lifecycle metadata row for a slug."""
    normalized_old = normalize_tag(old_slug).slug
    if not normalized_old:
        raise ValueError("Lifecycle metadata requires a valid old_slug.")

    own_session = session is None
    active_session = session or SessionLocal()
    try:
        history = None
        if action not in TAG_ALIAS_METADATA_ACTIONS:
            history = (
                active_session.query(TagLifecycleMetadata)
                .filter(
                    TagLifecycleMetadata.old_slug == normalized_old,
                    TagLifecycleMetadata.action.in_(TAG_CURRENT_METADATA_ACTIONS),
                )
                .order_by(TagLifecycleMetadata.id.desc())
                .first()
            )
        if history is None:
            history = TagLifecycleMetadata(old_slug=normalized_old)
            active_session.add(history)

        history.action = action
        history.old_display_name = old_display_name
        history.old_category_slug = old_category_slug
        history.new_slug = normalize_tag(new_slug).slug if new_slug else None
        history.new_display_name = new_display_name
        history.new_category_slug = new_category_slug
        history.metadata_json = _metadata_json(metadata or {})

        if own_session:
            active_session.commit()
            active_session.refresh(history)
        else:
            active_session.flush()
        return history
    except Exception:
        if own_session:
            active_session.rollback()
        raise
    finally:
        if own_session:
            active_session.close()


def get_current_tag_lifecycle_metadata(slug: str) -> dict:
    """Return the current lifecycle metadata for a tag slug."""
    normalized = normalize_tag(slug).slug
    if not normalized:
        return {}

    session = SessionLocal()
    try:
        history = (
            session.query(TagLifecycleMetadata)
            .filter(
                TagLifecycleMetadata.old_slug == normalized,
                TagLifecycleMetadata.action.in_(TAG_CURRENT_METADATA_ACTIONS),
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
    finally:
        session.close()


def clear_or_replace_tag_lifecycle_metadata(
    *,
    action: str,
    old_slug: str,
    metadata: dict,
    old_display_name: str | None = None,
    old_category_slug: str | None = None,
    new_slug: str | None = None,
    new_display_name: str | None = None,
    new_category_slug: str | None = None,
    session=None,
) -> TagLifecycleMetadata:
    """Replace the current lifecycle metadata for a slug."""
    return upsert_tag_lifecycle_metadata(
        action=action,
        old_slug=old_slug,
        old_display_name=old_display_name,
        old_category_slug=old_category_slug,
        new_slug=new_slug,
        new_display_name=new_display_name,
        new_category_slug=new_category_slug,
        metadata=metadata,
        session=session,
    )


def clear_current_tag_lifecycle_metadata(slug: str, session=None) -> None:
    """Remove current-state lifecycle metadata for a slug, preserving aliases."""
    normalized = normalize_tag(slug).slug
    if not normalized:
        return

    own_session = session is None
    active_session = session or SessionLocal()
    try:
        (
            active_session.query(TagLifecycleMetadata)
            .filter(
                TagLifecycleMetadata.old_slug == normalized,
                TagLifecycleMetadata.action.in_(TAG_CURRENT_METADATA_ACTIONS),
            )
            .delete(synchronize_session=False)
        )
        if own_session:
            active_session.commit()
    except Exception:
        if own_session:
            active_session.rollback()
        raise
    finally:
        if own_session:
            active_session.close()


def archive_metadata_for_tag(tag: dict) -> dict:
    """Return visible archive metadata for one lifecycle tag dict."""
    default = {
        "archive_origin": ARCHIVE_ORIGIN_IMPORTED
        if tag.get("category_id") is None
        else ARCHIVE_ORIGIN_DELETED,
        "archive_reason": ARCHIVE_REASON_UNKNOWN_IMPORT
        if tag.get("category_id") is None
        else ARCHIVE_REASON_USER_SOFT_DELETE,
        "visible_badge": ARCHIVE_BADGE_IMPORTED
        if tag.get("category_id") is None
        else ARCHIVE_BADGE_DELETED,
    }
    return {**default, **get_current_tag_lifecycle_metadata(tag.get("slug", ""))}


def parse_metadata_json(metadata_json: str | None) -> dict:
    """Return lifecycle metadata dict from stored JSON."""
    if not metadata_json:
        return {}
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def current_metadata_by_slug(session, slugs: list[str]) -> dict[str, dict]:
    """Return latest current-state lifecycle metadata for each slug."""
    if not slugs:
        return {}

    rows = (
        session.query(TagLifecycleMetadata)
        .filter(
            TagLifecycleMetadata.old_slug.in_(slugs),
            TagLifecycleMetadata.action.in_(TAG_CURRENT_METADATA_ACTIONS),
        )
        .order_by(TagLifecycleMetadata.id.desc())
        .all()
    )

    metadata_by_slug: dict[str, dict] = {}
    for row in rows:
        if row.old_slug in metadata_by_slug:
            continue
        metadata_by_slug[row.old_slug] = parse_metadata_json(row.metadata_json)
    return metadata_by_slug


def archive_metadata_for_tag_dict(tag: dict, metadata_by_slug: dict[str, dict]) -> dict:
    """Return visible archive metadata for one lifecycle tag dict."""
    default = {
        "archive_origin": ARCHIVE_ORIGIN_IMPORTED
        if tag.get("category_id") is None
        else ARCHIVE_ORIGIN_DELETED,
        "archive_reason": ARCHIVE_REASON_UNKNOWN_IMPORT
        if tag.get("category_id") is None
        else ARCHIVE_REASON_USER_SOFT_DELETE,
        "visible_badge": ARCHIVE_BADGE_IMPORTED
        if tag.get("category_id") is None
        else ARCHIVE_BADGE_DELETED,
    }
    return {**default, **metadata_by_slug.get(tag.get("slug", ""), {})}
