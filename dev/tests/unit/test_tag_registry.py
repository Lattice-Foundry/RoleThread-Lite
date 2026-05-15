import json
from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker

import core.tag_registry as tag_registry
import core.tag_migrations as tag_migrations
import core.tag_metadata as tag_metadata
import core.tag_resolution as tag_resolution
import services.tag_lifecycle_service as tag_lifecycle_service
from core.dataset import normalize_dataset_tags
from core.tag_constants import (
    TAG_LIFECYCLE_METADATA_ARCHIVE,
    TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
    TAG_LIFECYCLE_METADATA_DELETE,
    TAG_LIFECYCLE_METADATA_HIDE,
    TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
    TAG_LIFECYCLE_METADATA_MERGE,
    TAG_LIFECYCLE_METADATA_RENAME,
    TAG_RESOLUTION_ACTIVE,
    TAG_RESOLUTION_ALIAS_MAPPED,
    TAG_RESOLUTION_ARCHIVED,
    TAG_RESOLUTION_HIDDEN,
    TAG_RESOLUTION_RETIRED,
    TAG_RESOLUTION_UNKNOWN,
    MAX_ACTIVE_CATEGORIES,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
)
from core.models import (
    Base,
    CategoryHistory,
    Tag,
    TagCategory,
    TagLifecycleMetadata,
)
from services.tag_lifecycle_service import create_custom_tag


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
    monkeypatch.setattr(tag_metadata, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_resolution, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_migrations, "engine", engine)
    monkeypatch.setattr(tag_lifecycle_service, "engine", engine)
    monkeypatch.setattr(tag_lifecycle_service, "SessionLocal", session_factory)
    monkeypatch.setattr(
        tag_registry,
        "create_db_backup",
        lambda *, engine: tmp_path / "db_backup.sqlite",
    )
    monkeypatch.setattr(
        tag_lifecycle_service,
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
    builtin=False,
):
    tag = Tag(
        category_id=category.id if category is not None else None,
        name=name or tag_registry.prettify_tag_name(slug),
        slug=slug,
        sort_order=0,
        is_active=active,
        is_builtin=builtin,
        status=status,
    )
    session.add(tag)
    session.flush()
    return tag


def test_seed_default_tags_uses_current_category_order_without_unsorted(tag_db):
    tag_registry.seed_default_tags()
    tag_registry.seed_default_tags()

    registry = tag_registry.get_full_tag_registry()

    assert not hasattr(tag_registry, "ensure_unsorted_category")
    assert [category["name"] for category in registry] == [
        "Behavior",
        "Scene",
        "Style",
        "Source",
        "Status",
    ]
    assert [tag["slug"] for tag in registry[3]["tags"]] == [
        "manual",
        "ai_generated",
    ]
    assert [tag["slug"] for tag in registry[4]["tags"]] == [
        "needs_review",
        "needs_edit",
    ]
    assert "reviewed" not in tag_registry.get_tag_registry_snapshot().active_tag_slugs


def test_seed_default_tags_migrates_source_status_and_reviewed(tag_db):
    session = tag_db()
    try:
        legacy_category = _add_category(
            session,
            name="Source & Status",
            slug="source_status",
        )
        _add_tag(session, slug="manual", category=legacy_category, builtin=True)
        _add_tag(session, slug="ai_generated", category=legacy_category, builtin=True)
        _add_tag(
            session,
            slug="reviewed",
            name="Reviewed",
            category=legacy_category,
            builtin=True,
        )
        _add_tag(session, slug="needs_edit", category=legacy_category, builtin=True)
        custom_category = _add_category(session, name="Custom", slug="custom")
        custom_category.sort_order = 1
        session.commit()
    finally:
        session.close()

    tag_registry.seed_default_tags()

    registry = tag_registry.get_full_tag_registry()
    assert [category["name"] for category in registry] == [
        "Behavior",
        "Scene",
        "Style",
        "Source",
        "Status",
        "Custom",
    ]

    source = next(category for category in registry if category["name"] == "Source")
    status = next(category for category in registry if category["name"] == "Status")
    assert [tag["slug"] for tag in source["tags"]] == ["manual", "ai_generated"]
    assert [tag["slug"] for tag in status["tags"]] == [
        "needs_review",
        "needs_edit",
    ]
    assert [tag["name"] for tag in status["tags"]] == ["Needs Review", "Needs Edit"]

    session = tag_db()
    try:
        legacy = session.query(TagCategory).filter_by(slug="source_status").one()
        assert legacy.is_active is False
        assert session.query(Tag).filter_by(slug="reviewed", is_active=True).count() == 0
    finally:
        session.close()


