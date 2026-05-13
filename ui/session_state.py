"""Streamlit session-state bridge helpers.

This UI-layer module may touch st.session_state and coordinate service calls.
Pure dataset logic belongs in core or services.
"""
from pathlib import Path

import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import (
    build_entry_registry,
    get_entry_pairs,
    get_index_for_entry_id,
    rebuild_id_to_index,
    registry_is_valid,
    TagNormalizationSummary,
)
from core.load_pipeline import finalize_loaded_entries
from core.preferences import save_preferences
from services.dataset_service import (
    DatasetOperationResult,
    delete_entries_service,
    save_repaired_entries_service,
    save_quick_edit_service,
)
from ui.message_scaffolding import scaffold_editable_messages
from ui.flash_messages import enqueue_flash


# ── Preferences session helper ─────────────────────────────────────────────────

def update_prefs(updates: dict) -> None:
    """Update st.session_state.prefs in place and persist to disk."""
    st.session_state.prefs.update(updates)
    save_preferences(st.session_state.prefs)


# ── Registry / session helpers ─────────────────────────────────────────────────

def ensure_entry_registry() -> None:
    """Ensure entry_registry exists and is consistent with loaded_entries.

    Rebuilds silently if missing or invalid — safe to call anywhere.
    """
    entries = st.session_state.get("loaded_entries", [])
    if not registry_is_valid(st.session_state.get("entry_registry"), entries):
        st.session_state.entry_registry = build_entry_registry(entries)


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
    st.session_state.loaded_entries = result.entries
    st.session_state.dataset_source_format = result.dataset_source_format
    st.session_state.entry_registry = result.entry_registry
    st.session_state.tag_normalization_summary = result.tag_normalization_summary
    st.session_state.dataset_is_native = result.dataset_is_native
    st.session_state.normalization_pending = result.normalization_pending
    _replace_optional_session_value("working_copy_summary", result.working_copy_summary)
    _replace_optional_session_value("sidecar_import_summary", result.sidecar_import_summary)
    _replace_optional_session_value("pending_tag_trust", result.pending_tag_trust or None)
    _replace_optional_session_value("character_candidates", result.character_candidates)
    return result.effective_dataset_path


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
)


def clear_dataset_scoped_state() -> None:
    """Clear confirmation/edit state that must not survive dataset switches."""

    clear_entry_edit_state()
    for key in _DATASET_SCOPED_STATE_KEYS:
        st.session_state.pop(key, None)


