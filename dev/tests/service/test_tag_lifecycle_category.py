from dev.tests.service.tag_lifecycle_service_test_helpers import (
    CategoryHistory,
    Tag,
    TagCategory,
    _add_category,
    _add_tag,
    delete_empty_custom_category,
    json,
    rename_custom_category,
    tag_lifecycle_db,
    tag_lifecycle_service,
    tag_registry,
)


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

    registry = tag_registry.get_tag_registry_snapshot().active_registry
    assert "Story Shape" not in registry
    assert registry["Narrative Shape"] == ["slow_burn"]

def test_rename_custom_category_validation_and_noop_paths(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        _add_category(session, slug="behavior", name="Behavior")
        _add_category(session, slug="story_shape", name="Story Shape")
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

    monkeypatch.setattr(tag_lifecycle_service, "create_db_backup", fail_backup)

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

def test_delete_empty_custom_category_removes_category_without_touching_tags(
    tag_lifecycle_db,
):
    session = tag_lifecycle_db()
    try:
        _add_category(session, slug="story_shape", name="Story Shape")
        other = _add_category(session, slug="behavior", name="Behavior")
        tag = _add_tag(session, slug="slow_burn", category=other)
        tag_id = tag.id
        session.commit()
    finally:
        session.close()

    result = delete_empty_custom_category(category_slug="story_shape")

    assert result.ok is True
    assert result.message == 'Deleted category "Story Shape".'
    assert result.affected_count == 1
    assert result.category_slug == "story_shape"
    assert result.db_backup_path is not None
    assert result.dataset_backup_path is None

    session = tag_lifecycle_db()
    try:
        assert session.query(TagCategory).filter_by(slug="story_shape").count() == 0
        assert session.query(Tag).filter_by(id=tag_id).one().slug == "slow_burn"
        history = session.query(CategoryHistory).one()
        assert history.action == "delete"
        assert history.old_slug == "story_shape"
        assert history.old_display_name == "Story Shape"
        metadata = json.loads(history.metadata_json)
        assert metadata == {
            "delete_reason": "user_deleted_empty_category",
            "lifecycle_state": "deleted",
        }
    finally:
        session.close()

    registry = tag_registry.get_tag_registry_snapshot().active_registry
    assert "Story Shape" not in registry
    assert registry["Behavior"] == ["slow_burn"]

def test_delete_custom_category_validation_paths(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        builtin = _add_category(session, slug="behavior", name="Behavior")
        builtin_id = builtin.id
        non_empty = _add_category(session, slug="story_shape", name="Story Shape")
        _add_tag(session, slug="slow_burn", category=non_empty)
        _add_category(session, slug="empty_custom", name="Empty Custom")
        _add_category(session, slug="inactive", name="Inactive", active=False)
        session.commit()
    finally:
        session.close()

    builtin_result = delete_empty_custom_category(category_slug="behavior")
    missing = delete_empty_custom_category(category_slug="missing")
    inactive = delete_empty_custom_category(category_slug="inactive")
    non_empty_result = delete_empty_custom_category(category_slug="story_shape")
    invalid = delete_empty_custom_category(category_slug="!!!")

    assert builtin_result.ok is False
    assert builtin_result.errors == ["Built-in categories cannot be deleted: Behavior"]
    assert missing.ok is False
    assert missing.errors == ["Category not found: Missing"]
    assert inactive.ok is False
    assert inactive.errors == ["Category is inactive: Inactive"]
    assert non_empty_result.ok is False
    assert non_empty_result.errors == [
        "Move or delete all tags in this category before deleting it."
    ]
    assert invalid.ok is False
    assert invalid.errors == ["Selected category is invalid."]

    session = tag_lifecycle_db()
    try:
        assert session.query(TagCategory).filter_by(slug="behavior").one().id == builtin_id
        assert session.query(TagCategory).filter_by(slug="story_shape").count() == 1
        assert session.query(TagCategory).filter_by(slug="empty_custom").count() == 1
        assert session.query(CategoryHistory).count() == 0
    finally:
        session.close()

def test_delete_custom_category_backup_failure_fails_closed(
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

    monkeypatch.setattr(tag_lifecycle_service, "create_db_backup", fail_backup)

    result = delete_empty_custom_category(category_slug="story_shape")

    assert result.ok is False
    assert result.message == "Could not create database backup: db backup blocked"
    session = tag_lifecycle_db()
    try:
        assert session.query(TagCategory).filter_by(slug="story_shape").count() == 1
        assert session.query(CategoryHistory).count() == 0
    finally:
        session.close()
