"""Entry list rendering for the Manage Dataset page."""
from typing import Any

import streamlit as st

from core.backups import auto_backups_enabled
from core.character_display import get_turn_display_names
from core.dataset import validate_entry
from core.format_conversion import FORMAT_SHAREGPT
from services.dataset_service import duplicate_entry_service
from ui.browser_helpers import format_entry_summary_label
from ui.entry_edit_helpers import (
    has_entry_notification_issue,
    requires_full_edit_for_quick_edit,
)
from ui.flash_messages import enqueue_dataset_result_flash
from ui.message_scaffolding import scaffold_editable_messages
from ui.session_state import (
    apply_dataset_operation_result,
    cancel_quick_edit,
    ensure_entry_indexes,
    get_loaded_entry_index_by_uuid,
    save_quick_edit,
    start_quick_edit,
    toggle_entry_selection,
)
from ui.navigation import PAGE_EDIT_ENTRIES, navigate_to_page
from ui.ui_components import render_message_preview
from ui.ui_edit_entries import start_full_edit


def render_entry_list(
    *,
    visible_pairs: list[tuple[str, dict]],
    start: int,
    tag_snapshot: Any,
    tag_label_map: dict[str, str],
    character_display_cache: dict[str, dict[int, str]],
    last_page: int,
    current_page: int,
) -> None:
    """Render visible entries and pagination controls."""

    for entry_uuid, _entry in visible_pairs:
        st.session_state[f"select_{entry_uuid}"] = (
            entry_uuid in st.session_state.selected_entry_uuids
        )

    def _on_checkbox_change(entry_uuid: str) -> None:
        st.session_state["manage_select_all_mode"] = False
        toggle_entry_selection(
            entry_uuid, st.session_state[f"select_{entry_uuid}"]
        )

    for display_index, (entry_uuid, entry) in enumerate(visible_pairs, start=start):
        errs = validate_entry(entry)
        has_notification_issue = has_entry_notification_issue(entry, errs)
        label = format_entry_summary_label(
            display_index=display_index,
            entry=entry,
            errors=errs,
            has_issues=has_notification_issue,
            tag_label_map=tag_label_map,
        )
        col_cb, col_entry = st.columns([1, 20])
        is_quick_edit = st.session_state.get("quick_edit_entry_uuid") == entry_uuid
        with col_cb:
            st.checkbox(
                "Select",
                key=f"select_{entry_uuid}",
                on_change=_on_checkbox_change,
                args=(entry_uuid,),
                label_visibility="collapsed",
            )
        with col_entry:
            with st.expander(label, expanded=is_quick_edit):
                st.caption(f"Entry UUID: {entry_uuid}")

                if is_quick_edit:
                    _render_quick_edit(entry_uuid, entry)
                else:
                    _render_entry_preview(
                        entry_uuid=entry_uuid,
                        entry=entry,
                        errors=errs,
                        tag_snapshot=tag_snapshot,
                        character_display_cache=character_display_cache,
                    )

    col_prev, col_next, _pagination_spacer = st.columns([1, 1, 2])
    with col_prev:
        if st.button("Previous", disabled=(current_page == 0), width="stretch"):
            st.session_state.entry_page = current_page - 1
            st.rerun()
    with col_next:
        if st.button("Next", disabled=(current_page >= last_page), width="stretch"):
            st.session_state.entry_page = current_page + 1
            st.rerun()


def _render_quick_edit(entry_uuid: str, entry: dict) -> None:
    st.markdown("**Quick Edit Messages**")
    messages = entry.get("messages", [])
    if not isinstance(messages, list):
        messages = []
    messages = scaffold_editable_messages(messages)
    exchange_num = 0
    for message_index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role == "user":
            exchange_num += 1
        if role in ("user", "assistant"):
            st.text_area(
                f"{role.upper()} message {exchange_num}",
                key=f"quick_edit_{entry_uuid}_{message_index}",
                height=120,
            )
    col_save_qe, col_cancel_qe = st.columns(2)
    with col_save_qe:
        if st.button(
            "Save Quick Edit",
            key=f"btn_save_qe_{entry_uuid}",
            type="primary",
            width="stretch",
        ):
            quick_result = save_quick_edit(entry_uuid, entry)
            if quick_result.ok:
                cancel_quick_edit()
                backup_note = " Backup created." if quick_result.backup_path else ""
                enqueue_dataset_result_flash(
                    f"{quick_result.message}{backup_note}",
                    quick_result,
                )
                st.rerun()
            else:
                for err in quick_result.errors:
                    st.error(err)
                if not quick_result.errors:
                    st.error(quick_result.message)
    with col_cancel_qe:
        if st.button(
            "Cancel",
            key=f"btn_cancel_qe_{entry_uuid}",
            width="stretch",
        ):
            cancel_quick_edit()
            st.rerun()


def _render_entry_preview(
    *,
    entry_uuid: str,
    entry: dict,
    errors: list[str],
    tag_snapshot: Any,
    character_display_cache: dict[str, dict[int, str]],
) -> None:
    if requires_full_edit_for_quick_edit(entry):
        action_cols = st.columns([0.8, 0.8, 5])
        with action_cols[0]:
            if st.button(
                "Requires Full Edit",
                key=f"btn_requires_full_edit_{entry_uuid}",
            ):
                navigate_to_page(
                    PAGE_EDIT_ENTRIES,
                    clear_edit_state=False,
                    rerun=False,
                )
                start_full_edit(entry_uuid, tag_snapshot.active_registry)
        with action_cols[1]:
            _render_duplicate_button(entry_uuid)
    else:
        action_cols = st.columns([0.8, 0.8, 5])
        with action_cols[0]:
            st.button(
                "Quick Edit",
                key=f"btn_quick_edit_{entry_uuid}",
                on_click=start_quick_edit,
                args=(entry_uuid, entry),
            )
        with action_cols[1]:
            _render_duplicate_button(entry_uuid)
    if errors:
        for err in errors:
            st.error(err)
    include_system = True
    if st.session_state.get("dataset_source_format") == FORMAT_SHAREGPT:
        include_system = False
    render_message_preview(
        entry.get("messages", []),
        include_system=include_system,
        display_names=get_turn_display_names(
            entry,
            st.session_state.get("preview_user_name", "Scott"),
            st.session_state.get("preview_assistant_name", "Nicole"),
            character_display_cache,
        ),
    )


def _render_duplicate_button(entry_uuid: str) -> None:
    if not st.button("Duplicate", key=f"btn_duplicate_{entry_uuid}"):
        return
    entry_index = get_loaded_entry_index_by_uuid(entry_uuid)
    if entry_index is None:
        st.error("Could not find the selected entry.")
        return
    result = duplicate_entry_service(
        dataset_path=st.session_state.get("loaded_path", ""),
        entries=st.session_state.get("loaded_entries", []),
        entry_index=entry_index,
        backup_enabled=auto_backups_enabled(st.session_state.get("prefs", {})),
    )
    if not result.ok:
        for err in result.errors:
            st.error(err)
        if not result.errors:
            st.error(result.message)
        return
    if result.entries is not None:
        apply_dataset_operation_result(result)
        st.session_state.loaded_entries = result.entries
        ensure_entry_indexes()
    backup_note = " Backup created." if result.backup_path else ""
    enqueue_dataset_result_flash(f"{result.message}{backup_note}", result)
    st.rerun()
