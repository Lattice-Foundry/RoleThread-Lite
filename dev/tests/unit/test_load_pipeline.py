import json
from types import SimpleNamespace

import core.load_pipeline as load_pipeline
from core.dataset import load_dataset_with_summary
from core.format_conversion import FORMAT_SHAREGPT
from core.tag_constants import ARCHIVE_ORIGIN_IMPORTED, TAG_STATUS_ARCHIVED


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
    monkeypatch.setattr(load_pipeline, "get_tag_by_slug_any_status", lambda slug: None)
    monkeypatch.setattr(load_pipeline, "get_current_tag_lifecycle_metadata", lambda slug: {})
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
        "create_dataset_working_copy",
        lambda dataset_path: SimpleNamespace(
            original_path=str(path),
            working_path=str(working_path),
            created=True,
            sidecar_copied=False,
            sidecar_path=None,
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


def test_pipeline_imports_sidecar_before_tag_adoption(tmp_path, monkeypatch):
    _patch_pipeline_defaults(monkeypatch)
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
        load_pipeline,
        "get_tag_by_slug_any_status",
        lambda slug: SimpleNamespace(
            name="Archived Import",
            status=TAG_STATUS_ARCHIVED,
            category_id=None,
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "get_current_tag_lifecycle_metadata",
        lambda slug: {"archive_origin": ARCHIVE_ORIGIN_IMPORTED},
    )

    result = load_pipeline.finalize_loaded_entries([entry])

    pending = result.pending_tag_trust["archived_import"]
    assert pending["entry_indices"] == [0]
    assert pending["archive_origin"] == ARCHIVE_ORIGIN_IMPORTED
    assert result.tag_normalization_summary["pending_trust_count"] == 1
