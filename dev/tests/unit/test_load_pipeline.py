import json
from types import SimpleNamespace

import core.load_pipeline as core_load_pipeline
from core.dataset import DatasetDiagnosticSummary, TagNormalizationSummary, load_dataset_with_summary
from core.format_conversion import FORMAT_SHAREGPT
from core.loreforge_meta import LOREFORGE_META_KEY, get_entry_uuid, is_native_entry
from core.registry_sidecar import (
    SidecarDatasetInfo,
    SidecarMetadata,
    SidecarRegistry,
    read_sidecar,
    sidecar_path_for_dataset,
    write_sidecar,
)
from core.tag_constants import ARCHIVE_ORIGIN_IMPORTED, TAG_STATUS_ARCHIVED
import services.load_pipeline_service as load_pipeline


def _entry(tags=None):
    entry = {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ],
        "tags": tags or [],
    }
    return entry


def _patch_pipeline_defaults(monkeypatch):
    monkeypatch.setattr(
        load_pipeline,
        "ensure_tags_exist_for_dataset",
        lambda entries: SimpleNamespace(created_count=0, created_slugs=[]),
    )
    monkeypatch.setattr(core_load_pipeline, "get_tag_by_slug_any_status", lambda slug: None)
    monkeypatch.setattr(
        core_load_pipeline,
        "get_current_tag_lifecycle_metadata",
        lambda slug: {},
    )
    monkeypatch.setattr(
        load_pipeline,
        "resolve_tag_lifecycle",
        lambda slug: SimpleNamespace(should_rewrite_slug=False, resolved_slug=slug),
    )
    monkeypatch.setattr(
        load_pipeline,
        "normalize_known_character_roles",
        lambda entries: SimpleNamespace(
            entries=entries,
            mapping_payload=(),
            changed_entries=0,
            changed_turns=0,
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "upsert_character_mappings",
        lambda mappings: {"entries": 0, "turns": 0},
    )


def _load_summary(tmp_path, records):
    path = tmp_path / "dataset.jsonl"
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )
    return path, load_dataset_with_summary(str(path))


