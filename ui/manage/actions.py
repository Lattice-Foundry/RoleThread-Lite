"""Selection and bulk action controls for Manage Dataset."""
from typing import Any

import streamlit as st

from core.backups import auto_backups_enabled
from core.entry_search import EntrySearchOptions
from core.text_helpers import count_phrase
from services.dataset_service import join_entries_service, replace_system_prompt_bulk_service
from ui.browser_helpers import format_browser_status_caption
from ui.flash_messages import enqueue_dataset_result_flash, enqueue_flash
from ui.session_state import (
    apply_dataset_operation_result,
    clear_selected_entries,
    delete_selected_entries,
    ensure_entry_indexes,
    get_loaded_entry_index_by_uuid,
    get_selected_entry_uuids,
    prune_selection_to_loaded_entries,
    select_visible_entries,
)
from ui.manage.tag_actions import render_tag_editor


def render_actions(
    *,
    filtered_pairs: list[tuple[str, dict]],
    visible_pairs: list[tuple[str, dict]],
    filter_tags: list[str],
    match_mode: str,
    per_page: int,
    current_page: int,
    start: int,
    end: int,
    total_filtered: int,
    total_all: int,
    search_query: str,
    search_active: bool,
    search_options: EntrySearchOptions,
    stats_filter_active: bool,
    stats_filter_uuids: tuple[str, ...],
    tag_snapshot: Any,
) -> None:
    """Render selection actions and tag-edit controls."""

    view_fingerprint = (
        tuple(sorted(filter_tags)),
        match_mode,
        str(search_query or "").strip(),
        search_options.scopes,
        search_options.match_mode,
        stats_filter_uuids,
        st.session_state.entries_per_page,
        current_page,
    )
    if st.session_state.get("manage_select_all_mode", False):
        if st.session_state.get("_select_all_fingerprint") != view_fingerprint:
            st.session_state["manage_select_all_mode"] = False
            clear_selected_entries()

    selected_uuids = get_selected_entry_uuids()
    total_selected = len(selected_uuids)
    st.caption(
        format_browser_status_caption(
            start=start,
            end=end,
            total_filtered=total_filtered,
            total_all=total_all,
            filtered=bool(filter_tags) or search_active or stats_filter_active,
            selected_count=total_selected,
            filtered_label=(
                "matching entries"
                if search_active
                else "Stats entries"
                if stats_filter_active
                else "filtered entries"
            ),
        )
    )

    no_selection = total_selected == 0
    (
        col_sel_all, col_clear,
        col_sys_prompt, col_delete, _col_act_spacer,
    ) = st.columns([1, 1, 1, 1, 2])
    with col_sel_all:
        if st.button("Select all visible", key="btn_select_all_visible",
                     width="stretch"):
            st.session_state["manage_select_all_mode"] = True
            st.session_state["_select_all_fingerprint"] = view_fingerprint
            clear_selected_entries()
            select_visible_entries(visible_pairs)
            st.rerun()
    with col_clear:
        if st.button("Clear Selection", key="btn_clear_visible",
                     width="stretch"):
            st.session_state["manage_select_all_mode"] = False
            clear_selected_entries()
            st.rerun()
    with col_sys_prompt:
        if st.button("Modify System", key="btn_modify_sys_prompt",
                     disabled=no_selection, width="stretch"):
            st.session_state["pending_system_prompt_edit"] = True
            st.session_state.pop("bulk_system_prompt_text", None)
            st.rerun()
    with col_delete:
        if st.button("Delete Selected", key="btn_delete_selected",
                     disabled=no_selection, width="stretch"):
            if st.session_state.get("confirm_delete_entries", True):
                st.session_state["pending_delete_selected"] = True
                st.rerun()
            else:
                _delete_selected(per_page)

    if total_selected >= 2:
        if st.button("Join Selected", key="btn_join_selected", width="stretch"):
            st.session_state["pending_join_selected"] = True
            st.rerun()

    if st.session_state.get("pending_delete_selected"):
        pending_sel_uuids = get_selected_entry_uuids()
        selected_entry_phrase = count_phrase(
            len(pending_sel_uuids),
            "selected entry",
            "selected entries",
        )
        st.warning(f"Delete {selected_entry_phrase}? This cannot be undone.")
        col_confirm, col_cancel, _col_del_spacer = st.columns([1, 1, 2])
        with col_confirm:
            if st.button("Confirm Delete", type="primary",
                         key="btn_confirm_delete", width="stretch"):
                _delete_selected(per_page)
        with col_cancel:
            if st.button("Cancel", key="btn_cancel_delete", width="stretch"):
                st.session_state.pop("pending_delete_selected", None)
                st.rerun()

    if st.session_state.get("pending_join_selected"):
        _render_join_confirmation(filtered_pairs, selected_uuids)

    if st.session_state.get("pending_system_prompt_edit"):
        _render_system_prompt_editor(total_selected, selected_uuids)

    render_tag_editor(selected_uuids, tag_snapshot)