def clear_entry_edit_state() -> None:
    """Clear Quick Edit and Full Edit UI state without triggering a rerun."""

    st.session_state.quick_edit_entry_id = None
    st.session_state.edit_entries_mode = "browser"
    for key in (
        "editing_entry_id",
        "full_edit_entry_id",
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
        st.session_state.entry_registry = build_entry_registry(result.entries)
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


def get_loaded_entry_by_id(entry_id: str) -> dict | None:
    """Return the entry for the given temp ID, or None if not found."""
    ensure_entry_registry()
    idx = get_index_for_entry_id(st.session_state.entry_registry, entry_id)
    if idx is None:
        return None
    entries = st.session_state.loaded_entries
    return entries[idx] if 0 <= idx < len(entries) else None


def get_loaded_entry_index_by_id(entry_id: str) -> int | None:
    """Return the current source index for entry_id, or None if not found."""
    ensure_entry_registry()
    idx = get_index_for_entry_id(st.session_state.entry_registry, entry_id)
    entries = st.session_state.loaded_entries
    if idx is None or not (0 <= idx < len(entries)):
        return None
    return idx


def get_all_entry_pairs() -> list[tuple[str, dict]]:
    """Return [(entry_id, entry), ...] for all loaded entries."""
    ensure_entry_registry()
    return get_entry_pairs(st.session_state.loaded_entries, st.session_state.entry_registry)


# ── Selection helpers ──────────────────────────────────────────────────────────

def ensure_selection_state() -> None:
    """Ensure selected_entry_ids exists as a set in session state."""
    if not isinstance(st.session_state.get("selected_entry_ids"), set):
        st.session_state.selected_entry_ids = set()


def clear_selected_entries() -> None:
    """Clear all selected entry IDs."""
    st.session_state.selected_entry_ids = set()


def toggle_entry_selection(entry_id: str, selected: bool) -> None:
    """Add or remove entry_id from selected_entry_ids."""
    ensure_selection_state()
    if selected:
        st.session_state.selected_entry_ids.add(entry_id)
    else:
        st.session_state.selected_entry_ids.discard(entry_id)


def select_visible_entries(visible_pairs: list[tuple[str, dict]]) -> None:
    """Add all visible (current-page) entry IDs to selected_entry_ids."""
    ensure_selection_state()
    for entry_id, _ in visible_pairs:
        st.session_state.selected_entry_ids.add(entry_id)


def get_selected_entry_ids() -> list[str]:
    """Return selected IDs as a list."""
    ensure_selection_state()
    return list(st.session_state.selected_entry_ids)


def prune_selection_to_loaded_entries() -> None:
    """Remove selected IDs that no longer exist in the current registry.

    Call after loading, creating, deleting, or any registry rebuild.
    """
    ensure_selection_state()
    ensure_entry_registry()
    valid_ids = set(st.session_state.entry_registry.get("ids", []))
    st.session_state.selected_entry_ids &= valid_ids


def delete_selected_entries() -> tuple[int, list[str], bool]:
    """Delete selected entries by temp ID and persist to disk.

    Clears selection only if the save succeeds.
    Returns (count_deleted, list_of_failed_ids, backup_created).
    """
    ensure_entry_registry()
    ids_to_delete = set(get_selected_entry_ids())
    current_ids = st.session_state.entry_registry.get("ids", [])
    current_id_set = set(current_ids)
    failures = [entry_id for entry_id in ids_to_delete if entry_id not in current_id_set]
    attempted_ids = [entry_id for entry_id in current_ids if entry_id in ids_to_delete]

    proposed_ids: list[str] = []
    delete_indices: list[int] = []
    for index, entry_id in enumerate(current_ids):
        if entry_id in ids_to_delete:
            delete_indices.append(index)
            continue
        proposed_ids.append(entry_id)

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
            return 0, attempted_ids + failures, False
        if result.entries is None:
            st.error("Delete operation did not return updated entries.")
            return 0, attempted_ids + failures, False
        apply_dataset_operation_result(result)
        st.session_state.loaded_entries = result.entries
        st.session_state.entry_registry = {
            **st.session_state.entry_registry,
            "ids": proposed_ids,
            "id_to_index": rebuild_id_to_index(proposed_ids),
        }
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


# ── Quick-edit helpers ─────────────────────────────────────────────────────────

def start_quick_edit(entry_id: str, entry: dict) -> None:
    """Enter quick edit mode for entry_id.

    Sets quick_edit_entry_id and pre-loads each user/assistant message into
    its text-area session-state key so the widget opens with current content.
    """
    st.session_state.quick_edit_entry_id = entry_id
    messages = entry.get("messages", [])
    if not isinstance(messages, list):
        messages = []
    for idx, msg in enumerate(scaffold_editable_messages(messages)):
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
            st.session_state[f"quick_edit_{entry_id}_{idx}"] = msg.get("content", "")


def cancel_quick_edit() -> None:
    """Exit quick edit mode without saving."""
    entry_id = st.session_state.get("quick_edit_entry_id")
    st.session_state.quick_edit_entry_id = None
    # Remove stale text-area keys for the closed entry so re-opening starts fresh
    if entry_id:
        keys_to_drop = [
            k for k in list(st.session_state.keys())
            if k.startswith(f"quick_edit_{entry_id}_")
        ]
        for k in keys_to_drop:
            st.session_state.pop(k, None)


def save_quick_edit(entry_id: str, entry: dict) -> DatasetOperationResult:
    """Read edited message content from session state, then delegate saving.

    Updates only user/assistant message content.
    System message, role names, tags, and message order are preserved.
    """
    entry_index = get_loaded_entry_index_by_id(entry_id)
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
                f"quick_edit_{entry_id}_{msg_index}", msg.get("content", "")
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
        ensure_entry_registry()
    return result
