import json
import shutil

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.tag_registry as tag_registry
from core.dataset import load_dataset, save_dataset
from core.models import (
    Base,
    CategoryHistory,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
    Tag,
    TagCategory,
    TagLifecycleMetadata,
)
import services.tag_lifecycle_service as tag_lifecycle_service
from services.tag_lifecycle_service import (
    assign_archived_imported_tags_to_category,
    delete_active_tag,
    edit_active_tag,
    rename_active_tag,
    rename_custom_category,
)


@pytest.fixture
def tag_lifecycle_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'tag_lifecycle.db'}",
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


def _add_category(session, *, slug="behavior", name="Behavior", active=True):
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


def _add_imported_archived_tag(session, slug):
    tag = _add_tag(
        session,
        slug=slug,
        status=TAG_STATUS_ARCHIVED,
        active=False,
    )
    tag_registry.upsert_tag_lifecycle_metadata(
        action=tag_registry.TAG_LIFECYCLE_METADATA_IMPORT_ARCHIVED,
        old_slug=slug,
        old_display_name=tag.name,
        new_slug=slug,
        new_display_name=tag.name,
        metadata=tag_registry.build_imported_archive_metadata(),
        session=session,
    )
    return tag


def _metadata_for(session, slug):
    history = session.query(TagLifecycleMetadata).filter_by(old_slug=slug).one()
    return json.loads(history.metadata_json)


def _entry(tags):
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": tags,
    }


def _write_dataset(tmp_path, entries):
    path = tmp_path / "dataset.jsonl"
    save_dataset(path, entries)
    return path


def _fake_dataset_backup(tmp_path, monkeypatch):
    backups = []

    def fake_create_dataset_backup(dataset_path, reason):
        backup_path = tmp_path / f"{len(backups):03d}_{reason}.jsonl"
        shutil.copyfile(dataset_path, backup_path)
        backups.append(backup_path)
        return backup_path

    monkeypatch.setattr(
        tag_lifecycle_service,
        "create_dataset_backup",
        fake_create_dataset_backup,
    )
    return backups


def test_assign_one_archived_imported_tag_to_active_category(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        category_id = category.id
        _add_imported_archived_tag(session, "slow_burn")
        session.commit()
    finally:
        session.close()

    result = assign_archived_imported_tags_to_category(
        tag_slugs=["slow_burn"],
        category_slug="behavior",
    )

    assert result.ok is True
    assert result.affected_count == 1
    assert result.tag_slugs == ["slow_burn"]
    assert result.category_slug == "behavior"
    assert result.db_backup_path is not None

    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="slow_burn").one()
        assert tag.status == TAG_STATUS_ACTIVE
        assert tag.is_active is True
        assert tag.category_id == category_id
        metadata = _metadata_for(session, "slow_burn")
        assert metadata == tag_registry.build_active_assigned_metadata("behavior")
    finally:
        session.close()

    assert "slow_burn" in tag_registry.get_all_tag_slugs()
    assert tag_registry.get_imported_archived_tags() == []


