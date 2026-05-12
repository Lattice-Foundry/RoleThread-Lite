import json
import shutil
from types import SimpleNamespace

from services import dataset_service
import ui.session_state as session_state
from core.dataset import load_dataset_with_summary
from core.format_conversion import FORMAT_CHATML, FORMAT_SHAREGPT
from core.loreforge_meta import LOREFORGE_META_KEY
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
        session_state,
        "ensure_tags_exist_for_dataset",
        lambda entries: SimpleNamespace(created_count=0, created_slugs=[]),
    )
    monkeypatch.setattr(
        session_state,
        "get_tag_by_slug_any_status",
        lambda slug: None,
    )
    monkeypatch.setattr(
        session_state,
        "get_current_tag_lifecycle_metadata",
        lambda slug: {},
    )
    monkeypatch.setattr(
        session_state,
        "resolve_tag_lifecycle",
        lambda slug: SimpleNamespace(should_rewrite_slug=False, resolved_slug=slug),
    )
    return fake_state


def test_set_loaded_entries_tracks_pending_structural_normalization(monkeypatch):
    state = _patch_state(monkeypatch)
    state.quick_edit_entry_id = "tmp-entry-1"
    state.quick_edit_success = "Saved"
    state.quick_edit_tmp_entry_1_1 = "draft"
    state.edit_entries_mode = "workspace"
    state.editing_entry_id = "tmp-entry-1"
    state.full_edit_entry_id = "tmp-entry-1"
    state.full_edit_turn_0 = "draft"

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
    assert "quick_edit_entry_id" not in state
    assert "quick_edit_success" not in state
    assert "quick_edit_tmp_entry_1_1" not in state
    assert state.edit_entries_mode == "browser"
    assert "editing_entry_id" not in state
    assert "full_edit_entry_id" not in state
    assert "full_edit_turn_0" not in state


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
        session_state,
        "ensure_tags_exist_for_dataset",
        lambda entries: adoption_entries.append(entries)
        or SimpleNamespace(created_count=0, created_slugs=[]),
    )
    monkeypatch.setattr(
        session_state,
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


def test_set_loaded_entries_clears_character_candidates_when_none(monkeypatch):
    state = _patch_state(monkeypatch)
    state.character_candidates = "stale"

    session_state.set_loaded_entries([_entry_without_tags()])

    assert "character_candidates" not in state
    assert state.tag_normalization_summary["character_candidate_count"] == 0


def test_set_loaded_entries_creates_working_copy_for_foreign_dataset(tmp_path, monkeypatch):
    state = _patch_state(monkeypatch)
    path = tmp_path / "foreign.jsonl"
    path.write_text(json.dumps(_entry_without_tags()) + "\n", encoding="utf-8")
    normalization, errors = load_dataset_with_summary(str(path))

    assert errors == []
    working_path = tmp_path / "working" / "foreign.jsonl"
    monkeypatch.setattr(
        session_state,
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
        session_state,
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

    def fake_import_registry_sidecar(*, registry):
        call_order.append("import")
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

    monkeypatch.setattr(session_state, "read_sidecar", lambda path: registry)
    monkeypatch.setattr(
        session_state,
        "import_registry_sidecar",
        fake_import_registry_sidecar,
    )
    monkeypatch.setattr(
        session_state,
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
        session_state,
        "read_sidecar",
        lambda path: (_ for _ in ()).throw(ValueError("broken sidecar")),
    )
    monkeypatch.setattr(
        session_state,
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
        session_state,
        "get_tag_by_slug_any_status",
        lambda slug: SimpleNamespace(
            name="Some Custom Tag",
            status=TAG_STATUS_ARCHIVED,
            category_id=None,
        ),
    )
    monkeypatch.setattr(
        session_state,
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

    monkeypatch.setattr(session_state, "read_sidecar", lambda path: registry)
    monkeypatch.setattr(
        session_state,
        "import_registry_sidecar",
        lambda *, registry: SimpleNamespace(
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
        session_state,
        "get_tag_by_slug_any_status",
        lambda slug: SimpleNamespace(
            name="Sidecar Tag",
            status=TAG_STATUS_ARCHIVED,
            category_id=None,
        ),
    )
    monkeypatch.setattr(
        session_state,
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

    def fake_normalize_dataset_service(dataset_path, entries):
        return DatasetOperationResult(
            ok=True,
            message="Dataset normalized.",
            entries=entries,
            backup_path="backup.jsonl",
            affected_count=len(entries),
        )

    monkeypatch.setattr(
        session_state,
        "normalize_dataset_service",
        fake_normalize_dataset_service,
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


def test_auto_normalize_enabled_explicit_load_can_persist_missing_tag_metadata(tmp_path, monkeypatch):
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

    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=errors,
        normalization_pending=state.normalization_pending,
    ) is True

    result = session_state.persist_loaded_normalization(str(path))
    saved_text = path.read_text(encoding="utf-8")

    assert result.ok is True
    assert state.normalization_pending is False
    assert '"tags": []' in saved_text


def test_auto_normalize_enabled_explicit_load_can_persist_role_and_content_cleanup(
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

    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
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


def test_auto_normalize_disabled_explicit_load_keeps_disk_unchanged_and_pending(tmp_path, monkeypatch):
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

    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": False},
        parse_errors=errors,
        normalization_pending=state.normalization_pending,
    ) is False
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


def test_should_auto_normalize_loaded_dataset_respects_setting_errors_and_pending_state():
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=[],
        normalization_pending=True,
    ) is True
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": False},
        parse_errors=[],
        normalization_pending=True,
    ) is False
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=["Line 2: bad json"],
        normalization_pending=True,
    ) is False
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=[],
        normalization_pending=False,
    ) is False


def test_should_auto_normalize_loaded_dataset_prefers_live_session_value():
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": False},
        parse_errors=[],
        normalization_pending=True,
        auto_normalize_on_load=True,
    ) is True
    assert session_state.should_auto_normalize_loaded_dataset(
        prefs={"auto_normalize_on_load": True},
        parse_errors=[],
        normalization_pending=True,
        auto_normalize_on_load=False,
    ) is False
