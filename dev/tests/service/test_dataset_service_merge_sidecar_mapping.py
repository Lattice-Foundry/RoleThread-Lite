from dev.tests.service.dataset_service_test_helpers import (
    Character,
    EntryCharacterTurn,
    SidecarAlias,
    SidecarCategory,
    SidecarCharacter,
    SidecarDatasetInfo,
    SidecarEntryCharacterMapping,
    SidecarMetadata,
    SidecarRegistry,
    SidecarTag,
    SimpleNamespace,
    Tag,
    TagCategory,
    _entry,
    _registry_session_factory,
    get_entry_uuid,
    merge_datasets,
    read_sidecar,
    save_dataset,
    save_merged_entries_service,
    sidecar_path_for_dataset,
    stamp_entries,
    tag_resolution,
    write_sidecar,
)


def test_save_merged_entries_service_imports_source_sidecar_registry_metadata(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "merged.jsonl"
    source_entries = [_entry(tags=["slowburn"])]
    save_dataset(str(source_path), source_entries)
    source_sidecar_path = sidecar_path_for_dataset(source_path)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="source-dataset-uuid",
                filename=source_path.name,
            ),
            categories=(
                SidecarCategory(
                    slug="behavior",
                    name="Behavior",
                    sort_order=0,
                    is_builtin=True,
                ),
            ),
            tags=(
                SidecarTag(
                    slug="slow_burn",
                    name="Slow Burn",
                    category_slug="behavior",
                    status="active",
                ),
            ),
            aliases=(
                SidecarAlias(
                    old_slug="slowburn",
                    new_slug="slow_burn",
                    action="rename",
                    metadata={"resolver_behavior": "map_to_target"},
                ),
            ),
            characters=(
                SidecarCharacter(slug="scott", display_name="Scott"),
            ),
        ),
        source_sidecar_path,
    )
    original_source_text = source_path.read_text(encoding="utf-8")
    original_sidecar_text = source_sidecar_path.read_text(encoding="utf-8")

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.source_sidecar_summary.found_count == 1
    assert result.source_sidecar_summary.imported_count == 1
    assert result.source_sidecar_summary.categories_created == ["behavior"]
    assert result.source_sidecar_summary.tags_created == ["slow_burn"]
    assert result.source_sidecar_summary.aliases_imported == ["slowburn"]
    assert result.source_sidecar_summary.characters_created == ["scott"]
    assert result.source_sidecar_summary.character_mappings_imported == []
    assert result.entries[0]["tags"] == ["slow_burn"]
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert [category.slug for category in output_sidecar.categories] == ["behavior"]
    assert [tag.slug for tag in output_sidecar.tags] == ["slow_burn"]
    assert [alias.old_slug for alias in output_sidecar.aliases] == ["slowburn"]
    assert [character.slug for character in output_sidecar.characters] == ["scott"]
    assert output_sidecar.entry_character_mappings == ()
    assert source_path.read_text(encoding="utf-8") == original_source_text
    assert source_sidecar_path.read_text(encoding="utf-8") == original_sidecar_text

    session = session_factory()
    try:
        assert session.query(TagCategory).filter_by(slug="behavior").count() == 1
        assert session.query(Tag).filter_by(slug="slow_burn").count() == 1
        assert session.query(Character).filter_by(slug="scott").count() == 1
        assert session.query(EntryCharacterTurn).count() == 0
    finally:
        session.close()

def test_save_merged_entries_service_preserves_source_character_mapping_for_survivor(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "merged.jsonl"
    source_entries = stamp_entries(
        [_entry(user="Scott speaks", tags=[])],
        dataset_uuid="source-dataset-uuid",
    )
    source_entry_uuid = get_entry_uuid(source_entries[0])
    save_dataset(str(source_path), source_entries)
    source_sidecar_path = sidecar_path_for_dataset(source_path)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="source-dataset-uuid",
                filename=source_path.name,
            ),
            characters=(SidecarCharacter(slug="scott", display_name="Scott"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid=source_entry_uuid,
                    turns=(
                        {
                            "turn_index": 1,
                            "character_slug": "scott",
                            "training_role": "user",
                            "source_role_label": "Scott",
                        },
                    ),
                ),
            ),
        ),
        source_sidecar_path,
    )
    original_source_text = source_path.read_text(encoding="utf-8")
    original_sidecar_text = source_sidecar_path.read_text(encoding="utf-8")

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.source_sidecar_summary.character_mappings_imported == [
        source_entry_uuid
    ]
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert len(output_sidecar.entry_character_mappings) == 1
    mapping = output_sidecar.entry_character_mappings[0]
    assert mapping.entry_uuid == source_entry_uuid
    assert mapping.turns == (
        {
            "turn_index": 1,
            "character_slug": "scott",
            "training_role": "user",
            "source_role_label": "Scott",
        },
    )
    assert [character.slug for character in output_sidecar.characters] == ["scott"]
    assert source_path.read_text(encoding="utf-8") == original_source_text
    assert source_sidecar_path.read_text(encoding="utf-8") == original_sidecar_text

    session = session_factory()
    try:
        mappings = session.query(EntryCharacterTurn).all()
        assert len(mappings) == 1
        assert mappings[0].entry_uuid == source_entry_uuid
        assert mappings[0].character.slug == "scott"
    finally:
        session.close()

