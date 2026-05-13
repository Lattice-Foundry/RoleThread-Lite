"""SQLAlchemy ORM models for LoreForge metadata."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.tag_constants import TAG_STATUS_ACTIVE


def _utc_timestamp() -> str:
    """Return an ISO timestamp for registry metadata rows."""
    return datetime.now(timezone.utc).isoformat()


def _utc_datetime() -> datetime:
    """Return a UTC datetime for ORM timestamp columns."""
    return datetime.now(timezone.utc)


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


class Character(Base):
    """A reusable character identity for dataset previews and mappings."""
    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_character_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_datetime
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_datetime,
        onupdate=_utc_datetime,
    )

    turn_mappings: Mapped[list["EntryCharacterTurn"]] = relationship(
        "EntryCharacterTurn",
        back_populates="character",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Character id={self.id} slug={self.slug!r}>"


class EntryCharacterTurn(Base):
    """Character assignment for one turn in one stamped dataset entry."""
    __tablename__ = "entry_character_turns"
    __table_args__ = (
        UniqueConstraint("entry_uuid", "turn_index", name="uq_entry_character_turn"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    character_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    training_role: Mapped[str] = mapped_column(String(32), nullable=False)
    source_role_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_datetime
    )

    character: Mapped["Character"] = relationship(
        "Character",
        back_populates="turn_mappings",
    )

    def __repr__(self) -> str:
        return (
            f"<EntryCharacterTurn entry_uuid={self.entry_uuid!r} "
            f"turn_index={self.turn_index}>"
        )


class SystemPromptTemplate(Base):
    """Reusable system prompt text for entry creation and editing."""
    __tablename__ = "system_prompt_templates"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_system_prompt_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_datetime
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_datetime,
        onupdate=_utc_datetime,
    )

    def __repr__(self) -> str:
        return f"<SystemPromptTemplate id={self.id} slug={self.slug!r}>"


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
