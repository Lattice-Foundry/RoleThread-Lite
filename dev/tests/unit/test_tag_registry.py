import json

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker

import core.tag_registry as tag_registry
from core.dataset import normalize_dataset_tags
from core.models import (
    Base,
    CategoryHistory,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
    TAG_STATUS_UNCATEGORIZED,
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
    monkeypatch.setattr(
        tag_registry,
        "create_db_backup",
        lambda *, engine: tmp_path / "db_backup.sqlite",
    )
    return session_factory


def _add_category(session, *, name="Behavior", slug="behavior", active=True):
    category = TagCategory(
        name=name,
        slug=slug,
        sort_order=0,
        is_active=active,
    )
    session.add(category)
    session.flush()
    return category


def _add_tag(
    session,
    *,
    slug,
    name=None,
    category=None,
    status=TAG_STATUS_ACTIVE,
    active=True,
):
    tag = Tag(
        category_id=category.id if category is not None else None,
        name=name or tag_registry.prettify_tag_name(slug),
        slug=slug,
        sort_order=0,
        is_active=active,
        is_builtin=False,
        status=status,
    )
    session.add(tag)
    session.flush()
    return tag


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


@pytest.mark.parametrize(
    "raw",
    ["Slow Burn", "slow burn", "slow-burn", "SLOW BURN"],
)
def test_resolve_tag_lifecycle_normalizes_raw_values(tag_db, raw):
    result = tag_registry.resolve_tag_lifecycle(raw)

    assert result.normalized_slug == "slow_burn"
    assert result.normalized_display_name == "Slow Burn"
    assert result.resolved_slug == "slow_burn"
    assert result.result_type == tag_registry.TAG_RESOLUTION_UNKNOWN
    assert result.should_create_archived is True


def test_resolve_tag_lifecycle_returns_active_for_active_categorized_tag(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="slow_burn", category=category)
        session.commit()
    finally:
        session.close()

    result = tag_registry.resolve_tag_lifecycle("Slow Burn")

    assert result.result_type == tag_registry.TAG_RESOLUTION_ACTIVE
    assert result.resolved_slug == "slow_burn"
    assert result.should_rewrite_slug is False
    assert result.should_create_uncategorized is False


@pytest.mark.parametrize(
    "action",
    [tag_registry.TAG_HISTORY_RENAME, tag_registry.TAG_HISTORY_MERGE],
)
def test_resolve_tag_lifecycle_maps_alias_history_to_active_target(tag_db, action):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="new_tag", category=category)
        session.add(
            TagHistory(
                action=action,
                old_slug="old_tag",
                old_display_name="Old Tag",
                new_slug="new_tag",
                new_display_name="New Tag",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_registry.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == tag_registry.TAG_RESOLUTION_ALIAS_MAPPED
    assert result.resolved_slug == "new_tag"
    assert result.target_slug == "new_tag"
    assert result.should_rewrite_slug is True
    assert result.reason == action


def test_resolve_tag_lifecycle_follows_alias_lineage_to_active_target(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="final_tag", category=category)
        session.add_all(
            [
                TagHistory(
                    action=tag_registry.TAG_HISTORY_RENAME,
                    old_slug="old_tag",
                    new_slug="middle_tag",
                ),
                TagHistory(
                    action=tag_registry.TAG_HISTORY_MERGE,
                    old_slug="middle_tag",
                    new_slug="final_tag",
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    result = tag_registry.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == tag_registry.TAG_RESOLUTION_ALIAS_MAPPED
    assert result.resolved_slug == "final_tag"
    assert result.should_rewrite_slug is True


def test_resolve_tag_lifecycle_does_not_map_alias_when_target_is_missing(tag_db):
    session = tag_db()
    try:
        session.add(
            TagHistory(
                action=tag_registry.TAG_HISTORY_RENAME,
                old_slug="old_tag",
                new_slug="missing_tag",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_registry.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == tag_registry.TAG_RESOLUTION_UNKNOWN
    assert result.resolved_slug == "old_tag"
    assert result.should_rewrite_slug is False
    assert result.should_create_archived is True


def test_resolve_tag_lifecycle_does_not_map_alias_when_target_is_not_active(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(
            session,
            slug="archived_target",
            category=category,
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        session.add(
            TagHistory(
                action=tag_registry.TAG_HISTORY_MERGE,
                old_slug="old_tag",
                new_slug="archived_target",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_registry.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == tag_registry.TAG_RESOLUTION_UNKNOWN
    assert result.should_rewrite_slug is False
    assert result.should_create_archived is True


@pytest.mark.parametrize(
    ("status", "result_type"),
    [
        (TAG_STATUS_UNCATEGORIZED, tag_registry.TAG_RESOLUTION_UNCATEGORIZED),
        (TAG_STATUS_ARCHIVED, tag_registry.TAG_RESOLUTION_ARCHIVED),
        (TAG_STATUS_HIDDEN, tag_registry.TAG_RESOLUTION_HIDDEN),
    ],
)
def test_resolve_tag_lifecycle_recognizes_existing_inactive_states(
    tag_db, status, result_type
):
    session = tag_db()
    try:
        _add_tag(session, slug="legacy_tag", status=status, active=False)
        session.commit()
    finally:
        session.close()

    result = tag_registry.resolve_tag_lifecycle("Legacy Tag")

    assert result.result_type == result_type
    assert result.resolved_slug == "legacy_tag"
    assert result.should_skip_creation is True
    assert result.should_create_uncategorized is False


@pytest.mark.parametrize(
    "action",
    [
        tag_registry.TAG_HISTORY_HIDE,
        tag_registry.TAG_HISTORY_DELETE,
        tag_registry.TAG_HISTORY_ARCHIVE,
    ],
)
def test_resolve_tag_lifecycle_recognizes_retired_history_without_target(tag_db, action):
    session = tag_db()
    try:
        session.add(
            TagHistory(
                action=action,
                old_slug="retired_tag",
                old_display_name="Retired Tag",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_registry.resolve_tag_lifecycle("Retired Tag")

    assert result.result_type == tag_registry.TAG_RESOLUTION_RETIRED
    assert result.resolved_slug == "retired_tag"
    assert result.should_skip_creation is True
    assert result.should_create_uncategorized is False


def test_resolve_tag_lifecycle_returns_unknown_for_truly_unknown_tag(tag_db):
    result = tag_registry.resolve_tag_lifecycle("Brand New")

    assert result.result_type == tag_registry.TAG_RESOLUTION_UNKNOWN
    assert result.normalized_slug == "brand_new"
    assert result.resolved_slug == "brand_new"
    assert result.should_create_archived is True
    assert result.should_skip_creation is False


def test_active_registry_helpers_exclude_lifecycle_inactive_tags(tag_db):
    session = tag_db()
    try:
        active_category = _add_category(session, name="Behavior", slug="behavior")
        inactive_category = _add_category(
            session,
            name="Retired Category",
            slug="retired_category",
            active=False,
        )
        _add_tag(session, slug="active_tag", category=active_category)
        _add_tag(
            session,
            slug="uncategorized_tag",
            status=TAG_STATUS_UNCATEGORIZED,
            active=False,
        )
        _add_tag(
            session,
            slug="archived_tag",
            category=active_category,
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        _add_tag(
            session,
            slug="hidden_tag",
            category=active_category,
            status=TAG_STATUS_HIDDEN,
            active=False,
        )
        _add_tag(session, slug="no_category_active_tag", category=None)
        _add_tag(
            session,
            slug="inactive_category_tag",
            category=inactive_category,
        )
        session.commit()
    finally:
        session.close()

    assert tag_registry.get_tag_registry_dict() == {"Behavior": ["active_tag"]}
    assert tag_registry.get_all_tag_slugs() == ["active_tag"]
    assert tag_registry.get_tag_category_map() == {"active_tag": "Behavior"}

    label_map = tag_registry.get_tag_label_map(include_untagged=False)
    assert label_map == {"active_tag": "Behavior / Active Tag"}

    full_registry = tag_registry.get_full_tag_registry()
    assert len(full_registry) == 1
    assert full_registry[0]["name"] == "Behavior"
    assert [tag["slug"] for tag in full_registry[0]["tags"]] == ["active_tag"]

    session = tag_db()
    try:
        active_category = session.query(TagCategory).filter_by(slug="behavior").one()
        inactive_category = (
            session.query(TagCategory).filter_by(slug="retired_category").one()
        )
    finally:
        session.close()
    assert [tag.slug for tag in tag_registry.get_active_tags(active_category.id)] == [
        "active_tag"
    ]
    assert tag_registry.get_active_tags(inactive_category.id) == []


def test_active_registry_helpers_keep_empty_active_categories(tag_db):
    session = tag_db()
    try:
        _add_category(session, name="Empty", slug="empty")
        session.commit()
    finally:
        session.close()

    assert tag_registry.get_tag_registry_dict() == {"Empty": []}
    full_registry = tag_registry.get_full_tag_registry()
    assert full_registry == [
        {
            "id": full_registry[0]["id"],
            "name": "Empty",
            "slug": "empty",
            "sort_order": 0,
            "tags": [],
        }
    ]


def test_lifecycle_specific_helpers_return_status_scoped_tags(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="active_tag", category=category)
        _add_tag(
            session,
            slug="uncategorized_tag",
            status=TAG_STATUS_UNCATEGORIZED,
            active=False,
        )
        _add_tag(
            session,
            slug="archived_tag",
            category=category,
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        _add_tag(
            session,
            slug="hidden_tag",
            category=category,
            status=TAG_STATUS_HIDDEN,
            active=False,
        )
        session.commit()
    finally:
        session.close()

    assert [tag["slug"] for tag in tag_registry.get_uncategorized_tags()] == [
        "uncategorized_tag"
    ]
    assert [tag["slug"] for tag in tag_registry.get_archived_tags()] == ["archived_tag"]
    assert [tag["slug"] for tag in tag_registry.get_hidden_tags()] == ["hidden_tag"]
    assert [tag["slug"] for tag in tag_registry.get_tags_by_status(TAG_STATUS_ACTIVE)] == [
        "active_tag"
    ]

    uncategorized = tag_registry.get_uncategorized_tags()[0]
    archived = tag_registry.get_archived_tags()[0]
    assert uncategorized["category_id"] is None
    assert uncategorized["status"] == TAG_STATUS_UNCATEGORIZED
    assert archived["category_name"] == "Behavior"
    assert archived["status"] == TAG_STATUS_ARCHIVED

    imported = tag_registry.get_imported_archived_tags()
    deleted = tag_registry.get_deleted_archived_tags()
    assert [tag["slug"] for tag in imported] == ["uncategorized_tag"]
    assert imported[0]["visible_badge"] == "Imported"
    assert [tag["slug"] for tag in deleted] == ["archived_tag"]
    assert deleted[0]["visible_badge"] == "Deleted"

    visible_archived = tag_registry.get_visible_archived_tags()
    assert [tag["name"] for tag in visible_archived] == [
        "Archived Tag",
        "Uncategorized Tag",
    ]
    assert [tag["visible_badge"] for tag in visible_archived] == [
        "Deleted",
        "Imported",
    ]
    assert "hidden_tag" not in [tag["slug"] for tag in visible_archived]


@pytest.mark.parametrize(
    ("slug", "status"),
    [
        ("active_tag", TAG_STATUS_ACTIVE),
        ("uncategorized_tag", TAG_STATUS_UNCATEGORIZED),
        ("archived_tag", TAG_STATUS_ARCHIVED),
        ("hidden_tag", TAG_STATUS_HIDDEN),
    ],
)
def test_get_tag_by_slug_any_status_finds_lifecycle_tags(tag_db, slug, status):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="active_tag", category=category)
        _add_tag(
            session,
            slug="uncategorized_tag",
            status=TAG_STATUS_UNCATEGORIZED,
            active=False,
        )
        _add_tag(
            session,
            slug="archived_tag",
            category=category,
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        _add_tag(
            session,
            slug="hidden_tag",
            category=category,
            status=TAG_STATUS_HIDDEN,
            active=False,
        )
        session.commit()
    finally:
        session.close()

    tag = tag_registry.get_tag_by_slug_any_status(slug.replace("_", " "))

    assert tag is not None
    assert tag.slug == slug
    assert tag.status == status


def test_ensure_archived_import_tag_creates_inactive_archived_with_history(tag_db):
    result = tag_registry.ensure_archived_import_tag("Slow Burn")

    assert result.result_type == tag_registry.TAG_RESOLUTION_ARCHIVED
    assert result.normalized_slug == "slow_burn"
    assert result.should_create_archived is False
    assert result.should_skip_creation is True
    assert result.reason == tag_registry.TAG_HISTORY_IMPORT_ARCHIVED

    session = tag_db()
    try:
        tag = session.query(Tag).filter_by(slug="slow_burn").one()
        assert tag.name == "Slow Burn"
        assert tag.status == TAG_STATUS_ARCHIVED
        assert tag.category_id is None
        assert tag.is_active is False
        assert tag.is_builtin is False

        history = session.query(TagHistory).one()
        assert history.action == tag_registry.TAG_HISTORY_IMPORT_ARCHIVED
        assert history.old_slug == "slow_burn"
        assert history.old_display_name == "Slow Burn"
        assert history.old_category_slug is None
        assert history.new_slug == "slow_burn"
        assert history.new_display_name == "Slow Burn"
        assert history.new_category_slug is None
        metadata = json.loads(history.metadata_json)
        assert metadata["archive_origin"] == "imported"
        assert metadata["archive_reason"] == "unknown_import"
        assert metadata["visible_badge"] == "Imported"
    finally:
        session.close()

    assert tag_registry.get_tag_registry_dict() == {}
    assert [tag["slug"] for tag in tag_registry.get_imported_archived_tags()] == [
        "slow_burn"
    ]


def test_ensure_uncategorized_tag_reuses_existing_uncategorized_tag(tag_db):
    session = tag_db()
    try:
        _add_tag(
            session,
            slug="slow_burn",
            status=TAG_STATUS_UNCATEGORIZED,
            active=False,
        )
        session.commit()
    finally:
        session.close()

    result = tag_registry.ensure_uncategorized_tag("Slow Burn")

    assert result.result_type == tag_registry.TAG_RESOLUTION_UNCATEGORIZED
    assert result.should_skip_creation is True

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="slow_burn").count() == 1
        assert session.query(TagHistory).count() == 0
    finally:
        session.close()


def test_ensure_uncategorized_tag_does_not_duplicate_active_tag(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="slow_burn", category=category)
        session.commit()
    finally:
        session.close()

    result = tag_registry.ensure_uncategorized_tag("Slow Burn")

    assert result.result_type == tag_registry.TAG_RESOLUTION_ACTIVE
    assert result.should_create_uncategorized is False

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="slow_burn").count() == 1
        assert session.query(TagHistory).count() == 0
    finally:
        session.close()


@pytest.mark.parametrize(
    ("status", "result_type"),
    [
        (TAG_STATUS_ARCHIVED, tag_registry.TAG_RESOLUTION_ARCHIVED),
        (TAG_STATUS_HIDDEN, tag_registry.TAG_RESOLUTION_HIDDEN),
    ],
)
def test_ensure_uncategorized_tag_does_not_reactivate_archived_or_hidden(
    tag_db, status, result_type
):
    session = tag_db()
    try:
        _add_tag(session, slug="legacy_tag", status=status, active=False)
        session.commit()
    finally:
        session.close()

    result = tag_registry.ensure_uncategorized_tag("Legacy Tag")

    assert result.result_type == result_type
    assert result.should_skip_creation is True

    session = tag_db()
    try:
        tag = session.query(Tag).filter_by(slug="legacy_tag").one()
        assert tag.status == status
        assert tag.is_active is False
        assert session.query(TagHistory).count() == 0
    finally:
        session.close()


def test_ensure_uncategorized_tag_does_not_create_for_alias_mapped_slug(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="new_tag", category=category)
        session.add(
            TagHistory(
                action=tag_registry.TAG_HISTORY_RENAME,
                old_slug="old_tag",
                new_slug="new_tag",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_registry.ensure_uncategorized_tag("Old Tag")

    assert result.result_type == tag_registry.TAG_RESOLUTION_ALIAS_MAPPED
    assert result.resolved_slug == "new_tag"
    assert result.should_rewrite_slug is True

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="old_tag").count() == 0
        assert session.query(Tag).filter_by(slug="new_tag").count() == 1
        assert session.query(TagHistory).count() == 1
    finally:
        session.close()


def test_ensure_uncategorized_tag_does_not_create_for_retired_history(tag_db):
    session = tag_db()
    try:
        session.add(
            TagHistory(
                action=tag_registry.TAG_HISTORY_HIDE,
                old_slug="retired_tag",
                old_display_name="Retired Tag",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_registry.ensure_uncategorized_tag("Retired Tag")

    assert result.result_type == tag_registry.TAG_RESOLUTION_RETIRED
    assert result.should_skip_creation is True

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="retired_tag").count() == 0
        assert session.query(TagHistory).count() == 1
    finally:
        session.close()


def test_ensure_archived_import_tags_for_dataset_creates_only_unknown_tags(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="known_tag", category=category)
        _add_tag(
            session,
            slug="old_uncategorized",
            status=TAG_STATUS_UNCATEGORIZED,
            active=False,
        )
        session.commit()
    finally:
        session.close()

    summary = tag_registry.ensure_archived_import_tags_for_dataset(
        [
            {"tags": ["known_tag", "new tag"]},
            {"tags": ["old_uncategorized", "new-tag"]},
        ]
    )

    assert summary.created_count == 1
    assert summary.created_slugs == ["new_tag"]
    assert summary.existing_slugs == ["known_tag", "old_uncategorized"]
    assert summary.skipped_slugs == []

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="new_tag").one().status == (
            TAG_STATUS_ARCHIVED
        )
        assert session.query(TagHistory).filter_by(
            action=tag_registry.TAG_HISTORY_IMPORT_ARCHIVED
        ).count() == 1
    finally:
        session.close()


def test_archived_import_dataset_adoption_creates_one_db_backup(tag_db, monkeypatch):
    backup_calls = []

    def fake_backup(*, engine):
        backup_calls.append(engine.url.database)
        return "backup.sqlite"

    monkeypatch.setattr(tag_registry, "create_db_backup", fake_backup)

    summary = tag_registry.ensure_archived_import_tags_for_dataset(
        [
            {"tags": ["new tag", "another tag"]},
            {"tags": ["new-tag"]},
        ]
    )

    assert summary.created_count == 2
    assert backup_calls == [tag_registry.engine.url.database]


def test_archived_import_backup_failure_aborts_mutation(tag_db, monkeypatch):
    def fail_backup(*, engine):
        raise OSError("backup failed")

    monkeypatch.setattr(tag_registry, "create_db_backup", fail_backup)

    with pytest.raises(OSError, match="backup failed"):
        tag_registry.ensure_archived_import_tag("Slow Burn")

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="slow_burn").count() == 0
        assert session.query(TagHistory).count() == 0
    finally:
        session.close()


def test_custom_tag_backup_failure_aborts_mutation(tag_db, monkeypatch):
    session = tag_db()
    try:
        category = _add_category(session)
        category_id = category.id
        session.commit()
    finally:
        session.close()

    def fail_backup(*, engine):
        raise OSError("backup failed")

    monkeypatch.setattr(tag_registry, "create_db_backup", fail_backup)

    ok, message = tag_registry.create_custom_tag(category_id, "Slow Burn")

    assert ok is False
    assert "Could not create database backup" in message

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="slow_burn").count() == 0
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_adopts_unknown_tags_as_archived_imported(tag_db):
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
    assert unsorted_tags == []

    behavior = next(category for category in registry if category["name"] == "Behavior")
    assert [tag["slug"] for tag in behavior["tags"]] == ["reviewed"]
    assert "slow_burn" not in tag_registry.get_all_tag_slugs()
    assert [tag["slug"] for tag in tag_registry.get_imported_archived_tags()] == [
        "slow_burn"
    ]

    session = tag_db()
    try:
        adopted = session.query(Tag).filter_by(slug="slow_burn").one()
        unsorted = session.query(TagCategory).filter_by(slug="unsorted").one()
        assert adopted.status == TAG_STATUS_ARCHIVED
        assert adopted.category_id is None
        assert adopted.is_active is False
        assert adopted.category_id != unsorted.id
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_writes_import_archived_history(tag_db):
    summary = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow-burn"]}])

    assert summary.created_count == 1
    assert summary.created_slugs == ["slow_burn"]

    session = tag_db()
    try:
        history = session.query(TagHistory).one()
        assert history.action == tag_registry.TAG_HISTORY_IMPORT_ARCHIVED
        assert history.old_slug == "slow_burn"
        assert history.old_display_name == "Slow Burn"
        metadata = json.loads(history.metadata_json)
        assert metadata["archive_origin"] == "imported"
        assert metadata["visible_badge"] == "Imported"
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_does_not_reactivate_inactive_lifecycle_tags(tag_db):
    session = tag_db()
    try:
        _add_tag(
            session,
            slug="archived_tag",
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        _add_tag(
            session,
            slug="hidden_tag",
            status=TAG_STATUS_HIDDEN,
            active=False,
        )
        session.add(
            TagHistory(
                action=tag_registry.TAG_HISTORY_HIDE,
                old_slug="retired_tag",
                old_display_name="Retired Tag",
            )
        )
        session.commit()
    finally:
        session.close()

    summary = tag_registry.ensure_tags_exist_for_dataset(
        [{"tags": ["archived_tag", "hidden_tag", "retired_tag"]}]
    )

    assert summary.created_count == 0
    assert summary.created_slugs == []

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="archived_tag").one().status == (
            TAG_STATUS_ARCHIVED
        )
        assert session.query(Tag).filter_by(slug="hidden_tag").one().status == (
            TAG_STATUS_HIDDEN
        )
        assert session.query(Tag).filter_by(slug="retired_tag").count() == 0
        assert session.query(TagHistory).count() == 1
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_does_not_duplicate_imported_archived_tags(tag_db):
    tag_registry.ensure_unsorted_category()

    first = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow_burn"]}])
    second = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow-burn"]}])

    assert first.created_count == 1
    assert second.created_count == 0

    registry = tag_registry.get_full_tag_registry()
    unsorted_tags = registry[0]["tags"]
    assert unsorted_tags == []
    assert [tag["slug"] for tag in tag_registry.get_imported_archived_tags()] == [
        "slow_burn"
    ]


def test_ensure_tags_exist_preserves_normalized_entry_tag_slugs(tag_db):
    summary = normalize_dataset_tags([{"messages": [], "tags": ["sLow burn"]}])

    adoption = tag_registry.ensure_tags_exist_for_dataset(summary.entries)

    assert summary.entries[0]["tags"] == ["slow_burn"]
    assert adoption.created_slugs == ["slow_burn"]
    assert [tag["slug"] for tag in tag_registry.get_imported_archived_tags()] == [
        "slow_burn"
    ]


def test_existing_unsorted_active_tags_remain_active_until_migration(tag_db):
    unsorted = tag_registry.ensure_unsorted_category()
    session = tag_db()
    try:
        _add_tag(session, slug="old_unsorted_tag", category=unsorted)
        session.commit()
    finally:
        session.close()

    registry = tag_registry.get_full_tag_registry()

    unsorted_category = next(
        category for category in registry if category["name"] == "Unsorted"
    )
    assert [tag["slug"] for tag in unsorted_category["tags"]] == ["old_unsorted_tag"]
    assert "old_unsorted_tag" in tag_registry.get_all_tag_slugs()


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
