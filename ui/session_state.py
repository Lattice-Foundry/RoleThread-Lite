"""Streamlit session-state bridge helpers.

This UI-layer module may touch st.session_state and coordinate service calls.
Pure dataset logic belongs in core or services.
"""
from pathlib import Path

import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import (
    TagNormalizationSummary,
    build_entry_registry,
    get_entry_pairs,
    get_entry_tags,
    get_index_for_entry_id,
    normalize_dataset_tags,
    rebuild_id_to_index,
    registry_is_valid,
)
from core.preferences import save_preferences
from core.registry_sidecar import read_sidecar, sidecar_path_for_dataset
from core.tag_constants import ARCHIVE_ORIGIN_IMPORTED, TAG_STATUS_ARCHIVED
from core.tag_registry import (
    ensure_tags_exist_for_dataset,
    get_current_tag_lifecycle_metadata,
    get_tag_by_slug_any_status,
    prettify_tag_name,
)
from core.working_copy import create_dataset_working_copy
from services.dataset_service import (
    DatasetOperationResult,
    delete_entries_service,
    normalize_dataset_service,
    save_quick_edit_service,
)
from services.registry_sidecar_service import import_registry_sidecar


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
    """Replace loaded_entries and rebuild the registry from scratch."""
    normalization = normalization_summary or normalize_dataset_tags(entries)
    working_copy_summary, effective_dataset_path = _prepare_foreign_working_copy(
        dataset_path,
        dataset_is_native=normalization.dataset_is_native,
    )
    sidecar_summary, sidecar_tags, sidecar_categories = _import_sibling_sidecar(
        effective_dataset_path
    )
    adoption = ensure_tags_exist_for_dataset(normalization.entries)
    pending_trust = _build_pending_tag_trust(
        normalization.entries,
        sidecar_tags=sidecar_tags,
        sidecar_categories=sidecar_categories,
    )
    st.session_state.loaded_entries = normalization.entries
    st.session_state.dataset_source_format = normalization.source_format
    st.session_state.entry_registry = build_entry_registry(normalization.entries)
    st.session_state.tag_normalization_summary = {
        "changed_entries": normalization.changed_entries,
        "changed_tags": normalization.changed_tags,
        "structural_changed_entries": normalization.structural_changed_entries,
        "tag_metadata_added_count": normalization.tag_metadata_added_count,
        "dropped_tags": normalization.dropped_tags,
        "source_format": normalization.source_format,
        "format_counts": normalization.format_counts,
        "format_confidence": normalization.format_confidence,
        "format_converted_count": normalization.format_converted_count,
        "format_already_target_count": normalization.format_already_target_count,
        "format_warnings": normalization.format_warnings,
        "diagnostics": {
            "entries_analyzed": normalization.diagnostics.entries_analyzed,
            "valid_entries": normalization.diagnostics.valid_entries,
            "entries_with_errors": normalization.diagnostics.entries_with_errors,
            "entries_with_warnings": normalization.diagnostics.entries_with_warnings,
            "entries_with_info": normalization.diagnostics.entries_with_info,
            "error_count": normalization.diagnostics.error_count,
            "warning_count": normalization.diagnostics.warning_count,
            "info_count": normalization.diagnostics.info_count,
            "auto_repairable_count": normalization.diagnostics.auto_repairable_count,
        },
        "adopted_count": adoption.created_count,
        "adopted_slugs": adoption.created_slugs or [],
        "sidecar_import": sidecar_summary,
        "pending_trust_count": len(pending_trust),
        "dataset_is_native": normalization.dataset_is_native,
        "working_copy": working_copy_summary,
    }
    st.session_state.dataset_is_native = normalization.dataset_is_native
    st.session_state.normalization_pending = normalization.structural_changed_entries > 0
    _replace_optional_session_value("working_copy_summary", working_copy_summary)
    _replace_optional_session_value("sidecar_import_summary", sidecar_summary)
    _replace_optional_session_value("pending_tag_trust", pending_trust or None)
    return effective_dataset_path


def _replace_optional_session_value(key: str, value) -> None:
    if value:
        st.session_state[key] = value
    else:
        st.session_state.pop(key, None)


def _prepare_foreign_working_copy(
    dataset_path: str | None,
    *,
    dataset_is_native: bool,
) -> tuple[dict | None, str | None]:
    if not dataset_path:
        return None, dataset_path
    if dataset_is_native:
        return None, dataset_path
    if not Path(dataset_path).exists():
        return None, dataset_path

    result = create_dataset_working_copy(dataset_path)
    if not result.created:
        return None, result.working_path
    return (
        {
            "original_path": result.original_path,
            "working_path": result.working_path,
            "sidecar_copied": result.sidecar_copied,
            "sidecar_path": result.sidecar_path,
        },
        result.working_path,
    )


