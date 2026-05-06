"""Session-state bridge helpers.

All functions here read from or write to st.session_state.
Pure data logic lives in dataset.py; UI rendering lives in ui_components.py.
This module must not import app.py (would cause a circular import).
"""
import streamlit as st

from dataset import (
    append_registry_id,
    build_entry_registry,
    get_entry_pairs,
    get_index_for_entry_id,
    registry_is_valid,
    remove_registry_id,
    save_dataset,
    validate_entry,
)
from preferences import save_preferences


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


def append_loaded_entry(entry: dict) -> None:
    """Append one entry and add a matching temp ID to the registry."""
    ensure_entry_registry()
    st.session_state.loaded_entries.append(entry)
    append_registry_id(st.session_state.entry_registry)


def get_loaded_entry_by_id(entry_id: str) -> dict | None:
    """Return the entry for the given temp ID, or None if not found."""
    ensure_entry_registry()
    idx = get_index_for_entry_id(st.session_state.entry_registry, entry_id)
    if idx is None:
        return None
    entries = st.session_state.loaded_entries
    return entries[idx] if 0 <= idx < len(entries) else None


def replace_loaded_entry_by_id(entry_id: str, new_entry: dict) -> bool:
    """Overwrite the entry at entry_id in-place. Returns True on success."""
    ensure_entry_registry()
    idx = get_index_for_entry_id(st.session_state.entry_registry, entry_id)
    if idx is None:
        return False
    entries = st.session_state.loaded_entries
    if not (0 <= idx < len(entries)):
        return False
    st.session_state.loaded_entries[idx] = new_entry
    return True


def delete_loaded_entry_by_id(entry_id: str) -> bool:
    """Delete the entry at entry_id and remove it from the registry.

    Returns True on success.
    """
    ensure_entry_registry()
    idx = get_index_for_entry_id(st.session_state.entry_registry, entry_id)
    if idx is None:
        return False
    entries = st.session_state.loaded_entries
    if not (0 <= idx < len(entries)):
        return False
    del st.session_state.loaded_entries[idx]
    remove_registry_id(st.session_state.entry_registry, entry_id)
    return True


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


# ── Loaded dataset persistence helpers ────────────────────────────────────────

def save_loaded_dataset() -> bool:
    """Save loaded_entries to loaded_path. Returns True on success, False on failure."""
    try:
        save_dataset(st.session_state.loaded_path, st.session_state.loaded_entries)
        return True
    except Exception as exc:
        st.error(f"Failed to save dataset: {exc}")
        return False


def delete_selected_entries() -> tuple[int, list[str]]:
    """Delete selected entries by temp ID and persist to disk.

    Clears selection only if the save succeeds.
    Returns (count_deleted, list_of_failed_ids).
    """
    ids_to_delete = get_selected_entry_ids()
    deleted = 0
    failures: list[str] = []
    for entry_id in ids_to_delete:
        if delete_loaded_entry_by_id(entry_id):
            deleted += 1
        else:
            failures.append(entry_id)
    if deleted > 0 and save_loaded_dataset():
        clear_selected_entries()
    return deleted, failures


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


def save_quick_edit(entry_id: str, entry: dict) -> bool:
    """Read edited message content from session state, validate, then save.

    Updates only user/assistant message content in place.
    System message, role names, tags, and message order are preserved.
    Returns True on successful save, False if validation fails or save errors.
    """
    msgs = entry.get("messages", [])
    updated_msgs = []
    for idx, msg in enumerate(msgs):
        if not isinstance(msg, dict):
            updated_msgs.append(msg)
            continue
        role = msg.get("role")
        if role in ("user", "assistant"):
            new_content = st.session_state.get(
                f"quick_edit_{entry_id}_{idx}", msg.get("content", "")
            )
            updated_msgs.append({**msg, "content": new_content})
        else:
            updated_msgs.append(dict(msg))

    # Validate against a temporary copy before committing
    temp_entry = {**entry, "messages": updated_msgs}
    errors = validate_entry(temp_entry)
    if errors:
        for err in errors:
            st.error(err)
        return False

    # Apply in-place and persist
    entry["messages"] = updated_msgs
    return save_loaded_dataset()
