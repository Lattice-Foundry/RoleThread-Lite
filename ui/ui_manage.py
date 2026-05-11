"""Streamlit page for managing the loaded dataset.

This module owns selection, filters, pagination, and widgets. Durable
dataset mutations delegate to services.
"""
from pathlib import Path
from tkinter import filedialog

import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import (
    clear_validate_entry_cache,
    filter_entry_pairs_by_tags,
    get_entry_tags,
    load_dataset_with_summary,
    save_dataset,
    validate_entry,
)
from core.format_conversion import FORMAT_CHATML, FORMAT_SHAREGPT, FORMAT_UNKNOWN
from core.tag_registry import (
    get_tag_registry_snapshot,
    prettify_tag_name,
)
from ui.file_dialogs import JSONL_TYPES, _tk_root, browse_open_file, path_input
from core.preferences import get_initial_dir
from ui.session_state import (
    cancel_quick_edit,
    clear_selected_entries,
    delete_selected_entries,
    ensure_entry_registry,
    ensure_selection_state,
    get_all_entry_pairs,
    get_loaded_entry_index_by_id,
    get_loaded_entry_by_id,
    get_selected_entry_ids,
    persist_loaded_normalization,
    prune_selection_to_loaded_entries,
    save_quick_edit,
    select_visible_entries,
    set_loaded_entries,
    should_auto_normalize_loaded_dataset,
    start_quick_edit,
    toggle_entry_selection,
    update_prefs,
)
from services.dataset_service import (
    clear_tags_bulk_service,
    replace_single_entry_tags_service,
    replace_system_prompt_bulk_service,
    replace_tags_bulk_service,
)
from ui.browser_helpers import (
    DEFAULT_PAGE_SIZE,
    MATCH_MODE_OPTIONS,
    PAGE_SIZE_OPTIONS,
    build_filter_tag_state,
    calculate_pagination,
    format_browser_status_caption,
    format_entry_summary_label,
    normalize_untagged_selection,
    slice_visible_pairs,
)
from ui.ui_components import render_message_preview

_UNTAGGED = "__untagged__"


def _format_source_format(source_format: str) -> str:
    labels = {
        FORMAT_CHATML: "ChatML",
        FORMAT_SHAREGPT: "ShareGPT",
        FORMAT_UNKNOWN: "Unknown",
    }
    return labels.get(source_format, source_format or "Unknown")


def _render_load_format_summary(normalization) -> None:
    source_format = normalization.source_format
    if source_format == FORMAT_SHAREGPT:
        st.info(
            "Detected format: ShareGPT. "
            f"Converted {normalization.format_converted_count} entries to ChatML."
        )
    else:
        st.info(f"Detected format: {_format_source_format(source_format)}.")

    if normalization.parse_error_count:
        st.warning(
            f"Loaded {normalization.parsed_entry_count} entr(y/ies) from "
            f"{normalization.source_line_count} non-empty line(s). "
            f"{normalization.parse_error_count} line(s) had parse errors."
        )

    warnings = list(normalization.format_warnings or [])
    for warning in warnings[:3]:
        st.caption(f"Conversion warning: {warning}")
    if len(warnings) > 3:
        st.caption(f"{len(warnings) - 3} additional conversion warning(s) hidden.")

    diagnostics = normalization.diagnostics
    if (
        diagnostics.entries_with_errors
        or diagnostics.entries_with_warnings
        or diagnostics.auto_repairable_count
    ):
        issue_entries = max(0, diagnostics.entries_analyzed - diagnostics.valid_entries)
        st.info(
            "Dataset diagnostics: "
            f"{diagnostics.entries_analyzed} entr(y/ies) loaded "
            f"({diagnostics.valid_entries} valid, {issue_entries} with issues)."
        )
        if diagnostics.auto_repairable_count:
            st.caption(
                f"{diagnostics.auto_repairable_count} auto-fixable issue(s) detected."
            )

    sidecar_summary = st.session_state.get("sidecar_import_summary")
    if sidecar_summary:
        if sidecar_summary.get("ok"):
            category_count = len(sidecar_summary.get("categories_created", []) or [])
            created_count = len(sidecar_summary.get("tags_created", []) or [])
            promoted_count = len(sidecar_summary.get("tags_promoted", []) or [])
            st.info(
                "Registry sidecar restored: "
                f"{category_count} categor(y/ies), "
                f"{created_count} tag(s), "
                f"{promoted_count} promoted tag(s)."
            )
        else:
            st.warning(
                "Registry sidecar could not be restored. "
                "Dataset loading continued normally."
            )
            for error in (sidecar_summary.get("errors") or [])[:3]:
                st.caption(f"Sidecar warning: {error}")

        conflicts = sidecar_summary.get("conflicts") or []
        if conflicts:
            st.warning(
                f"{len(conflicts)} tag conflict(s) detected - resolve on Validation page."
            )

    pending_trust = st.session_state.get("pending_tag_trust") or {}
    if pending_trust:
        st.warning(
            f"{len(pending_trust)} unknown tag(s) found in dataset - review on Validation page."
        )


