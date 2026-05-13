import json
import shutil
from types import SimpleNamespace

import core.load_pipeline as load_pipeline
from services import dataset_service
import ui.session_state as session_state
from core.dataset import load_dataset_with_summary
from core.format_conversion import FORMAT_CHATML, FORMAT_SHAREGPT
from core.loreforge_meta import LOREFORGE_META_KEY, get_entry_uuid
from core.tag_constants import ARCHIVE_ORIGIN_IMPORTED, TAG_STATUS_ARCHIVED
from services.dataset_service import DatasetOperationResult


class FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _entry_without_tags():
    return {
        "messages": [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
    }


def _patch_state(monkeypatch):
    fake_state = FakeSessionState()
    monkeypatch.setattr(session_state, "st", SimpleNamespace(session_state=fake_state))
    monkeypatch.setattr(
        load_pipeline,
        "ensure_tags_exist_for_dataset",
        lambda entries: SimpleNamespace(created_count=0, created_slugs=[]),
    )
    monkeypatch.setattr(
        load_pipeline,
        "get_tag_by_slug_any_status",
        lambda slug: None,
    )
    monkeypatch.setattr(
        load_pipeline,
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
    return fake_state


def test_set_loaded_entries_tracks_pending_structural_normalization(monkeypatch):
    state = _patch_state(monkeypatch)
    state.quick_edit_entry_uuid = "entry-uuid-1"
    state.quick_edit_success = "Saved"
    state.quick_edit_entry_uuid_1_1 = "draft"
    state.edit_entries_mode = "workspace"
    state.editing_entry_uuid = "entry-uuid-1"
    state.full_edit_entry_uuid = "entry-uuid-1"
    state.full_edit_turn_0 = "draft"
    state.pending_delete_selected = True
    state.pending_system_prompt_edit = True
    state.validation_pending_fix = {"mode": "all"}

    normalization, errors = _load_entries_with_summary([_entry_without_tags()])

    assert errors == []
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert state.loaded_entries[0]["tags"] == []
    assert state.dataset_source_format == FORMAT_CHATML
    assert state.tag_normalization_summary["source_format"] == FORMAT_CHATML
    assert state.normalization_pending is True
    assert state.tag_normalization_summary["tag_metadata_added_count"] == 1
    assert state.tag_normalization_summary["structural_changed_entries"] == 1
    assert "quick_edit_entry_uuid" not in state
    assert "quick_edit_success" not in state
    assert "quick_edit_entry_uuid_1_1" not in state
    assert state.edit_entries_mode == "browser"
    assert "editing_entry_uuid" not in state
    assert "full_edit_entry_uuid" not in state
    assert "full_edit_turn_0" not in state
    assert "pending_delete_selected" not in state
    assert "pending_system_prompt_edit" not in state
    assert "validation_pending_fix" not in state


def test_set_loaded_entries_tracks_pending_tag_slug_normalization(monkeypatch):
    state = _patch_state(monkeypatch)
    entry = _entry_without_tags()
    entry["tags"] = ["sLow burn"]

    session_state.set_loaded_entries([entry])

    assert state.loaded_entries[0]["tags"] == ["slow_burn"]
    assert state.normalization_pending is True
    assert state.tag_normalization_summary["changed_entries"] == 1


def test_set_loaded_entries_rewrites_stale_aliases_before_adoption(monkeypatch):
    state = _patch_state(monkeypatch)
    entry = _entry_without_tags()
    entry["tags"] = ["old_tag", "active_tag"]
    adoption_entries = []

    monkeypatch.setattr(
        load_pipeline,
        "ensure_tags_exist_for_dataset",
        lambda entries: adoption_entries.append(entries)
        or SimpleNamespace(created_count=0, created_slugs=[]),
    )
    monkeypatch.setattr(
        load_pipeline,
        "resolve_tag_lifecycle",
        lambda slug: SimpleNamespace(
            should_rewrite_slug=slug == "old_tag",
            resolved_slug="active_tag" if slug == "old_tag" else slug,
        ),
    )

    session_state.set_loaded_entries([entry])

    assert state.loaded_entries[0]["tags"] == ["active_tag"]
    assert adoption_entries[0][0]["tags"] == ["active_tag"]
    assert state.normalization_pending is True
    assert state.tag_normalization_summary["alias_rewrites"] == {
        "old_tag": "active_tag"
    }
    assert state.tag_normalization_summary["alias_rewrite_count"] == 1


def test_set_loaded_entries_tracks_dataset_source_format(monkeypatch):
    state = _patch_state(monkeypatch)
    sharegpt_record = {
        "conversations": [
            {"from": "human", "value": "Hi"},
            {"from": "gpt", "value": "Hello"},
        ]
    }
    normalization, errors = _load_entries_with_summary([sharegpt_record])

    assert errors == []
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert state.dataset_source_format == FORMAT_SHAREGPT
    assert state.tag_normalization_summary["source_format"] == FORMAT_SHAREGPT
    assert state.tag_normalization_summary["format_converted_count"] == 1


def test_set_loaded_entries_stores_character_candidates(monkeypatch):
    state = _patch_state(monkeypatch)
    entry = _entry_without_tags()
    entry["_loreforge"] = {"native": True, "entry_uuid": "entry-1"}
    entry["messages"] = [
        {"role": "Scott", "content": "Hi"},
        {"role": "Emma", "content": "Hello"},
        {"role": "Scott", "content": "Again"},
        {"role": "Emma", "content": "Again"},
    ]

    session_state.set_loaded_entries([entry])

    report = state.character_candidates
    assert report.has_candidates is True
    assert [candidate.source_role_label for candidate in report.candidates] == [
        "Emma",
        "Scott",
    ]
    assert state.tag_normalization_summary["character_candidate_count"] == 2
    assert state.tag_normalization_summary["character_candidate_labels"] == [
        "Emma",
        "Scott",
    ]


def test_set_loaded_entries_applies_known_character_role_mappings(monkeypatch):
    state = _patch_state(monkeypatch)
    entry = _entry_without_tags()
    entry["_loreforge"] = {"native": True, "entry_uuid": "entry-1"}
    entry["messages"][1]["role"] = "Scott"
    mapped_entries = [json.loads(json.dumps(entry))]
    mapped_entries[0]["messages"][1]["role"] = "user"
    mapping_payload = (
        {
            "entry_uuid": "entry-1",
            "turns": [
                {
                    "turn_index": 1,
                    "character_slug": "scott",
                    "training_role": "user",
                    "source_role_label": "Scott",
                }
            ],
        },
    )
    upsert_calls = []

    monkeypatch.setattr(
        load_pipeline,
        "normalize_known_character_roles",
        lambda entries: SimpleNamespace(
            entries=mapped_entries,
            mapping_payload=mapping_payload,
            changed_entries=1,
            changed_turns=1,
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "upsert_character_mappings",
        lambda mappings: upsert_calls.append(mappings) or {"entries": 1, "turns": 1},
    )

    session_state.set_loaded_entries([entry])

    assert state.loaded_entries[0]["messages"][1]["role"] == "user"
    assert "character_candidates" not in state
    assert state.normalization_pending is True
    assert state.tag_normalization_summary["role_values_normalized"] == 1
    assert upsert_calls == [mapping_payload]


def test_set_loaded_entries_clears_character_candidates_when_none(monkeypatch):
    state = _patch_state(monkeypatch)
    state.character_candidates = "stale"

    session_state.set_loaded_entries([_entry_without_tags()])

    assert "character_candidates" not in state
    assert state.tag_normalization_summary["character_candidate_count"] == 0


def test_set_loaded_entries_builds_uuid_index_and_lookup_helpers(monkeypatch):
    state = _patch_state(monkeypatch)

    session_state.set_loaded_entries([_entry_without_tags(), _entry_without_tags()])

    first_uuid = get_entry_uuid(state.loaded_entries[0])
    second_uuid = get_entry_uuid(state.loaded_entries[1])
    assert state.uuid_to_index == {
        first_uuid: 0,
        second_uuid: 1,
    }
    assert session_state.get_loaded_entry_index_by_uuid(second_uuid) == 1
    assert session_state.get_loaded_entry_by_uuid(second_uuid) == state.loaded_entries[1]
    assert session_state.get_loaded_entry_index_by_uuid("missing") is None
    assert session_state.get_loaded_entry_by_uuid("missing") is None


def test_delete_selected_entries_rebuilds_uuid_index(monkeypatch):
    state = _patch_state(monkeypatch)
    state.prefs = {}
    state.loaded_path = "dataset.jsonl"
    session_state.set_loaded_entries([_entry_without_tags(), _entry_without_tags()])
    second_uuid = get_entry_uuid(state.loaded_entries[1])
    first_uuid = get_entry_uuid(state.loaded_entries[0])
    state.selected_entry_uuids = {first_uuid}

    monkeypatch.setattr(
        session_state,
        "delete_entries_service",
        lambda **kwargs: DatasetOperationResult(
            ok=True,
            message="Deleted.",
            entries=[state.loaded_entries[1]],
            affected_count=1,
        ),
    )

    deleted_count, failures, backup_created = session_state.delete_selected_entries()

    assert deleted_count == 1
    assert failures == []
    assert backup_created is False
    assert state.uuid_to_index == {second_uuid: 0}


def test_set_loaded_entries_creates_working_copy_for_foreign_dataset(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "foreign.jsonl"
    path.write_text(json.dumps(_entry_without_tags()) + "\n", encoding="utf-8")
    normalization, errors = load_dataset_with_summary(str(path))

    assert errors == []
    working_path = tmp_path / "working" / "foreign.jsonl"
    monkeypatch.setattr(
        load_pipeline,
        "create_dataset_working_copy",
        lambda dataset_path: SimpleNamespace(
            original_path=str(path),
            working_path=str(working_path),
            created=True,
            sidecar_copied=True,
            sidecar_path=str(tmp_path / "working" / "foreign.registry.json"),
        ),
    )

    effective_path = session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
        dataset_path=str(path),
    )

    assert effective_path == str(working_path)
    assert state.dataset_is_native is False
    assert state.working_copy_summary["original_path"] == str(path)
    assert state.working_copy_summary["working_path"] == str(working_path)
    assert state.tag_normalization_summary["working_copy"] == state.working_copy_summary


def test_set_loaded_entries_does_not_copy_native_dataset(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "native.jsonl"
    entry = {
        **_entry_without_tags(),
        LOREFORGE_META_KEY: {"native": True},
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    normalization, errors = load_dataset_with_summary(str(path))
    copy_calls = []

    assert errors == []
    assert normalization.dataset_is_native is True
    monkeypatch.setattr(
        load_pipeline,
        "create_dataset_working_copy",
        lambda dataset_path: copy_calls.append(dataset_path),
    )

    effective_path = session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
        dataset_path=str(path),
    )

    assert effective_path == str(path)
    assert copy_calls == []
    assert state.dataset_is_native is True
    assert "working_copy_summary" not in state


def test_set_loaded_entries_imports_sibling_sidecar_before_tag_adoption(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    dataset_path = tmp_path / "dataset.jsonl"
    sidecar_path = tmp_path / "dataset.registry.json"
    sidecar_path.write_text("{}", encoding="utf-8")
    registry = SimpleNamespace(tags=(), categories=())
    call_order = []

    def fake_import_registry_sidecar(*, registry, entries):
        call_order.append("import")
        assert entries == []
        return SimpleNamespace(
            ok=True,
            message="Imported.",
            categories_created=["custom"],
            tags_created=["restored"],
            tags_promoted=[],
            aliases_imported=[],
            conflicts=[],
            warnings=[],
            errors=[],
        )

    monkeypatch.setattr(load_pipeline, "read_sidecar", lambda path: registry)
    monkeypatch.setattr(
        load_pipeline,
        "import_registry_sidecar",
        fake_import_registry_sidecar,
    )
    monkeypatch.setattr(
        load_pipeline,
        "ensure_tags_exist_for_dataset",
        lambda entries: call_order.append("adoption")
        or SimpleNamespace(created_count=0, created_slugs=[]),
    )

    session_state.set_loaded_entries([], dataset_path=str(dataset_path))

    assert call_order == ["import", "adoption"]
    assert state.sidecar_import_summary["ok"] is True
    assert state.sidecar_import_summary["categories_created"] == ["custom"]
    assert "pending_tag_trust" not in state


def test_set_loaded_entries_keeps_loading_when_sidecar_read_fails(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    dataset_path = tmp_path / "dataset.jsonl"
    sidecar_path = tmp_path / "dataset.registry.json"
    sidecar_path.write_text("{not json", encoding="utf-8")
    adoption_called = []

    monkeypatch.setattr(
        load_pipeline,
        "read_sidecar",
        lambda path: (_ for _ in ()).throw(ValueError("broken sidecar")),
    )
    monkeypatch.setattr(
        load_pipeline,
        "ensure_tags_exist_for_dataset",
        lambda entries: adoption_called.append(True)
        or SimpleNamespace(created_count=0, created_slugs=[]),
    )

    session_state.set_loaded_entries([], dataset_path=str(dataset_path))

    assert adoption_called == [True]
    assert state.sidecar_import_summary["ok"] is False
    assert state.sidecar_import_summary["errors"] == ["broken sidecar"]


def test_set_loaded_entries_builds_pending_trust_for_imported_archived_tags(monkeypatch):
    state = _patch_state(monkeypatch)
    entry = _entry_without_tags()
    entry["tags"] = ["some_custom_tag"]

    monkeypatch.setattr(
        load_pipeline,
        "get_tag_by_slug_any_status",
        lambda slug: SimpleNamespace(
            name="Some Custom Tag",
            status=TAG_STATUS_ARCHIVED,
            category_id=None,
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "get_current_tag_lifecycle_metadata",
        lambda slug: {"archive_origin": ARCHIVE_ORIGIN_IMPORTED},
    )

    session_state.set_loaded_entries([entry])

    pending = state.pending_tag_trust["some_custom_tag"]
    assert pending["display_name"] == "Some Custom Tag"
    assert pending["entry_indices"] == [0]
    assert pending["usage_count"] == 1
    assert pending["registry_status"] == TAG_STATUS_ARCHIVED
    assert pending["archive_origin"] == ARCHIVE_ORIGIN_IMPORTED
    assert pending["resolution"] == "no_hint"
    assert state.tag_normalization_summary["pending_trust_count"] == 1


def test_pending_trust_includes_sidecar_hints(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    dataset_path = tmp_path / "dataset.jsonl"
    sidecar_path = tmp_path / "dataset.registry.json"
    sidecar_path.write_text("{}", encoding="utf-8")
    entry = _entry_without_tags()
    entry["tags"] = ["sidecar_tag"]
    registry = SimpleNamespace(
        categories=(
            SimpleNamespace(slug="behavior", name="Behavior"),
        ),
        tags=(
            SimpleNamespace(
                slug="sidecar_tag",
                name="Sidecar Tag",
                category_slug="behavior",
                status="active",
            ),
        ),
    )

    monkeypatch.setattr(load_pipeline, "read_sidecar", lambda path: registry)
    monkeypatch.setattr(
        load_pipeline,
        "import_registry_sidecar",
        lambda *, registry, entries: SimpleNamespace(
            ok=True,
            message="Imported.",
            categories_created=[],
            tags_created=[],
            tags_promoted=[],
            aliases_imported=[],
            conflicts=["sidecar conflict"],
            warnings=[],
            errors=[],
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "get_tag_by_slug_any_status",
        lambda slug: SimpleNamespace(
            name="Sidecar Tag",
            status=TAG_STATUS_ARCHIVED,
            category_id=None,
        ),
    )
    monkeypatch.setattr(
        load_pipeline,
        "get_current_tag_lifecycle_metadata",
        lambda slug: {"archive_origin": ARCHIVE_ORIGIN_IMPORTED},
    )

    session_state.set_loaded_entries([entry], dataset_path=str(dataset_path))

    pending = state.pending_tag_trust["sidecar_tag"]
    assert pending["sidecar_category_slug"] == "behavior"
    assert pending["sidecar_category_name"] == "Behavior"
    assert pending["sidecar_status"] == "active"
    assert pending["resolution"] == "sidecar_hint"
    assert state.sidecar_import_summary["conflicts"] == ["sidecar conflict"]


def test_persist_loaded_normalization_clears_pending_state_on_success(monkeypatch):
    state = _patch_state(monkeypatch)
    normalization, _ = _load_entries_with_summary([_entry_without_tags()])
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    def fake_save_repaired_entries_service(dataset_path, repaired_entries, backup_reason):
        return DatasetOperationResult(
            ok=True,
            message="Repaired entries saved.",
            entries=repaired_entries,
            backup_path="backup.jsonl",
            affected_count=len(repaired_entries),
        )

    monkeypatch.setattr(
        session_state,
        "save_repaired_entries_service",
        fake_save_repaired_entries_service,
    )

    result = session_state.persist_loaded_normalization("dataset.jsonl")

    assert result.ok is True
    assert state.normalization_pending is False
    assert state.tag_normalization_summary["tag_metadata_added_count"] == 0
    assert state.tag_normalization_summary["structural_changed_entries"] == 0


def _load_entries_with_summary(entries):
    from tempfile import TemporaryDirectory
    from pathlib import Path

    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "dataset.jsonl"
        path.write_text(
            "\n".join(json.dumps(entry) for entry in entries) + "\n",
            encoding="utf-8",
        )
        return load_dataset_with_summary(str(path))


def test_explicit_load_persists_missing_tag_metadata(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "legacy.jsonl"
    legacy_entries = [_entry_without_tags(), _entry_without_tags()]
    path.write_text(
        "\n".join(json.dumps(entry) for entry in legacy_entries) + "\n",
        encoding="utf-8",
    )
    backup_path = tmp_path / "backup.jsonl"
    monkeypatch.setattr(
        dataset_service,
        "create_dataset_backup",
        lambda dataset_path, reason: shutil.copyfile(dataset_path, backup_path) or backup_path,
    )

    normalization, errors = load_dataset_with_summary(str(path))
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert session_state.should_persist_loaded_normalization(
        parse_errors=errors,
        normalization_pending=state.normalization_pending,
    ) is True

    result = session_state.persist_loaded_normalization(str(path))
    saved_text = path.read_text(encoding="utf-8")

    assert result.ok is True
    assert state.normalization_pending is False
    assert '"tags": []' in saved_text


def test_explicit_load_persists_role_and_content_cleanup(
    tmp_path,
    monkeypatch,
):
    state = _patch_state(monkeypatch)
    path = tmp_path / "role_cleanup.jsonl"
    entry = {
        "messages": [
            {"role": "SYSTEM", "content": " System "},
            {"role": "Human", "content": " Hi "},
            {"role": "GPT", "content": " Hello "},
        ],
        "tags": [],
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    backup_path = tmp_path / "backup.jsonl"
    monkeypatch.setattr(
        dataset_service,
        "create_dataset_backup",
        lambda dataset_path, reason: shutil.copyfile(dataset_path, backup_path) or backup_path,
    )

    normalization, errors = load_dataset_with_summary(str(path))
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert session_state.should_persist_loaded_normalization(
        parse_errors=errors,
        normalization_pending=state.normalization_pending,
    ) is True

    result = session_state.persist_loaded_normalization(str(path))
    saved_entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert result.ok is True
    assert state.normalization_pending is False
    assert saved_entries[0]["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]


def test_explicit_load_with_pending_normalization_should_persist_even_when_setting_off(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "legacy.jsonl"
    legacy_entry = _entry_without_tags()
    original_text = json.dumps(legacy_entry) + "\n"
    path.write_text(original_text, encoding="utf-8")

    normalization, errors = load_dataset_with_summary(str(path))
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert session_state.should_persist_loaded_normalization(
        parse_errors=errors,
        normalization_pending=state.normalization_pending,
    ) is True
    assert state.loaded_entries[0]["tags"] == []
    assert state.normalization_pending is True
    assert path.read_text(encoding="utf-8") == original_text


def test_startup_reload_can_track_pending_without_persisting(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "legacy.jsonl"
    legacy_entry = _entry_without_tags()
    original_text = json.dumps(legacy_entry) + "\n"
    path.write_text(original_text, encoding="utf-8")

    normalization, errors = load_dataset_with_summary(str(path))
    session_state.set_loaded_entries(
        normalization.entries,
        normalization_summary=normalization,
    )

    assert errors == []
    assert state.loaded_entries[0]["tags"] == []
    assert state.normalization_pending is True
    assert path.read_text(encoding="utf-8") == original_text


def test_should_persist_loaded_normalization_respects_errors_and_pending_state():
    assert session_state.should_persist_loaded_normalization(
        parse_errors=[],
        normalization_pending=True,
    ) is True
    assert session_state.should_persist_loaded_normalization(
        parse_errors=["Line 2: bad json"],
        normalization_pending=True,
    ) is False
    assert session_state.should_persist_loaded_normalization(
        parse_errors=[],
        normalization_pending=False,
    ) is False
