"""SQLAlchemy ORM models for LoreForge metadata."""
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tag_categories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Many-to-one back-reference
    category: Mapped["TagCategory"] = relationship("TagCategory", back_populates="tags")

    def __repr__(self) -> str:
        return f"<Tag id={self.id} slug={self.slug!r} category_id={self.category_id}>"
