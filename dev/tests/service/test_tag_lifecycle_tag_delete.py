import pytest

from dev.tests.service.tag_lifecycle_service_test_helpers import (
    TAG_RESOLUTION_ARCHIVED,
    TAG_STATUS_ACTIVE,
    TAG_STATUS_ARCHIVED,
    TAG_STATUS_HIDDEN,
    Tag,
    TagLifecycleMetadata,
    _add_category,
    _add_tag,
    _assert_stamped,
    _entry,
    _fake_dataset_backup,
    _metadata_for,
    _without_loreforge_meta,
    _write_dataset,
    delete_active_tag,
    load_dataset,
    tag_lifecycle_db,
    tag_lifecycle_service,
    tag_metadata,
    tag_registry,
    tag_resolution,
)


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
    assert _without_loreforge_meta(result.entries) == [
        _entry(["tone"]),
        _entry([]),
        _entry(["tone"]),
    ]
    _assert_stamped(result.entries)

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
        assert metadata == tag_metadata.build_deleted_archive_metadata("style")
    finally:
        session.close()

    assert "slow_burn" not in tag_registry.get_all_tag_slugs()
    deleted = tag_registry.get_deleted_archived_tags()
    assert [tag["slug"] for tag in deleted] == ["slow_burn"]
    assert deleted[0]["visible_badge"] == "Deleted"
    assert deleted[0]["can_assign_to_category"] is False
    resolved = tag_resolution.resolve_tag_lifecycle("Slow Burn")
    assert resolved.result_type == TAG_RESOLUTION_ARCHIVED

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

    monkeypatch.setattr(tag_lifecycle_service, "create_db_backup", fail_db_backup)

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
