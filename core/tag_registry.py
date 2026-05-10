"""DB-backed tag registry helpers.

JSONL entries store tag slugs; this module owns slug/display conversion,
registry seeding, lookup helpers, and additive custom tag writes.
"""
import json
from dataclasses import dataclass, field

from sqlalchemy import func, inspect as sa_inspect, text

from core.dataset import TAGS, get_used_tags
from core.db import SessionLocal, engine, init_db
from core.db_backups import create_db_backup
from core.models import (
    Base,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
    TAG_STATUS_UNCATEGORIZED,
    Tag,
    TagCategory,
    TagHistory,
)
from core.tag_normalization import normalize_tag


# Legacy category from earlier archived-import handling. New unknown imports do
# not use it; seed_default_tags deactivates an empty legacy row.
UNSORTED_CATEGORY_NAME = "Unsorted"
UNSORTED_CATEGORY_SLUG = "unsorted"
UNSORTED_SORT_ORDER = -1000

TAG_HISTORY_RENAME = "rename"
TAG_HISTORY_MERGE = "merge"
TAG_HISTORY_ARCHIVE = "archive"
TAG_HISTORY_RESTORE = "restore"
TAG_HISTORY_ASSIGN_CATEGORY = "assign_category"
TAG_HISTORY_HIDE = "hide"
TAG_HISTORY_DELETE = "delete"
TAG_HISTORY_IMPORT_ARCHIVED = "import_archived"
TAG_HISTORY_IMPORT_UNCATEGORIZED = "import_uncategorized"

LIFECYCLE_STATE_ACTIVE = "active"
LIFECYCLE_STATE_ARCHIVED = "archived"
LIFECYCLE_STATE_HIDDEN = "hidden"
ARCHIVE_ORIGIN_IMPORTED = "imported"
ARCHIVE_ORIGIN_DELETED = "deleted"
ARCHIVE_REASON_UNKNOWN_IMPORT = "unknown_import"
ARCHIVE_REASON_USER_SOFT_DELETE = "user_soft_delete"
ARCHIVE_BADGE_IMPORTED = "Imported"
ARCHIVE_BADGE_DELETED = "Deleted"
ACTIVATION_ORIGIN_IMPORTED_ASSIGNMENT = "imported_assignment"
HIDE_REASON_HIDDEN_FROM_ARCHIVE = "hidden_from_archive"
RESOLVER_BEHAVIOR_MAP_TO_TARGET = "map_to_target"

TAG_CURRENT_METADATA_ACTIONS = [
    TAG_HISTORY_IMPORT_ARCHIVED,
    TAG_HISTORY_IMPORT_UNCATEGORIZED,
    TAG_HISTORY_ARCHIVE,
    TAG_HISTORY_RESTORE,
    TAG_HISTORY_ASSIGN_CATEGORY,
    TAG_HISTORY_HIDE,
    TAG_HISTORY_DELETE,
]
TAG_ALIAS_METADATA_ACTIONS = [
    TAG_HISTORY_RENAME,
    TAG_HISTORY_MERGE,
]

TAG_RESOLUTION_ACTIVE = "active"
TAG_RESOLUTION_ALIAS_MAPPED = "alias_mapped"
TAG_RESOLUTION_UNCATEGORIZED = "uncategorized"
TAG_RESOLUTION_ARCHIVED = "archived"
TAG_RESOLUTION_HIDDEN = "hidden"
TAG_RESOLUTION_RETIRED = "retired"
TAG_RESOLUTION_UNKNOWN = "unknown"


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


UncategorizedTagSummary = ArchivedTagImportSummary


@dataclass(frozen=True)
class TagResolutionResult:
    """Lifecycle resolution result for one imported tag value."""

    raw: str
    normalized_slug: str
    normalized_display_name: str
    resolved_slug: str
    result_type: str
    should_rewrite_slug: bool = False
    should_create_uncategorized: bool = False
    should_create_archived: bool = False
    should_skip_creation: bool = False
    target_slug: str | None = None
    reason: str = ""


# ── Slug helper ────────────────────────────────────────────────────────────────

def slugify_tag_name(name: str) -> str:
    """Convert a display name to a lowercase_snake_case slug."""
    return normalize_tag(name).slug