def test_tag_lifecycle_schema_exists_for_fresh_database(tag_db):
    inspector = sa_inspect(tag_registry.engine)

    assert "tag_lifecycle_metadata" in inspector.get_table_names()
    assert "tag_history" not in inspector.get_table_names()
    assert "category_history" in inspector.get_table_names()

    tag_columns = {column["name"]: column for column in inspector.get_columns("tags")}
    assert tag_columns["status"]["nullable"] is False
    assert tag_columns["category_id"]["nullable"] is True

    tag_constraints = inspector.get_unique_constraints("tags")
    assert any(
        constraint["name"] == "uq_tag_slug"
        and constraint["column_names"] == ["slug"]
        for constraint in tag_constraints
    )


def test_duplicate_slug_preflight_warns_without_crashing(tmp_path, capsys):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'legacy_duplicates.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tags (
                    id INTEGER NOT NULL,
                    category_id INTEGER,
                    name VARCHAR(120) NOT NULL,
                    slug VARCHAR(120) NOT NULL,
                    sort_order INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    is_builtin BOOLEAN NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    PRIMARY KEY (id)
                )
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
                    slug,
                    sort_order,
                    is_active,
                    is_builtin,
                    status
                )
                VALUES
                    (1, NULL, 'Slow Burn', 'slow_burn', 0, 0, 0, 'archived'),
                    (2, 1, 'Slow Burn', 'slow_burn', 1, 1, 0, 'active')
                """
            )
        )

    session = session_factory()
    try:
        tag_registry._warn_duplicate_tag_slugs(session)
    finally:
        session.close()

    output = capsys.readouterr().out
    assert "WARNING: Duplicate tag slugs found:" in output
    assert "slow_burn (2)" in output
    assert "UniqueConstraint on Tag.slug cannot be enforced" in output


def test_schema_allows_archived_tags_without_category(tag_db):
    session = tag_db()
    try:
        tag = Tag(
            category_id=None,
            name="Loose Tag",
            slug="loose_tag",
            sort_order=0,
            is_active=False,
            is_builtin=False,
            status=TAG_STATUS_ARCHIVED,
        )
        session.add(tag)
        session.commit()
        session.refresh(tag)

        assert tag.status == TAG_STATUS_ARCHIVED
        assert tag.category_id is None
        assert tag.is_active is False
    finally:
        session.close()


def test_old_tag_history_rows_migrate_to_lifecycle_metadata(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'legacy_history.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(tag_registry, "engine", engine)
    monkeypatch.setattr(tag_registry, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_metadata, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_resolution, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_migrations, "engine", engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tag_history (
                    id INTEGER NOT NULL,
                    action VARCHAR(40) NOT NULL,
                    old_slug VARCHAR(120),
                    old_display_name VARCHAR(120),
                    old_category_slug VARCHAR(120),
                    new_slug VARCHAR(120),
                    new_display_name VARCHAR(120),
                    new_category_slug VARCHAR(120),
                    created_at VARCHAR(40) NOT NULL,
                    metadata_json TEXT,
                    PRIMARY KEY (id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO tag_history (
                    id,
                    action,
                    old_slug,
                    old_display_name,
                    old_category_slug,
                    new_slug,
                    new_display_name,
                    new_category_slug,
                    created_at,
                    metadata_json
                )
                VALUES (
                    1,
                    'rename',
                    'old_tag',
                    'Old Tag',
                    NULL,
                    'new_tag',
                    'New Tag',
                    NULL,
                    '2026-01-01T00:00:00+00:00',
                    '{"resolver_behavior":"map_to_target"}'
                )
                """
            )
        )

    session = session_factory()
    try:
        category = _add_category(session)
        _add_tag(session, slug="new_tag", category=category)
        session.commit()
    finally:
        session.close()

    tag_migrations._migrate_tag_lifecycle_schema()
    tag_migrations._migrate_tag_lifecycle_schema()

    session = session_factory()
    try:
        row = session.query(TagLifecycleMetadata).one()
        assert row.action == TAG_LIFECYCLE_METADATA_RENAME
        assert row.old_slug == "old_tag"
        assert row.new_slug == "new_tag"
        assert session.query(TagLifecycleMetadata).count() == 1
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")
    assert result.result_type == TAG_RESOLUTION_ALIAS_MAPPED
    assert result.resolved_slug == "new_tag"


