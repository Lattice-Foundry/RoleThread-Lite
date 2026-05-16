"""DB-backed tag registry helpers.

JSONL entries store tag slugs; this module owns slug/display conversion,
registry seeding, lookup helpers, and additive custom tag writes.
"""
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from core.dataset import TAGS, get_used_tags
from core.db import SessionLocal, engine, init_db
from core.db_backups import create_db_backup
from core.tag_migrations import (
    _deactivate_empty_unsorted_category,
    _migrate_legacy_source_status_category,
    _migrate_tag_history_table,
    _migrate_tag_lifecycle_schema,
    _migrate_tags_slug_column,
)
from core.tag_constants import (
    ARCHIVE_BADGE_DELETED,
    ARCHIVE_BADGE_IMPORTED,
    ARCHIVE_ORIGIN_DELETED,
    ARCHIVE_ORIGIN_IMPORTED,
    ARCHIVE_REASON_UNKNOWN_IMPORT,
    ARCHIVE_REASON_USER_SOFT_DELETE,
    MAX_ACTIVE_CATEGORIES,
    TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
    TAG_LIFECYCLE_METADATA_IMPORT_UNCATEGORIZED,
    TAG_RESOLUTION_ARCHIVED,
    TAG_RESOLUTION_UNKNOWN,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
    TAG_STATUS_UNCATEGORIZED,
    TagResolutionResult,
)
from core.models import Tag, TagCategory
from core.tag_metadata import (
    archive_metadata_for_tag,
    archive_metadata_for_tag_dict,
    build_active_assigned_metadata,
    build_deleted_archive_metadata,
    build_imported_archive_metadata,
    build_rename_alias_metadata,
    clear_current_tag_lifecycle_metadata,
    clear_or_replace_tag_lifecycle_metadata,
    current_metadata_by_slug,
    get_current_tag_lifecycle_metadata,
    upsert_tag_lifecycle_metadata,
)
from core.tag_normalization import normalize_tag
from core.tag_resolution import resolve_tag_lifecycle


@dataclass
class TagAdoptionSummary:
    """Result of adopting dataset tags into the registry."""

    created_count: int = 0
    created_slugs: list[str] = field(default_factory=list)


@dataclass
class ArchivedTagImportSummary:
    """Result of ensuring imported tags exist as archived records."""

    created_count: int = 0
    created_slugs: list[str] = field(default_factory=list)
    existing_slugs: list[str] = field(default_factory=list)
    skipped_slugs: list[str] = field(default_factory=list)


# ── Slug helper ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TagRegistrySnapshot:
    """Point-in-time read model for UI tag registry rendering."""

    active_registry: dict[str, list[str]]
    active_categories: list[dict]
    active_tag_slugs: list[str]
    active_tag_slug_set: set[str]
    tag_label_map: dict[str, str]
    tag_label_map_with_untagged: dict[str, str]
    tag_category_map: dict[str, str]
    visible_archived_tags: list[dict]
    default_category_slugs: set[str]
    max_active_categories: int


def slugify_tag_name(name: str) -> str:
    """Convert a display name to a lowercase_snake_case slug."""
    return normalize_tag(name).slug


# ── Display-name helper ────────────────────────────────────────────────────────

def prettify_tag_name(slug: str) -> str:
    """Convert a tag slug to a display label."""
    return normalize_tag(slug).display_name



def _query_active_tags(session):
    """Return a query for active tags with active category membership."""
    return (
        session.query(Tag)
        .join(TagCategory, Tag.category_id == TagCategory.id)
        .filter(
            Tag.status == TAG_STATUS_ACTIVE,
            Tag.is_active.is_(True),
            Tag.category_id.isnot(None),
            TagCategory.is_active.is_(True),
        )
    )


def ensure_archived_import_tag(raw_tag: str) -> TagResolutionResult:
    """Create an archived/imported tag for a truly unknown imported tag."""
    resolution = resolve_tag_lifecycle(raw_tag)
    if not resolution.should_create_archived or not resolution.normalized_slug:
        return resolution

    create_db_backup(engine=engine)
    return _create_archived_import_tag_from_resolution(resolution)


