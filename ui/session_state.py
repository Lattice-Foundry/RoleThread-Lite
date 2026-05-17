"""Streamlit session-state bridge helpers.

This UI-layer module may touch st.session_state and coordinate service calls.
Pure dataset logic belongs in core or services.
"""
from pathlib import Path

import streamlit as st

from core.backups import auto_backups_enabled
from core.cloud_sync import save_backup_config_from_settings
from core.dataset import (
    build_uuid_index,
    get_entry_by_uuid,
    get_entry_index_by_uuid,
    TagNormalizationSummary,
)
from core.rolethread_meta import get_dataset_uuid_for_entries, get_entry_uuid
from core.preferences import save_preferences
from services.dataset_service import (
    DatasetOperationResult,
    delete_entries_service,
    save_repaired_entries_service,
    save_quick_edit_service,
)
from services.load_pipeline_service import finalize_loaded_entries
from ui.message_scaffolding import scaffold_editable_messages
from ui.flash_messages import enqueue_flash
from ui.entry_search_state import sync_entry_search_state_for_dataset


# â”€â”€ Preferences session helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def update_prefs(updates: dict) -> None:
    """Update st.session_state.prefs in place and persist to disk."""
    st.session_state.prefs.update(updates)
    save_preferences(st.session_state.prefs)
    if set(updates) & {
        "backup_destination_type",
        "backup_destination_custom_path",
        "cloud_backup_last_sync_at",
    }:
        save_backup_config_from_settings(st.session_state.prefs)


# UUID / session helpers

def ensure_entry_indexes() -> None:
    """Ensure UUID indexes are consistent with loaded_entries.

    Rebuilds silently if missing or invalid â€” safe to call anywhere.
    """
    entries = st.session_state.get("loaded_entries", [])
    if st.session_state.get("uuid_to_index") != build_uuid_index(entries):
        st.session_state.uuid_to_index = build_uuid_index(entries)


def set_loaded_entries(
    entries: list[dict],
    normalization_summary: TagNormalizationSummary | None = None,
    dataset_path: str | None = None,
) -> str | None:
    """Replace loaded_entries using the core load pipeline, then publish state."""
    result = finalize_loaded_entries(
        entries,
        dataset_path=dataset_path,
        normalization_summary=normalization_summary,
    )
    clear_dataset_scoped_state()
    sync_entry_search_state_for_dataset(
        _entry_search_dataset_identifier(
            entries=result.entries,
            dataset_path=result.effective_dataset_path,
        )
    )
    st.session_state.loaded_entries = result.entries
    st.session_state.dataset_source_format = result.dataset_source_format
    st.session_state.uuid_to_index = build_uuid_index(result.entries)
    st.session_state.tag_normalization_summary = result.tag_normalization_summary
    st.session_state.dataset_is_native = result.dataset_is_native
    st.session_state.normalization_pending = result.normalization_pending
    _replace_optional_session_value("working_copy_summary", result.working_copy_summary)
    _replace_optional_session_value("sidecar_import_summary", result.sidecar_import_summary)
    _replace_optional_session_value("pending_tag_trust", result.pending_tag_trust or None)
    _replace_optional_session_value("character_candidates", result.character_candidates)
    return result.effective_dataset_path


def _entry_search_dataset_identifier(
    *,
    entries: list[dict],
    dataset_path: str | None,
) -> str:
    """Return the dataset-scoped search marker for the current load."""

    if dataset_path:
        return str(Path(dataset_path).expanduser())
    dataset_uuid = get_dataset_uuid_for_entries(entries)
    return dataset_uuid or ""


_DATASET_SCOPED_STATE_KEYS = (
    "quick_edit_success",
    "tag_save_success",
    "sys_prompt_success",
    "full_edit_success",
    "tm_success",
    "export_success_msg",
    "export_warning_msg",
    "character_success_msg",
    "character_warning_msg",
    "validation_success_msg",
    "validation_warning_msg",
    "validation_post_fix_manual_issue_count",
    "pending_delete_selected",
    "pending_system_prompt_edit",
    "validation_pending_fix",
    "pending_character_delete",
    "tm_pending_archived_assignment",
    "tm_pending_category_delete",
    "tm_pending_category_rename",
    "tm_pending_tag_delete",
    "tm_pending_tag_edit",
    "bulk_system_prompt_text",
    "stats_filter_uuids",
    "stats_filter_label",
)


def clear_dataset_scoped_state() -> None:
    """Clear confirmation/edit state that must not survive dataset switches."""

    clear_entry_edit_state()
    for key in _DATASET_SCOPED_STATE_KEYS:
        st.session_state.pop(key, None)


def clear_entry_edit_state() -> None:
    """Clear Quick Edit and Full Edit UI state without triggering a rerun."""

    st.session_state.quick_edit_entry_uuid = None
    st.session_state.edit_entries_mode = "browser"
    for key in (
        "editing_entry_uuid",
        "full_edit_entry_uuid",
        "full_edit_system_prompt",
        "full_edit_turns",
        "full_edit_planned_exchanges",
        "full_edit_unknown_tags",
        "_ee_browser_snapshot",
    ):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if (
            key.startswith("quick_edit_")
            or key.startswith("full_edit_turn_")
            or key.startswith("full_edit_tags_")
        ):
            st.session_state.pop(key, None)


