"""Selection, bulk action, and quick tag edit controls for Manage Dataset."""
from typing import Any

import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import get_entry_tags
from core.tag_registry import prettify_tag_name
from core.text_helpers import count_phrase
from services.dataset_service import (
    clear_tags_bulk_service,
    replace_single_entry_tags_service,
    replace_system_prompt_bulk_service,
    replace_tags_bulk_service,
)
from ui.browser_helpers import format_browser_status_caption
from ui.flash_messages import enqueue_dataset_result_flash, enqueue_flash
from ui.session_state import (
    apply_dataset_operation_result,
    clear_selected_entries,
    delete_selected_entries,
    ensure_entry_registry,
    get_loaded_entry_by_id,
    get_loaded_entry_index_by_id,
    get_selected_entry_ids,
    prune_selection_to_loaded_entries,
    select_visible_entries,
)


def render_actions(
    *,
    visible_pairs: list[tuple[str, dict]],
    filter_tags: list[str],
    match_mode: str,
    per_page: int,
    current_page: int,
    start: int,
    end: int,
    total_filtered: int,
    total_all: int,
    tag_snapshot: Any,
) -> None:
    """Render selection actions and tag-edit controls."""

    view_fingerprint = (
        tuple(sorted(filter_tags)),
        match_mode,
        st.session_state.entries_per_page,
        current_page,
    )
    if st.session_state.get("manage_select_all_mode", False):
        if st.session_state.get("_select_all_fingerprint") != view_fingerprint:
            st.session_state["manage_select_all_mode"] = False
            clear_selected_entries()

    selected_ids = get_selected_entry_ids()
    total_selected = len(selected_ids)
    st.caption(
        format_browser_status_caption(
            start=start,
            end=end,
            total_filtered=total_filtered,
            total_all=total_all,
            filtered=bool(filter_tags),
            selected_count=total_selected,
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

    if st.session_state.get("pending_delete_selected"):
        pending_sel_ids = get_selected_entry_ids()
        selected_entry_phrase = count_phrase(
            len(pending_sel_ids),
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

    if st.session_state.get("pending_system_prompt_edit"):
        _render_system_prompt_editor(total_selected, selected_ids)

    _render_tag_editor(selected_ids, tag_snapshot)


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
    selected_ids: list[str],
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
                    get_loaded_entry_index_by_id(selected_id)
                    for selected_id in selected_ids
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
                ensure_entry_registry()
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


def _render_tag_editor(selected_ids: list[str], tag_snapshot: Any) -> None:
    selected_count = len(selected_ids)
    if selected_count < 1:
        return

    tag_label_map = tag_snapshot.tag_label_map
    all_slugs = tag_snapshot.active_tag_slugs
    all_slugs_set = set(all_slugs)

    if selected_count == 1:
        st.markdown("**Quick Tag Edit**")
        entry_id = selected_ids[0]
        entry = get_loaded_entry_by_id(entry_id)
        if entry is None:
            return
        current_tags = get_entry_tags(entry)
        unknown = [tag for tag in current_tags if tag not in all_slugs_set]
        options = all_slugs + unknown
        chosen = st.multiselect(
            "Tags for selected entry",
            options=options,
            default=current_tags,
            format_func=lambda tag: tag_label_map.get(tag, prettify_tag_name(tag)),
            key=f"single_quick_tags_{entry_id}",
        )
        if st.button("Save Tags", key="btn_save_single_tags"):
            idx = get_loaded_entry_index_by_id(entry_id)
            if idx is not None:
                tag_result = replace_single_entry_tags_service(
                    dataset_path=st.session_state.get("loaded_path", ""),
                    entries=st.session_state.loaded_entries,
                    entry_index=idx,
                    tags=chosen,
                    backup_enabled=auto_backups_enabled(
                        st.session_state.get("prefs", {})
                    ),
                )
                if tag_result.ok and tag_result.entries is not None:
                    apply_dataset_operation_result(tag_result)
                    st.session_state.loaded_entries = tag_result.entries
                    ensure_entry_registry()
                    backup_note = " Backup created." if tag_result.backup_path else ""
                    enqueue_dataset_result_flash(
                        f"{tag_result.message}{backup_note}",
                        tag_result,
                    )
                    st.rerun()
                else:
                    for err in tag_result.errors:
                        st.error(err)
                    if not tag_result.errors:
                        st.error(tag_result.message)
            else:
                st.error("Could not find the selected entry.")

    elif selected_count >= 2:
        _render_bulk_tag_editor(
            selected_ids=selected_ids,
            selected_count=selected_count,
            all_slugs=all_slugs,
            tag_label_map=tag_label_map,
        )


def _render_bulk_tag_editor(
    *,
    selected_ids: list[str],
    selected_count: int,
    all_slugs: list[str],
    tag_label_map: dict[str, str],
) -> None:
    st.markdown("**Bulk Tag Edit**")
    bulk_chosen = st.multiselect(
        "Replacement tags",
        options=all_slugs,
        format_func=lambda tag: tag_label_map.get(tag, prettify_tag_name(tag)),
        key="bulk_replace_tags",
    )
    col_bulk_replace, col_bulk_clear = st.columns(2)
    with col_bulk_replace:
        if st.button(
            f"Replace tags on {selected_count} selected",
            key="btn_bulk_replace_tags",
            disabled=not bulk_chosen,
            width="stretch",
        ):
            indices = _selected_indices(selected_ids)
            bulk_result = replace_tags_bulk_service(
                dataset_path=st.session_state.get("loaded_path", ""),
                entries=st.session_state.loaded_entries,
                entry_indices=indices,
                tags=bulk_chosen,
                backup_enabled=auto_backups_enabled(
                    st.session_state.get("prefs", {})
                ),
            )
            _handle_bulk_tag_result(bulk_result)
    with col_bulk_clear:
        if st.button(
            f"Clear tags on {selected_count} selected",
            key="btn_bulk_clear_tags",
            width="stretch",
        ):
            indices = _selected_indices(selected_ids)
            bulk_result = clear_tags_bulk_service(
                dataset_path=st.session_state.get("loaded_path", ""),
                entries=st.session_state.loaded_entries,
                entry_indices=indices,
                backup_enabled=auto_backups_enabled(
                    st.session_state.get("prefs", {})
                ),
            )
            _handle_bulk_tag_result(bulk_result)


def _selected_indices(selected_ids: list[str]) -> list[int]:
    return [
        idx for idx in (
            get_loaded_entry_index_by_id(selected_id)
            for selected_id in selected_ids
        )
        if idx is not None
    ]


def _handle_bulk_tag_result(bulk_result) -> None:
    if bulk_result.ok and bulk_result.entries is not None:
        apply_dataset_operation_result(bulk_result)
        st.session_state.loaded_entries = bulk_result.entries
        ensure_entry_registry()
        backup_note = " Backup created." if bulk_result.backup_path else ""
        enqueue_dataset_result_flash(
            f"{bulk_result.message}{backup_note}",
            bulk_result,
        )
        st.rerun()
    else:
        for err in bulk_result.errors:
            st.error(err)
        if not bulk_result.errors:
            st.error(bulk_result.message)
