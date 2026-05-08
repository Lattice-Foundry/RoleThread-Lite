"""Streamlit session-state bridge helpers.

This module may touch st.session_state, but durable dataset mutations should
delegate to services. It must not import app.py.
"""
import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import (
    build_entry_registry,
    get_entry_pairs,
    get_index_for_entry_id,
    rebuild_id_to_index,
    registry_is_valid,
)
from core.preferences import save_preferences
from services.dataset_service import (
    DatasetOperationResult,
    delete_entries_service,
    save_quick_edit_service,
)


# ── Preferences session helper ─────────────────────────────────────────────────

def _update_prefs(updates: dict) -> None:
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


def set_loaded_entries(entries: list[dict]) -> None:
    """Replace loaded_entries and rebuild the registry from scratch."""
    st.session_state.loaded_entries = entries
    st.session_state.entry_registry = build_entry_registry(entries)


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


def deselect_visible_entries(visible_pairs: list[tuple[str, dict]]) -> None:
    """Remove all visible (current-page) entry IDs from selected_entry_ids."""
    ensure_selection_state()
    for entry_id, _ in visible_pairs:
        st.session_state.selected_entry_ids.discard(entry_id)


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
        st.session_state.loaded_entries = result.entries
        st.session_state.entry_registry = {
            **st.session_state.entry_registry,
            "ids": proposed_ids,
            "id_to_index": rebuild_id_to_index(proposed_ids),
        }
        clear_selected_entries()
        return result.affected_count, failures, result.backup_path is not None
    return 0, failures, False


# ── Quick-edit helpers ─────────────────────────────────────────────────────────

def start_quick_edit(entry_id: str, entry: dict) -> None:
    """Enter quick edit mode for entry_id.

    Sets quick_edit_entry_id and pre-loads each user/assistant message into
    its text-area session-state key so the widget opens with current content.
    """
    st.session_state.quick_edit_entry_id = entry_id
    for idx, msg in enumerate(entry.get("messages", [])):
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
        st.session_state.loaded_entries = result.entries
        ensure_entry_registry()
    return result