def test_save_merged_entries_service_skips_character_mapping_for_discarded_duplicate(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    survivor_path = tmp_path / "survivor.jsonl"
    discarded_path = tmp_path / "discarded.jsonl"
    output_path = tmp_path / "merged.jsonl"
    survivor_entries = stamp_entries(
        [_entry(user="Same conversation", tags=[])],
        dataset_uuid="survivor-dataset-uuid",
    )
    discarded_entries = stamp_entries(
        [_entry(user="Same conversation", tags=[])],
        dataset_uuid="discarded-dataset-uuid",
    )
    survivor_uuid = get_entry_uuid(survivor_entries[0])
    discarded_uuid = get_entry_uuid(discarded_entries[0])
    save_dataset(str(survivor_path), survivor_entries)
    save_dataset(str(discarded_path), discarded_entries)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="discarded-dataset-uuid",
                filename=discarded_path.name,
            ),
            characters=(SidecarCharacter(slug="emma", display_name="Emma"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid=discarded_uuid,
                    turns=(
                        {
                            "turn_index": 2,
                            "character_slug": "emma",
                            "training_role": "assistant",
                            "source_role_label": "Emma",
                        },
                    ),
                ),
            ),
        ),
        sidecar_path_for_dataset(discarded_path),
    )

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=survivor_entries,
        source_paths=[str(survivor_path), str(discarded_path)],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.source_sidecar_summary.character_mappings_imported == []
    assert any(
        discarded_uuid in warning
        for warning in result.source_sidecar_summary.warnings
    )
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert output_sidecar.entry_character_mappings == ()
    assert get_entry_uuid(result.entries[0]) == survivor_uuid

    session = session_factory()
    try:
        assert session.query(EntryCharacterTurn).filter_by(
            entry_uuid=discarded_uuid
        ).count() == 0
    finally:
        session.close()

def test_merge_then_save_preserves_duplicate_tags_and_skips_discarded_mapping(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    session = session_factory()
    try:
        category = TagCategory(slug="behavior", name="Behavior")
        session.add(category)
        session.flush()
        session.add_all([
            Tag(
                slug="first_tag",
                name="First Tag",
                category_id=category.id,
                status="active",
            ),
            Tag(
                slug="new_tag",
                name="New Tag",
                category_id=category.id,
                status="active",
            ),
        ])
        session.commit()
    finally:
        session.close()

    def fake_resolve_tag_lifecycle(tag):
        if tag == "old_tag":
            return SimpleNamespace(should_rewrite_slug=True, resolved_slug="new_tag")
        return SimpleNamespace(should_rewrite_slug=False, resolved_slug=tag)

    monkeypatch.setattr(tag_resolution, "resolve_tag_lifecycle", fake_resolve_tag_lifecycle)

    survivor_path = tmp_path / "survivor.jsonl"
    duplicate_path = tmp_path / "duplicate.jsonl"
    output_path = tmp_path / "merged.jsonl"
    survivor_entries = stamp_entries(
        [
            _entry(
                user="Same conversation",
                assistant="Same reply",
                tags=["first_tag"],
            )
        ],
        dataset_uuid="survivor-dataset-uuid",
    )
    duplicate_entries = stamp_entries(
        [
            _entry(
                user="Same conversation",
                assistant="Same reply",
                tags=["old_tag"],
            )
        ],
        dataset_uuid="duplicate-dataset-uuid",
    )
    duplicate_uuid = get_entry_uuid(duplicate_entries[0])
    save_dataset(str(survivor_path), survivor_entries)
    save_dataset(str(duplicate_path), duplicate_entries)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="duplicate-dataset-uuid",
                filename=duplicate_path.name,
            ),
            characters=(SidecarCharacter(slug="emma", display_name="Emma"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid=duplicate_uuid,
                    turns=(
                        {
                            "turn_index": 2,
                            "character_slug": "emma",
                            "training_role": "assistant",
                            "source_role_label": "Emma",
                        },
                    ),
                ),
            ),
        ),
        sidecar_path_for_dataset(duplicate_path),
    )

    merged, stats = merge_datasets(
        [str(survivor_path), str(duplicate_path)],
        shuffle=False,
    )
    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=merged,
        source_paths=[str(survivor_path), str(duplicate_path)],
        backup_enabled=False,
    )

    assert stats["duplicates_removed"] == 1
    assert result.ok is True
    assert result.entries[0]["tags"] == ["first_tag", "new_tag"]
    assert result.source_sidecar_summary.character_mappings_imported == []
    assert any(
        duplicate_uuid in warning
        for warning in result.source_sidecar_summary.warnings
    )
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert output_sidecar.dataset_info.tag_usage_counts == {
        "first_tag": 1,
        "new_tag": 1,
    }
    assert [tag.slug for tag in output_sidecar.tags] == ["first_tag", "new_tag"]
    assert output_sidecar.entry_character_mappings == ()
    session = session_factory()
    try:
        assert session.query(EntryCharacterTurn).filter_by(
            entry_uuid=duplicate_uuid
        ).count() == 0
    finally:
        session.close()

