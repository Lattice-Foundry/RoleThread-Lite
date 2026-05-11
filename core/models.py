"""SQLAlchemy ORM models for LoreForge metadata."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.tag_constants import TAG_STATUS_ACTIVE


def _utc_timestamp() -> str:
    """Return an ISO timestamp for registry metadata rows."""
    return datetime.now(timezone.utc).isoformat()


# ── Base ───────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for LoreForge ORM models."""

    pass


# ── TagCategory ────────────────────────────────────────────────────────────────
class TagCategory(Base):
    """A named category that groups related tags."""
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
    """A single tag that can be applied to a dataset entry."""
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tag_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tag_categories.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TAG_STATUS_ACTIVE
    )

    # Many-to-one back-reference
    category: Mapped["TagCategory | None"] = relationship(
        "TagCategory", back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag id={self.id} slug={self.slug!r} category_id={self.category_id}>"


class TagLifecycleMetadata(Base):
    """Current lifecycle metadata and resolver intelligence for one tag slug."""
    __tablename__ = "tag_lifecycle_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    old_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    old_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    old_category_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    new_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    new_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    new_category_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(40), nullable=False, default=_utc_timestamp
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<TagLifecycleMetadata id={self.id} action={self.action!r}>"


class CategoryHistory(Base):
    """Append-only lifecycle history for category slug changes and retirement."""
    __tablename__ = "category_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    old_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    old_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    new_slug: Mapped[str | None] = mapped_column(String(120), nullable=True)
    new_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[str] = mapped_column(
        String(40), nullable=False, default=_utc_timestamp
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<CategoryHistory id={self.id} action={self.action!r}>"