def _render_join_confirmation(
    filtered_pairs: list[tuple[str, dict]],
    selected_uuids: list[str],
) -> None:
    ordered_selected_uuids = [
        entry_uuid for entry_uuid, _entry in filtered_pairs
        if entry_uuid in set(selected_uuids)
    ]
    st.warning(
        f"Join {count_phrase(len(ordered_selected_uuids), 'selected entry', 'selected entries')} "
        "into one multi-turn conversation? Order: current display order. "
        "System prompt from first entry."
    )
    col_confirm, col_cancel, _col_join_spacer = st.columns([1, 1, 2])
    with col_confirm:
        if st.button("Confirm Join", key="btn_confirm_join", type="primary",
                     width="stretch"):
            result = join_entries_service(
                dataset_path=st.session_state.get("loaded_path", ""),
                entries=st.session_state.loaded_entries,
                entry_uuids=ordered_selected_uuids,
                backup_enabled=auto_backups_enabled(st.session_state.get("prefs", {})),
            )
            st.session_state.pop("pending_join_selected", None)
            if result.ok and result.entries is not None:
                apply_dataset_operation_result(result)
                st.session_state.loaded_entries = result.entries
                ensure_entry_indexes()
                clear_selected_entries()
                st.session_state["manage_select_all_mode"] = False
                backup_note = " Backup created." if result.backup_path else ""
                enqueue_dataset_result_flash(
                    f"{result.message}{backup_note}",
                    result,
                )
                for warning in result.warnings:
                    enqueue_flash("warning", warning)
                st.rerun()
            else:
                for error in result.errors:
                    st.error(error)
                if not result.errors:
                    st.error(result.message)
    with col_cancel:
        if st.button("Cancel", key="btn_cancel_join", width="stretch"):
            st.session_state.pop("pending_join_selected", None)
            st.rerun()


def _delete_selected(per_page: int) -> None:
    deleted_count, failures, backup_created = delete_selected_entries()
    st.session_state.pop("pending_delete_selected", None)
    st.session_state["manage_select_all_mode"] = False
    prune_selection_to_loaded_entries()
    new_total = len(st.session_state.loaded_entries)
    if new_total == 0 or st.session_state.entry_page > max(
        0, (new_total - 1) // per_page
    ):
        st.session_state.entry_page = 0
    if failures:
        st.warning(
            f"Deleted {deleted_count} entries. "
            f"{len(failures)} could not be removed."
        )
    else:
        backup_note = " Backup created." if backup_created else ""
        enqueue_flash("success", f"Deleted {deleted_count} entries.{backup_note}")
    st.rerun()


def _render_system_prompt_editor(
    total_selected: int,
    selected_uuids: list[str],
) -> None:
    st.info(
        "Replace the system prompt for "
        f"{count_phrase(total_selected, 'selected entry', 'selected entries')}. "
        "This will overwrite existing system prompts "
        "or insert one if missing."
    )
    new_prompt = st.text_area(
        "New system prompt",
        key="bulk_system_prompt_text",
        height=120,
    )
    col_apply, col_sp_cancel, _col_sp_spacer = st.columns([1, 1, 2])
    with col_apply:
        if st.button(
            "Apply System Prompt",
            key="btn_apply_sys_prompt",
            disabled=not (new_prompt or "").strip(),
            width="stretch",
        ):
            indices = [
                idx for idx in (
                    get_loaded_entry_index_by_uuid(selected_uuid)
                    for selected_uuid in selected_uuids
                )
                if idx is not None
            ]
            sys_result = replace_system_prompt_bulk_service(
                dataset_path=st.session_state.get("loaded_path", ""),
                entries=st.session_state.loaded_entries,
                entry_indices=indices,
                system_prompt=new_prompt.strip(),
                backup_enabled=auto_backups_enabled(
                    st.session_state.get("prefs", {})
                ),
            )
            if sys_result.ok and sys_result.entries is not None:
                apply_dataset_operation_result(sys_result)
                st.session_state.loaded_entries = sys_result.entries
                ensure_entry_indexes()
                backup_note = " Backup created." if sys_result.backup_path else ""
                st.session_state.pop("pending_system_prompt_edit", None)
                enqueue_dataset_result_flash(
                    f"{sys_result.message}{backup_note}",
                    sys_result,
                )
                st.rerun()
            else:
                for err in sys_result.errors:
                    st.error(err)
                if not sys_result.errors:
                    st.error(sys_result.message)
    with col_sp_cancel:
        if st.button("Cancel", key="btn_sp_cancel", width="stretch"):
            st.session_state.pop("pending_system_prompt_edit", None)
            st.rerun()