# ── Display-name helper ────────────────────────────────────────────────────────

def prettify_tag_name(slug: str) -> str:
    """Convert a tag slug to a display label."""
    return normalize_tag(slug).display_name


# ── Schema migration ───────────────────────────────────────────────────────────

def _migrate_tags_slug_column() -> None:
    """Add the ``slug`` column to the ``tags`` table if it is missing.

    Safe to call repeatedly — checks column existence before altering.
    Also backfills ``slug`` (and prettifies ``name``) for any rows that
    were inserted before this column existed (i.e. Phase-1 seed rows).

    Must be called *after* ``init_db()`` so the ``tags`` table exists.
    """
    inspector = sa_inspect(engine)

    # Determine whether the tags table exists at all (fresh DB handled by
    # init_db; this guard avoids crashing if called before init_db somehow).
    if "tags" not in inspector.get_table_names():
        return

    existing_cols = {c["name"] for c in inspector.get_columns("tags")}

    with engine.connect() as conn:
        # ── Add column if missing ──────────────────────────────────────────────
        if "slug" not in existing_cols:
            # SQLite ALTER TABLE ADD COLUMN allows NULL for existing rows;
            # we backfill below immediately afterwards.
            conn.execute(text("ALTER TABLE tags ADD COLUMN slug VARCHAR(120)"))
            conn.commit()

        # ── Backfill rows where slug is NULL or empty ──────────────────────────
        rows = conn.execute(
            text("SELECT id, name FROM tags WHERE slug IS NULL OR slug = ''")
        ).fetchall()

        for row_id, row_name in rows:
            slug = slugify_tag_name(row_name)
            pretty_name = prettify_tag_name(slug)
            conn.execute(
                text("UPDATE tags SET slug = :slug, name = :name WHERE id = :id"),
                {"slug": slug, "name": pretty_name, "id": row_id},
            )

        if rows:
            conn.commit()


