"""Tag registry helpers for LoreForge.

Public API
----------
slugify_tag_name(name)       — normalise any display name to a lowercase_snake_case slug
prettify_tag_name(slug)      — convert a slug to a title-case display label
seed_default_tags()          — idempotently seed TAGS dict into the DB (runs migration)
get_active_tag_categories()  — return active TagCategory rows, ordered
get_active_tags(category_id) — return active Tag rows for a category
get_tag_registry_dict()      — return {category_name: [tag_slug, ...], ...}
                                values are slugs (JSONL canonical identifiers)
get_tag_label_map(include_untagged, untagged_key)
                             — return {slug: "Category / Pretty Name", ...}
                                used for format_func in filter and tag-edit multiselects
get_all_tag_slugs()          — flat list of all active tag slugs in category/sort order
get_tag_category_map()       — return {tag_slug: category_display_name} for all active tags
get_full_tag_registry()      — return list[dict] of categories + tags for UI display
create_custom_category(name) — validate and insert a new user category; returns (ok, msg)
create_custom_tag(category_id, name)
                             — validate and insert a new custom tag; returns (ok, msg)
"""
import re

from sqlalchemy import func, inspect as sa_inspect, text

from core.dataset import TAGS
from core.db import SessionLocal, engine, init_db
from core.models import Tag, TagCategory


# ── Known abbreviations that should stay fully uppercase in display names ──────
_UPPERCASE_WORDS: frozenset[str] = frozenset({"ai", "id"})


# ── Slug helper ────────────────────────────────────────────────────────────────

def slugify_tag_name(name: str) -> str:
    """Convert a display name to a lowercase_snake_case slug.

    Steps
    -----
    1. Strip whitespace and lowercase.
    2. Replace ``&`` with a space so "Source & Status" doesn't become
       "source__status" after step 3.
    3. Replace every run of non-alphanumeric characters with a single ``_``.
    4. Collapse any remaining repeated underscores.
    5. Strip leading/trailing underscores.

    Examples
    --------
    "Behavior"         → "behavior"
    "Source & Status"  → "source_status"
    "no_user_control"  → "no_user_control"
    "AI Generated"     → "ai_generated"
    "emotional-awareness" → "emotional_awareness"
    """
    slug = name.strip().lower()
    slug = slug.replace("&", " ")
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = re.sub(r"_+", "_", slug)
    slug = slug.strip("_")
    return slug


# ── Display-name helper ────────────────────────────────────────────────────────

def prettify_tag_name(slug: str) -> str:
    """Convert a slug to a title-case display label.

    Words listed in ``_UPPERCASE_WORDS`` (e.g. "ai") are rendered fully
    uppercase; all other words are capitalised normally.

    Examples
    --------
    "pacing"             → "Pacing"
    "no_user_control"    → "No User Control"
    "followup_question"  → "Followup Question"
    "emotional_awareness"→ "Emotional Awareness"
    "ai_generated"       → "AI Generated"
    "needs_edit"         → "Needs Edit"
    """
    words = re.split(r"[_\-]+", slug.strip())
    titled = [
        w.upper() if w.lower() in _UPPERCASE_WORDS else w.capitalize()
        for w in words
        if w
    ]
    return " ".join(titled)


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
    """Idempotently seed the hardcoded TAGS dict into the database.

    Behaviour
    ---------
    1. Calls ``init_db()`` to ensure tables exist (idempotent CREATE TABLE).
    2. Calls ``_migrate_tags_slug_column()`` to upgrade existing databases
       that lack the ``slug`` column and backfill any legacy rows.
    3. For each category in TAGS (in definition order):
       - Gets or creates a ``TagCategory`` row matched by slug.
       - Updates ``name`` and ``sort_order`` on existing rows (allows
         display-name fixes without losing custom tags).
    4. For each tag value in the category:
       - Derives ``slug = slugify_tag_name(raw_value)``
         and ``name = prettify_tag_name(slug)``.
       - Primary lookup: ``(category_id, slug)``.
       - Fallback lookup: ``(category_id, name=raw_value)`` for rows that
         were inserted in Phase 1 before slug existed.
       - Creates a new row if neither lookup finds anything.
       - Updates ``slug``, ``name``, ``sort_order``, ``is_builtin`` on hits.
    5. Commits once at the end.  Rolls back on any error and re-raises.
    6. Never deletes existing tags — users may have referenced them in
       saved JSONL entries on disk.
    """
    init_db()
    _migrate_tags_slug_column()

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
    """Return active categories with their active tags as plain dicts.

    Shape::

        [
            {
                "id": 1, "name": "Behavior", "slug": "behavior",
                "sort_order": 0,
                "tags": [
                    {"id": 1, "name": "Pacing", "slug": "pacing",
                     "sort_order": 0, "is_builtin": True},
                    ...
                ],
            },
            ...
        ]

    Returns plain dicts (not ORM objects) so callers never hit detached-
    instance errors after the session is closed.  Returns an empty list if
    the DB is unseeded.
    """
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
    """Validate and insert a new user-defined tag category.

    Rules
    -----
    - Name must be non-empty after stripping.
    - Slug derived via ``slugify_tag_name`` must be non-empty.
    - Slug must not already exist in ``tag_categories``.
    - Active category count must be below ``_MAX_ACTIVE_CATEGORIES``.
    - ``sort_order`` = current max + 1.
    - ``TagCategory`` has no ``is_builtin`` column, so none is set.

    Returns
    -------
    ``(True, "Category created.")`` on success,
    ``(False, "<reason>")`` on any validation or DB error.
    """
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
    """Validate and insert a new custom tag into an existing category.

    Rules
    -----
    - Name must be non-empty after stripping.
    - Slug derived via ``slugify_tag_name`` must be non-empty.
    - Target category must exist and be active.
    - Slug must not already exist **globally** across all tags, because JSONL
      files store tag slugs as flat strings — a collision in any category
      would produce ambiguous entries.
    - ``sort_order`` = current max within the target category + 1.
    - ``is_builtin`` is explicitly set to ``False``.

    Returns
    -------
    ``(True, "Tag created.")`` on success,
    ``(False, "<reason>")`` on any validation or DB error.
    """
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
