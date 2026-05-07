"""Tag registry helpers for LoreForge.

Public API
----------
slugify_tag_name(name)       — normalise a display name to a slug
seed_default_tags()          — idempotently seed TAGS dict into the DB
get_active_tag_categories()  — return active TagCategory rows, ordered
get_active_tags(category_id) — return active Tag rows for a category
get_tag_registry_dict()      — return {category_name: [tag_name, ...], ...}
                                for active categories/tags (mirrors TAGS shape)
"""
import re

from core.dataset import TAGS
from core.db import SessionLocal, init_db
from core.models import Tag, TagCategory


# ── Slug helper ────────────────────────────────────────────────────────────────

def slugify_tag_name(name: str) -> str:
    """Convert a display name to a lowercase, hyphen-separated slug.

    Examples
    --------
    "Behavior"       → "behavior"
    "Source & Status" → "source-status"
    "no_user_control" → "no-user-control"
    """
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


# ── Seeding ────────────────────────────────────────────────────────────────────

def seed_default_tags() -> None:
    """Idempotently seed the hardcoded TAGS dict into the database.

    Behaviour
    ---------
    - Calls init_db() first to ensure tables exist.
    - For each category in TAGS (in definition order):
        * Gets or creates a TagCategory row matched by slug.
        * Updates name and sort_order if the row already exists (allows
          display-name fixes without losing custom tags).
        * For each tag name in the category:
            - Gets or creates a Tag row matched by (category_id, name).
            - Ensures is_builtin=True and preserves sort_order.
            - Never deletes existing tags (user may have applied them to
              entries that are already saved to disk).
    - Commits once at the end.  Rolls back on any error and re-raises.
    """
    init_db()

    session = SessionLocal()
    try:
        for cat_order, (cat_name, tag_names) in enumerate(TAGS.items()):
            cat_slug = slugify_tag_name(cat_name)

            # Get or create category
            category = session.query(TagCategory).filter_by(slug=cat_slug).first()
            if category is None:
                category = TagCategory(
                    name=cat_name,
                    slug=cat_slug,
                    sort_order=cat_order,
                    is_active=True,
                )
                session.add(category)
                session.flush()  # populate category.id before inserting tags
            else:
                # Update mutable fields in case the display name changed
                category.name = cat_name
                category.sort_order = cat_order

            # Get or create each tag in this category
            for tag_order, tag_name in enumerate(tag_names):
                tag = (
                    session.query(Tag)
                    .filter_by(category_id=category.id, name=tag_name)
                    .first()
                )
                if tag is None:
                    tag = Tag(
                        category_id=category.id,
                        name=tag_name,
                        sort_order=tag_order,
                        is_active=True,
                        is_builtin=True,
                    )
                    session.add(tag)
                else:
                    # Ensure built-in flag and update sort order
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
            .order_by(Tag.sort_order, Tag.name)
            .all()
        )
    finally:
        session.close()


def get_tag_registry_dict() -> dict[str, list[str]]:
    """Return active tags as {category_name: [tag_name, ...]} (mirrors TAGS shape).

    Only includes active categories and active tags.  Order follows sort_order.
    Returns an empty dict if the database has not been seeded yet.
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
                .order_by(Tag.sort_order, Tag.name)
                .all()
            )
            result[cat.name] = [t.name for t in tags]
        return result
    finally:
        session.close()
