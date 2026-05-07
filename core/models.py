"""SQLAlchemy ORM models for LoreForge.

Models
------
TagCategory  — a named group of tags (e.g. "Behavior", "Scene")
Tag          — a single tag belonging to a category

Both models use SQLAlchemy 2.x declarative style (DeclarativeBase,
Mapped, mapped_column).
"""
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── Base ───────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── TagCategory ────────────────────────────────────────────────────────────────
class TagCategory(Base):
    """A named category that groups related tags.

    Columns
    -------
    id          — auto-increment primary key
    name        — display name (e.g. "Behavior")
    slug        — URL/code-safe identifier derived from name (e.g. "behavior")
    sort_order  — integer used to preserve display order; lower = earlier
    is_active   — soft-delete flag; inactive categories are hidden in the UI
    """
    __tablename__ = "tag_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # One-to-many: a category owns many tags
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="Tag.sort_order",
    )

    def __repr__(self) -> str:
        return f"<TagCategory id={self.id} slug={self.slug!r}>"


# ── Tag ────────────────────────────────────────────────────────────────────────
class Tag(Base):
    """A single tag that can be applied to a dataset entry.

    Columns
    -------
    id           — auto-increment primary key
    category_id  — FK → tag_categories.id
    name         — display name / slug (e.g. "pacing")
    sort_order   — integer used to preserve display order within a category
    is_active    — soft-delete flag; inactive tags are hidden in the UI
    is_builtin   — True for tags seeded from the hardcoded TAGS dict; False
                   for tags added by the user in the future Custom Tags UI
    """
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tag_categories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Many-to-one back-reference
    category: Mapped["TagCategory"] = relationship("TagCategory", back_populates="tags")

    def __repr__(self) -> str:
        return f"<Tag id={self.id} name={self.name!r} category_id={self.category_id}>"
