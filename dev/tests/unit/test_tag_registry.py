import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker

import core.tag_registry as tag_registry
from core.models import (
    Base,
    CategoryHistory,
    TAG_STATUS_ACTIVE,
    Tag,
    TagCategory,
    TagHistory,
)


@pytest.fixture
def tag_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'tag_registry.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(tag_registry, "engine", engine)
    monkeypatch.setattr(tag_registry, "SessionLocal", session_factory)
    return session_factory


def test_ensure_unsorted_category_creates_protected_first_category(tag_db):
    category = tag_registry.ensure_unsorted_category()

    assert category.name == "Unsorted"
    assert category.slug == "unsorted"
    assert category.sort_order == tag_registry.UNSORTED_SORT_ORDER

    registry = tag_registry.get_full_tag_registry()
    assert registry[0]["name"] == "Unsorted"


def test_tag_lifecycle_schema_exists_for_fresh_database(tag_db):
    inspector = sa_inspect(tag_registry.engine)

    assert "tag_history" in inspector.get_table_names()
    assert "category_history" in inspector.get_table_names()

    tag_columns = {column["name"]: column for column in inspector.get_columns("tags")}
    assert tag_columns["status"]["nullable"] is False
    assert tag_columns["category_id"]["nullable"] is True


def test_tags_default_to_active_and_can_have_no_category(tag_db):
    session = tag_db()
    try:
        tag = Tag(
            category_id=None,
            name="Loose Tag",
            slug="loose_tag",
            sort_order=0,
            is_active=True,
            is_builtin=False,
        )
        session.add(tag)
        session.commit()
        session.refresh(tag)

        assert tag.status == TAG_STATUS_ACTIVE
        assert tag.category_id is None
    finally:
        session.close()


def test_history_models_can_be_inserted(tag_db):
    session = tag_db()
    try:
        tag_history = TagHistory(
            action="rename",
            old_slug="old_tag",
            old_display_name="Old Tag",
            new_slug="new_tag",
            new_display_name="New Tag",
        )
        category_history = CategoryHistory(
            action="rename",
            old_slug="old_category",
            old_display_name="Old Category",
            new_slug="new_category",
            new_display_name="New Category",
        )
        session.add_all([tag_history, category_history])
        session.commit()

        assert session.query(TagHistory).count() == 1
        assert session.query(CategoryHistory).count() == 1
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_adopts_unknown_tags_under_unsorted(tag_db):
    tag_registry.ensure_unsorted_category()
    session = tag_db()
    try:
        known_category = TagCategory(
            name="Behavior",
            slug="behavior",
            sort_order=0,
            is_active=True,
        )
        session.add(known_category)
        session.flush()
        session.add(
            Tag(
                category_id=known_category.id,
                name="Reviewed",
                slug="reviewed",
                sort_order=0,
                is_active=True,
                is_builtin=True,
            )
        )
        session.commit()
    finally:
        session.close()

    summary = tag_registry.ensure_tags_exist_for_dataset(
        [{"tags": ["reviewed", "slow_burn"]}]
    )

    assert summary.created_count == 1
    assert summary.created_slugs == ["slow_burn"]

    registry = tag_registry.get_full_tag_registry()
    assert registry[0]["name"] == "Unsorted"
    unsorted_tags = registry[0]["tags"]
    assert [tag["slug"] for tag in unsorted_tags] == ["slow_burn"]
    assert unsorted_tags[0]["name"] == "Slow Burn"

    behavior = next(category for category in registry if category["name"] == "Behavior")
    assert [tag["slug"] for tag in behavior["tags"]] == ["reviewed"]

    session = tag_db()
    try:
        adopted = session.query(Tag).filter_by(slug="slow_burn").one()
        unsorted = session.query(TagCategory).filter_by(slug="unsorted").one()
        assert adopted.status == TAG_STATUS_ACTIVE
        assert adopted.category_id == unsorted.id
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_does_not_duplicate_known_tags(tag_db):
    tag_registry.ensure_unsorted_category()

    first = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow_burn"]}])
    second = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow-burn"]}])

    assert first.created_count == 1
    assert second.created_count == 0

    registry = tag_registry.get_full_tag_registry()
    unsorted_tags = registry[0]["tags"]
    assert [tag["slug"] for tag in unsorted_tags] == ["slow_burn"]


def test_lifecycle_migration_updates_legacy_tags_table(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'legacy_tag_registry.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(tag_registry, "engine", engine)
    monkeypatch.setattr(tag_registry, "SessionLocal", session_factory)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tag_categories (
                    id INTEGER NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    slug VARCHAR(120) NOT NULL,
                    sort_order INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    PRIMARY KEY (id),
                    UNIQUE (name),
                    UNIQUE (slug)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE tags (
                    id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    sort_order INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    is_builtin BOOLEAN NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(category_id) REFERENCES tag_categories (id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO tag_categories (id, name, slug, sort_order, is_active)
                VALUES (1, 'Behavior', 'behavior', 0, 1)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO tags (
                    id,
                    category_id,
                    name,
                    sort_order,
                    is_active,
                    is_builtin
                )
                VALUES (1, 1, 'Needs Edit', 0, 1, 1)
                """
            )
        )

    tag_registry._migrate_tags_slug_column()
    tag_registry._migrate_tag_lifecycle_schema()
    tag_registry._migrate_tag_lifecycle_schema()

    inspector = sa_inspect(engine)
    assert "tag_history" in inspector.get_table_names()
    assert "category_history" in inspector.get_table_names()

    tag_columns = {column["name"]: column for column in inspector.get_columns("tags")}
    assert tag_columns["status"]["nullable"] is False
    assert tag_columns["category_id"]["nullable"] is True

    session = session_factory()
    try:
        tag = session.query(Tag).one()
        assert tag.slug == "needs_edit"
        assert tag.name == "Needs Edit"
        assert tag.status == TAG_STATUS_ACTIVE
        assert tag.category_id == 1
    finally:
        session.close()