def _replace_optional_session_value(key: str, value) -> None:
    if value:
        st.session_state[key] = value
    else:
        st.session_state.pop(key, None)


def clear_normalization_pending() -> None:
    """Clear pending deterministic-normalization state after disk persistence."""
    st.session_state.normalization_pending = False
    summary = st.session_state.get("tag_normalization_summary", {})
    st.session_state.tag_normalization_summary = {
        **summary,
        "changed_entries": 0,
        "changed_tags": 0,
        "structural_changed_entries": 0,
        "tag_metadata_added_count": 0,
        "role_values_normalized": 0,
        "message_content_trimmed": 0,
        "alias_rewrites": {},
        "alias_rewrite_count": 0,
        "alias_rewritten_entries": 0,
        "character_candidate_count": 0,
        "character_candidate_labels": [],
        "character_candidate_pattern": None,
    }


def should_persist_loaded_normalization(
    *,
    parse_errors: list[str],
    normalization_pending: bool,
) -> bool:
    """Return True when load-time normalization should be persisted."""

    return not parse_errors and normalization_pending


def persist_loaded_normalization(dataset_path: str) -> DatasetOperationResult:
    """Persist normalized loaded entries and clear pending state on success."""
    result = save_repaired_entries_service(
        dataset_path=dataset_path,
        repaired_entries=st.session_state.loaded_entries,
        backup_reason="before_load_normalization",
    )
    if result.ok and result.entries is not None:
        apply_dataset_operation_result(result)
        st.session_state.loaded_entries = result.entries
        st.session_state.uuid_to_index = build_uuid_index(result.entries)
        clear_normalization_pending()
        _enqueue_sidecar_warning_if_needed(result)
    return result


def apply_dataset_operation_result(result: DatasetOperationResult) -> None:
    """Adopt a service-returned dataset path after flat training_data migration."""

    if not result.dataset_path:
        return
    if st.session_state.get("loaded_path") == result.dataset_path:
        return
    st.session_state.loaded_path = result.dataset_path
    if isinstance(st.session_state.get("prefs"), dict):
        update_prefs({
            "last_loaded_dataset_path": result.dataset_path,
            "last_open_directory": str(Path(result.dataset_path).parent),
        })


def get_loaded_entry_by_uuid(entry_uuid: str) -> dict | None:
    """Return the entry for the given stable UUID, or None if not found."""

    entries = st.session_state.loaded_entries
    return get_entry_by_uuid(entries, entry_uuid)


def get_loaded_entry_index_by_uuid(entry_uuid: str) -> int | None:
    """Return the current source index for entry_uuid, or None if not found."""

    entries = st.session_state.loaded_entries
    ensure_entry_indexes()
    index = st.session_state.get("uuid_to_index", {}).get(entry_uuid)
    if index is None or not (0 <= index < len(entries)):
        return get_entry_index_by_uuid(entries, entry_uuid)
    return index


def get_all_entry_pairs() -> list[tuple[str, dict]]:
    """Return [(entry_uuid, entry), ...] for all loaded entries."""

    ensure_entry_indexes()
    pairs: list[tuple[str, dict]] = []
    for entry in st.session_state.get("loaded_entries", []):
        entry_uuid = get_entry_uuid(entry) if isinstance(entry, dict) else None
        if entry_uuid:
            pairs.append((entry_uuid, entry))
    return pairs


# â”€â”€ Selection helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def ensure_selection_state() -> None:
    """Ensure selected_entry_uuids exists as a set in session state."""
    if not isinstance(st.session_state.get("selected_entry_uuids"), set):
        st.session_state.selected_entry_uuids = set()


def clear_selected_entries() -> None:
    """Clear all selected entry UUIDs."""
    st.session_state.selected_entry_uuids = set()


def toggle_entry_selection(entry_uuid: str, selected: bool) -> None:
    """Add or remove entry_uuid from selected_entry_uuids."""
    ensure_selection_state()
    if selected:
        st.session_state.selected_entry_uuids.add(entry_uuid)
    else:
        st.session_state.selected_entry_uuids.discard(entry_uuid)


def select_visible_entries(visible_pairs: list[tuple[str, dict]]) -> None:
    """Add all visible (current-page) entry UUIDs to selected_entry_uuids."""
    ensure_selection_state()
    for entry_uuid, _ in visible_pairs:
        st.session_state.selected_entry_uuids.add(entry_uuid)


def get_selected_entry_uuids() -> list[str]:
    """Return selected UUIDs as a list."""
    ensure_selection_state()
    return list(st.session_state.selected_entry_uuids)


def prune_selection_to_loaded_entries() -> None:
    """Remove selected UUIDs that no longer exist in the loaded entries.

    Call after loading, creating, deleting, or any index rebuild.
    """
    ensure_selection_state()
    ensure_entry_indexes()
    valid_uuids = set(st.session_state.get("uuid_to_index", {}))
    st.session_state.selected_entry_uuids &= valid_uuids