def test_history_models_can_be_inserted(tag_db):
    session = tag_db()
    try:
        tag_lifecycle_metadata = TagLifecycleMetadata(
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
        session.add_all([tag_lifecycle_metadata, category_history])
        session.commit()

        assert session.query(TagLifecycleMetadata).count() == 1
        assert session.query(CategoryHistory).count() == 1
    finally:
        session.close()


def test_current_lifecycle_metadata_upserts_one_current_row(tag_db):
    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
        old_slug="slow_burn",
        old_display_name="Slow Burn",
        new_slug="slow_burn",
        new_display_name="Slow Burn",
        metadata=tag_metadata.build_imported_archive_metadata(),
    )
    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
        old_slug="slow-burn",
        old_display_name="Slow Burn",
        new_slug="slow_burn",
        new_display_name="Slow Burn",
        metadata=tag_metadata.build_imported_archive_metadata(),
    )

    session = tag_db()
    try:
        histories = session.query(TagLifecycleMetadata).all()
        assert len(histories) == 1
        assert histories[0].action == TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED
    finally:
        session.close()


def test_current_lifecycle_metadata_replaces_imported_with_active_deleted_and_hidden(tag_db):
    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
        old_slug="slow_burn",
        metadata=tag_metadata.build_imported_archive_metadata(),
    )
    tag_metadata.clear_or_replace_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_ASSIGN_CATEGORY,
        old_slug="slow_burn",
        new_slug="slow_burn",
        new_category_slug="pacing",
        metadata=tag_metadata.build_active_assigned_metadata("pacing"),
    )

    active_metadata = tag_metadata.get_current_tag_lifecycle_metadata("slow burn")
    assert active_metadata["lifecycle_state"] == "active"
    assert active_metadata["activation_origin"] == "imported_assignment"
    assert active_metadata["assigned_category_slug"] == "pacing"

    tag_metadata.clear_or_replace_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_ARCHIVE,
        old_slug="slow_burn",
        old_category_slug="pacing",
        metadata=tag_metadata.build_deleted_archive_metadata("pacing"),
    )
    deleted_metadata = tag_metadata.get_current_tag_lifecycle_metadata("slow_burn")
    assert deleted_metadata["lifecycle_state"] == "archived"
    assert deleted_metadata["archive_origin"] == "deleted"
    assert deleted_metadata["previous_category_slug"] == "pacing"

    tag_metadata.clear_or_replace_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_HIDE,
        old_slug="slow_burn",
        metadata=tag_metadata.build_hidden_metadata(),
    )
    hidden_metadata = tag_metadata.get_current_tag_lifecycle_metadata("slow_burn")
    assert hidden_metadata["lifecycle_state"] == "hidden"
    assert hidden_metadata["hide_reason"] == "hidden_from_archive"

    session = tag_db()
    try:
        histories = session.query(TagLifecycleMetadata).all()
        assert len(histories) == 1
        assert histories[0].action == TAG_LIFECYCLE_METADATA_HIDE
    finally:
        session.close()