def test_pipeline_finalizes_sharegpt_load_without_streamlit(tmp_path, monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
    training_dir = tmp_path / "training_data"
    monkeypatch.setattr(
        "core.working_copy.get_default_training_data_dir",
        lambda: training_dir,
    )
    path, (summary, errors) = _load_summary(
        tmp_path,
        [
            {
                "conversations": [
                    {"from": "human", "value": "Hi"},
                    {"from": "gpt", "value": "Hello"},
                ],
                "tags": [],
            }
        ],
    )

    result = load_pipeline.finalize_loaded_entries(
        summary.entries,
        dataset_path=str(path),
        normalization_summary=summary,
    )

    assert errors == []
    assert result.dataset_source_format == FORMAT_SHAREGPT
    assert result.entries[0]["messages"][1]["role"] == "user"
    assert result.tag_normalization_summary["format_converted_count"] == 1


def test_pipeline_creates_foreign_working_copy(tmp_path, monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
    path, (summary, _errors) = _load_summary(tmp_path, [_entry()])
    working_path = tmp_path / "training_data" / "dataset" / "dataset.jsonl"

    monkeypatch.setattr(
        load_pipeline,
        "prepare_foreign_working_copy",
        lambda dataset_path, *, dataset_is_native: (
            {
                "original_path": str(path),
                "working_path": str(working_path),
                "sidecar_copied": False,
                "sidecar_path": None,
            },
            str(working_path),
        ),
    )

    result = load_pipeline.finalize_loaded_entries(
        summary.entries,
        dataset_path=str(path),
        normalization_summary=summary,
    )

    assert result.effective_dataset_path == str(working_path)
    assert result.working_copy_summary["original_path"] == str(path)
    assert result.dataset_is_native is False
    assert get_entry_uuid(result.entries[0]) is not None
    assert is_native_entry(result.entries[0]) is False
    assert set(result.entries[0][LOREFORGE_META_KEY]) == {"entry_uuid"}


def test_pipeline_loads_empty_dataset_without_sidecar_as_initialization(
    tmp_path,
    monkeypatch,
):
    _patch_pipeline_defaults(monkeypatch)
    training_dir = tmp_path / "training_data"
    monkeypatch.setattr(
        "core.working_copy.get_default_training_data_dir",
        lambda: training_dir,
    )
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    summary, errors = load_dataset_with_summary(str(path))

    result = load_pipeline.finalize_loaded_entries(
        summary.entries,
        dataset_path=str(path),
        normalization_summary=summary,
    )

    assert errors == []
    assert result.entries == []
    assert result.dataset_is_native is False
    assert result.sidecar_import_summary is None
    assert result.pending_tag_trust == {}
    assert result.effective_dataset_path == str(
        training_dir / "empty" / "empty.jsonl"
    )
    assert (training_dir / "empty" / "empty.jsonl").exists()


def test_pipeline_loads_empty_dataset_with_sidecar_and_preserves_sidecar_uuid(
    tmp_path,
    monkeypatch,
):
    _patch_pipeline_defaults(monkeypatch)
    training_dir = tmp_path / "training_data"
    monkeypatch.setattr(
        "core.working_copy.get_default_training_data_dir",
        lambda: training_dir,
    )
    path = tmp_path / "empty_with_sidecar.jsonl"
    path.write_text("", encoding="utf-8")
    write_sidecar(
        SidecarRegistry(
            metadata=SidecarMetadata(exported_at="2026-05-11T00:00:00+00:00"),
            dataset_info=SidecarDatasetInfo(
                dataset_uuid="empty-sidecar-uuid",
                filename="empty_with_sidecar.jsonl",
            ),
        ),
        sidecar_path_for_dataset(path),
    )

    imported_dataset_uuids = []

    def fake_import_sidecar(*, registry, entries):
        imported_dataset_uuids.append(registry.dataset_info.dataset_uuid)
        assert entries == []
        return SimpleNamespace(
            ok=True,
            message="Registry sidecar already matches the current registry.",
            categories_created=[],
            tags_created=[],
            tags_promoted=[],
            aliases_imported=[],
            characters_created=[],
            character_mappings_imported=[],
            conflicts=[],
            warnings=[],
            errors=[],
        )

    monkeypatch.setattr(load_pipeline, "import_registry_sidecar", fake_import_sidecar)
    summary, errors = load_dataset_with_summary(str(path))

    result = load_pipeline.finalize_loaded_entries(
        summary.entries,
        dataset_path=str(path),
        normalization_summary=summary,
    )

    copied_sidecar = sidecar_path_for_dataset(
        training_dir / "empty_with_sidecar" / "empty_with_sidecar.jsonl"
    )
    assert errors == []
    assert result.entries == []
    assert result.sidecar_import_summary["ok"] is True
    assert imported_dataset_uuids == ["empty-sidecar-uuid"]
    assert read_sidecar(copied_sidecar).dataset_info.dataset_uuid == "empty-sidecar-uuid"


def test_pipeline_preserves_existing_uuid_without_trust_stamp(monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
    entry = _entry()
    entry[LOREFORGE_META_KEY] = {
        "version": "0.5.9",
        "entry_uuid": "existing-entry-uuid",
    }

    result = load_pipeline.finalize_loaded_entries([entry])

    assert get_entry_uuid(result.entries[0]) == "existing-entry-uuid"
    assert result.entries[0][LOREFORGE_META_KEY]["version"] == "0.5.9"
    assert "native" not in result.entries[0][LOREFORGE_META_KEY]
    assert "validated_at" not in result.entries[0][LOREFORGE_META_KEY]


def test_pipeline_does_not_rerun_analysis_when_entries_are_unchanged(monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
    entry = _entry()
    normalization = TagNormalizationSummary(
        entries=[entry],
        dataset_is_native=False,
        source_format="chatml",
        format_counts={},
        format_confidence=0.0,
        format_converted_count=0,
        format_already_target_count=1,
        format_warnings=[],
        diagnostics=DatasetDiagnosticSummary(
            entries_analyzed=1,
            valid_entries=1,
            entries_with_errors=0,
            entries_with_warnings=0,
            entries_with_info=0,
            error_count=0,
            warning_count=0,
            info_count=0,
            auto_repairable_count=0,
        ),
        changed_entries=0,
        changed_tags=0,
        structural_changed_entries=0,
        tag_metadata_added_count=0,
        role_values_normalized=0,
        message_content_trimmed=0,
        dropped_tags=[],
        alias_rewrites={},
        alias_rewrite_count=0,
        alias_rewritten_entries=0,
    )
    analysis_calls = []
    monkeypatch.setattr(
        load_pipeline,
        "summarize_entry_analysis",
        lambda entries, **kwargs: analysis_calls.append((entries, kwargs))
        or normalization.diagnostics,
    )

    result = load_pipeline.finalize_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert result.entries[0]["messages"] == entry["messages"]
    assert analysis_calls == []


def test_pipeline_canonicalizes_aliases_before_adoption(monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
    adoption_entries = []
    entry = _entry(tags=["old_tag", "current_tag"])

    monkeypatch.setattr(
        load_pipeline,
        "resolve_tag_lifecycle",
        lambda slug: SimpleNamespace(
            should_rewrite_slug=slug == "old_tag",
            resolved_slug="current_tag" if slug == "old_tag" else slug,
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "ensure_tags_exist_for_dataset",
        lambda entries: adoption_entries.append(entries)
        or SimpleNamespace(created_count=0, created_slugs=[]),
    )

    result = load_pipeline.finalize_loaded_entries([entry])

    assert result.entries[0]["tags"] == ["current_tag"]
    assert adoption_entries[0][0]["tags"] == ["current_tag"]
    assert result.tag_normalization_summary["alias_rewrites"] == {
        "old_tag": "current_tag"
    }


def test_pipeline_reruns_analysis_after_alias_canonicalization(monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
    diagnostics = SimpleNamespace(
        entries_analyzed=1,
        valid_entries=1,
        entries_with_errors=0,
        entries_with_warnings=0,
        entries_with_info=0,
        error_count=0,
        warning_count=0,
        info_count=0,
        auto_repairable_count=0,
    )
    analysis_calls = []

    monkeypatch.setattr(
        load_pipeline,
        "resolve_tag_lifecycle",
        lambda slug: SimpleNamespace(
            should_rewrite_slug=slug == "old_tag",
            resolved_slug="current_tag" if slug == "old_tag" else slug,
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "summarize_entry_analysis",
        lambda entries, **kwargs: analysis_calls.append((entries, kwargs))
        or diagnostics,
    )

    result = load_pipeline.finalize_loaded_entries([_entry(tags=["old_tag"])])

    assert result.entries[0]["tags"] == ["current_tag"]
    assert len(analysis_calls) == 1
    assert analysis_calls[0][1] == {"metadata_errors_block_validity": False}


def test_pipeline_imports_sidecar_before_tag_adoption(tmp_path, monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
    training_dir = tmp_path / "training_data"
    monkeypatch.setattr(
        "core.working_copy.get_default_training_data_dir",
        lambda: training_dir,
    )
    dataset_path = tmp_path / "dataset.jsonl"
    sidecar_path = tmp_path / "dataset.registry.json"
    dataset_path.write_text("", encoding="utf-8")
    sidecar_path.write_text("{}", encoding="utf-8")
    registry = SimpleNamespace(tags=(), categories=())
    call_order = []

    monkeypatch.setattr(load_pipeline, "read_sidecar", lambda path: registry)
    monkeypatch.setattr(
        load_pipeline,
        "import_registry_sidecar",
        lambda *, registry, entries: call_order.append("import")
        or SimpleNamespace(
            ok=True,
            message="Imported.",
            categories_created=["custom"],
            tags_created=[],
            tags_promoted=[],
            aliases_imported=[],
            characters_created=[],
            character_mappings_imported=[],
            conflicts=[],
            warnings=[],
            errors=[],
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "ensure_tags_exist_for_dataset",
        lambda entries: call_order.append("adoption")
        or SimpleNamespace(created_count=0, created_slugs=[]),
    )

    result = load_pipeline.finalize_loaded_entries([], dataset_path=str(dataset_path))

    assert call_order == ["import", "adoption"]
    assert result.sidecar_import_summary["categories_created"] == ["custom"]


def test_pipeline_builds_pending_trust_for_imported_archived_tags(monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
    entry = _entry(tags=["archived_import"])

    monkeypatch.setattr(
        core_load_pipeline,
        "get_tag_by_slug_any_status",
        lambda slug: SimpleNamespace(
            name="Archived Import",
            status=TAG_STATUS_ARCHIVED,
            category_id=None,
        ),
    )
    monkeypatch.setattr(
        core_load_pipeline,
        "get_current_tag_lifecycle_metadata",
        lambda slug: {"archive_origin": ARCHIVE_ORIGIN_IMPORTED},
    )

    result = load_pipeline.finalize_loaded_entries([entry])

    pending = result.pending_tag_trust["archived_import"]
    assert pending["entry_indices"] == [0]
    assert pending["archive_origin"] == ARCHIVE_ORIGIN_IMPORTED
    assert result.tag_normalization_summary["pending_trust_count"] == 1