def _create_archived_import_tag_from_resolution(
    resolution: TagResolutionResult,
) -> TagResolutionResult:
    """Create an archived/imported tag after caller-owned backup handling."""
    if not resolution.should_create_archived or not resolution.normalized_slug:
        return resolution

    session = SessionLocal()
    try:
        existing_tag = (
            session.query(Tag)
            .filter_by(slug=resolution.normalized_slug)
            .order_by(Tag.id)
            .first()
        )
        if existing_tag is not None:
            return TagResolutionResult(
                raw=resolution.raw,
                normalized_slug=resolution.normalized_slug,
                normalized_display_name=resolution.normalized_display_name,
                resolved_slug=resolution.resolved_slug,
                result_type=resolution.result_type,
                should_rewrite_slug=resolution.should_rewrite_slug,
                should_create_archived=False,
                should_skip_creation=True,
                target_slug=resolution.target_slug,
                reason=f"existing_{existing_tag.status}",
            )

        tag = Tag(
            category_id=None,
            name=resolution.normalized_display_name,
            slug=resolution.normalized_slug,
            sort_order=0,
            is_active=False,
            is_builtin=False,
            status=TAG_STATUS_ARCHIVED,
        )
        session.add(tag)
        upsert_tag_lifecycle_metadata(
            action=TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
            old_slug=resolution.normalized_slug,
            old_display_name=resolution.normalized_display_name,
            old_category_slug=None,
            new_slug=resolution.normalized_slug,
            new_display_name=resolution.normalized_display_name,
            new_category_slug=None,
            metadata=build_imported_archive_metadata(),
            session=session,
        )
        session.commit()
        return TagResolutionResult(
            raw=resolution.raw,
            normalized_slug=resolution.normalized_slug,
            normalized_display_name=resolution.normalized_display_name,
            resolved_slug=resolution.resolved_slug,
            result_type=TAG_RESOLUTION_ARCHIVED,
            should_create_archived=False,
            should_skip_creation=True,
            reason=TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_archived_import_tags_for_dataset(entries: list[dict]) -> ArchivedTagImportSummary:
    """Ensure used dataset tags are known as archived imported records."""
    used_slugs: set[str] = set()
    for tag in get_used_tags(entries):
        normalized = normalize_tag(tag)
        if normalized.slug:
            used_slugs.add(normalized.slug)

    summary = ArchivedTagImportSummary()
    resolutions = [resolve_tag_lifecycle(slug) for slug in sorted(used_slugs)]
    if any(result.should_create_archived for result in resolutions):
        create_db_backup(engine=engine)
    for resolution in resolutions:
        result = _create_archived_import_tag_from_resolution(resolution)
        if result.reason == TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED:
            summary.created_count += 1
            summary.created_slugs.append(result.normalized_slug)
        elif result.result_type == TAG_RESOLUTION_UNKNOWN:
            summary.skipped_slugs.append(result.normalized_slug)
        else:
            summary.existing_slugs.append(result.resolved_slug)
    return summary


def _warn_duplicate_tag_slugs(session) -> None:
    """Warn about legacy duplicate tag slugs before relying on DB uniqueness."""
    duplicates = (
        session.query(Tag.slug, func.count(Tag.id).label("cnt"))
        .group_by(Tag.slug)
        .having(func.count(Tag.id) > 1)
        .all()
    )
    if not duplicates:
        return

    duplicate_text = ", ".join(
        f"{slug or '<empty>'} ({count})" for slug, count in duplicates
    )
    # SQLite cannot add this constraint to an existing table without rebuilding.
    # New databases get uq_tag_slug from the ORM model; legacy duplicates must be
    # resolved manually before any future table rebuild can enforce it safely.
    print(
        "WARNING: Duplicate tag slugs found: "
        f"{duplicate_text}. UniqueConstraint on Tag.slug cannot be enforced. "
        "Resolve duplicates manually before restarting."
    )


# ── Seeding ────────────────────────────────────────────────────────────────────

def seed_default_tags() -> None:
    """Idempotently seed built-in tags without deleting user data."""
    init_db()
    _migrate_tags_slug_column()
    _migrate_tag_lifecycle_schema()

    session = SessionLocal()
    try:
        _warn_duplicate_tag_slugs(session)
        default_category_slugs = [slugify_tag_name(cat_name) for cat_name in TAGS]
        for cat_order, (cat_name, tag_raws) in enumerate(TAGS.items()):
            cat_slug = slugify_tag_name(cat_name)

            # ── Get or create category ─────────────────────────────────────────
            category = session.query(TagCategory).filter_by(slug=cat_slug).first()
            if category is None:
                category = TagCategory(
                    name=cat_name,
                    slug=cat_slug,
                    sort_order=cat_order,
                    is_active=True,
                )
                session.add(category)
                session.flush()  # populate category.id before inserting child tags
            else:
                # Update mutable fields so display-name fixes propagate
                category.name = cat_name
                category.sort_order = cat_order
                category.is_active = True

            # ── Get or create each tag ─────────────────────────────────────────
            for tag_order, tag_raw in enumerate(tag_raws):
                tag_slug = slugify_tag_name(tag_raw)
                tag_name = prettify_tag_name(tag_slug)
                lookup_slugs = [tag_slug]
                if tag_slug == "approved":
                    lookup_slugs.append("reviewed")

                # Primary lookup: by slug (Phase 1.5+ rows)
                tag = (
                    session.query(Tag)
                    .filter(Tag.category_id == category.id, Tag.slug.in_(lookup_slugs))
                    .order_by(Tag.id)
                    .first()
                )

                # Fallback: by old name value (Phase 1 rows seeded before slug)
                if tag is None:
                    tag = (
                        session.query(Tag)
                        .filter_by(category_id=category.id, name=tag_raw)
                        .first()
                    )

                # Legacy built-ins may live under an old category. Reuse them
                # before inserting so fresh schemas can keep global slug
                # uniqueness while seed maintenance moves the row in place.
                if tag is None:
                    tag = (
                        session.query(Tag)
                        .filter(
                            Tag.slug.in_(lookup_slugs),
                            Tag.is_builtin.is_(True),
                        )
                        .order_by(Tag.id)
                        .first()
                    )

                if tag is None:
                    tag = Tag(
                        category_id=category.id,
                        name=tag_name,
                        slug=tag_slug,
                        sort_order=tag_order,
                        is_active=True,
                        is_builtin=True,
                        status=TAG_STATUS_ACTIVE,
                    )
                    session.add(tag)
                else:
                    # Normalise existing row to the new name/slug scheme
                    tag.slug = tag_slug
                    tag.name = tag_name
                    tag.is_builtin = True
                    tag.sort_order = tag_order
                    tag.status = TAG_STATUS_ACTIVE
                    tag.is_active = True
                    tag.category_id = category.id

        session.flush()
        _migrate_legacy_source_status_category(session)
        _deactivate_empty_unsorted_category(session)
        _order_custom_categories_after_defaults(session, default_category_slugs)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Query helpers ──────────────────────────────────────────────────────────────


def _order_custom_categories_after_defaults(
    session,
    default_category_slugs: list[str],
) -> None:
    """Keep default categories first and active custom categories after them."""
    default_slug_set = set(default_category_slugs)
    custom_categories = (
        session.query(TagCategory)
        .filter(
            TagCategory.is_active.is_(True),
            TagCategory.slug.notin_(default_slug_set),
        )
        .order_by(TagCategory.sort_order, TagCategory.name)
        .all()
    )
    for offset, category in enumerate(custom_categories, start=len(default_category_slugs)):
        category.sort_order = offset


def ensure_tags_exist_for_dataset(entries: list[dict]) -> TagAdoptionSummary:
    """Adopt unknown dataset tag slugs as inactive archived/imported records."""
    summary = ensure_archived_import_tags_for_dataset(entries)
    return TagAdoptionSummary(
        created_count=summary.created_count,
        created_slugs=summary.created_slugs,
    )


def _tag_to_dict(tag: Tag) -> dict:
    """Return a plain lifecycle tag shape for non-picker registry views."""
    category = tag.category
    return {
        "id": tag.id,
        "name": tag.name,
        "slug": tag.slug,
        "sort_order": tag.sort_order,
        "is_active": tag.is_active,
        "is_builtin": tag.is_builtin,
        "status": tag.status,
        "category_id": tag.category_id,
        "category_name": category.name if category is not None else None,
        "category_slug": category.slug if category is not None else None,
    }


def get_tags_by_status(status: str) -> list[dict]:
    """Return tags with one lifecycle status as plain dicts."""
    session = SessionLocal()
    try:
        tags = (
            session.query(Tag)
            .filter_by(status=status)
            .order_by(Tag.sort_order, Tag.name, Tag.slug)
            .all()
        )
        return [_tag_to_dict(tag) for tag in tags]
    finally:
        session.close()


def get_archived_tags() -> list[dict]:
    """Return archived/deleted tags for future restore surfaces."""
    return get_tags_by_status(TAG_STATUS_ARCHIVED)


def get_imported_archived_tags() -> list[dict]:
    """Return visible imported archived tags."""
    tags = [
        tag
        for tag in get_archived_tags()
        if tag.get("category_id") is None
    ]
    result = []
    for tag in tags:
        metadata = archive_metadata_for_tag(tag)
        if metadata.get("archive_origin") != ARCHIVE_ORIGIN_IMPORTED:
            continue
        result.append(
            {
                **tag,
                "display_name": tag["name"],
                "archive_origin": metadata.get("archive_origin", ARCHIVE_ORIGIN_IMPORTED),
                "archive_reason": metadata.get(
                    "archive_reason", ARCHIVE_REASON_UNKNOWN_IMPORT
                ),
                "visible_badge": metadata.get("visible_badge", ARCHIVE_BADGE_IMPORTED),
                "selectable": True,
                "has_selection_slot": True,
                "can_assign_to_category": True,
                "disabled_reason": None,
            }
        )
    return result


def get_deleted_archived_tags() -> list[dict]:
    """Return visible deleted archived tags for future restore surfaces."""
    result = []
    for tag in get_archived_tags():
        metadata = archive_metadata_for_tag(tag)
        if metadata.get("archive_origin") != ARCHIVE_ORIGIN_DELETED:
            continue
        result.append(
            {
                **tag,
                "display_name": tag["name"],
                "archive_origin": metadata.get("archive_origin", ARCHIVE_ORIGIN_DELETED),
                "archive_reason": metadata.get(
                    "archive_reason", ARCHIVE_REASON_USER_SOFT_DELETE
                ),
                "visible_badge": metadata.get("visible_badge", ARCHIVE_BADGE_DELETED),
                "selectable": False,
                "has_selection_slot": True,
                "can_assign_to_category": False,
                "disabled_reason": "Restore flow is separate.",
            }
        )
    return result


def get_visible_archived_tags() -> list[dict]:
    """Return visible archived tags with origin metadata for Tag Management."""
    tags = get_imported_archived_tags() + get_deleted_archived_tags()
    return sorted(tags, key=lambda tag: (tag.get("name") or "", tag.get("slug") or ""))


def get_hidden_tags() -> list[dict]:
    """Return internal history-only tags."""
    return get_tags_by_status(TAG_STATUS_HIDDEN)


def get_tag_by_slug_any_status(slug: str) -> Tag | None:
    """Return a tag row by canonical slug regardless of lifecycle status."""
    normalized = normalize_tag(slug)
    if not normalized.slug:
        return None
    session = SessionLocal()
    try:
        return (
            session.query(Tag)
            .filter_by(slug=normalized.slug)
            .order_by(Tag.id)
            .first()
        )
    finally:
        session.close()


# ── Write helpers (additive-only) ─────────────────────────────────────────────

def get_tag_registry_snapshot(
    untagged_key: str = "__untagged__",
) -> TagRegistrySnapshot:
    """Return all UI-facing registry read shapes from one database session."""
    session = SessionLocal()
    try:
        categories = (
            session.query(TagCategory)
            .options(selectinload(TagCategory.tags))
            .filter_by(is_active=True)
            .order_by(TagCategory.sort_order, TagCategory.name)
            .all()
        )

        active_registry: dict[str, list[str]] = {}
        active_categories: list[dict] = []
        active_tag_slugs: list[str] = []
        tag_label_map: dict[str, str] = {}
        tag_category_map: dict[str, str] = {}

        for category in categories:
            active_tags = [
                tag
                for tag in category.tags
                if tag.status == TAG_STATUS_ACTIVE
                and tag.is_active
                and tag.category_id is not None
            ]
            registry_tags = sorted(active_tags, key=lambda tag: (tag.sort_order, tag.slug))
            full_registry_tags = sorted(active_tags, key=lambda tag: (tag.sort_order, tag.name))

            active_registry[category.name] = [tag.slug for tag in registry_tags]
            active_tag_slugs.extend(tag.slug for tag in registry_tags)
            for tag in registry_tags:
                tag_label_map[tag.slug] = f"{category.name} / {tag.name}"
                tag_category_map[tag.slug] = category.name

            active_categories.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "slug": category.slug,
                    "sort_order": category.sort_order,
                    "tags": [
                        {
                            "id": tag.id,
                            "name": tag.name,
                            "slug": tag.slug,
                            "sort_order": tag.sort_order,
                            "is_builtin": tag.is_builtin,
                        }
                        for tag in full_registry_tags
                    ],
                }
            )

        tag_label_map_with_untagged = {untagged_key: "Untagged", **tag_label_map}

        archived_tags = (
            session.query(Tag)
            .options(selectinload(Tag.category))
            .filter_by(status=TAG_STATUS_ARCHIVED)
            .order_by(Tag.sort_order, Tag.name, Tag.slug)
            .all()
        )
        archived_tag_dicts = [_tag_to_dict(tag) for tag in archived_tags]
        metadata_by_slug = current_metadata_by_slug(
            session,
            [tag["slug"] for tag in archived_tag_dicts],
        )

        imported_archived_tags = []
        for tag in archived_tag_dicts:
            if tag.get("category_id") is not None:
                continue
            metadata = archive_metadata_for_tag_dict(tag, metadata_by_slug)
            if metadata.get("archive_origin") != ARCHIVE_ORIGIN_IMPORTED:
                continue
            imported_archived_tags.append(
                {
                    **tag,
                    "display_name": tag["name"],
                    "archive_origin": metadata.get("archive_origin", ARCHIVE_ORIGIN_IMPORTED),
                    "archive_reason": metadata.get(
                        "archive_reason", ARCHIVE_REASON_UNKNOWN_IMPORT
                    ),
                    "visible_badge": metadata.get("visible_badge", ARCHIVE_BADGE_IMPORTED),
                    "selectable": True,
                    "has_selection_slot": True,
                    "can_assign_to_category": True,
                    "disabled_reason": None,
                }
            )

        deleted_archived_tags = []
        for tag in archived_tag_dicts:
            metadata = archive_metadata_for_tag_dict(tag, metadata_by_slug)
            if metadata.get("archive_origin") != ARCHIVE_ORIGIN_DELETED:
                continue
            deleted_archived_tags.append(
                {
                    **tag,
                    "display_name": tag["name"],
                    "archive_origin": metadata.get("archive_origin", ARCHIVE_ORIGIN_DELETED),
                    "archive_reason": metadata.get(
                        "archive_reason", ARCHIVE_REASON_USER_SOFT_DELETE
                    ),
                    "visible_badge": metadata.get("visible_badge", ARCHIVE_BADGE_DELETED),
                    "selectable": False,
                    "has_selection_slot": True,
                    "can_assign_to_category": False,
                    "disabled_reason": "Restore flow is separate.",
                }
            )

        visible_archived_tags = sorted(
            imported_archived_tags + deleted_archived_tags,
            key=lambda tag: (tag.get("name") or "", tag.get("slug") or ""),
        )

        return TagRegistrySnapshot(
            active_registry=active_registry,
            active_categories=active_categories,
            active_tag_slugs=active_tag_slugs,
            active_tag_slug_set=set(active_tag_slugs),
            tag_label_map=tag_label_map,
            tag_label_map_with_untagged=tag_label_map_with_untagged,
            tag_category_map=tag_category_map,
            visible_archived_tags=visible_archived_tags,
            default_category_slugs={slugify_tag_name(name) for name in TAGS},
            max_active_categories=MAX_ACTIVE_CATEGORIES,
        )
    finally:
        session.close()


def get_full_tag_registry() -> list[dict]:
    """Return active categories and tags as plain dicts for UI rendering."""
    session = SessionLocal()
    try:
        categories = (
            session.query(TagCategory)
            .filter_by(is_active=True)
            .order_by(TagCategory.sort_order, TagCategory.name)
            .all()
        )
        result: list[dict] = []
        for cat in categories:
            tags = (
                _query_active_tags(session)
                .filter(Tag.category_id == cat.id)
                .order_by(Tag.sort_order, Tag.name)
                .all()
            )
            result.append({
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "sort_order": cat.sort_order,
                "tags": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "slug": t.slug,
                        "sort_order": t.sort_order,
                        "is_builtin": t.is_builtin,
                    }
                    for t in tags
                ],
            })
        return result
    finally:
        session.close()
