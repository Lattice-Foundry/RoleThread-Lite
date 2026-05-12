"""Streamlit page for managing the loaded dataset.

This module owns selection, filters, pagination, and widgets. Durable
dataset mutations delegate to services.
"""
from pathlib import Path
import streamlit as st

from core.backups import auto_backups_enabled
from core.dataset import (
    clear_validate_entry_cache,
    filter_entry_pairs_by_tags,
    get_entry_tags,
    analyze_entry,
    load_dataset_with_summary,
    save_dataset,
    validate_entry,
)
from core.format_conversion import FORMAT_CHATML, FORMAT_SHAREGPT, FORMAT_UNKNOWN
from core.character_display import build_character_display_cache, get_turn_display_names
from core.text_helpers import count_phrase
from core.tag_registry import (
    get_tag_registry_snapshot,
    prettify_tag_name,
)
from core.working_copy import canonical_training_dataset_path
from ui.file_dialogs import JSONL_TYPES, browse_open_file, path_input, safe_saveas_filename
from ui.entry_edit_helpers import (
    has_entry_notification_issue,
    requires_full_edit_for_quick_edit,
)
from ui.message_scaffolding import scaffold_editable_messages
from core.preferences import get_initial_dir
from ui.session_state import (
    cancel_quick_edit,
    apply_dataset_operation_result,
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
    should_persist_loaded_normalization,
    start_quick_edit,
    toggle_entry_selection,
    update_prefs,
)
from services.dataset_service import (
    clear_tags_bulk_service,
    replace_single_entry_tags_service,
    replace_system_prompt_bulk_service,
    replace_tags_bulk_service,
    save_repaired_entries_service,
)
from services.registry_sidecar_service import export_registry_sidecar
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
from ui.ui_edit_entries import start_full_edit

_UNTAGGED = "__untagged__"


def _format_source_format(source_format: str) -> str:
    labels = {
        FORMAT_CHATML: "ChatML",
        FORMAT_SHAREGPT: "ShareGPT",
        FORMAT_UNKNOWN: "Unknown",
    }
    return labels.get(source_format, source_format or "Unknown")


def _render_load_format_summary(
    normalization,
    *,
    loaded_dataset_path: str | None = None,
    loaded_entry_count: int | None = None,
    correction_saved: bool = False,
    correction_failed: bool = False,
    corrected_entries: int = 0,
) -> None:
    source_format = normalization.source_format
    if source_format == FORMAT_SHAREGPT:
        st.info(
            "Detected format: ShareGPT. "
            "Export as ShareGPT to preserve the original format."
        )
    else:
        st.info(f"Detected format: {_format_source_format(source_format)}.")

    if loaded_dataset_path is not None and loaded_entry_count is not None:
        diagnostics = normalization.diagnostics
        issue_entries = max(0, diagnostics.entries_analyzed - diagnostics.valid_entries)
        st.success(
            f"Loaded {count_phrase(loaded_entry_count, 'entry', 'entries')} "
            f"from `{loaded_dataset_path}`. "
            f"({diagnostics.valid_entries} valid, {issue_entries} with issues)."
        )

    if correction_saved:
        st.info(
            "LoreForge automatically corrected "
            f"{count_phrase(corrected_entries, 'entry', 'entries')} on load "
            "(role formatting, missing metadata). Your original file is preserved. "
            "See Validation page for remaining issues."
        )
    elif correction_failed:
        st.warning(
            "Automatic corrections were applied in memory, but were not saved."
        )

    if normalization.parse_error_count:
        st.warning(
            f"Loaded {count_phrase(normalization.parsed_entry_count, 'entry', 'entries')} "
            f"from {count_phrase(normalization.source_line_count, 'non-empty line')}. "
            f"{count_phrase(normalization.parse_error_count, 'line')} had parse errors."
        )
    if normalization.role_values_normalized or normalization.message_content_trimmed:
        st.caption(
            "Corrected "
            f"{count_phrase(normalization.role_values_normalized, 'role value')} and "
            f"{count_phrase(normalization.message_content_trimmed, 'message content field')}."
        )
    if normalization.alias_rewrites:
        rewrite_items = list(normalization.alias_rewrites.items())
        preview = ", ".join(
            f"{old_slug} -> {new_slug}"
            for old_slug, new_slug in rewrite_items[:3]
        )
        if len(rewrite_items) > 3:
            preview += f", and {count_phrase(len(rewrite_items) - 3, 'more alias')}"
        st.caption(f"Resolved stale tag aliases: {preview}.")

    warnings = list(normalization.format_warnings or [])
    for warning in warnings[:3]:
        st.caption(f"Conversion warning: {warning}")
    if len(warnings) > 3:
        st.caption(
            f"{count_phrase(len(warnings) - 3, 'additional conversion warning')} hidden."
        )

    working_copy = st.session_state.get("working_copy_summary")
    if working_copy and not correction_saved:
        st.info(
            "Original file preserved. "
            f"Working copy created at `{working_copy.get('working_path')}`."
        )

    character_candidates = st.session_state.get("character_candidates")
    if character_candidates and character_candidates.has_candidates:
        labels = [
            candidate.source_role_label
            for candidate in character_candidates.candidates
        ]
        preview = ", ".join(labels[:5])
        if len(labels) > 5:
            preview += f", and {count_phrase(len(labels) - 5, 'more')}"
        st.info(
            f"{count_phrase(len(labels), 'custom role name')} detected "
            f"({preview}). Review on Validation page."
        )

    sidecar_summary = st.session_state.get("sidecar_import_summary")
    if sidecar_summary:
        if sidecar_summary.get("ok"):
            category_count = len(sidecar_summary.get("categories_created", []) or [])
            created_count = len(sidecar_summary.get("tags_created", []) or [])
            promoted_count = len(sidecar_summary.get("tags_promoted", []) or [])
            st.info(
                "Registry sidecar restored: "
                f"{count_phrase(category_count, 'category', 'categories')}, "
                f"{count_phrase(created_count, 'tag')}, "
                f"{count_phrase(promoted_count, 'promoted tag')}."
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
                f"{count_phrase(len(conflicts), 'tag conflict')} detected - resolve on Validation page."
            )

    pending_trust = st.session_state.get("pending_tag_trust") or {}
    if pending_trust:
        st.warning(
            f"{count_phrase(len(pending_trust), 'unknown tag')} imported to archive "
            "in Tag Management. Assign categories to make them available in tag pickers."
        )


