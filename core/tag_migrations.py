"""Startup-only tag registry schema migrations and legacy cleanup."""
from sqlalchemy import inspect as sa_inspect, text

from core.db import engine
from core.models import Base, Tag, TagCategory
from core.tag_constants import (
    _UNSORTED_CATEGORY_SLUG,
    TAG_STATUS_ACTIVE,
)
from core.tag_normalization import normalize_tag


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

        # ── Backfill rows where slug is NULL or empty ─────────────────────────
        rows = conn.execute(
            text("SELECT id, name FROM tags WHERE slug IS NULL OR slug = ''")
        ).fetchall()

        for row_id, row_name in rows:
            normalized = normalize_tag(row_name)
            slug = normalized.slug
            pretty_name = normalized.display_name
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
    _migrate_tag_history_table()

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

def _migrate_tag_history_table() -> None:
    """Copy old tag_history rows into tag_lifecycle_metadata if needed."""
    inspector = sa_inspect(engine)
    tables = set(inspector.get_table_names())
    if "tag_history" not in tables or "tag_lifecycle_metadata" not in tables:
        return

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tag_lifecycle_metadata (
                    id,
                    action,
                    old_slug,
                    old_display_name,
                    old_category_slug,
                    new_slug,
                    new_display_name,
                    new_category_slug,
                    created_at,
                    metadata_json
                )
                SELECT
                    old.id,
                    old.action,
                    old.old_slug,
                    old.old_display_name,
                    old.old_category_slug,
                    old.new_slug,
                    old.new_display_name,
                    old.new_category_slug,
                    old.created_at,
                    old.metadata_json
                FROM tag_history AS old
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM tag_lifecycle_metadata AS current
                    WHERE current.id = old.id
                )
                """
            )
        )
        conn.commit()


def _migrate_legacy_source_status_category(session) -> None:
    """Move old Source & Status built-ins into Source and Status categories."""
    source = session.query(TagCategory).filter_by(slug="source").first()
    status = session.query(TagCategory).filter_by(slug="status").first()
    if source is None or status is None:
        return

    move_targets = {
        "manual": (source, "manual", 0),
        "ai_generated": (source, "ai_generated", 1),
        "reviewed": (status, "approved", 3),
        "needs_review": (status, "needs_review", 1),
        "needs_edit": (status, "needs_edit", 2),
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
        legacy_tag.name = normalize_tag(new_slug).display_name
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
    category = session.query(TagCategory).filter_by(slug=_UNSORTED_CATEGORY_SLUG).first()
    if category is None:
        return
    has_tags = session.query(Tag).filter_by(category_id=category.id).first() is not None
    if not has_tags:
        category.is_active = False