def _migrate_tag_lifecycle_schema() -> None:
    """Add lifecycle columns/tables while preserving existing registry rows."""
    _migrate_tags_slug_column()
    Base.metadata.create_all(bind=engine)

    inspector = sa_inspect(engine)
    if "tags" not in inspector.get_table_names():
        return

    columns = inspector.get_columns("tags")
    existing_cols = {c["name"] for c in columns}

    with engine.connect() as conn:
        if "status" not in existing_cols:
            conn.execute(
                text(
                    "ALTER TABLE tags "
                    "ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'active'"
                )
            )
            conn.commit()
        else:
            conn.execute(
                text(
                    "UPDATE tags "
                    "SET status = :status "
                    "WHERE status IS NULL OR status = ''"
                ),
                {"status": TAG_STATUS_ACTIVE},
            )
            conn.commit()

    inspector = sa_inspect(engine)
    category_column = next(
        (c for c in inspector.get_columns("tags") if c["name"] == "category_id"),
        None,
    )
    if category_column is None or category_column.get("nullable", True):
        return

    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text("DROP TABLE IF EXISTS tags__lifecycle_migration"))
        conn.execute(
            text(
                """
                CREATE TABLE tags__lifecycle_migration (
                    id INTEGER NOT NULL,
                    category_id INTEGER,
                    name VARCHAR(120) NOT NULL,
                    slug VARCHAR(120) NOT NULL,
                    sort_order INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    is_builtin BOOLEAN NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(category_id) REFERENCES tag_categories (id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO tags__lifecycle_migration (
                    id,
                    category_id,
                    name,
                    slug,
                    sort_order,
                    is_active,
                    is_builtin,
                    status
                )
                SELECT
                    id,
                    category_id,
                    name,
                    slug,
                    sort_order,
                    is_active,
                    is_builtin,
                    COALESCE(NULLIF(status, ''), 'active')
                FROM tags
                """
            )
        )
        conn.execute(text("DROP TABLE tags"))
        conn.execute(text("ALTER TABLE tags__lifecycle_migration RENAME TO tags"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.commit()


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


def _resolve_alias_mapping(session, slug: str) -> tuple[str, str] | None:
    """Follow rename/merge history to an active target slug."""
    seen: set[str] = set()
    current_slug = slug

    for _ in range(20):
        if current_slug in seen:
            return None
        seen.add(current_slug)

        history = (
            session.query(TagHistory)
            .filter(
                TagHistory.old_slug == current_slug,
                TagHistory.action.in_([TAG_HISTORY_RENAME, TAG_HISTORY_MERGE]),
                TagHistory.new_slug.isnot(None),
                TagHistory.new_slug != "",
            )
            .order_by(TagHistory.id.desc())
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
    retired_actions = [TAG_HISTORY_ARCHIVE, TAG_HISTORY_HIDE, TAG_HISTORY_DELETE]
    histories = (
        session.query(TagHistory)
        .filter(
            TagHistory.old_slug == slug,
            TagHistory.action.in_(retired_actions),
        )
        .order_by(TagHistory.id.desc())
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
                TAG_STATUS_UNCATEGORIZED: TAG_RESOLUTION_UNCATEGORIZED,
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


def build_rename_alias_metadata() -> dict:
    """Return resolver metadata for a hidden rename alias."""
    return {
        "lifecycle_state": LIFECYCLE_STATE_HIDDEN,
        "alias_type": TAG_HISTORY_RENAME,
        "resolver_behavior": RESOLVER_BEHAVIOR_MAP_TO_TARGET,
    }


def build_merge_alias_metadata() -> dict:
    """Return resolver metadata for a hidden merge alias."""
    return {
        "lifecycle_state": LIFECYCLE_STATE_HIDDEN,
        "alias_type": TAG_HISTORY_MERGE,
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
) -> TagHistory:
    """Create or replace the current lifecycle metadata row for a slug."""
    normalized_old = normalize_tag(old_slug).slug
    if not normalized_old:
        raise ValueError("Lifecycle metadata requires a valid old_slug.")

    actions = (
        TAG_ALIAS_METADATA_ACTIONS
        if action in TAG_ALIAS_METADATA_ACTIONS
        else TAG_CURRENT_METADATA_ACTIONS
    )
    own_session = session is None
    active_session = session or SessionLocal()
    try:
        history = (
            active_session.query(TagHistory)
            .filter(
                TagHistory.old_slug == normalized_old,
                TagHistory.action.in_(actions),
            )
            .order_by(TagHistory.id.desc())
            .first()
        )
        if history is None:
            history = TagHistory(old_slug=normalized_old)
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
            session.query(TagHistory)
            .filter(
                TagHistory.old_slug == normalized,
                TagHistory.action.in_(TAG_CURRENT_METADATA_ACTIONS),
            )
            .order_by(TagHistory.id.desc())
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
) -> TagHistory:
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


def _archive_metadata_for_tag(tag: dict) -> dict:
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
                should_create_uncategorized=False,
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
            action=TAG_HISTORY_IMPORT_ARCHIVED,
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
            should_create_uncategorized=False,
            should_create_archived=False,
            should_skip_creation=True,
            reason=TAG_HISTORY_IMPORT_ARCHIVED,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_uncategorized_tag(raw_tag: str) -> TagResolutionResult:
    """Compatibility wrapper for archived/imported tag adoption."""
    return ensure_archived_import_tag(raw_tag)


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
        if result.reason == TAG_HISTORY_IMPORT_ARCHIVED:
            summary.created_count += 1
            summary.created_slugs.append(result.normalized_slug)
        elif result.result_type == TAG_RESOLUTION_UNKNOWN:
            summary.skipped_slugs.append(result.normalized_slug)
        else:
            summary.existing_slugs.append(result.resolved_slug)
    return summary


def ensure_uncategorized_tags_for_dataset(entries: list[dict]) -> ArchivedTagImportSummary:
    """Compatibility wrapper for archived/imported dataset adoption."""
    return ensure_archived_import_tags_for_dataset(entries)


# ── Seeding ────────────────────────────────────────────────────────────────────

def seed_default_tags() -> None:
    """Idempotently seed built-in tags without deleting user data."""
    init_db()
    _migrate_tags_slug_column()
    _migrate_tag_lifecycle_schema()

    session = SessionLocal()
    try:
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
                if tag_slug == "needs_review":
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

def _migrate_legacy_source_status_category(session) -> None:
    """Move old Source & Status built-ins into Source and Status categories."""
    source = session.query(TagCategory).filter_by(slug="source").first()
    status = session.query(TagCategory).filter_by(slug="status").first()
    if source is None or status is None:
        return

    move_targets = {
        "manual": (source, "manual", 0),
        "ai_generated": (source, "ai_generated", 1),
        "reviewed": (status, "needs_review", 0),
        "needs_review": (status, "needs_review", 0),
        "needs_edit": (status, "needs_edit", 1),
    }
    for old_slug, (category, new_slug, sort_order) in move_targets.items():
        legacy_tag = (
            session.query(Tag)
            .filter(Tag.slug == old_slug, Tag.is_builtin.is_(True))
            .order_by(Tag.id)
            .first()
        )
        if legacy_tag is None:
            continue

        target_tag = (
            session.query(Tag)
            .filter(
                Tag.slug == new_slug,
                Tag.category_id == category.id,
                Tag.id != legacy_tag.id,
            )
            .first()
        )
        if target_tag is not None:
            legacy_tag.is_active = False
            continue

        legacy_tag.category_id = category.id
        legacy_tag.slug = new_slug
        legacy_tag.name = prettify_tag_name(new_slug)
        legacy_tag.sort_order = sort_order
        legacy_tag.is_builtin = True
        legacy_tag.is_active = True
        legacy_tag.status = TAG_STATUS_ACTIVE

    legacy_category = session.query(TagCategory).filter_by(slug="source_status").first()
    if legacy_category is not None:
        legacy_category.is_active = False

    legacy_reviewed_tags = (
        session.query(Tag)
        .filter(Tag.slug == "reviewed", Tag.is_builtin.is_(True))
        .all()
    )
    for legacy_tag in legacy_reviewed_tags:
        legacy_tag.is_active = False

    for category, new_slug, _sort_order in {
        (target_category, new_slug, sort_order)
        for target_category, new_slug, sort_order in move_targets.values()
    }:
        duplicate_tags = (
            session.query(Tag)
            .filter(Tag.slug == new_slug, Tag.is_builtin.is_(True))
            .order_by(Tag.id)
            .all()
        )
        keeper = next(
            (tag for tag in duplicate_tags if tag.category_id == category.id),
            None,
        )
        for tag in duplicate_tags:
            if keeper is not None and tag.id == keeper.id:
                continue
            tag.is_active = False


def _deactivate_empty_unsorted_category(session) -> None:
    """Deactivate legacy Unsorted only when no tags depend on it."""
    category = session.query(TagCategory).filter_by(slug=UNSORTED_CATEGORY_SLUG).first()
    if category is None:
        return
    has_tags = session.query(Tag).filter_by(category_id=category.id).first() is not None
    if not has_tags:
        category.is_active = False


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


def ensure_unsorted_category() -> TagCategory:
    """Ensure legacy Unsorted exists for compatibility-only tests/migrations."""
    session = SessionLocal()
    try:
        category = (
            session.query(TagCategory)
            .filter_by(slug=UNSORTED_CATEGORY_SLUG)
            .first()
        )
        if category is None:
            category = TagCategory(
                name=UNSORTED_CATEGORY_NAME,
                slug=UNSORTED_CATEGORY_SLUG,
                sort_order=UNSORTED_SORT_ORDER,
                is_active=True,
            )
            session.add(category)
            session.commit()
            session.refresh(category)
        else:
            category.name = UNSORTED_CATEGORY_NAME
            category.sort_order = UNSORTED_SORT_ORDER
            category.is_active = True
            session.commit()
            session.refresh(category)
        return category
    finally:
        session.close()


def ensure_tags_exist_for_dataset(entries: list[dict]) -> TagAdoptionSummary:
    """Adopt unknown dataset tag slugs as inactive archived/imported records."""
    summary = ensure_archived_import_tags_for_dataset(entries)
    return TagAdoptionSummary(
        created_count=summary.created_count,
        created_slugs=summary.created_slugs,
    )


def get_active_tag_categories() -> list[TagCategory]:
    """Return all active TagCategory rows, ordered by sort_order then name."""
    session = SessionLocal()
    try:
        return (
            session.query(TagCategory)
            .filter_by(is_active=True)
            .order_by(TagCategory.sort_order, TagCategory.name)
            .all()
        )
    finally:
        session.close()


def get_active_tags(category_id: int) -> list[Tag]:
    """Return all active Tag rows for a given category, ordered by sort_order."""
    session = SessionLocal()
    try:
        return (
            _query_active_tags(session)
            .filter(Tag.category_id == category_id)
            .order_by(Tag.sort_order, Tag.slug)
            .all()
        )
    finally:
        session.close()


def get_tag_registry_dict() -> dict[str, list[str]]:
    """Return active tags as ``{category_name: [tag_slug, ...]}``.

    Values are **slugs** (not display names) because JSONL files store the
    slug as the canonical tag identifier.  This shape mirrors the hardcoded
    ``core.dataset.TAGS`` dict and is intended for UI wiring.

    Only active categories and active tags are included; order follows
    ``sort_order``.  Returns an empty dict if the database is unseeded.
    """
    session = SessionLocal()
    try:
        categories = (
            session.query(TagCategory)
            .filter_by(is_active=True)
            .order_by(TagCategory.sort_order, TagCategory.name)
            .all()
        )
        result: dict[str, list[str]] = {}
        for cat in categories:
            tags = (
                _query_active_tags(session)
                .filter(Tag.category_id == cat.id)
                .order_by(Tag.sort_order, Tag.slug)
                .all()
            )
            result[cat.name] = [t.slug for t in tags]
        return result
    finally:
        session.close()


def get_tag_label_map(
    include_untagged: bool = True,
    untagged_key: str = "__untagged__",
) -> dict[str, str]:
    """Return ``{tag_slug: "Category / Pretty Name"}`` for all active tags.

    Used as the ``format_func`` source for filter and tag-edit multiselects.
    Unknown tags (slugs not in the DB) are not included; callers should fall
    back to ``prettify_tag_name(slug)`` for those.

    When ``include_untagged`` is True, adds ``{untagged_key: "Untagged"}``.
    Returns a minimal dict (just the untagged entry) if the DB is unseeded.
    """
    session = SessionLocal()
    try:
        categories = (
            session.query(TagCategory)
            .filter_by(is_active=True)
            .order_by(TagCategory.sort_order, TagCategory.name)
            .all()
        )
        result: dict[str, str] = {}
        if include_untagged:
            result[untagged_key] = "Untagged"
        for cat in categories:
            tags = (
                _query_active_tags(session)
                .filter(Tag.category_id == cat.id)
                .order_by(Tag.sort_order, Tag.slug)
                .all()
            )
            for t in tags:
                result[t.slug] = f"{cat.name} / {t.name}"
        return result
    finally:
        session.close()


def get_all_tag_slugs() -> list[str]:
    """Return all active tag slugs as a flat list in category/sort order.

    Used to populate ``options`` in multiselects that should show all known
    tags (quick-edit, bulk-edit, ``only_used=False`` filter).
    Returns an empty list if the DB is unseeded.
    """
    session = SessionLocal()
    try:
        categories = (
            session.query(TagCategory)
            .filter_by(is_active=True)
            .order_by(TagCategory.sort_order, TagCategory.name)
            .all()
        )
        result: list[str] = []
        for cat in categories:
            tags = (
                _query_active_tags(session)
                .filter(Tag.category_id == cat.id)
                .order_by(Tag.sort_order, Tag.slug)
                .all()
            )
            result.extend(t.slug for t in tags)
        return result
    finally:
        session.close()


def get_tag_category_map() -> dict[str, str]:
    """Return ``{tag_slug: category_display_name}`` for all active tags.

    Used by ``build_dataset_stats()`` to bucket tags into display categories.
    Tags not in the map (unknown slugs) will fall through to the ``"Unknown"``
    bucket.  Returns an empty dict if the DB is unseeded.
    """
    session = SessionLocal()
    try:
        categories = (
            session.query(TagCategory)
            .filter_by(is_active=True)
            .all()
        )
        result: dict[str, str] = {}
        for cat in categories:
            tags = (
                _query_active_tags(session)
                .filter(Tag.category_id == cat.id)
                .all()
            )
            for t in tags:
                result[t.slug] = cat.name
        return result
    finally:
        session.close()


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


def get_uncategorized_tags() -> list[dict]:
    """Return known-but-untrusted imported tags."""
    return get_tags_by_status(TAG_STATUS_UNCATEGORIZED)


def get_archived_tags() -> list[dict]:
    """Return archived/deleted tags for future restore surfaces."""
    return get_tags_by_status(TAG_STATUS_ARCHIVED)


def get_imported_archived_tags() -> list[dict]:
    """Return visible imported archived tags, including recent uncategorized rows."""
    tags = [
        tag
        for tag in get_archived_tags() + get_uncategorized_tags()
        if tag.get("category_id") is None
    ]
    result = []
    for tag in tags:
        metadata = _archive_metadata_for_tag(tag)
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
                "can_assign_to_category": True,
                "disabled_reason": None,
            }
        )
    return result


def get_deleted_archived_tags() -> list[dict]:
    """Return visible deleted archived tags for future restore surfaces."""
    result = []
    for tag in get_archived_tags():
        metadata = _archive_metadata_for_tag(tag)
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

# Hard ceiling on active categories to keep the UI manageable.
_MAX_ACTIVE_CATEGORIES = 10


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


def create_custom_category(name: str) -> tuple[bool, str]:
    """Validate and insert a user-defined tag category."""
    name = name.strip()
    if not name:
        return False, "Category name cannot be empty."

    slug = slugify_tag_name(name)
    if not slug:
        return False, "Could not generate a valid slug from the provided name."

    display_name = prettify_tag_name(slug)

    session = SessionLocal()
    try:
        # ── Duplicate slug check ───────────────────────────────────────────────
        if session.query(TagCategory).filter_by(slug=slug).first() is not None:
            return False, f"A category with slug '{slug}' already exists."

        # ── Active category limit ──────────────────────────────────────────────
        active_count = session.query(TagCategory).filter_by(is_active=True).count()
        if active_count >= _MAX_ACTIVE_CATEGORIES:
            return (
                False,
                f"Category limit reached. "
                f"This version supports {_MAX_ACTIVE_CATEGORIES} active categories.",
            )

        # ── sort_order: one after the current maximum ──────────────────────────
        max_order: int = session.query(func.max(TagCategory.sort_order)).scalar() or 0

        try:
            create_db_backup(engine=engine)
        except Exception as exc:
            return False, f"Could not create database backup: {exc}"

        category = TagCategory(
            name=display_name,
            slug=slug,
            sort_order=max_order + 1,
            is_active=True,
        )
        session.add(category)
        session.commit()
        return True, "Category created."
    except Exception as exc:
        session.rollback()
        return False, f"Database error: {exc}"
    finally:
        session.close()


def create_custom_tag(category_id: int, name: str) -> tuple[bool, str]:
    """Validate and insert a custom tag into an existing category."""
    name = name.strip()
    if not name:
        return False, "Tag name cannot be empty."

    slug = slugify_tag_name(name)
    if not slug:
        return False, "Could not generate a valid slug from the provided name."

    display_name = prettify_tag_name(slug)

    session = SessionLocal()
    try:
        # ── Validate category ──────────────────────────────────────────────────
        category = (
            session.query(TagCategory)
            .filter_by(id=category_id, is_active=True)
            .first()
        )
        if category is None:
            return False, "Selected category does not exist or is inactive."

        # ── Global duplicate slug check ────────────────────────────────────────
        if session.query(Tag).filter_by(slug=slug).first() is not None:
            return False, f"A tag with slug '{slug}' already exists."

        # ── sort_order: one after current max in this category ─────────────────
        max_order: int = (
            session.query(func.max(Tag.sort_order))
            .filter_by(category_id=category_id)
            .scalar()
        ) or 0

        try:
            create_db_backup(engine=engine)
        except Exception as exc:
            return False, f"Could not create database backup: {exc}"

        tag = Tag(
            category_id=category_id,
            name=display_name,
            slug=slug,
            sort_order=max_order + 1,
            is_active=True,
            is_builtin=False,
            status=TAG_STATUS_ACTIVE,
        )
        session.add(tag)
        session.commit()
        return True, "Tag created."
    except Exception as exc:
        session.rollback()
        return False, f"Database error: {exc}"
    finally:
        session.close()