def test_save_merged_entries_service_skips_character_mapping_for_absent_entry_uuid(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "merged.jsonl"
    source_entries = stamp_entries(
        [_entry(user="Present", tags=[])],
        dataset_uuid="source-dataset-uuid",
    )
    save_dataset(str(source_path), source_entries)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="source-dataset-uuid",
                filename=source_path.name,
            ),
            characters=(SidecarCharacter(slug="kai", display_name="Kai"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid="absent-entry-uuid",
                    turns=(
                        {
                            "turn_index": 1,
                            "character_slug": "kai",
                            "training_role": "user",
                            "source_role_label": "Kai",
                        },
                    ),
                ),
            ),
        ),
        sidecar_path_for_dataset(source_path),
    )

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )

    assert result.ok is True
    assert result.source_sidecar_summary.character_mappings_imported == []
    assert any(
        "absent-entry-uuid" in warning
        for warning in result.source_sidecar_summary.warnings
    )
    assert (
        read_sidecar(sidecar_path_for_dataset(output_path)).entry_character_mappings
        == ()
    )
    session = session_factory()
    try:
        assert session.query(EntryCharacterTurn).filter_by(
            entry_uuid="absent-entry-uuid"
        ).count() == 0
    finally:
        session.close()

def test_save_merged_entries_service_character_mapping_import_is_idempotent(
    tmp_path,
    monkeypatch,
):
    session_factory = _registry_session_factory(tmp_path, monkeypatch)
    source_path = tmp_path / "source.jsonl"
    output_path = tmp_path / "merged.jsonl"
    source_entries = stamp_entries(
        [_entry(user="Scott speaks", tags=[])],
        dataset_uuid="source-dataset-uuid",
    )
    source_entry_uuid = get_entry_uuid(source_entries[0])
    save_dataset(str(source_path), source_entries)
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00Z"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="source-dataset-uuid",
                filename=source_path.name,
            ),
            characters=(SidecarCharacter(slug="scott", display_name="Scott"),),
            entry_character_mappings=(
                SidecarEntryCharacterMapping(
                    entry_uuid=source_entry_uuid,
                    turns=(
                        {
                            "turn_index": 1,
                            "character_slug": "scott",
                            "training_role": "user",
                            "source_role_label": "Scott",
                        },
                    ),
                ),
            ),
        ),
        sidecar_path_for_dataset(source_path),
    )

    first = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )
    second = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=source_entries,
        source_paths=[str(source_path)],
        backup_enabled=False,
    )

    assert first.ok is True
    assert second.ok is True
    assert second.source_sidecar_summary.character_mappings_imported == [
        source_entry_uuid
    ]
    output_sidecar = read_sidecar(sidecar_path_for_dataset(output_path))
    assert len(output_sidecar.entry_character_mappings) == 1
    session = session_factory()
    try:
        mappings = session.query(EntryCharacterTurn).filter_by(
            entry_uuid=source_entry_uuid
        ).all()
        assert len(mappings) == 1
    finally:
        session.close()

def test_save_merged_entries_service_skips_missing_and_bad_source_sidecars(
    tmp_path,
    monkeypatch,
):
    _registry_session_factory(tmp_path, monkeypatch)
    missing_source = tmp_path / "missing_sidecar.jsonl"
    bad_source = tmp_path / "bad_sidecar.jsonl"
    output_path = tmp_path / "merged.jsonl"
    entries = [_entry(tags=["merged"])]
    save_dataset(str(missing_source), entries)
    save_dataset(str(bad_source), entries)
    bad_sidecar_path = sidecar_path_for_dataset(bad_source)
    bad_sidecar_path.write_text("{not valid json}", encoding="utf-8")

    result = save_merged_entries_service(
        dataset_path=str(output_path),
        entries=entries,
        source_paths=[str(missing_source), str(bad_source)],
        backup_enabled=False,
    )

    assert result.ok is True
    summary = result.source_sidecar_summary
    assert summary.source_count == 2
    assert summary.found_count == 1
    assert summary.imported_count == 0
    assert summary.missing_paths == [str(sidecar_path_for_dataset(missing_source))]
    assert summary.failed_paths == [str(bad_sidecar_path)]
    assert summary.errors