def render_manage_page() -> None:
    """Render the Manage Dataset page."""
    clear_validate_entry_cache()
    ensure_entry_registry()
    ensure_selection_state()
    _tag_snapshot = get_tag_registry_snapshot(untagged_key=_UNTAGGED)
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
            normalization, errors = load_dataset_with_summary(p)
            entries = normalization.entries
            if errors:
                for e in errors[:3]:
                    st.error(e)
                if len(errors) > 3:
                    st.caption(f"{len(errors) - 3} additional load error(s) hidden.")
            if errors and not entries:
                st.error("No dataset was loaded.")
                return
            set_loaded_entries(
                entries,
                normalization_summary=normalization,
                dataset_path=p,
            )
            st.session_state.loaded_path = p
            st.session_state.stale_last_path = ""
            st.session_state.entry_page = 0
            st.session_state["manage_select_all_mode"] = False
            clear_selected_entries()
            _auto_normalized = False
            _auto_normalize_failed = False
            if should_auto_normalize_loaded_dataset(
                prefs=st.session_state.get("prefs", {}),
                parse_errors=errors,
                normalization_pending=st.session_state.get("normalization_pending", False),
                auto_normalize_on_load=st.session_state.get(
                    "auto_normalize_on_load",
                    st.session_state.get("prefs", {}).get("auto_normalize_on_load", True),
                ),
            ):
                _normalize_result = persist_loaded_normalization(p)
                if _normalize_result.ok:
                    _auto_normalized = True
                else:
                    _auto_normalize_failed = True
                    st.error(_normalize_result.message)
                    for _err in _normalize_result.errors:
                        st.error(_err)
            update_prefs({
                "last_loaded_dataset_path": p,
                "last_open_directory": str(Path(p).parent),
            })
            if _auto_normalized:
                st.success(f"Loaded {len(entries)} entries from `{p}`. Normalized data saved.")
            elif _auto_normalize_failed:
                st.warning(f"Loaded {len(entries)} entries from `{p}`, but normalization was not saved.")
            else:
                st.success(f"Loaded {len(entries)} entries from `{p}`.")
            _render_load_format_summary(normalization)

    with col_new:
        if st.button("New Dataset", width="stretch"):
            prefs = st.session_state.prefs
            root = _tk_root()
            new_path = filedialog.asksaveasfilename(
                title="Create new dataset",
                defaultextension=".jsonl",
                initialfile="dataset.jsonl",
                initialdir=get_initial_dir(prefs, dir_key="default_dataset_directory"),
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
                    st.session_state["manage_select_all_mode"] = False
                    clear_selected_entries()
                    st.session_state["manage_load_path_pending"] = new_path
                    st.session_state["clear_entry_fields"] = True
                    update_prefs({
                        "last_loaded_dataset_path": new_path,
                        "last_open_directory": str(Path(new_path).parent),
                    })
                    st.success(f"New dataset created at `{Path(new_path).resolve()}`.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to create dataset: {exc}")

    if st.session_state.get("normalization_pending") and st.session_state.get("loaded_path"):
        _norm_summary = st.session_state.get("tag_normalization_summary", {})
        _metadata_count = int(_norm_summary.get("tag_metadata_added_count", 0) or 0)
        st.info(
            "This dataset contains legacy/un-normalized metadata. "
            "LoreForge cleaned the dataset in memory. Normalize Data will persist "
            "the cleaned structure to disk."
        )
        if _metadata_count:
            st.caption(f"Pending cleanup: tag metadata added for {_metadata_count} entries.")
        if st.button("Normalize Data", width="stretch"):
            _normalize_result = persist_loaded_normalization(st.session_state.loaded_path)
            if _normalize_result.ok:
                _backup_note = " Backup created." if _normalize_result.backup_path else ""
                st.success(f"Dataset normalized.{_backup_note}")
                st.rerun()
            else:
                st.error(_normalize_result.message)
                for _err in _normalize_result.errors:
                    st.error(_err)

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
        # DB-backed label map: {slug: "Category / Pretty Name", __untagged__: "Untagged"}
        _label_map = _tag_snapshot.tag_label_map_with_untagged
        _all_known_slugs = _tag_snapshot.active_tag_slugs

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

        # Apply pending correction BEFORE the widget instantiates (Streamlit
        # forbids writing a widget's key after it has rendered in the same run).
        if "filter_tags_pending" in st.session_state:
            st.session_state["filter_tags"] = st.session_state.pop("filter_tags_pending")

        _filter_state = build_filter_tag_state(
            entries=entries,
            selected_tags=st.session_state.get("filter_tags", []),
            only_used_tags=only_used,
            all_known_tags=_all_known_slugs,
            untagged_key=_UNTAGGED,
        )
        _available = _filter_state.available_tags
        if _filter_state.selected_tags_changed:
            st.session_state["filter_tags"] = _filter_state.clamped_selected_tags

        filter_col, mode_col = st.columns([3, 1])
        with filter_col:
            filter_tags = st.multiselect(
                "Filter entries by tag",
                options=_available,
                # Known slugs → "Category / Pretty Name"; unknown slugs → prettified
                format_func=lambda x: _label_map.get(x, prettify_tag_name(x)),
                key="filter_tags",
                on_change=_reset_page,
            )

        # If every available real tag is selected alongside __untagged__, the
        # user almost certainly hit "Select all". Write the correction to a
        # pending key and rerun so it is applied before the widget renders.
        _normalized_filter_tags = normalize_untagged_selection(
            selected_tags=filter_tags,
            available_tags=_available,
            untagged_key=_UNTAGGED,
        )
        if _normalized_filter_tags != filter_tags:
            st.session_state["filter_tags_pending"] = _normalized_filter_tags
            st.rerun()
        with mode_col:
            match_mode = st.radio(
                "Match mode",
                options=MATCH_MODE_OPTIONS,
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
        _saved_per_page = st.session_state.get("entries_per_page", DEFAULT_PAGE_SIZE)
        default_idx = (
            PAGE_SIZE_OPTIONS.index(_saved_per_page)
            if _saved_per_page in PAGE_SIZE_OPTIONS
            else PAGE_SIZE_OPTIONS.index(DEFAULT_PAGE_SIZE)
        )
        _col_per_page, _col_per_page_spacer = st.columns([1, 3])
        with _col_per_page:
            selected_per_page = st.selectbox(
                "Entries per page",
                options=PAGE_SIZE_OPTIONS,
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
            _pagination = calculate_pagination(
                total_items=total_filtered,
                requested_page=st.session_state.get("entry_page", 0),
                per_page_setting=st.session_state.entries_per_page,
            )
            per_page = _pagination.per_page
            last_page = _pagination.last_page
            _cur_page = _pagination.page
            start = _pagination.start
            end = _pagination.end
            visible_pairs = slice_visible_pairs(filtered_pairs, _pagination)
            if _pagination.is_show_all_capped:
                st.warning(
                    f"Showing first 1,000 of {_pagination.total_items} entries. "
                    "Use pagination or filters to narrow results."
                )

            # ── Select-all-mode fingerprint guard ─────────────────────────────
            # Captures (filter, match-mode, per-page, page) when "Select all
            # visible" is clicked.  If any of those change on a later render the
            # selection is stale, so clear it immediately before anything renders.
            _view_fingerprint = (
                tuple(sorted(filter_tags)),
                match_mode,
                st.session_state.entries_per_page,
                _cur_page,
            )
            if st.session_state.get("manage_select_all_mode", False):
                if st.session_state.get("_select_all_fingerprint") != _view_fingerprint:
                    st.session_state["manage_select_all_mode"] = False
                    clear_selected_entries()

            # ── Flash messages ─────────────────────────────────────────────────
            if "quick_edit_success" in st.session_state:
                st.success(st.session_state.pop("quick_edit_success"))
            if "tag_save_success" in st.session_state:
                st.success(st.session_state.pop("tag_save_success"))

            # ── Status line (always visible) ───────────────────────────────────
            _selected_ids = get_selected_entry_ids()
            _total_sel = len(_selected_ids)
            st.caption(
                format_browser_status_caption(
                    start=start,
                    end=end,
                    total_filtered=total_filtered,
                    total_all=total_all,
                    filtered=bool(filter_tags),
                    selected_count=_total_sel,
                )
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
                    st.session_state["manage_select_all_mode"] = True
                    st.session_state["_select_all_fingerprint"] = _view_fingerprint
                    clear_selected_entries()
                    select_visible_entries(visible_pairs)
                    st.rerun()
            with _col_clear:
                if st.button("Clear Selection", key="btn_clear_visible",
                             width="stretch"):
                    st.session_state["manage_select_all_mode"] = False
                    clear_selected_entries()
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
                        _n, _failures, _backup_created = delete_selected_entries()
                        st.session_state["manage_select_all_mode"] = False
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
                            _backup_note = " Backup created." if _backup_created else ""
                            st.success(f"Deleted {_n} entries.{_backup_note}")
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
                        _n, _failures, _backup_created = delete_selected_entries()
                        st.session_state.pop("pending_delete_selected", None)
                        st.session_state["manage_select_all_mode"] = False
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
                            _backup_note = " Backup created." if _backup_created else ""
                            st.success(f"Deleted {_n} entries.{_backup_note}")
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
                        _indices = [
                            _idx for _idx in (
                                get_loaded_entry_index_by_id(_sid)
                                for _sid in _selected_ids
                            )
                            if _idx is not None
                        ]
                        _sys_result = replace_system_prompt_bulk_service(
                            dataset_path=st.session_state.get("loaded_path", ""),
                            entries=st.session_state.loaded_entries,
                            entry_indices=_indices,
                            system_prompt=_new_prompt.strip(),
                            backup_enabled=auto_backups_enabled(
                                st.session_state.get("prefs", {})
                            ),
                        )
                        if _sys_result.ok and _sys_result.entries is not None:
                            st.session_state.loaded_entries = _sys_result.entries
                            ensure_entry_registry()
                            _backup_note = (
                                " Backup created." if _sys_result.backup_path else ""
                            )
                            st.session_state.pop("pending_system_prompt_edit", None)
                            st.session_state["sys_prompt_success"] = (
                                f"{_sys_result.message}{_backup_note}"
                            )
                            st.rerun()
                        else:
                            for _err in _sys_result.errors:
                                st.error(_err)
                            if not _sys_result.errors:
                                st.error(_sys_result.message)
                with _col_sp_cancel:
                    if st.button("Cancel", key="btn_sp_cancel", width="stretch"):
                        st.session_state.pop("pending_system_prompt_edit", None)
                        st.rerun()

            # ── Quick tag editor ───────────────────────────────────────────────
            _selected_count = len(_selected_ids)
            if _selected_count >= 1:
                # DB-backed label map for tag selectors (no untagged sentinel)
                _tag_label_map = _tag_snapshot.tag_label_map
                _all_slugs = _tag_snapshot.active_tag_slugs
                _all_slugs_set = set(_all_slugs)

            if _selected_count == 1:
                st.markdown("**Quick Tag Edit**")
                _qt_entry_id = _selected_ids[0]
                _qt_entry = get_loaded_entry_by_id(_qt_entry_id)
                if _qt_entry is not None:
                    _qt_current_tags = get_entry_tags(_qt_entry)
                    # Include any unknown tags already on this entry in the
                    # options list so they can be kept or deselected — they
                    # won't appear in fresh selections from the registry.
                    _qt_unknown = [t for t in _qt_current_tags if t not in _all_slugs_set]
                    _qt_options = _all_slugs + _qt_unknown
                    _qt_chosen = st.multiselect(
                        "Tags for selected entry",
                        options=_qt_options,
                        default=_qt_current_tags,
                        format_func=lambda t: _tag_label_map.get(t, prettify_tag_name(t)),
                        key=f"single_quick_tags_{_qt_entry_id}",
                    )
                    if st.button("Save Tags", key="btn_save_single_tags"):
                        _idx = get_loaded_entry_index_by_id(_qt_entry_id)
                        if _idx is not None:
                            _tag_result = replace_single_entry_tags_service(
                                dataset_path=st.session_state.get("loaded_path", ""),
                                entries=st.session_state.loaded_entries,
                                entry_index=_idx,
                                tags=_qt_chosen,
                                backup_enabled=auto_backups_enabled(
                                    st.session_state.get("prefs", {})
                                ),
                            )
                            if _tag_result.ok and _tag_result.entries is not None:
                                st.session_state.loaded_entries = _tag_result.entries
                                ensure_entry_registry()
                                _backup_note = (
                                    " Backup created." if _tag_result.backup_path else ""
                                )
                                st.session_state["tag_save_success"] = (
                                    f"{_tag_result.message}{_backup_note}"
                                )
                                st.rerun()
                            else:
                                for _err in _tag_result.errors:
                                    st.error(_err)
                                if not _tag_result.errors:
                                    st.error(_tag_result.message)
                        else:
                            st.error("Could not find the selected entry.")

            elif _selected_count >= 2:
                st.markdown("**Bulk Tag Edit**")
                _bulk_chosen = st.multiselect(
                    "Replacement tags",
                    options=_all_slugs,
                    format_func=lambda t: _tag_label_map.get(t, prettify_tag_name(t)),
                    key="bulk_replace_tags",
                )
                _col_bulk_replace, _col_bulk_clear = st.columns(2)
                with _col_bulk_replace:
                    if st.button(
                        f"Replace tags on {_selected_count} selected",
                        key="btn_bulk_replace_tags",
                        disabled=not _bulk_chosen,
                        width="stretch",
                    ):
                        _indices = [
                            _idx for _idx in (
                                get_loaded_entry_index_by_id(_bid)
                                for _bid in _selected_ids
                            )
                            if _idx is not None
                        ]
                        _bulk_result = replace_tags_bulk_service(
                            dataset_path=st.session_state.get("loaded_path", ""),
                            entries=st.session_state.loaded_entries,
                            entry_indices=_indices,
                            tags=_bulk_chosen,
                            backup_enabled=auto_backups_enabled(
                                st.session_state.get("prefs", {})
                            ),
                        )
                        if _bulk_result.ok and _bulk_result.entries is not None:
                            st.session_state.loaded_entries = _bulk_result.entries
                            ensure_entry_registry()
                            _backup_note = (
                                " Backup created." if _bulk_result.backup_path else ""
                            )
                            st.session_state["tag_save_success"] = (
                                f"{_bulk_result.message}{_backup_note}"
                            )
                            st.rerun()
                        else:
                            for _err in _bulk_result.errors:
                                st.error(_err)
                            if not _bulk_result.errors:
                                st.error(_bulk_result.message)
                with _col_bulk_clear:
                    if st.button(
                        f"Clear tags on {_selected_count} selected",
                        key="btn_bulk_clear_tags",
                        width="stretch",
                    ):
                        _indices = [
                            _idx for _idx in (
                                get_loaded_entry_index_by_id(_bid)
                                for _bid in _selected_ids
                            )
                            if _idx is not None
                        ]
                        _bulk_result = clear_tags_bulk_service(
                            dataset_path=st.session_state.get("loaded_path", ""),
                            entries=st.session_state.loaded_entries,
                            entry_indices=_indices,
                            backup_enabled=auto_backups_enabled(
                                st.session_state.get("prefs", {})
                            ),
                        )
                        if _bulk_result.ok and _bulk_result.entries is not None:
                            st.session_state.loaded_entries = _bulk_result.entries
                            ensure_entry_registry()
                            _backup_note = (
                                " Backup created." if _bulk_result.backup_path else ""
                            )
                            st.session_state["tag_save_success"] = (
                                f"{_bulk_result.message}{_backup_note}"
                            )
                            st.rerun()
                        else:
                            for _err in _bulk_result.errors:
                                st.error(_err)
                            if not _bulk_result.errors:
                                st.error(_bulk_result.message)

            # ── Entry list ─────────────────────────────────────────────────────
            # Sync all visible checkbox widget keys from selected_entry_ids
            # BEFORE any checkbox widget renders so visual state is always correct.
            # Only visible_pairs (current page) are synced — other pages are unaffected.
            for _sync_id, _ in visible_pairs:
                st.session_state[f"select_{_sync_id}"] = (
                    _sync_id in st.session_state.selected_entry_ids
                )

            def _on_checkbox_change(entry_id: str) -> None:
                st.session_state["manage_select_all_mode"] = False
                toggle_entry_selection(
                    entry_id, st.session_state[f"select_{entry_id}"]
                )

            for i, (entry_id, entry) in enumerate(visible_pairs, start=start):
                errs = validate_entry(entry)
                label = format_entry_summary_label(
                    display_index=i,
                    entry=entry,
                    errors=errs,
                    tag_label_map=_label_map,
                )
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
                                    _quick_result = save_quick_edit(entry_id, entry)
                                    if _quick_result.ok:
                                        cancel_quick_edit()
                                        _backup_note = (
                                            " Backup created."
                                            if _quick_result.backup_path else ""
                                        )
                                        st.session_state["quick_edit_success"] = (
                                            f"{_quick_result.message}{_backup_note}"
                                        )
                                        st.rerun()
                                    else:
                                        for _err in _quick_result.errors:
                                            st.error(_err)
                                        if not _quick_result.errors:
                                            st.error(_quick_result.message)
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
                            _include_system = True
                            if (
                                st.session_state.get("dataset_source_format")
                                == FORMAT_SHAREGPT
                            ):
                                _include_system = False
                            render_message_preview(
                                entry.get("messages", []), include_system=_include_system
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