def _entry_has_reportable_diagnostics(entry: dict) -> bool:
    result = analyze_entry(entry)
    return any(
        diagnostic.severity.value in {"error", "warning"}
        or (diagnostic.fixable and diagnostic.repair_kind.value == "automatic")
        for diagnostic in result.diagnostics
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
            _auto_correct_enabled = st.session_state.get(
                "auto_correct_validation_errors",
                st.session_state.get("prefs", {}).get(
                    "auto_correct_validation_errors",
                    st.session_state.get("prefs", {}).get("auto_normalize_on_load", True),
                ),
            )
            normalization, errors = load_dataset_with_summary(
                p,
                auto_normalize=_auto_correct_enabled,
            )
            entries = normalization.entries
            if errors:
                for e in errors[:3]:
                    st.error(e)
                if len(errors) > 3:
                    st.caption(
                        f"{count_phrase(len(errors) - 3, 'additional load error')} hidden."
                    )
            if errors and not entries:
                st.error("No dataset was loaded.")
                return
            loaded_dataset_path = set_loaded_entries(
                entries,
                normalization_summary=normalization,
                dataset_path=p,
            ) or p
            st.session_state.loaded_path = loaded_dataset_path
            st.session_state.stale_last_path = ""
            st.session_state.entry_page = 0
            st.session_state["manage_select_all_mode"] = False
            clear_selected_entries()
            _normalization_saved = False
            _normalization_failed = False
            _corrected_entries = int(
                st.session_state.get("tag_normalization_summary", {}).get(
                    "changed_entries",
                    0,
                )
                or 0
            )
            if should_persist_loaded_normalization(
                parse_errors=errors,
                normalization_pending=st.session_state.get("normalization_pending", False),
            ):
                _normalize_result = persist_loaded_normalization(loaded_dataset_path)
                if _normalize_result.ok:
                    _normalization_saved = True
                else:
                    _normalization_failed = True
                    st.error(_normalize_result.message)
                    for _err in _normalize_result.errors:
                        st.error(_err)
            update_prefs({
                "last_loaded_dataset_path": loaded_dataset_path,
                "last_open_directory": str(Path(loaded_dataset_path).parent),
            })
            _render_load_format_summary(
                normalization,
                loaded_dataset_path=loaded_dataset_path,
                loaded_entry_count=len(entries),
                correction_saved=_normalization_saved,
                correction_failed=_normalization_failed,
                corrected_entries=_corrected_entries,
            )

    with col_new:
        if st.button("New Dataset", width="stretch"):
            prefs = st.session_state.prefs
            new_path = safe_saveas_filename(
                title="Create new dataset",
                defaultextension=".jsonl",
                initialfile="dataset.jsonl",
                initialdir=get_initial_dir(prefs, dir_key="default_dataset_directory"),
                filetypes=JSONL_TYPES,
            )

            if new_path:
                # Flush any in-memory entries to the current dataset first
                if st.session_state.loaded_entries and st.session_state.loaded_path:
                    result = save_repaired_entries_service(
                        dataset_path=st.session_state.loaded_path,
                        repaired_entries=st.session_state.loaded_entries,
                        backup_reason="before_new_dataset_switch",
                    )
                    if result.ok:
                        apply_dataset_operation_result(result)
                        st.session_state.loaded_entries = result.entries or []
                    else:
                        st.error(
                            "Could not save current dataset before switching: "
                            f"{result.message}"
                        )
                        new_path = ""  # cancel

            if new_path:
                try:
                    new_path = str(canonical_training_dataset_path(new_path))
                    save_dataset(new_path, [])  # create empty file
                    sidecar_result = export_registry_sidecar(
                        dataset_path=new_path,
                        entries=[],
                    )
                    if not sidecar_result.ok:
                        st.warning(sidecar_result.message)
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

    entries = st.session_state.loaded_entries
    all_pairs = get_all_entry_pairs()
    if all_pairs:
        st.divider()
        st.subheader(f"Entries ({len(all_pairs)})")

        invalid_count = sum(1 for e in entries if _entry_has_reportable_diagnostics(e))
        if invalid_count:
            st.warning(
                f"{count_phrase(invalid_count, 'entry', 'entries')} "
                "have validation issues."
            )
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
            _character_display_cache = build_character_display_cache([
                entry for _entry_id, entry in visible_pairs
            ])
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
                _selected_entry_phrase = count_phrase(
                    len(_pending_sel_ids),
                    "selected entry",
                    "selected entries",
                )
                st.warning(
                    f"Delete {_selected_entry_phrase}? This cannot be undone."
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
                    "Replace the system prompt for "
                    f"{count_phrase(_total_sel, 'selected entry', 'selected entries')}. "
                    "This will overwrite existing system prompts "
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
                            apply_dataset_operation_result(_sys_result)
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
                                apply_dataset_operation_result(_tag_result)
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
                            apply_dataset_operation_result(_bulk_result)
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
                            apply_dataset_operation_result(_bulk_result)
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
                has_notification_issue = has_entry_notification_issue(entry, errs)
                label = format_entry_summary_label(
                    display_index=i,
                    entry=entry,
                    errors=errs,
                    has_issues=has_notification_issue,
                    tag_label_map=_label_map,
                )
                _col_cb, _col_entry = st.columns([1, 20])
                _is_qe = (
                    st.session_state.get("quick_edit_entry_id") == entry_id
                )
                with _col_cb:
                    st.checkbox(
                        "Select",
                        key=f"select_{entry_id}",
                        on_change=_on_checkbox_change,
                        args=(entry_id,),
                        label_visibility="collapsed",
                    )
                with _col_entry:
                    with st.expander(label, expanded=_is_qe):
                        st.caption(f"Temp ID: {entry_id}")

                        if _is_qe:
                            # ── Quick edit mode ────────────────────────────────
                            st.markdown("**Quick Edit Messages**")
                            _qe_msgs = entry.get("messages", [])
                            if not isinstance(_qe_msgs, list):
                                _qe_msgs = []
                            _qe_msgs = scaffold_editable_messages(_qe_msgs)
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
                            if requires_full_edit_for_quick_edit(entry):
                                if st.button(
                                    "Requires Full Edit",
                                    key=f"btn_requires_full_edit_{entry_id}",
                                ):
                                    st.session_state.page = "Edit Entries"
                                    start_full_edit(entry_id, _tag_snapshot.active_registry)
                            else:
                                st.button(
                                    "Quick Edit",
                                    key=f"btn_quick_edit_{entry_id}",
                                    on_click=start_quick_edit,
                                    args=(entry_id, entry),
                                )
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
                                entry.get("messages", []),
                                include_system=_include_system,
                                display_names=get_turn_display_names(
                                    entry,
                                    st.session_state.get("preview_user_name", "User"),
                                    st.session_state.get(
                                        "preview_assistant_name",
                                        "Assistant",
                                    ),
                                    _character_display_cache,
                                ),
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
