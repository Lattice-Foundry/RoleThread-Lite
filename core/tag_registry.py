"""DB-backed tag registry helpers.

JSONL entries store tag slugs; this module owns slug/display conversion,
registry seeding, lookup helpers, and additive custom tag writes.
"""
from dataclasses import dataclass, field

from sqlalchemy import func, inspect as sa_inspect, text

from core.dataset import TAGS, get_used_tags
from core.db import SessionLocal, engine, init_db
from core.models import Tag, TagCategory
from core.tag_normalization import NormalizedTag, normalize_tag


# Protected system category for normalized tags without an existing home.
UNSORTED_CATEGORY_NAME = "Unsorted"
UNSORTED_CATEGORY_SLUG = "unsorted"
UNSORTED_SORT_ORDER = -1000


@dataclass
class TagAdoptionSummary:
    """Result of adopting dataset tags into the registry."""

    created_count: int = 0
    created_slugs: list[str] = field(default_factory=list)


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


# ── Seeding ────────────────────────────────────────────────────────────────────

def seed_default_tags() -> None:
    """Idempotently seed built-in tags without deleting user data."""
    init_db()
    _migrate_tags_slug_column()
    ensure_unsorted_category()

    session = SessionLocal()
    try:
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

            # ── Get or create each tag ─────────────────────────────────────────
            for tag_order, tag_raw in enumerate(tag_raws):
                tag_slug = slugify_tag_name(tag_raw)
                tag_name = prettify_tag_name(tag_slug)

                # Primary lookup: by slug (Phase 1.5+ rows)
                tag = (
                    session.query(Tag)
                    .filter_by(category_id=category.id, slug=tag_slug)
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
                    )
                    session.add(tag)
                else:
                    # Normalise existing row to the new name/slug scheme
                    tag.slug = tag_slug
                    tag.name = tag_name
                    tag.is_builtin = True
                    tag.sort_order = tag_order

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Query helpers ──────────────────────────────────────────────────────────────

def ensure_unsorted_category() -> TagCategory:
    """Ensure the protected Unsorted category exists and sorts first."""
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
    """Adopt unknown dataset tag slugs into the Unsorted category."""
    used_slugs: set[str] = set()
    for tag in get_used_tags(entries):
        normalized = normalize_tag(tag)
        if normalized.slug:
            used_slugs.add(normalized.slug)
    if not used_slugs:
        return TagAdoptionSummary()

    ensure_unsorted_category()
    session = SessionLocal()
    created_slugs: list[str] = []
    try:
        unsorted = (
            session.query(TagCategory)
            .filter_by(slug=UNSORTED_CATEGORY_SLUG)
            .first()
        )
        if unsorted is None:
            return TagAdoptionSummary()

        existing_slugs = {
            slug
            for (slug,) in session.query(Tag.slug)
            .filter(Tag.slug.in_(used_slugs))
            .all()
        }
        missing_slugs = sorted(used_slugs - existing_slugs)
        if not missing_slugs:
            return TagAdoptionSummary()

        max_order: int = (
            session.query(func.max(Tag.sort_order))
            .filter_by(category_id=unsorted.id)
            .scalar()
        ) or 0
        for offset, slug in enumerate(missing_slugs, 1):
            session.add(
                Tag(
                    category_id=unsorted.id,
                    name=prettify_tag_name(slug),
                    slug=slug,
                    sort_order=max_order + offset,
                    is_active=True,
                    is_builtin=False,
                )
            )
            created_slugs.append(slug)
        session.commit()
        return TagAdoptionSummary(
            created_count=len(created_slugs),
            created_slugs=created_slugs,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


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
            session.query(Tag)
            .filter_by(category_id=category_id, is_active=True)
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
                session.query(Tag)
                .filter_by(category_id=cat.id, is_active=True)
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
                session.query(Tag)
                .filter_by(category_id=cat.id, is_active=True)
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
                session.query(Tag)
                .filter_by(category_id=cat.id, is_active=True)
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
                session.query(Tag)
                .filter_by(category_id=cat.id, is_active=True)
                .all()
            )
            for t in tags:
                result[t.slug] = cat.name
        return result
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
                session.query(Tag)
                .filter_by(category_id=cat.id, is_active=True)
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

        tag = Tag(
            category_id=category_id,
            name=display_name,
            slug=slug,
            sort_order=max_order + 1,
            is_active=True,
            is_builtin=False,
        )
        session.add(tag)
        session.commit()
        return True, "Tag created."
    except Exception as exc:
        session.rollback()
        return False, f"Database error: {exc}"
    finally:
        session.close()
