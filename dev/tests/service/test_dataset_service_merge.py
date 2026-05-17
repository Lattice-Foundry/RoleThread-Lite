from dev.tests.service.dataset_service_test_helpers import (
    SidecarDatasetInfo,
    SidecarMetadata,
    SidecarRegistry,
    SimpleNamespace,
    _assert_stamped,
    _backup_recorder,
    _entry,
    _fail_if_backup_called,
    _force_backup_failure,
    _read_entries,
    _without_rolethread_meta,
    copy,
    get_dataset_uuid_for_entries,
    read_sidecar,
    save_dataset,
    save_merged_entries_service,
    sidecar_path_for_dataset,
    stamp_entries,
    tag_resolution,
    write_sidecar,
)


def test_save_merged_entries_service_saves_new_output_and_preserves_metadata(tmp_path):
    path = tmp_path / "merged.jsonl"
    entries = [_entry(tags=["merged"], metadata={"source": "merge"})]
    original_entries = copy.deepcopy(entries)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=entries,
        backup_enabled=True,
    )

    assert result.ok is True
    assert result.backup_path is None
    assert _without_rolethread_meta(result.entries) == entries
    _assert_stamped(result.entries)
    assert entries == original_entries
    assert _read_entries(path) == result.entries

def test_save_merged_entries_service_forces_new_dataset_uuid_for_single_source_dataset(
    tmp_path,
):
    path = tmp_path / "merged.jsonl"
    source_uuid = "source-dataset-uuid"
    entries = stamp_entries([_entry(tags=["merged"])], dataset_uuid=source_uuid)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=entries,
        backup_enabled=False,
    )

    assert result.ok is True
    merged_uuid = get_dataset_uuid_for_entries(result.entries)
    assert merged_uuid is not None
    assert merged_uuid != source_uuid
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert sidecar.dataset_info.dataset_uuid == merged_uuid

def test_save_merged_entries_service_forces_new_dataset_uuid_for_multiple_sources(
    tmp_path,
):
    path = tmp_path / "merged.jsonl"
    source_one = stamp_entries([_entry(user="One", tags=["one"])], dataset_uuid="source-one")
    source_two = stamp_entries([_entry(user="Two", tags=["two"])], dataset_uuid="source-two")

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=source_one + source_two,
        backup_enabled=False,
    )

    assert result.ok is True
    merged_uuid = get_dataset_uuid_for_entries(result.entries)
    assert merged_uuid is not None
    assert merged_uuid not in {"source-one", "source-two"}
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert sidecar.dataset_info.dataset_uuid == merged_uuid

def test_save_merged_entries_service_does_not_reuse_existing_output_sidecar_uuid(
    tmp_path,
):
    path = tmp_path / "merged.jsonl"
    existing_sidecar_uuid = "existing-output-sidecar-uuid"
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid=existing_sidecar_uuid,
                filename=path.name,
            ),
        ),
        sidecar_path_for_dataset(path),
    )

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["merged"])],
        backup_enabled=False,
    )

    assert result.ok is True
    merged_uuid = get_dataset_uuid_for_entries(result.entries)
    assert merged_uuid is not None
    assert merged_uuid != existing_sidecar_uuid
    sidecar = read_sidecar(sidecar_path_for_dataset(path))
    assert sidecar.dataset_info.dataset_uuid == merged_uuid

def test_save_merged_entries_service_canonicalizes_alias_tags(tmp_path, monkeypatch):
    path = tmp_path / "merged.jsonl"

    def fake_resolve_tag_lifecycle(tag):
        if tag == "old_tag":
            return SimpleNamespace(should_rewrite_slug=True, resolved_slug="new_tag")
        return SimpleNamespace(should_rewrite_slug=False, resolved_slug=tag)

    monkeypatch.setattr(tag_resolution, "resolve_tag_lifecycle", fake_resolve_tag_lifecycle)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["old_tag", "new_tag", "kept_tag"])],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.entries[0]["tags"] == ["new_tag", "kept_tag"]
    assert _read_entries(path)[0]["tags"] == ["new_tag", "kept_tag"]

def test_save_merged_entries_service_overwrite_backup_enabled_and_disabled(tmp_path, monkeypatch):
    path = tmp_path / "merged.jsonl"
    original = [_entry(tags=["old"])]
    save_dataset(str(path), original)
    backups = _backup_recorder(monkeypatch, tmp_path)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["new"])],
        backup_enabled=True,
    )

    assert result.ok is True
    assert len(backups) == 1
    assert result.backup_path == str(backups[0])

    _fail_if_backup_called(monkeypatch)
    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["newer"])],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.backup_path is None
    assert _read_entries(path) == result.entries

def test_save_merged_entries_service_invalid_path_fails_safely():
    result = save_merged_entries_service(
        dataset_path="",
        entries=[],
        backup_enabled=False,
    )

    assert result.ok is False
    assert result.entries is None

def test_save_merged_entries_service_backup_failure_aborts_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "merged.jsonl"
    existing = [_entry(tags=["existing"])]
    save_dataset(str(path), existing)
    _force_backup_failure(monkeypatch)

    result = save_merged_entries_service(
        dataset_path=str(path),
        entries=[_entry(tags=["replacement"])],
        backup_enabled=True,
    )

    assert result.ok is False
    assert _read_entries(path) == existing

