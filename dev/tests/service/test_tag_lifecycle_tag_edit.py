import pytest

from dev.tests.service.tag_lifecycle_service_test_helpers import (
    TAG_LIFECYCLE_METADATA_RENAME,
    TAG_RESOLUTION_ALIAS_MAPPED,
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
    _without_rolethread_meta,
    _write_dataset,
    edit_active_tag,
    json,
    load_dataset,
    tag_lifecycle_db,
    tag_lifecycle_service,
    tag_metadata,
    tag_registry,
    tag_resolution,
)


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

    result = edit_active_tag(
        old_slug="followup_question",
        new_display_name="Follow Up Question",
        category_slug="behavior",
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
    assert _without_rolethread_meta(result.entries) == [
        _entry(["follow_up_question", "tone"]),
        _entry(["tone", "follow_up_question"]),
        _entry(["other_tag"]),
    ]
    _assert_stamped(result.entries)

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
                action=TAG_LIFECYCLE_METADATA_RENAME,
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

    active_slugs = tag_registry.get_tag_registry_snapshot().active_tag_slugs
    assert "follow_up_question" in active_slugs
    assert "followup_question" not in active_slugs

    resolved = tag_resolution.resolve_tag_lifecycle("Followup Question")
    assert resolved.result_type == TAG_RESOLUTION_ALIAS_MAPPED
    assert resolved.resolved_slug == "follow_up_question"


def test_rename_chain_preserves_alias_history_and_resolves_original_slug(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [_entry(["old_tag"])]
    path = _write_dataset(tmp_path, entries)

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="old_tag", name="Old Tag", category=category)
        session.commit()
    finally:
        session.close()

    first = edit_active_tag(
        old_slug="old_tag",
        new_display_name="Middle Tag",
        category_slug="behavior",
        dataset_path=str(path),
        entries=entries,
    )
    second = edit_active_tag(
        old_slug="middle_tag",
        new_display_name="Final Tag",
        category_slug="behavior",
        dataset_path=str(path),
        entries=first.entries,
    )

    assert first.ok is True
    assert second.ok is True
    assert _without_rolethread_meta(second.entries) == [_entry(["final_tag"])]

    session = tag_lifecycle_db()
    try:
        aliases = (
            session.query(TagLifecycleMetadata)
            .filter_by(action=TAG_LIFECYCLE_METADATA_RENAME)
            .order_by(TagLifecycleMetadata.id)
            .all()
        )
        assert [(alias.old_slug, alias.new_slug) for alias in aliases] == [
            ("old_tag", "middle_tag"),
            ("middle_tag", "final_tag"),
        ]
        assert session.query(Tag).filter_by(slug="final_tag").one().status == (
            TAG_STATUS_ACTIVE
        )
        assert session.query(Tag).filter_by(slug="old_tag").count() == 0
        assert session.query(Tag).filter_by(slug="middle_tag").count() == 0
    finally:
        session.close()

    original = tag_resolution.resolve_tag_lifecycle("Old Tag")
    intermediate = tag_resolution.resolve_tag_lifecycle("Middle Tag")
    assert original.result_type == TAG_RESOLUTION_ALIAS_MAPPED
    assert original.resolved_slug == "final_tag"
    assert intermediate.result_type == TAG_RESOLUTION_ALIAS_MAPPED
    assert intermediate.resolved_slug == "final_tag"


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

    result = edit_active_tag(
        old_slug="old_tag",
        new_display_name="New Tag",
        category_slug="behavior",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is True
    assert _without_rolethread_meta(result.entries) == [_entry(["new_tag"])]
    _assert_stamped(result.entries)

def test_tag_lifecycle_rewrite_refreshes_registry_sidecar(
    tag_lifecycle_db,
    tmp_path,
    monkeypatch,
):
    _fake_dataset_backup(tmp_path, monkeypatch)
    entries = [_entry(["old_tag"])]
    path = _write_dataset(tmp_path, entries)
    sidecar_calls = []

    session = tag_lifecycle_db()
    try:
        category = _add_category(session)
        _add_tag(session, slug="old_tag", name="Old Tag", category=category)
        session.commit()
    finally:
        session.close()

    monkeypatch.setattr(
        tag_lifecycle_service,
        "export_registry_sidecar",
        lambda *, dataset_path, entries: sidecar_calls.append(
            (dataset_path, json.loads(json.dumps(entries)))
        )
        or type("Result", (), {"ok": True, "message": "ok"})(),
    )

    result = edit_active_tag(
        old_slug="old_tag",
        new_display_name="New Tag",
        category_slug="behavior",
        dataset_path=str(path),
        entries=entries,
    )

    assert result.ok is True
    assert sidecar_calls == [(str(path), result.entries)]

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
            action=TAG_LIFECYCLE_METADATA_RENAME
        ).count() == 0
    finally:
        session.close()

    registry = tag_registry.get_tag_registry_snapshot().active_registry
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
    assert _without_rolethread_meta(result.entries) == [_entry(["follow_up_question"])]
    _assert_stamped(result.entries)
    assert result.dataset_backup_path is not None
    assert result.db_backup_path is not None

    session = tag_lifecycle_db()
    try:
        tag = session.query(Tag).filter_by(slug="follow_up_question").one()
        assert tag.name == "Follow Up Question"
        assert tag.category_id == scene_id
        alias = session.query(TagLifecycleMetadata).filter_by(
            old_slug="followup_question",
            action=TAG_LIFECYCLE_METADATA_RENAME,
        ).one()
        assert alias.new_slug == "follow_up_question"
        current_metadata = _metadata_for(session, "follow_up_question")
        assert current_metadata["assigned_category_slug"] == "scene"
    finally:
        session.close()

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

    result = edit_active_tag(
        old_slug=slug,
        new_display_name="Renamed Tag",
        category_slug="behavior",
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
        tag_metadata.upsert_tag_lifecycle_metadata(
            action=TAG_LIFECYCLE_METADATA_RENAME,
            old_slug="reserved_tag",
            new_slug="duplicate_tag",
            metadata=tag_metadata.build_rename_alias_metadata(
                old_slug="reserved_tag",
                new_slug="duplicate_tag",
            ),
            session=session,
        )
        session.commit()
    finally:
        session.close()

    duplicate = edit_active_tag(
        old_slug="source_tag",
        new_display_name="Duplicate Tag",
        category_slug="behavior",
        dataset_path=str(path),
        entries=[_entry(["source_tag"])],
    )
    empty = edit_active_tag(
        old_slug="source_tag",
        new_display_name="!!!",
        category_slug="behavior",
        dataset_path=str(path),
        entries=[_entry(["source_tag"])],
    )
    same = edit_active_tag(
        old_slug="source_tag",
        new_display_name="Source Tag",
        category_slug="behavior",
        dataset_path=str(path),
        entries=[_entry(["source_tag"])],
    )
    reserved = edit_active_tag(
        old_slug="source_tag",
        new_display_name="Reserved Tag",
        category_slug="behavior",
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

    dataset_failure = edit_active_tag(
        old_slug="source_tag",
        new_display_name="Renamed Tag",
        category_slug="behavior",
        dataset_path=str(path),
        entries=entries,
    )
    assert dataset_failure.ok is False
    assert "dataset backup blocked" in dataset_failure.message

    _fake_dataset_backup(tmp_path, monkeypatch)

    def fail_db_backup(*, engine):
        raise OSError("db backup blocked")

    monkeypatch.setattr(tag_lifecycle_service, "create_db_backup", fail_db_backup)

    db_failure = edit_active_tag(
        old_slug="source_tag",
        new_display_name="Renamed Tag",
        category_slug="behavior",
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

    result = edit_active_tag(
        old_slug="source_tag",
        new_display_name="Renamed Tag",
        category_slug="behavior",
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

