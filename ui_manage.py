"""Manage Dataset page — load, browse, select, edit, and delete entries."""
from pathlib import Path
from tkinter import filedialog

import streamlit as st

from dataset import (
    count_exchanges,
    filter_entry_pairs_by_tags,
    get_all_tags,
    get_available_filter_tags,
    get_entry_tags,
    get_tag_label_map,
    load_dataset,
    replace_entry_tags,
    save_dataset,
    set_entry_system_prompt,
    validate_entry,
)
from file_dialogs import JSONL_TYPES, _tk_root, browse_open_file, path_input
from preferences import get_initial_dir
from state import (
    _update_prefs,
    cancel_quick_edit,
    clear_selected_entries,
    delete_selected_entries,
    deselect_visible_entries,
    ensure_entry_registry,
    ensure_selection_state,
    get_all_entry_pairs,
    get_loaded_entry_by_id,
    get_selected_entry_ids,
    prune_selection_to_loaded_entries,
    save_loaded_dataset,
    save_quick_edit,
    select_visible_entries,
    set_loaded_entries,
    start_quick_edit,
    toggle_entry_selection,
)
from ui_components import render_message_preview

_UNTAGGED = "__untagged__"


def render_manage_page() -> None:
    """Render the Manage Dataset page."""
    ensure_entry_registry()
    ensure_selection_state()
    if st.session_state.stale_last_path and not st.session_state.loaded_path:
        st.warning(
            f"Last dataset `{st.session_state.stale_last_path}` no longer exists. "
            "Please load or create a dataset."
        )

    st.subheader("Load Dataset")

    load_path = path_input(
        "File path",
        state_key="manage_load_path",
        browse_fn=browse_open_file,
        browse_kwargs={"pref_path_key": "last_loaded_dataset_path"},
        default=st.session_state.prefs.get("last_loaded_dataset_path")
        or st.session_state.loaded_path
        or "dataset.jsonl",
    )

    col_load, col_new = st.columns(2)

    with col_load:
        if st.button("Load", width="stretch", disabled=not load_path.strip()):
            p = load_path.strip()
            entries, errors = load_dataset(p)
            if errors:
                for e in errors:
                    st.error(e)
            set_loaded_entries(entries)
            st.session_state.loaded_path = p
            st.session_state.stale_last_path = ""
            st.session_state.entry_page = 0
            clear_selected_entries()
            _update_prefs({
                "last_loaded_dataset_path": p,
                "last_open_directory": str(Path(p).parent),
            })
            st.success(f"Loaded {len(entries)} entries from `{p}`.")

    with col_new:
        if st.button("New Dataset", width="stretch"):
            prefs = st.session_state.prefs
            root = _tk_root()
            new_path = filedialog.asksaveasfilename(
                title="Create new dataset",
                defaultextension=".jsonl",
                initialfile="dataset.jsonl",
                initialdir=get_initial_dir(prefs, dir_key="last_open_directory"),
                filetypes=JSONL_TYPES,
            )
            root.destroy()

            if new_path:
                # Flush any in-memory entries to the current dataset first
                if st.session_state.loaded_entries and st.session_state.loaded_path:
                    try:
                        save_dataset(
                            st.session_state.loaded_path, st.session_state.loaded_entries
                        )
                    except Exception as exc:
                        st.error(f"Could not save current dataset before switching: {exc}")
                        new_path = ""  # cancel

            if new_path:
                try:
                    save_dataset(new_path, [])  # create empty file
                    set_loaded_entries([])
                    st.session_state.loaded_path = new_path
                    st.session_state.stale_last_path = ""
                    st.session_state.entry_page = 0
                    clear_selected_entries()
                    st.session_state["manage_load_path_pending"] = new_path
                    st.session_state["clear_entry_fields"] = True
                    _update_prefs({
                        "last_loaded_dataset_path": new_path,
                        "last_open_directory": str(Path(new_path).parent),
                    })
                    st.success(f"New dataset created at `{Path(new_path).resolve()}`.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to create dataset: {exc}")

    entries = st.session_state.loaded_entries
    all_pairs = get_all_entry_pairs()
    if all_pairs:
        st.divider()
        st.subheader(f"Entries ({len(all_pairs)})")

        invalid_count = sum(1 for e in entries if validate_entry(e))
        if invalid_count:
            st.warning(f"{invalid_count} entry/entries have validation issues.")
        else:
            st.success("All entries are valid.")

        # ── Filter controls ────────────────────────────────────────────────────
        _label_map = get_tag_label_map(untagged_key=_UNTAGGED)

        def _reset_page() -> None:
            st.session_state.entry_page = 0

        def _reset_page_and_selection() -> None:
            st.session_state.entry_page = 0
            st.session_state.filter_tags = []

        only_used = st.checkbox(
            "Only show used tags",
            value=st.session_state.get("filter_only_used", True),
            key="filter_only_used",
            on_change=_reset_page_and_selection,
        )

        _available = get_available_filter_tags(
            entries, only_used=only_used, untagged_key=_UNTAGGED
        )

        # Apply pending correction BEFORE the widget instantiates (Streamlit
        # forbids writing a widget's key after it has rendered in the same run).
        if "filter_tags_pending" in st.session_state:
            st.session_state["filter_tags"] = st.session_state.pop("filter_tags_pending")

        # Drop any stale selections no longer in the available option list
        _clamped = [t for t in st.session_state.get("filter_tags", []) if t in _available]
        if _clamped != st.session_state.get("filter_tags", []):
            st.session_state["filter_tags"] = _clamped

        filter_col, mode_col = st.columns([3, 1])
        with filter_col:
            filter_tags = st.multiselect(
                "Filter entries by tag",
                options=_available,
                format_func=lambda x: _label_map.get(x, x),
                key="filter_tags",
                on_change=_reset_page,
            )

        # If every available real tag is selected alongside __untagged__, the
        # user almost certainly hit "Select all". Write the correction to a
        # pending key and rerun so it is applied before the widget renders.
        _available_real = [t for t in _available if t != _UNTAGGED]
        _selected_real = [t for t in filter_tags if t != _UNTAGGED]
        if (
            _UNTAGGED in filter_tags
            and _available_real
            and set(_selected_real) == set(_available_real)
        ):
            st.session_state["filter_tags_pending"] = _selected_real
            st.rerun()
        with mode_col:
            match_mode = st.radio(
                "Match mode",
                options=["Any selected tags", "All selected tags", "Exact match"],
                key="filter_match_mode",
                on_change=_reset_page,
            )

        # ── Apply filter ───────────────────────────────────────────────────────
        filtered_pairs = filter_entry_pairs_by_tags(
            all_pairs,
            selected_tags=filter_tags,
            match_mode=match_mode,
        )

        # ── Pagination ─────────────────────────────────────────────────────────
        per_page_options = [10, 25, 50, 100, 500, "Show All"]
        _saved_per_page = st.session_state.get("entries_per_page", 25)
        default_idx = (
            per_page_options.index(_saved_per_page)
            if _saved_per_page in per_page_options
            else 1  # fallback to 25
        )
        _col_per_page, _col_per_page_spacer = st.columns([1, 3])
        with _col_per_page:
            selected_per_page = st.selectbox(
                "Entries per page",
                options=per_page_options,
                index=default_idx,
                key="_entries_per_page_select",
            )
        if selected_per_page != st.session_state.get("entries_per_page"):
            st.session_state.entries_per_page = selected_per_page
            st.session_state.entry_page = 0
            st.rerun()

        total_filtered = len(filtered_pairs)
        total_all = len(all_pairs)

        if total_filtered == 0:
            st.info("No entries match the current filters.")
        else:
            _per_page_setting = st.session_state.entries_per_page
            if _per_page_setting == "Show All":
                per_page = total_filtered
                last_page = 0
                _cur_page = 0
                start = 0
                end = total_filtered
            else:
                per_page = _per_page_setting
                last_page = max(0, (total_filtered - 1) // per_page)
                # _cur_page used here to avoid shadowing the navigation `page` variable
                _cur_page = min(st.session_state.get("entry_page", 0), last_page)
                start = _cur_page * per_page
                end = min(start + per_page, total_filtered)
            visible_pairs = filtered_pairs[start:end]

            # ── Flash messages ─────────────────────────────────────────────────
            if "quick_edit_success" in st.session_state:
                st.success(st.session_state.pop("quick_edit_success"))

            # ── Status line (always visible) ───────────────────────────────────
            _selected_ids = get_selected_entry_ids()
            _total_sel = len(_selected_ids)
            if filter_tags:
                st.caption(
                    f"Showing {start + 1}–{end} of {total_filtered} filtered entries "
                    f"({total_all} total) | {_total_sel} of {total_filtered} selected"
                )
            else:
                st.caption(
                    f"Showing {start + 1}–{end} of {total_all} entries "
                    f"| {_total_sel} of {total_all} selected"
                )

            # ── Selection + action buttons (single row) ────────────────────────
            _no_sel = _total_sel == 0
            (
                _col_sel_all, _col_clear,
                _col_sys_prompt, _col_delete, _col_act_spacer,
            ) = st.columns([1, 1, 1, 1, 2])
            with _col_sel_all:
                if st.button("Select all visible", key="btn_select_all_visible",
                             width="stretch"):
                    select_visible_entries(visible_pairs)
                    st.rerun()
            with _col_clear:
                if st.button("Clear Selection", key="btn_clear_visible",
                             width="stretch"):
                    deselect_visible_entries(visible_pairs)
                    st.rerun()
            with _col_sys_prompt:
                if st.button("Modify System", key="btn_modify_sys_prompt",
                             disabled=_no_sel, width="stretch"):
                    st.session_state["pending_system_prompt_edit"] = True
                    st.session_state.pop("bulk_system_prompt_text", None)
                    st.rerun()
            with _col_delete:
                if st.button("Delete Selected", key="btn_delete_selected",
                             disabled=_no_sel, width="stretch"):
                    if st.session_state.get("confirm_delete_entries", True):
                        st.session_state["pending_delete_selected"] = True
                        st.rerun()
                    else:
                        _n, _failures = delete_selected_entries()
                        prune_selection_to_loaded_entries()
                        _new_total = len(st.session_state.loaded_entries)
                        if _new_total == 0 or st.session_state.entry_page > max(
                            0, (_new_total - 1) // per_page
                        ):
                            st.session_state.entry_page = 0
                        if _failures:
                            st.warning(
                                f"Deleted {_n} entries. "
                                f"{len(_failures)} could not be removed."
                            )
                        else:
                            st.success(f"Deleted {_n} entries.")
                        st.rerun()

            # ── Confirmation UI (shown below button row when pending) ───────────
            if st.session_state.get("pending_delete_selected"):
                _pending_sel_ids = get_selected_entry_ids()
                st.warning(
                    f"Delete {len(_pending_sel_ids)} selected entrie(s)? "
                    "This cannot be undone."
                )
                _col_confirm, _col_cancel, _col_del_spacer = st.columns([1, 1, 2])
                with _col_confirm:
                    if st.button("Confirm Delete", type="primary",
                                 key="btn_confirm_delete", width="stretch"):
                        _n, _failures = delete_selected_entries()
                        st.session_state.pop("pending_delete_selected", None)
                        prune_selection_to_loaded_entries()
                        _new_total = len(st.session_state.loaded_entries)
                        if _new_total == 0 or st.session_state.entry_page > max(
                            0, (_new_total - 1) // per_page
                        ):
                            st.session_state.entry_page = 0
                        if _failures:
                            st.warning(
                                f"Deleted {_n} entries. "
                                f"{len(_failures)} could not be removed."
                            )
                        else:
                            st.success(f"Deleted {_n} entries.")
                        st.rerun()
                with _col_cancel:
                    if st.button("Cancel", key="btn_cancel_delete", width="stretch"):
                        st.session_state.pop("pending_delete_selected", None)
                        st.rerun()

            # ── System prompt editor (shown when pending) ──────────────────────
            if "sys_prompt_success" in st.session_state:
                st.success(st.session_state.pop("sys_prompt_success"))

            if st.session_state.get("pending_system_prompt_edit"):
                st.info(
                    f"Replace the system prompt for {_total_sel} selected "
                    "entrie(s). This will overwrite existing system prompts "
                    "or insert one if missing."
                )
                _new_prompt = st.text_area(
                    "New system prompt",
                    key="bulk_system_prompt_text",
                    height=120,
                )
                _col_apply, _col_sp_cancel, _col_sp_spacer = st.columns([1, 1, 2])
                with _col_apply:
                    if st.button(
                        "Apply System Prompt",
                        key="btn_apply_sys_prompt",
                        disabled=not (_new_prompt or "").strip(),
                        width="stretch",
                    ):
                        for _sid in _selected_ids:
                            _se = get_loaded_entry_by_id(_sid)
                            if _se is not None:
                                set_entry_system_prompt(_se, _new_prompt.strip())
                        if save_loaded_dataset():
                            st.session_state.pop("pending_system_prompt_edit", None)
                            st.session_state["sys_prompt_success"] = (
                                f"System prompt updated for {_total_sel} entries."
                            )
                            st.rerun()
                with _col_sp_cancel:
                    if st.button("Cancel", key="btn_sp_cancel", width="stretch"):
                        st.session_state.pop("pending_system_prompt_edit", None)
                        st.rerun()

            # ── Quick tag editor ───────────────────────────────────────────────
            _selected_count = len(_selected_ids)
            if _selected_count >= 1:
                _tag_label_map = get_tag_label_map(include_untagged=False)

            if _selected_count == 1:
                st.markdown("**Quick Tag Edit**")
                _qt_entry_id = _selected_ids[0]
                _qt_entry = get_loaded_entry_by_id(_qt_entry_id)
                if _qt_entry is not None:
                    _qt_current_tags = get_entry_tags(_qt_entry)
                    _qt_chosen = st.multiselect(
                        "Tags for selected entry",
                        options=get_all_tags(),
                        default=_qt_current_tags,
                        format_func=lambda t: _tag_label_map.get(t, t),
                        key=f"single_quick_tags_{_qt_entry_id}",
                    )
                    if st.button("Save Tags", key="btn_save_single_tags"):
                        replace_entry_tags(_qt_entry, _qt_chosen)
                        if save_loaded_dataset():
                            st.success("Tags updated for selected entry.")
                            st.rerun()

            elif _selected_count >= 2:
                st.markdown("**Bulk Tag Edit**")
                _bulk_chosen = st.multiselect(
                    "Replacement tags",
                    options=get_all_tags(),
                    format_func=lambda t: _tag_label_map.get(t, t),
                    key="bulk_replace_tags",
                )
                _col_bulk_replace, _col_bulk_clear = st.columns(2)
                with _col_bulk_replace:
                    if st.button(
                        f"Replace tags on {_selected_count} selected",
                        key="btn_bulk_replace_tags",
                        width="stretch",
                    ):
                        for _bid in _selected_ids:
                            _be = get_loaded_entry_by_id(_bid)
                            if _be is not None:
                                replace_entry_tags(_be, _bulk_chosen)
                        if save_loaded_dataset():
                            st.success(f"Tags replaced for {_selected_count} entries.")
                            st.rerun()
                with _col_bulk_clear:
                    if st.button(
                        f"Clear tags on {_selected_count} selected",
                        key="btn_bulk_clear_tags",
                        width="stretch",
                    ):
                        for _bid in _selected_ids:
                            _be = get_loaded_entry_by_id(_bid)
                            if _be is not None:
                                replace_entry_tags(_be, [])
                        if save_loaded_dataset():
                            st.success(f"Tags cleared for {_selected_count} entries.")
                            st.rerun()

            # ── Entry list ─────────────────────────────────────────────────────
            # Sync all visible checkbox widget keys from selected_entry_ids
            # BEFORE any checkbox widget renders so visual state is always correct.
            # Only visible_pairs (current page) are synced — other pages are unaffected.
            for _sync_id, _ in visible_pairs:
                st.session_state[f"select_{_sync_id}"] = (
                    _sync_id in st.session_state.selected_entry_ids
                )

            def _on_checkbox_change(entry_id: str) -> None:
                toggle_entry_selection(
                    entry_id, st.session_state[f"select_{entry_id}"]
                )

            for i, (entry_id, entry) in enumerate(visible_pairs, start=start):
                errs = validate_entry(entry)
                entry_tags = get_entry_tags(entry)
                _tag_part = ", ".join(entry_tags) if entry_tags else "untagged"
                _fmt_part = st.session_state.dataset_format
                _exc_part = count_exchanges(entry)
                label = (
                    f"Entry {i + 1} | FORMAT: {_fmt_part} | "
                    f"TAGS: {_tag_part} | EXCHANGES: {_exc_part}"
                )
                if errs:
                    label += " ⚠️"
                _col_cb, _col_entry = st.columns([1, 20])
                with _col_cb:
                    st.checkbox(
                        "Select",
                        key=f"select_{entry_id}",
                        on_change=_on_checkbox_change,
                        args=(entry_id,),
                        label_visibility="collapsed",
                    )
                with _col_entry:
                    with st.expander(label):
                        st.caption(f"Temp ID: {entry_id}")
                        _is_qe = (
                            st.session_state.get("quick_edit_entry_id") == entry_id
                        )

                        if _is_qe:
                            # ── Quick edit mode ────────────────────────────────
                            st.markdown("**Quick Edit Messages**")
                            _qe_msgs = entry.get("messages", [])
                            _exchange_num = 0
                            for _qe_idx, _qe_msg in enumerate(_qe_msgs):
                                if not isinstance(_qe_msg, dict):
                                    continue
                                _qe_role = _qe_msg.get("role")
                                if _qe_role == "user":
                                    _exchange_num += 1
                                if _qe_role in ("user", "assistant"):
                                    st.text_area(
                                        f"{_qe_role.upper()} message {_exchange_num}",
                                        key=f"quick_edit_{entry_id}_{_qe_idx}",
                                        height=120,
                                    )
                            _col_save_qe, _col_cancel_qe = st.columns(2)
                            with _col_save_qe:
                                if st.button(
                                    "Save Quick Edit",
                                    key=f"btn_save_qe_{entry_id}",
                                    type="primary",
                                    width="stretch",
                                ):
                                    if save_quick_edit(entry_id, entry):
                                        cancel_quick_edit()
                                        st.session_state["quick_edit_success"] = (
                                            "Entry updated."
                                        )
                                        st.rerun()
                            with _col_cancel_qe:
                                if st.button(
                                    "Cancel",
                                    key=f"btn_cancel_qe_{entry_id}",
                                    width="stretch",
                                ):
                                    cancel_quick_edit()
                                    st.rerun()

                        else:
                            # ── Normal preview mode ────────────────────────────
                            if st.button(
                                "Quick Edit",
                                key=f"btn_quick_edit_{entry_id}",
                            ):
                                start_quick_edit(entry_id, entry)
                                st.rerun()
                            if errs:
                                for err in errs:
                                    st.error(err)
                            render_message_preview(
                                entry.get("messages", []), include_system=True
                            )

            # ── Pagination buttons ─────────────────────────────────────────────
            col_prev, col_next = st.columns(2)
            with col_prev:
                if st.button("Previous", disabled=(_cur_page == 0), width="stretch"):
                    st.session_state.entry_page = _cur_page - 1
                    st.rerun()
            with col_next:
                if st.button("Next", disabled=(_cur_page >= last_page), width="stretch"):
                    st.session_state.entry_page = _cur_page + 1
                    st.rerun()