def test_assign_multiple_archived_imported_tags_to_active_category(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        category = _add_category(session, slug="tone", name="Tone")
        category_id = category.id
        _add_imported_archived_tag(session, "slow_burn")
        _add_imported_archived_tag(session, "angst")
        session.commit()
    finally:
        session.close()

    result = assign_archived_imported_tags_to_category(
        tag_slugs=["slow-burn", "angst", "slow_burn"],
        category_slug="tone",
    )

    assert result.ok is True
    assert result.affected_count == 2
    assert result.tag_slugs == ["slow_burn", "angst"]

    session = tag_lifecycle_db()
    try:
        tags = session.query(Tag).order_by(Tag.slug).all()
        assert {tag.slug: tag.category_id for tag in tags} == {
            "angst": category_id,
            "slow_burn": category_id,
        }
        assert {tag.status for tag in tags} == {TAG_STATUS_ACTIVE}
    finally:
        session.close()


def test_assign_rejects_no_selected_tags(tag_lifecycle_db):
    result = assign_archived_imported_tags_to_category(
        tag_slugs=[],
        category_slug="behavior",
    )

    assert result.ok is False
    assert "No archived tags selected." in result.errors


def test_assign_rejects_missing_or_inactive_category(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        _add_category(session, slug="inactive", name="Inactive", active=False)
        _add_imported_archived_tag(session, "slow_burn")
        session.commit()
    finally:
        session.close()

    missing = assign_archived_imported_tags_to_category(
        tag_slugs=["slow_burn"],
        category_slug="missing",
    )
    inactive = assign_archived_imported_tags_to_category(
        tag_slugs=["slow_burn"],
        category_slug="inactive",
    )

    assert missing.ok is False
    assert inactive.ok is False
    assert missing.errors == ["Selected category does not exist or is inactive."]
    assert inactive.errors == ["Selected category does not exist or is inactive."]


def test_assign_rejects_missing_active_hidden_and_deleted_tags(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="active_tag", category=category)
        _add_tag(
            session,
            slug="hidden_tag",
            status=TAG_STATUS_HIDDEN,
            active=False,
        )
        deleted = _add_tag(
            session,
            slug="deleted_tag",
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        tag_registry.upsert_tag_lifecycle_metadata(
            action=tag_registry.TAG_LIFECYCLE_METADATA_ARCHIVE,
            old_slug=deleted.slug,
            old_display_name=deleted.name,
            old_category_slug="behavior",
            metadata=tag_registry.build_deleted_archive_metadata("behavior"),
            session=session,
        )
        session.commit()
    finally:
        session.close()

    result = assign_archived_imported_tags_to_category(
        tag_slugs=["missing_tag", "active_tag", "hidden_tag", "deleted_tag"],
        category_slug="behavior",
    )

    assert result.ok is False
    assert "Tag not found: Missing Tag" in result.errors
    assert "Tag is not archived: Active Tag" in result.errors
    assert "Tag is not archived: Hidden Tag" in result.errors
    assert "Tag is not an imported archived tag: Deleted Tag" in result.errors


def test_assign_rejects_non_imported_archived_tag(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(
            session,
            slug="non_imported",
            category=category,
            status=TAG_STATUS_ARCHIVED,
            active=False,
        )
        session.commit()
    finally:
        session.close()

    result = assign_archived_imported_tags_to_category(
        tag_slugs=["non_imported"],
        category_slug="behavior",
    )

    assert result.ok is False
    assert result.errors == ["Tag is not an imported archived tag: Non Imported"]


def test_assign_rejects_conflicting_active_tag_with_same_slug(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_imported_archived_tag(session, "slow_burn")
        _add_tag(session, slug="slow_burn", category=category)
        session.commit()
    finally:
        session.close()

    result = assign_archived_imported_tags_to_category(
        tag_slugs=["slow_burn"],
        category_slug="behavior",
    )

    assert result.ok is False
    assert result.errors == ["An active tag already exists for: Slow Burn"]


def test_assign_backup_failure_fails_closed(tag_lifecycle_db, monkeypatch):
    session = tag_lifecycle_db()
    try:
        _add_category(session)
        _add_imported_archived_tag(session, "slow_burn")
        session.commit()
    finally:
        session.close()

    def fail_backup(*, engine):
        raise OSError("backup blocked")

    monkeypatch.setattr(tag_registry, "create_db_backup", fail_backup)

    result = assign_archived_imported_tags_to_category(
        tag_slugs=["slow_burn"],
        category_slug="behavior",
    )

    assert result.ok is False
    assert result.message == "Could not create database backup: backup blocked"

    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="slow_burn").one()
        assert tag.status == TAG_STATUS_ARCHIVED
        assert tag.is_active is False
        assert tag.category_id is None
        metadata = _metadata_for(session, "slow_burn")
        assert metadata == tag_registry.build_imported_archive_metadata()
    finally:
        session.close()


def test_rename_custom_category_updates_slug_and_preserves_tags(
    tag_lifecycle_db,
):
    session = tag_lifecycle_db()
    try:
        category = _add_category(session, slug="story_shape", name="Story Shape")
        category_id = category.id
        tag = _add_tag(session, slug="slow_burn", category=category)
        tag_id = tag.id
        session.commit()
    finally:
        session.close()

    result = rename_custom_category(
        category_slug="story_shape",
        new_display_name="Narrative Shape",
    )

    assert result.ok is True
    assert result.message == 'Renamed category "Story Shape" to "Narrative Shape".'
    assert result.category_slug == "narrative_shape"
    assert result.db_backup_path is not None
    assert result.dataset_backup_path is None

    session = tag_lifecycle_db()
    try:
        renamed = session.query(TagCategory).filter_by(slug="narrative_shape").one()
        assert renamed.id == category_id
        assert renamed.name == "Narrative Shape"
        assert renamed.is_active is True
        attached_tag = session.query(Tag).filter_by(id=tag_id).one()
        assert attached_tag.category_id == category_id
        history = session.query(CategoryHistory).one()
        assert history.action == "rename"
        assert history.old_slug == "story_shape"
        assert history.new_slug == "narrative_shape"
        metadata = json.loads(history.metadata_json)
        assert metadata["lifecycle_state"] == "active"
        assert metadata["action"] == "rename"
    finally:
        session.close()

    registry = tag_registry.get_tag_registry_dict()
    assert "Story Shape" not in registry
    assert registry["Narrative Shape"] == ["slow_burn"]


def test_rename_custom_category_validation_and_noop_paths(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        builtin = _add_category(session, slug="behavior", name="Behavior")
        custom = _add_category(session, slug="story_shape", name="Story Shape")
        _add_category(session, slug="duplicate", name="Duplicate")
        _add_category(session, slug="inactive", name="Inactive", active=False)
        session.commit()
    finally:
        session.close()

    builtin_result = rename_custom_category(
        category_slug="behavior",
        new_display_name="New Behavior",
    )
    missing = rename_custom_category(
        category_slug="missing",
        new_display_name="Missing",
    )
    inactive = rename_custom_category(
        category_slug="inactive",
        new_display_name="Still Inactive",
    )
    empty = rename_custom_category(
        category_slug="story_shape",
        new_display_name="!!!",
    )
    duplicate = rename_custom_category(
        category_slug="story_shape",
        new_display_name="Duplicate",
    )
    same = rename_custom_category(
        category_slug="story_shape",
        new_display_name="Story Shape",
    )

    assert builtin_result.ok is False
    assert builtin_result.errors == ["Built-in categories cannot be renamed: Behavior"]
    assert missing.ok is False
    assert missing.errors == ["Category not found: Missing"]
    assert inactive.ok is False
    assert inactive.errors == ["Category is inactive: Inactive"]
    assert empty.ok is False
    assert empty.errors == ["Category name cannot be empty."]
    assert duplicate.ok is False
    assert duplicate.errors == ["A category named Duplicate already exists."]
    assert same.ok is True
    assert same.affected_count == 0
    assert same.db_backup_path is None

    session = tag_lifecycle_db()
    try:
        assert session.query(TagCategory).filter_by(slug="story_shape").one().name == (
            "Story Shape"
        )
        assert session.query(TagCategory).filter_by(slug="new_behavior").count() == 0
        assert session.query(CategoryHistory).count() == 0
    finally:
        session.close()


def test_rename_custom_category_backup_failure_fails_closed(
    tag_lifecycle_db,
    monkeypatch,
):
    session = tag_lifecycle_db()
    try:
        _add_category(session, slug="story_shape", name="Story Shape")
        session.commit()
    finally:
        session.close()

    def fail_backup(*, engine):
        raise OSError("db backup blocked")

    monkeypatch.setattr(tag_registry, "create_db_backup", fail_backup)

    result = rename_custom_category(
        category_slug="story_shape",
        new_display_name="Narrative Shape",
    )

    assert result.ok is False
    assert result.message == "Could not create database backup: db backup blocked"
    session = tag_lifecycle_db()
    try:
        assert session.query(TagCategory).filter_by(slug="story_shape").one().name == (
            "Story Shape"
        )
        assert session.query(TagCategory).filter_by(slug="narrative_shape").count() == 0
        assert session.query(CategoryHistory).count() == 0
    finally:
        session.close()


def test_rename_custom_active_tag_rewrites_dataset_and_aliases_old_slug(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    dataset_backups = _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [
        _entry(["followup_question", "tone"]),
        _entry(["tone", "followup_question"]),
        _entry(["other_tag"]),
    ]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        category_id = category.id
        _add_tag(session, slug="followup_question", name="Followup Question", category=category)
        _add_tag(session, slug="tone", category=category)
        _add_tag(session, slug="other_tag", category=category)
        session.commit()
    finally:
        session.close()

    result = rename_active_tag(
        old_slug="followup_question",
        new_display_name="Follow Up Question",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is True
    assert result.old_slug == "followup_question"
    assert result.new_slug == "follow_up_question"
    assert result.old_display_name == "Followup Question"
    assert result.new_display_name == "Follow Up Question"
    assert result.affected_count == 2
    assert result.dataset_backup_path == str(dataset_backups[0])
    assert result.db_backup_path is not None
    assert result.entries == [
        _entry(["follow_up_question", "tone"]),
        _entry(["tone", "follow_up_question"]),
        _entry(["other_tag"]),
    ]

    loaded, errors = load_dataset(path)
    assert errors == []
    assert loaded == result.entries

    session = tag_lifecycle_db()
    try:
        assert session.query(Tag).filter_by(slug="followup_question").count() == 0
        renamed = session.query(Tag).filter_by(slug="follow_up_question").one()
        assert renamed.name == "Follow Up Question"
        assert renamed.category_id == category_id
        assert renamed.status == TAG_STATUS_ACTIVE
        assert renamed.is_active is True
        assert renamed.is_builtin is False

        alias_metadata = (
            session.query(TagLifecycleMetadata)
            .filter_by(
                old_slug="followup_question",
                action=tag_registry.TAG_LIFECYCLE_METADATA_RENAME,
            )
            .one()
        )
        assert alias_metadata.new_slug == "follow_up_question"
        metadata = json.loads(alias_metadata.metadata_json)
        assert metadata["alias_type"] == "rename"
        assert metadata["old_slug"] == "followup_question"
        assert metadata["new_slug"] == "follow_up_question"

        current_metadata = _metadata_for(session, "follow_up_question")
        assert current_metadata["lifecycle_state"] == "active"
        assert current_metadata["activation_origin"] == "tag_edit"
    finally:
        session.close()

    assert "follow_up_question" in tag_registry.get_all_tag_slugs()
    assert "followup_question" not in tag_registry.get_all_tag_slugs()

    resolved = tag_registry.resolve_tag_lifecycle("Followup Question")
    assert resolved.result_type == tag_registry.TAG_RESOLUTION_ALIAS_MAPPED
    assert resolved.resolved_slug == "follow_up_question"


def test_rename_custom_active_tag_deduplicates_rewritten_entry_tags(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [_entry(["old_tag", "new_tag", "old_tag"])]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="old_tag", name="Old Tag", category=category)
        session.commit()
    finally:
        session.close()

    result = rename_active_tag(
        old_slug="old_tag",
        new_display_name="New Tag",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is True
    assert result.entries == [_entry(["new_tag"])]


def test_edit_active_tag_moves_category_without_dataset_rewrite(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    dataset_backups = _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [_entry(["followup_question"])]

    session = tag_lifecycle_db()
    try:
        behavior = _add_category(session, slug="behavior", name="Behavior")
        scene = _add_category(session, slug="scene", name="Scene")
        scene_id = scene.id
        _add_tag(
            session,
            slug="followup_question",
            name="Followup Question",
            category=behavior,
        )
        session.commit()
    finally:
        session.close()

    result = edit_active_tag(
        old_slug="followup_question",
        new_display_name="Followup Question",
        category_slug="scene",
        dataset_path="",
        entries=entries,
    )

    assert result.ok is True
    assert result.message == 'Moved tag "Followup Question" to Scene.'
    assert result.dataset_backup_path is None
    assert result.db_backup_path is not None
    assert result.entries == entries
    assert dataset_backups == []

    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="followup_question").one()
        assert tag.name == "Followup Question"
        assert tag.category_id == scene_id
        metadata = _metadata_for(session, "followup_question")
        assert metadata["lifecycle_state"] == "active"
        assert metadata["assigned_category_slug"] == "scene"
        assert metadata["activation_origin"] == "tag_edit"
        assert session.query(TagLifecycleMetadata).filter_by(
            action=tag_registry.TAG_LIFECYCLE_METADATA_RENAME
        ).count() == 0
    finally:
        session.close()

    registry = tag_registry.get_tag_registry_dict()
    assert registry["Behavior"] == []
    assert registry["Scene"] == ["followup_question"]


def test_edit_active_tag_changes_name_and_category_together(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [_entry(["followup_question"])]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        behavior = _add_category(session, slug="behavior", name="Behavior")
        scene = _add_category(session, slug="scene", name="Scene")
        scene_id = scene.id
        _add_tag(
            session,
            slug="followup_question",
            name="Followup Question",
            category=behavior,
        )
        session.commit()
    finally:
        session.close()

    result = edit_active_tag(
        old_slug="followup_question",
        new_display_name="Follow Up Question",
        category_slug="scene",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is True
    assert result.message == (
        'Edited tag "Followup Question" to "Follow Up Question" and moved it to Scene.'
    )
    assert result.entries == [_entry(["follow_up_question"])]
    assert result.dataset_backup_path is not None
    assert result.db_backup_path is not None

    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="follow_up_question").one()
        assert tag.name == "Follow Up Question"
        assert tag.category_id == scene_id
        alias = session.query(TagLifecycleMetadata).filter_by(
            old_slug="followup_question",
            action=tag_registry.TAG_LIFECYCLE_METADATA_RENAME,
        ).one()
        assert alias.new_slug == "follow_up_question"
        current_metadata = _metadata_for(session, "follow_up_question")
        assert current_metadata["assigned_category_slug"] == "scene"
    finally:
        session.close()


def test_delete_custom_active_tag_archives_tag_and_removes_from_entries(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    dataset_backups = _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [
        _entry(["slow_burn", "tone"]),
        _entry(["slow_burn"]),
        _entry(["tone"]),
    ]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session, slug="style", name="Style")
        _add_tag(session, slug="slow_burn", name="Slow Burn", category=category)
        _add_tag(session, slug="tone", name="Tone", category=category)
        session.commit()
    finally:
        session.close()

    result = delete_active_tag(
        tag_slug="slow_burn",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is True
    assert result.message == 'Deleted tag "Slow Burn" and removed it from 2 entries.'
    assert result.affected_count == 2
    assert result.dataset_backup_path == str(dataset_backups[0])
    assert result.db_backup_path is not None
    assert result.entries == [
        _entry(["tone"]),
        _entry([]),
        _entry(["tone"]),
    ]

    loaded, errors = load_dataset(path)
    assert errors == []
    assert loaded == result.entries

    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="slow_burn").one()
        assert tag.status == TAG_STATUS_ARCHIVED
        assert tag.is_active is False
        assert tag.category_id is None
        metadata = _metadata_for(session, "slow_burn")
        assert metadata == tag_registry.build_deleted_archive_metadata("style")
    finally:
        session.close()

    assert "slow_burn" not in tag_registry.get_all_tag_slugs()
    deleted = tag_registry.get_deleted_archived_tags()
    assert [tag["slug"] for tag in deleted] == ["slow_burn"]
    assert deleted[0]["visible_badge"] == "Deleted"
    assert deleted[0]["can_assign_to_category"] is False
    resolved = tag_registry.resolve_tag_lifecycle("Slow Burn")
    assert resolved.result_type == tag_registry.TAG_RESOLUTION_ARCHIVED


def test_delete_custom_active_tag_handles_no_loaded_entries(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    entries = []
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="unused_tag", name="Unused Tag", category=category)
        session.commit()
    finally:
        session.close()

    result = delete_active_tag(
        tag_slug="unused_tag",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is True
    assert result.affected_count == 0
    assert result.entries == []
    assert load_dataset(path)[0] == []


@pytest.mark.parametrize(
    ("slug", "status", "active", "builtin", "expected_error"),
    [
        (
            "builtin_tag",
            TAG_STATUS_ACTIVE,
            True,
            True,
            "Built-in tags cannot be deleted: Builtin Tag",
        ),
        (
            "archived_tag",
            TAG_STATUS_ARCHIVED,
            False,
            False,
            "Tag is not an active custom tag: Archived Tag",
        ),
        (
            "hidden_tag",
            TAG_STATUS_HIDDEN,
            False,
            False,
            "Tag is not an active custom tag: Hidden Tag",
        ),
    ],
)
def test_delete_rejects_non_custom_active_tags(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
    slug,
    status,
    active,
    builtin,
    expected_error,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    path = _write_dataset(tmp_path, [_entry([slug])])

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(
            session,
            slug=slug,
            category=category,
            status=status,
            active=active,
        ).is_builtin = builtin
        session.commit()
    finally:
        session.close()

    result = delete_active_tag(
        tag_slug=slug,
        dataset_path=str(path),
        entries=[_entry([slug])],
    )

    assert result.ok is False
    assert expected_error in result.errors


def test_delete_rejects_missing_tag_and_missing_dataset(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    path = _write_dataset(tmp_path, [_entry(["missing_tag"])])

    missing_tag = delete_active_tag(
        tag_slug="missing_tag",
        dataset_path=str(path),
        entries=[_entry(["missing_tag"])],
    )
    missing_dataset = delete_active_tag(
        tag_slug="missing_tag",
        dataset_path=str(tmp_path / "missing.jsonl"),
        entries=[_entry(["missing_tag"])],
    )

    assert missing_tag.ok is False
    assert missing_tag.errors == ["Tag not found: Missing Tag"]
    assert missing_dataset.ok is False
    assert missing_dataset.errors == ["Dataset file was not found."]


def test_delete_backup_failures_fail_closed(tag_lifecycle_db, tmp_path, monkeypatch):
    entries = [_entry(["source_tag"])]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="source_tag", name="Source Tag", category=category)
        session.commit()
    finally:
        session.close()

    def fail_dataset_backup(dataset_path, reason):
        raise OSError("dataset backup blocked")

    monkeypatch.setattr(
        tag_lifecycle_service,
        "create_dataset_backup",
        fail_dataset_backup,
    )

    dataset_failure = delete_active_tag(
        tag_slug="source_tag",
        dataset_path=str(path),
        entries=entries,
    )
    assert dataset_failure.ok is False
    assert "dataset backup blocked" in dataset_failure.message

    _fake_dataset_backup(tmp_path, monkeypatch)

    def fail_db_backup(*, engine):
        raise OSError("db backup blocked")

    monkeypatch.setattr(tag_registry, "create_db_backup", fail_db_backup)

    db_failure = delete_active_tag(
        tag_slug="source_tag",
        dataset_path=str(path),
        entries=entries,
    )
    assert db_failure.ok is False
    assert db_failure.message == "Could not create database backup: db backup blocked"

    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="source_tag").one()
        assert tag.status == TAG_STATUS_ACTIVE
        assert tag.is_active is True
        assert tag.category_id is not None
        assert session.query(TagLifecycleMetadata).count() == 0
    finally:
        session.close()
    assert load_dataset(path)[0] == entries


def test_delete_dataset_save_failure_rolls_back_db(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [_entry(["source_tag"])]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="source_tag", name="Source Tag", category=category)
        session.commit()
    finally:
        session.close()

    def fail_save(dataset_path, proposed_entries):
        raise OSError("save blocked")

    monkeypatch.setattr(tag_lifecycle_service, "save_dataset", fail_save)

    result = delete_active_tag(
        tag_slug="source_tag",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is False
    assert result.message == "Failed to save dataset: save blocked"
    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="source_tag").one()
        assert tag.status == TAG_STATUS_ACTIVE
        assert tag.is_active is True
        assert tag.category_id is not None
        assert session.query(TagLifecycleMetadata).count() == 0
    finally:
        session.close()
    assert load_dataset(path)[0] == entries


@pytest.mark.parametrize(
    ("slug", "status", "active", "builtin", "expected_error"),
    [
        (
            "builtin_tag",
            TAG_STATUS_ACTIVE,
            True,
            True,
            "Built-in tags cannot be edited: Builtin Tag",
        ),
        (
            "archived_tag",
            TAG_STATUS_ARCHIVED,
            False,
            False,
            "Tag is not an active custom tag: Archived Tag",
        ),
        (
            "hidden_tag",
            TAG_STATUS_HIDDEN,
            False,
            False,
            "Tag is not an active custom tag: Hidden Tag",
        ),
    ],
)
def test_rename_rejects_non_custom_active_tags(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
    slug,
    status,
    active,
    builtin,
    expected_error,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    path = _write_dataset(tmp_path, [_entry([slug])])

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(
            session,
            slug=slug,
            category=category,
            status=status,
            active=active,
        ).is_builtin = builtin
        session.commit()
    finally:
        session.close()

    result = rename_active_tag(
        old_slug=slug,
        new_display_name="Renamed Tag",
        dataset_path=str(path),
        entries=[_entry([slug])],
    )

    assert result.ok is False
    assert expected_error in result.errors


def test_rename_rejects_duplicate_empty_same_and_alias_reserved_names(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    path = _write_dataset(tmp_path, [_entry(["source_tag"])])

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="source_tag", name="Source Tag", category=category)
        _add_tag(session, slug="duplicate_tag", name="Duplicate Tag", category=category)
        tag_registry.upsert_tag_lifecycle_metadata(
            action=tag_registry.TAG_LIFECYCLE_METADATA_RENAME,
            old_slug="reserved_tag",
            new_slug="duplicate_tag",
            metadata=tag_registry.build_rename_alias_metadata(
                old_slug="reserved_tag",
                new_slug="duplicate_tag",
            ),
            session=session,
        )
        session.commit()
    finally:
        session.close()

    duplicate = rename_active_tag(
        old_slug="source_tag",
        new_display_name="Duplicate Tag",
        dataset_path=str(path),
        entries=[_entry(["source_tag"])],
    )
    empty = rename_active_tag(
        old_slug="source_tag",
        new_display_name="!!!",
        dataset_path=str(path),
        entries=[_entry(["source_tag"])],
    )
    same = rename_active_tag(
        old_slug="source_tag",
        new_display_name="Source Tag",
        dataset_path=str(path),
        entries=[_entry(["source_tag"])],
    )
    reserved = rename_active_tag(
        old_slug="source_tag",
        new_display_name="Reserved Tag",
        dataset_path=str(path),
        entries=[_entry(["source_tag"])],
    )

    assert duplicate.ok is False
    assert duplicate.errors == ["A tag named Duplicate Tag already exists."]
    assert empty.ok is False
    assert "Tag name cannot be empty." in empty.errors
    assert same.ok is True
    assert same.affected_count == 0
    assert same.dataset_backup_path is None
    assert reserved.ok is False
    assert reserved.errors == [
        "Canonical ID is reserved by lifecycle metadata: Reserved Tag"
    ]


def test_edit_rejects_missing_or_inactive_category(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [_entry(["source_tag"])]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_category(session, slug="inactive", name="Inactive", active=False)
        _add_tag(session, slug="source_tag", name="Source Tag", category=category)
        session.commit()
    finally:
        session.close()

    missing = edit_active_tag(
        old_slug="source_tag",
        new_display_name="Source Tag",
        category_slug="missing",
        dataset_path=str(path),
        entries=entries,
    )
    inactive = edit_active_tag(
        old_slug="source_tag",
        new_display_name="Source Tag",
        category_slug="inactive",
        dataset_path=str(path),
        entries=entries,
    )

    assert missing.ok is False
    assert inactive.ok is False
    assert missing.errors == ["Selected category does not exist or is inactive."]
    assert inactive.errors == ["Selected category does not exist or is inactive."]


def test_rename_backup_failures_fail_closed(tag_lifecycle_db, tmp_path, monkeypatch):
    entries = [_entry(["source_tag"])]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="source_tag", name="Source Tag", category=category)
        session.commit()
    finally:
        session.close()

    def fail_dataset_backup(dataset_path, reason):
        raise OSError("dataset backup blocked")

    monkeypatch.setattr(
        tag_lifecycle_service,
        "create_dataset_backup",
        fail_dataset_backup,
    )

    dataset_failure = rename_active_tag(
        old_slug="source_tag",
        new_display_name="Renamed Tag",
        dataset_path=str(path),
        entries=entries,
    )
    assert dataset_failure.ok is False
    assert "dataset backup blocked" in dataset_failure.message

    _fake_dataset_backup(tmp_path, monkeypatch)

    def fail_db_backup(*, engine):
        raise OSError("db backup blocked")

    monkeypatch.setattr(tag_registry, "create_db_backup", fail_db_backup)

    db_failure = rename_active_tag(
        old_slug="source_tag",
        new_display_name="Renamed Tag",
        dataset_path=str(path),
        entries=entries,
    )
    assert db_failure.ok is False
    assert db_failure.message == "Could not create database backup: db backup blocked"

    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="source_tag").one()
        assert tag.name == "Source Tag"
        assert session.query(Tag).filter_by(slug="renamed_tag").count() == 0
        assert session.query(TagLifecycleMetadata).count() == 0
    finally:
        session.close()
    assert load_dataset(path)[0] == entries


def test_rename_dataset_save_failure_rolls_back_db(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [_entry(["source_tag"])]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="source_tag", name="Source Tag", category=category)
        session.commit()
    finally:
        session.close()

    def fail_save(dataset_path, proposed_entries):
        raise OSError("save blocked")

    monkeypatch.setattr(tag_lifecycle_service, "save_dataset", fail_save)

    result = rename_active_tag(
        old_slug="source_tag",
        new_display_name="Renamed Tag",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is False
    assert result.message == "Failed to save dataset: save blocked"
    session = tag_lifecycle_db()
    try:
        assert session.query(Tag).filter_by(slug="source_tag").count() == 1
        assert session.query(Tag).filter_by(slug="renamed_tag").count() == 0
        assert session.query(TagLifecycleMetadata).count() == 0
    finally:
        session.close()
    assert load_dataset(path)[0] == entries


def test_unknown_import_still_creates_archived_imported_tag(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        _add_category(session)
        session.commit()
    finally:
        session.close()

    summary = tag_registry.ensure_tags_exist_for_dataset([{"tags": ["Slow Burn"]}])

    assert summary.created_slugs == ["slow_burn"]
    assert "slow_burn" not in tag_registry.get_all_tag_slugs()
    assert [tag["slug"] for tag in tag_registry.get_imported_archived_tags()] == [
        "slow_burn"
    ]