def _import_sibling_sidecar(dataset_path: str | None):
    if not dataset_path:
        return None, {}, {}

    sidecar_path = sidecar_path_for_dataset(Path(dataset_path))
    if not sidecar_path.exists():
        return None, {}, {}

    try:
        registry = read_sidecar(sidecar_path)
    except Exception as exc:
        return (
            {
                "found": True,
                "ok": False,
                "path": str(sidecar_path),
                "message": f"Could not read registry sidecar: {exc}",
                "categories_created": [],
                "tags_created": [],
                "tags_promoted": [],
                "aliases_imported": [],
                "conflicts": [],
                "warnings": [],
                "errors": [str(exc)],
            },
            {},
            {},
        )

    try:
        result = import_registry_sidecar(registry=registry)
    except Exception as exc:
        return (
            {
                "found": True,
                "ok": False,
                "path": str(sidecar_path),
                "message": f"Could not import registry sidecar: {exc}",
                "categories_created": [],
                "tags_created": [],
                "tags_promoted": [],
                "aliases_imported": [],
                "conflicts": [],
                "warnings": [],
                "errors": [str(exc)],
            },
            {tag.slug: tag for tag in registry.tags},
            {category.slug: category for category in registry.categories},
        )
    summary = {
        "found": True,
        "ok": result.ok,
        "path": str(sidecar_path),
        "message": result.message,
        "categories_created": list(result.categories_created),
        "tags_created": list(result.tags_created),
        "tags_promoted": list(result.tags_promoted),
        "aliases_imported": list(result.aliases_imported),
        "conflicts": list(result.conflicts),
        "warnings": list(result.warnings),
        "errors": list(result.errors),
    }
    return (
        summary,
        {tag.slug: tag for tag in registry.tags},
        {category.slug: category for category in registry.categories},
    )


def _build_pending_tag_trust(
    entries: list[dict],
    *,
    sidecar_tags: dict,
    sidecar_categories: dict,
) -> dict[str, dict]:
    entry_indices_by_slug: dict[str, list[int]] = {}
    for index, entry in enumerate(entries):
        for slug in get_entry_tags(entry):
            entry_indices_by_slug.setdefault(slug, []).append(index)

    pending: dict[str, dict] = {}
    for slug, entry_indices in sorted(entry_indices_by_slug.items()):
        tag = get_tag_by_slug_any_status(slug)
        if tag is None or tag.status != TAG_STATUS_ARCHIVED:
            continue

        metadata = get_current_tag_lifecycle_metadata(slug)
        archive_origin = metadata.get("archive_origin")
        if archive_origin is None and getattr(tag, "category_id", None) is None:
            archive_origin = ARCHIVE_ORIGIN_IMPORTED
        if archive_origin != ARCHIVE_ORIGIN_IMPORTED:
            continue

        sidecar_tag = sidecar_tags.get(slug)
        sidecar_category = (
            sidecar_categories.get(sidecar_tag.category_slug)
            if sidecar_tag and sidecar_tag.category_slug
            else None
        )
        pending[slug] = {
            "display_name": getattr(tag, "name", None) or prettify_tag_name(slug),
            "entry_indices": entry_indices,
            "usage_count": len(entry_indices),
            "registry_status": getattr(tag, "status", TAG_STATUS_ARCHIVED),
            "archive_origin": archive_origin,
            "sidecar_category_slug": sidecar_tag.category_slug if sidecar_tag else None,
            "sidecar_category_name": sidecar_category.name if sidecar_category else None,
            "sidecar_status": sidecar_tag.status if sidecar_tag else None,
            "resolution": "sidecar_hint" if sidecar_tag else "no_hint",
            "status": "pending",
        }
    return pending


def clear_normalization_pending() -> None:
    """Clear pending structural-normalization state after disk persistence."""
    st.session_state.normalization_pending = False
    summary = st.session_state.get("tag_normalization_summary", {})
    st.session_state.tag_normalization_summary = {
        **summary,
        "structural_changed_entries": 0,
        "tag_metadata_added_count": 0,
    }


def should_auto_normalize_loaded_dataset(
    *,
    prefs: dict,
    parse_errors: list[str],
    normalization_pending: bool,
    auto_normalize_on_load: bool | None = None,
) -> bool:
    """Return True when an explicit load should persist normalized structure."""
    enabled = (
        prefs.get("auto_normalize_on_load", True)
        if auto_normalize_on_load is None
        else auto_normalize_on_load
    )
    return (
        bool(enabled)
        and not parse_errors
        and normalization_pending
    )


def persist_loaded_normalization(dataset_path: str) -> DatasetOperationResult:
    """Persist normalized loaded entries and clear pending state on success."""
    result = normalize_dataset_service(
        dataset_path=dataset_path,
        entries=st.session_state.loaded_entries,
    )
    if result.ok and result.entries is not None:
        st.session_state.loaded_entries = result.entries
        st.session_state.entry_registry = build_entry_registry(result.entries)
        clear_normalization_pending()
    return result


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