@pytest.mark.parametrize(
    ("action", "metadata_builder"),
    [
        (TAG_LIFECYCLE_METADATA_RENAME, tag_metadata.build_rename_alias_metadata),
        (TAG_LIFECYCLE_METADATA_MERGE, tag_metadata.build_merge_alias_metadata),
    ],
)
def test_alias_metadata_remains_resolver_usable(tag_db, action, metadata_builder):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="new_tag", category=category)
        session.commit()
    finally:
        session.close()

    tag_metadata.upsert_tag_lifecycle_metadata(
        action=action,
        old_slug="old_tag",
        new_slug="new_tag",
        metadata=metadata_builder(),
    )

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == TAG_RESOLUTION_ALIAS_MAPPED
    assert result.resolved_slug == "new_tag"
    assert result.should_rewrite_slug is True


def test_alias_metadata_always_inserts_and_preserves_previous_aliases(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="final_tag", category=category)
        session.commit()
    finally:
        session.close()

    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_RENAME,
        old_slug="old_tag",
        new_slug="middle_tag",
        metadata=tag_metadata.build_rename_alias_metadata(
            old_slug="old_tag",
            new_slug="middle_tag",
        ),
    )
    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_RENAME,
        old_slug="middle_tag",
        new_slug="final_tag",
        metadata=tag_metadata.build_rename_alias_metadata(
            old_slug="middle_tag",
            new_slug="final_tag",
        ),
    )
    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_RENAME,
        old_slug="middle_tag",
        new_slug="old_tag",
        metadata=tag_metadata.build_rename_alias_metadata(
            old_slug="middle_tag",
            new_slug="old_tag",
        ),
    )

    session = tag_db()
    try:
        middle_aliases = (
            session.query(TagLifecycleMetadata)
            .filter_by(old_slug="middle_tag")
            .order_by(TagLifecycleMetadata.id)
            .all()
        )
        assert [alias.new_slug for alias in middle_aliases] == [
            "final_tag",
            "old_tag",
        ]
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Middle Tag")
    assert result.result_type == TAG_RESOLUTION_UNKNOWN
    assert result.should_create_archived is True


def test_current_metadata_update_does_not_destroy_alias_lineage(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="new_tag", category=category)
        session.commit()
    finally:
        session.close()

    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_RENAME,
        old_slug="old_tag",
        new_slug="new_tag",
        metadata=tag_metadata.build_rename_alias_metadata(
            old_slug="old_tag",
            new_slug="new_tag",
        ),
    )
    tag_metadata.upsert_tag_lifecycle_metadata(
        action=TAG_LIFECYCLE_METADATA_ARCHIVE,
        old_slug="old_tag",
        old_category_slug="legacy",
        metadata=tag_metadata.build_deleted_archive_metadata("legacy"),
    )

    session = tag_db()
    try:
        aliases = (
            session.query(TagLifecycleMetadata)
            .filter_by(old_slug="old_tag", action=TAG_LIFECYCLE_METADATA_RENAME)
            .all()
        )
        current_rows = (
            session.query(TagLifecycleMetadata)
            .filter_by(old_slug="old_tag", action=TAG_LIFECYCLE_METADATA_ARCHIVE)
            .all()
        )
        assert len(aliases) == 1
        assert aliases[0].new_slug == "new_tag"
        assert len(current_rows) == 1
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")
    assert result.result_type == TAG_RESOLUTION_ALIAS_MAPPED
    assert result.resolved_slug == "new_tag"


@pytest.mark.parametrize(
    "raw",
    ["Slow Burn", "slow burn", "slow-burn", "SLOW BURN"],
)
def test_resolve_tag_lifecycle_normalizes_raw_values(tag_db, raw):
    result = tag_resolution.resolve_tag_lifecycle(raw)

    assert result.normalized_slug == "slow_burn"
    assert result.normalized_display_name == "Slow Burn"
    assert result.resolved_slug == "slow_burn"
    assert result.result_type == TAG_RESOLUTION_UNKNOWN
    assert result.should_create_archived is True


def test_resolve_tag_lifecycle_returns_active_for_active_categorized_tag(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="slow_burn", category=category)
        session.commit()
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Slow Burn")

    assert result.result_type == TAG_RESOLUTION_ACTIVE
    assert result.resolved_slug == "slow_burn"
    assert result.should_rewrite_slug is False