def delete_selected_entries() -> tuple[int, list[str], bool]:
    """Delete selected entries by UUID and persist to disk.

    Clears selection only if the save succeeds.
    Returns (count_deleted, list_of_failed_uuids, backup_created).
    """
    ensure_entry_indexes()
    uuids_to_delete = set(get_selected_entry_uuids())
    entries = st.session_state.get("loaded_entries", [])
    current_uuids = [
        entry_uuid
        for entry in entries
        if isinstance(entry, dict)
        for entry_uuid in [get_entry_uuid(entry)]
        if entry_uuid
    ]
    current_uuid_set = set(current_uuids)
    failures = [
        entry_uuid
        for entry_uuid in uuids_to_delete
        if entry_uuid not in current_uuid_set
    ]
    attempted_uuids = [
        entry_uuid for entry_uuid in current_uuids if entry_uuid in uuids_to_delete
    ]

    delete_indices: list[int] = []
    for index, entry in enumerate(entries):
        entry_uuid = get_entry_uuid(entry) if isinstance(entry, dict) else None
        if entry_uuid in uuids_to_delete:
            delete_indices.append(index)

    if delete_indices:
        result = delete_entries_service(
            dataset_path=st.session_state.get("loaded_path", ""),
            entries=st.session_state.loaded_entries,
            entry_indices=delete_indices,
            backup_enabled=auto_backups_enabled(st.session_state.get("prefs", {})),
        )
        if not result.ok:
            for err in result.errors:
                st.error(err)
            if not result.errors:
                st.error(result.message)
            return 0, attempted_uuids + failures, False
        if result.entries is None:
            st.error("Delete operation did not return updated entries.")
            return 0, attempted_uuids + failures, False
        apply_dataset_operation_result(result)
        st.session_state.loaded_entries = result.entries
        st.session_state.uuid_to_index = build_uuid_index(result.entries)
        clear_selected_entries()
        _enqueue_sidecar_warning_if_needed(result)
        return result.affected_count, failures, result.backup_path is not None
    return 0, failures, False


def _enqueue_sidecar_warning_if_needed(result: DatasetOperationResult) -> None:
    if getattr(result, "sidecar_ok", True):
        return
    detail = getattr(result, "sidecar_message", None)
    warning = "Dataset saved successfully but registry sidecar could not be updated."
    if detail:
        warning = f"{warning} {detail}"
    enqueue_flash("warning", warning)


# â”€â”€ Quick-edit helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def start_quick_edit(entry_uuid: str, entry: dict) -> None:
    """Enter quick edit mode for entry_uuid.

    Sets quick_edit_entry_uuid and pre-loads each user/assistant message into
    its text-area session-state key so the widget opens with current content.
    """
    st.session_state.quick_edit_entry_uuid = entry_uuid
    messages = entry.get("messages", [])
    if not isinstance(messages, list):
        messages = []
    for idx, msg in enumerate(scaffold_editable_messages(messages)):
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
            st.session_state[f"quick_edit_{entry_uuid}_{idx}"] = msg.get("content", "")


def cancel_quick_edit() -> None:
    """Exit quick edit mode without saving."""
    entry_uuid = st.session_state.get("quick_edit_entry_uuid")
    st.session_state.quick_edit_entry_uuid = None
    # Remove stale text-area keys for the closed entry so re-opening starts fresh
    if entry_uuid:
        keys_to_drop = [
            k for k in list(st.session_state.keys())
            if k.startswith(f"quick_edit_{entry_uuid}_")
        ]
        for k in keys_to_drop:
            st.session_state.pop(k, None)


def save_quick_edit(entry_uuid: str, entry: dict) -> DatasetOperationResult:
    """Read edited message content from session state, then delegate saving.

    Updates only user/assistant message content.
    System message, role names, tags, and message order are preserved.
    """
    entry_index = get_loaded_entry_index_by_uuid(entry_uuid)
    if entry_index is None:
        return DatasetOperationResult(
            ok=False,
            message="Could not find the selected entry.",
        )

    msgs = entry.get("messages", [])
    if not isinstance(msgs, list):
        msgs = []
    msgs = scaffold_editable_messages(msgs)
    updated_msgs = []
    for msg_index, msg in enumerate(msgs):
        if not isinstance(msg, dict):
            updated_msgs.append(msg)
            continue
        role = msg.get("role")
        if role in ("user", "assistant"):
            new_content = st.session_state.get(
                f"quick_edit_{entry_uuid}_{msg_index}", msg.get("content", "")
            )
            updated_msgs.append({**msg, "content": new_content})
        else:
            updated_msgs.append(dict(msg))

    result = save_quick_edit_service(
        dataset_path=st.session_state.get("loaded_path", ""),
        entries=st.session_state.loaded_entries,
        entry_index=entry_index,
        updated_messages=updated_msgs,
        backup_enabled=auto_backups_enabled(st.session_state.get("prefs", {})),
    )
    if result.ok and result.entries is not None:
        apply_dataset_operation_result(result)
        st.session_state.loaded_entries = result.entries
        st.session_state.uuid_to_index = build_uuid_index(result.entries)
    return result

