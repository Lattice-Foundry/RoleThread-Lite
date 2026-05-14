from dev.tests.service.tag_lifecycle_service_test_helpers import (
    TAG_LIFECYCLE_METADATA_ARCHIVE,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
    Tag,
    _add_category,
    _add_imported_archived_tag,
    _add_tag,
    _metadata_for,
    assign_archived_imported_tags_to_category,
    tag_lifecycle_db,
    tag_lifecycle_service,
    tag_metadata,
    tag_registry,
)


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
        assert metadata == tag_metadata.build_active_assigned_metadata("behavior")
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

def test_assign_rejects_active_tag_without_creating_duplicate_slug(tag_lifecycle_db):
    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="slow_burn", category=category)
        session.commit()
    finally:
        session.close()

    result = assign_archived_imported_tags_to_category(
        tag_slugs=["slow_burn"],
        category_slug="behavior",
    )

    assert result.ok is False
    assert result.errors == ["Tag is not archived: Slow Burn"]

    session = tag_lifecycle_db()
    try:
        assert session.query(Tag).filter_by(slug="slow_burn").count() == 1
    finally:
        session.close()

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

    monkeypatch.setattr(tag_lifecycle_service, "create_db_backup", fail_backup)

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
        assert metadata == tag_metadata.build_imported_archive_metadata()
    finally:
        session.close()

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