@pytest.mark.parametrize(
    "action",
    [TAG_LIFECYCLE_METADATA_RENAME, TAG_LIFECYCLE_METADATA_MERGE],
)
def test_resolve_tag_lifecycle_maps_alias_history_to_active_target(tag_db, action):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="new_tag", category=category)
        session.add(
            TagLifecycleMetadata(
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

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == TAG_RESOLUTION_ALIAS_MAPPED
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
                TagLifecycleMetadata(
                    action=TAG_LIFECYCLE_METADATA_RENAME,
                    old_slug="old_tag",
                    new_slug="middle_tag",
                ),
                TagLifecycleMetadata(
                    action=TAG_LIFECYCLE_METADATA_MERGE,
                    old_slug="middle_tag",
                    new_slug="final_tag",
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == TAG_RESOLUTION_ALIAS_MAPPED
    assert result.resolved_slug == "final_tag"
    assert result.should_rewrite_slug is True


def test_resolve_tag_lifecycle_follows_three_hop_alias_lineage(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="final_tag", category=category)
        session.add_all(
            [
                TagLifecycleMetadata(
                    action=TAG_LIFECYCLE_METADATA_RENAME,
                    old_slug="old_tag",
                    new_slug="middle_tag",
                ),
                TagLifecycleMetadata(
                    action=TAG_LIFECYCLE_METADATA_RENAME,
                    old_slug="middle_tag",
                    new_slug="newer_tag",
                ),
                TagLifecycleMetadata(
                    action=TAG_LIFECYCLE_METADATA_MERGE,
                    old_slug="newer_tag",
                    new_slug="final_tag",
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == TAG_RESOLUTION_ALIAS_MAPPED
    assert result.resolved_slug == "final_tag"
    assert result.should_rewrite_slug is True


def test_resolve_tag_lifecycle_handles_alias_cycle_without_hanging(tag_db):
    session = tag_db()
    try:
        session.add_all(
            [
                TagLifecycleMetadata(
                    action=TAG_LIFECYCLE_METADATA_RENAME,
                    old_slug="old_tag",
                    new_slug="middle_tag",
                ),
                TagLifecycleMetadata(
                    action=TAG_LIFECYCLE_METADATA_RENAME,
                    old_slug="middle_tag",
                    new_slug="old_tag",
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == TAG_RESOLUTION_UNKNOWN
    assert result.resolved_slug == "old_tag"
    assert result.should_rewrite_slug is False
    assert result.should_create_archived is True


def test_resolve_tag_lifecycle_does_not_map_alias_when_target_is_missing(tag_db):
    session = tag_db()
    try:
        session.add(
            TagLifecycleMetadata(
                action=TAG_LIFECYCLE_METADATA_RENAME,
                old_slug="old_tag",
                new_slug="missing_tag",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == TAG_RESOLUTION_UNKNOWN
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
            TagLifecycleMetadata(
                action=TAG_LIFECYCLE_METADATA_MERGE,
                old_slug="old_tag",
                new_slug="archived_target",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Old Tag")

    assert result.result_type == TAG_RESOLUTION_UNKNOWN
    assert result.should_rewrite_slug is False
    assert result.should_create_archived is True


@pytest.mark.parametrize(
    ("status", "result_type"),
    [
        (TAG_STATUS_ARCHIVED, TAG_RESOLUTION_ARCHIVED),
        (TAG_STATUS_HIDDEN, TAG_RESOLUTION_HIDDEN),
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

    result = tag_resolution.resolve_tag_lifecycle("Legacy Tag")

    assert result.result_type == result_type
    assert result.resolved_slug == "legacy_tag"
    assert result.should_skip_creation is True


@pytest.mark.parametrize(
    "action",
    [
        TAG_LIFECYCLE_METADATA_HIDE,
        TAG_LIFECYCLE_METADATA_DELETE,
        TAG_LIFECYCLE_METADATA_ARCHIVE,
    ],
)
def test_resolve_tag_lifecycle_recognizes_retired_history_without_target(tag_db, action):
    session = tag_db()
    try:
        session.add(
            TagLifecycleMetadata(
                action=action,
                old_slug="retired_tag",
                old_display_name="Retired Tag",
            )
        )
        session.commit()
    finally:
        session.close()

    result = tag_resolution.resolve_tag_lifecycle("Retired Tag")

    assert result.result_type == TAG_RESOLUTION_RETIRED
    assert result.resolved_slug == "retired_tag"
    assert result.should_skip_creation is True


def test_resolve_tag_lifecycle_returns_unknown_for_truly_unknown_tag(tag_db):
    result = tag_resolution.resolve_tag_lifecycle("Brand New")

    assert result.result_type == TAG_RESOLUTION_UNKNOWN
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

    snapshot = tag_registry.get_tag_registry_snapshot()
    assert snapshot.active_registry == {"Behavior": ["active_tag"]}
    assert snapshot.active_tag_slugs == ["active_tag"]
    assert snapshot.tag_category_map == {"active_tag": "Behavior"}
    assert snapshot.tag_label_map == {"active_tag": "Behavior / Active Tag"}
    assert snapshot.tag_label_map_with_untagged == {
        "__untagged__": "Untagged",
        "active_tag": "Behavior / Active Tag",
    }

    full_registry = tag_registry.get_full_tag_registry()
    assert len(full_registry) == 1
    assert full_registry[0]["name"] == "Behavior"
    assert [tag["slug"] for tag in full_registry[0]["tags"]] == ["active_tag"]

    assert len(snapshot.active_categories) == 1
    assert snapshot.active_categories[0]["slug"] == "behavior"
    assert [tag["slug"] for tag in snapshot.active_categories[0]["tags"]] == [
        "active_tag"
    ]


def test_active_registry_helpers_keep_empty_active_categories(tag_db):
    session = tag_db()
    try:
        _add_category(session, name="Empty", slug="empty")
        session.commit()
    finally:
        session.close()

    assert tag_registry.get_tag_registry_snapshot().active_registry == {"Empty": []}
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


def test_tag_registry_snapshot_matches_existing_read_helpers(tag_db):
    session = tag_db()
    try:
        behavior = _add_category(session, name="Behavior", slug="behavior")
        scene = _add_category(session, name="Scene", slug="scene")
        scene.sort_order = 1
        _add_tag(session, slug="active_tag", name="Active Tag", category=behavior)
        second = _add_tag(session, slug="second_tag", name="Second Tag", category=scene)
        second.sort_order = 2
        imported = _add_tag(
            session,
            slug="imported_tag",
            name="Imported Tag",
            category=None,
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        deleted = _add_tag(
            session,
            slug="deleted_tag",
            name="Deleted Tag",
            category=None,
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        tag_metadata.upsert_tag_lifecycle_metadata(
            action=TAG_LIFECYCLE_METADATA_ARCHIVE,
            old_slug=imported.slug,
            old_display_name=imported.name,
            metadata=tag_metadata.build_imported_archive_metadata(),
            session=session,
        )
        tag_metadata.upsert_tag_lifecycle_metadata(
            action=TAG_LIFECYCLE_METADATA_ARCHIVE,
            old_slug=deleted.slug,
            old_display_name=deleted.name,
            old_category_slug="behavior",
            metadata=tag_metadata.build_deleted_archive_metadata("behavior"),
            session=session,
        )
        session.commit()
    finally:
        session.close()

    snapshot = tag_registry.get_tag_registry_snapshot(
        untagged_key="__custom_untagged__"
    )

    assert snapshot.active_registry == {
        "Behavior": ["active_tag"],
        "Scene": ["second_tag"],
    }
    assert snapshot.active_categories == tag_registry.get_full_tag_registry()
    assert snapshot.active_tag_slugs == ["active_tag", "second_tag"]
    assert snapshot.active_tag_slug_set == {"active_tag", "second_tag"}
    assert snapshot.tag_label_map == {
        "active_tag": "Behavior / Active Tag",
        "second_tag": "Scene / Second Tag",
    }
    assert snapshot.tag_label_map_with_untagged == {
        "__custom_untagged__": "Untagged",
        "active_tag": "Behavior / Active Tag",
        "second_tag": "Scene / Second Tag",
    }
    assert snapshot.tag_category_map == {
        "active_tag": "Behavior",
        "second_tag": "Scene",
    }
    assert snapshot.visible_archived_tags == tag_registry.get_visible_archived_tags()
    assert snapshot.default_category_slugs == {
        tag_registry.slugify_tag_name(name) for name in tag_registry.TAGS
    }
    assert snapshot.max_active_categories == MAX_ACTIVE_CATEGORIES


def test_tag_registry_snapshot_is_frozen(tag_db):
    snapshot = tag_registry.get_tag_registry_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.max_active_categories = 11


def test_lifecycle_specific_helpers_return_status_scoped_tags(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="active_tag", category=category)
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

    assert [tag["slug"] for tag in tag_registry.get_archived_tags()] == ["archived_tag"]
    assert [tag["slug"] for tag in tag_registry.get_hidden_tags()] == ["hidden_tag"]
    assert [tag["slug"] for tag in tag_registry.get_tags_by_status(TAG_STATUS_ACTIVE)] == [
        "active_tag"
    ]

    archived = tag_registry.get_archived_tags()[0]
    assert archived["category_name"] == "Behavior"
    assert archived["status"] == TAG_STATUS_ARCHIVED

    imported = tag_registry.get_imported_archived_tags()
    deleted = tag_registry.get_deleted_archived_tags()
    assert imported == []
    assert [tag["slug"] for tag in deleted] == ["archived_tag"]
    assert deleted[0]["visible_badge"] == "Deleted"
    assert deleted[0]["selectable"] is False
    assert deleted[0]["has_selection_slot"] is True
    assert deleted[0]["can_assign_to_category"] is False

    visible_archived = tag_registry.get_visible_archived_tags()
    assert [tag["name"] for tag in visible_archived] == ["Archived Tag"]
    assert [tag["visible_badge"] for tag in visible_archived] == ["Deleted"]
    assert [tag["has_selection_slot"] for tag in visible_archived] == [True]
    assert "hidden_tag" not in [tag["slug"] for tag in visible_archived]


@pytest.mark.parametrize(
    ("slug", "status"),
    [
        ("active_tag", TAG_STATUS_ACTIVE),
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

    assert result.result_type == TAG_RESOLUTION_ARCHIVED
    assert result.normalized_slug == "slow_burn"
    assert result.should_create_archived is False
    assert result.should_skip_creation is True
    assert result.reason == TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED

    session = tag_db()
    try:
        tag = session.query(Tag).filter_by(slug="slow_burn").one()
        assert tag.name == "Slow Burn"
        assert tag.status == TAG_STATUS_ARCHIVED
        assert tag.category_id is None
        assert tag.is_active is False
        assert tag.is_builtin is False

        history = session.query(TagLifecycleMetadata).one()
        assert history.action == TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED
        assert history.old_slug == "slow_burn"
        assert history.old_display_name == "Slow Burn"
        assert history.old_category_slug is None
        assert history.new_slug == "slow_burn"
        assert history.new_display_name == "Slow Burn"
        assert history.new_category_slug is None
        metadata = json.loads(history.metadata_json)
        assert metadata["lifecycle_state"] == "archived"
        assert metadata["archive_origin"] == "imported"
        assert metadata["archive_reason"] == "unknown_import"
        assert metadata["visible_badge"] == "Imported"
    finally:
        session.close()

    assert tag_registry.get_tag_registry_snapshot().active_registry == {}
    imported = tag_registry.get_imported_archived_tags()
    assert [tag["slug"] for tag in imported] == ["slow_burn"]
    assert imported[0]["selectable"] is True
    assert imported[0]["has_selection_slot"] is True
    assert imported[0]["can_assign_to_category"] is True
    session = tag_db()
    try:
        assert session.query(TagLifecycleMetadata).filter_by(old_slug="slow_burn").count() == 1
    finally:
        session.close()


def test_ensure_archived_import_tags_for_dataset_creates_only_unknown_tags(tag_db):
    session = tag_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="known_tag", category=category)
        _add_tag(
            session,
            slug="old_archived",
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        session.commit()
    finally:
        session.close()

    summary = tag_registry.ensure_archived_import_tags_for_dataset(
        [
            {"tags": ["known_tag", "new tag"]},
            {"tags": ["old_archived", "new-tag"]},
        ]
    )

    assert summary.created_count == 1
    assert summary.created_slugs == ["new_tag"]
    assert summary.existing_slugs == ["known_tag", "old_archived"]
    assert summary.skipped_slugs == []

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="new_tag").one().status == (
            TAG_STATUS_ARCHIVED
        )
        assert session.query(TagLifecycleMetadata).filter_by(
            action=TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED
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
        assert session.query(TagLifecycleMetadata).count() == 0
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

    monkeypatch.setattr(tag_lifecycle_service, "create_db_backup", fail_backup)

    ok, message = create_custom_tag(category_id, "Slow Burn")

    assert ok is False
    assert "Could not create database backup" in message

    session = tag_db()
    try:
        assert session.query(Tag).filter_by(slug="slow_burn").count() == 0
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_adopts_unknown_tags_as_archived_imported(tag_db):
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
    assert "Unsorted" not in [category["name"] for category in registry]

    behavior = next(category for category in registry if category["name"] == "Behavior")
    assert [tag["slug"] for tag in behavior["tags"]] == ["reviewed"]
    assert "slow_burn" not in tag_registry.get_tag_registry_snapshot().active_tag_slugs
    assert [tag["slug"] for tag in tag_registry.get_imported_archived_tags()] == [
        "slow_burn"
    ]

    session = tag_db()
    try:
        adopted = session.query(Tag).filter_by(slug="slow_burn").one()
        unsorted = session.query(TagCategory).filter_by(slug="unsorted").first()
        assert adopted.status == TAG_STATUS_ARCHIVED
        assert adopted.category_id is None
        assert adopted.is_active is False
        assert unsorted is None
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_writes_import_archived_history(tag_db):
    summary = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow-burn"]}])

    assert summary.created_count == 1
    assert summary.created_slugs == ["slow_burn"]

    session = tag_db()
    try:
        history = session.query(TagLifecycleMetadata).one()
        assert history.action == TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED
        assert history.old_slug == "slow_burn"
        assert history.old_display_name == "Slow Burn"
        metadata = json.loads(history.metadata_json)
        assert metadata["lifecycle_state"] == "archived"
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
            TagLifecycleMetadata(
                action=TAG_LIFECYCLE_METADATA_HIDE,
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
        assert session.query(TagLifecycleMetadata).count() == 1
    finally:
        session.close()


def test_ensure_tags_exist_for_dataset_does_not_duplicate_imported_archived_tags(tag_db):
    first = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow_burn"]}])
    second = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["slow-burn"]}])

    assert first.created_count == 1
    assert second.created_count == 0

    registry = tag_registry.get_full_tag_registry()
    assert "Unsorted" not in [category["name"] for category in registry]
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


def test_seed_deactivates_empty_legacy_unsorted_category(tag_db):
    session = tag_db()
    try:
        unsorted = TagCategory(
            name="Unsorted",
            slug="unsorted",
            sort_order=-1000,
            is_active=True,
        )
        session.add(unsorted)
        session.flush()
        assert unsorted.is_active is True
        session.commit()
    finally:
        session.close()

    tag_registry.seed_default_tags()

    registry = tag_registry.get_full_tag_registry()
    assert "Unsorted" not in [category["name"] for category in registry]

    session = tag_db()
    try:
        unsorted = session.query(TagCategory).filter_by(slug="unsorted").one()
        assert unsorted.is_active is False
    finally:
        session.close()


def test_lifecycle_migration_updates_legacy_tags_table(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'legacy_tag_registry.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(tag_registry, "engine", engine)
    monkeypatch.setattr(tag_registry, "SessionLocal", session_factory)
    monkeypatch.setattr(tag_migrations, "engine", engine)

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

    tag_migrations._migrate_tags_slug_column()
    tag_migrations._migrate_tag_lifecycle_schema()
    tag_migrations._migrate_tag_lifecycle_schema()

    inspector = sa_inspect(engine)
    assert "tag_lifecycle_metadata" in inspector.get_table_names()
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
