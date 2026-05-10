import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.tag_registry as tag_registry
from core.models import Base, Tag, TagCategory


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


def test_ensure_tags_exist_for_dataset_does_not_duplicate_known_tags(tag_db):
    tag_registry.ensure_unsorted_category()

    first = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow_burn"]}])
    second = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow-burn"]}])

    assert first.created_count == 1
    assert second.created_count == 0

    registry = tag_registry.get_full_tag_registry()
    unsorted_tags = registry[0]["tags"]
    assert [tag["slug"] for tag in unsorted_tags] == ["slow_burn"]
