"""Streamlit page for exporting the loaded dataset."""
from pathlib import Path

import streamlit as st

from core.dataset import save_dataset
from core.format_conversion import (
    FORMAT_CHATML,
    FORMAT_SHAREGPT,
    convert_chatml_to_format,
)
from core.working_copy import canonical_training_dataset_path
from services.registry_sidecar_service import export_registry_sidecar
from ui.browser_helpers import MATCH_MODE_ANY
from ui.entry_search_controls import is_entry_search_query_active
from ui.entry_search_state import ENTRY_SEARCH_QUERY_KEY, get_entry_search_options
from ui.export_scope import (
    EXPORT_SCOPE_ALL,
    EXPORT_SCOPE_SELECTED_FILTERED,
    scoped_export_pairs,
)
from ui.file_dialogs import browse_export_file, path_input
from ui.flash_messages import enqueue_flash, render_flash_messages
from ui.guidance import render_manage_dataset_cta
from ui.manage.filters import apply_manage_entry_filters
from ui.session_state import ensure_entry_indexes
from ui.session_state import get_all_entry_pairs

_EXPORT_FORMAT_OPTIONS = {
    "ChatML": FORMAT_CHATML,
    "ShareGPT": FORMAT_SHAREGPT,
}


def _prepare_export_entries(
    entries: list[dict],
    *,
    export_format: str,
    clean_export: bool,
) -> list[dict]:
    """Return entries in the requested export shape without mutating input."""
    if export_format == FORMAT_SHAREGPT:
        return convert_chatml_to_format(
            entries,
            target_format=FORMAT_SHAREGPT,
            include_metadata=not clean_export,
        ).entries
    if clean_export:
        return [{"messages": e["messages"]} for e in entries]
    return entries


def render_export_page() -> None:
    """Render the Export Dataset page."""
    ensure_entry_indexes()
    st.subheader("Export Dataset")
    render_flash_messages()

    _export_entries = st.session_state.loaded_entries
    if not _export_entries:
        st.info("Load a dataset to export.")
        render_manage_dataset_cta(key="export_go_to_manage_empty")
        return

    all_pairs = get_all_entry_pairs()
    scoped_pairs, scoped_label, scoped_available = _resolve_export_scope(all_pairs)

    st.caption(
        f"{len(_export_entries)} entries loaded from "
        f"`{st.session_state.loaded_path or 'unknown'}`"
    )

    format_col, _format_spacer = st.columns([1, 3])
    with format_col:
        _format_label = st.selectbox(
            "Export format",
            options=list(_EXPORT_FORMAT_OPTIONS),
            key="export_format_select",
        )
    _export_format = _EXPORT_FORMAT_OPTIONS[_format_label]

    clean_export = st.checkbox(
        "Clean - Metadata removed",
        value=False,
        key="export_clean",
    )

    scope_options = [EXPORT_SCOPE_ALL]
    if scoped_available:
        scope_options.append(EXPORT_SCOPE_SELECTED_FILTERED)
    export_scope = st.radio(
        "Export scope",
        options=scope_options,
        format_func=lambda value: (
            "Export all entries"
            if value == EXPORT_SCOPE_ALL
            else f"Export {scoped_label} only"
        ),
        key="export_scope_select",
    )
    if not scoped_available:
        st.caption("Select or filter entries in Manage Dataset first.")
    active_export_pairs = (
        scoped_pairs if export_scope == EXPORT_SCOPE_SELECTED_FILTERED else all_pairs
    )
    active_export_entries = [entry for _entry_uuid, entry in active_export_pairs]
    st.caption(f"Exporting {len(active_export_entries)} entr{'y' if len(active_export_entries) == 1 else 'ies'}.")

    # Browse button opens save dialog (pure Tkinter → rerun, no save work done here).
    # Export button only calls save_dataset — no Tkinter, no threading risk.
    export_save_path = path_input(
        "Export file path",
        state_key="export_save_path",
        browse_fn=browse_export_file,
        browse_kwargs={},
        default="",
        show_browse=False,
    )

    browse_col, export_col, _export_spacer = st.columns([1, 1, 2])
    with browse_col:
        if st.button("Browse", key="browse_export_save_path", width="stretch"):
            browse_export_file("export_save_path_pending")
    with export_col:
        export_clicked = st.button("Export as JSONL", type="primary", width="stretch")

    if export_clicked:
        _p = export_save_path.strip()
        if not _p:
            st.error("Set an export path or use Browse to pick a location.")
        else:
            try:
                _p = str(canonical_training_dataset_path(_p))
                _out = _prepare_export_entries(
                    active_export_entries,
                    export_format=_export_format,
                    clean_export=clean_export,
                )
                # Export writes a user-selected output file, not the protected working dataset.
                save_dataset(_p, _out)
                success_message = f"Exported {len(_out)} entries to `{Path(_p).resolve()}`."
                sidecar_result = export_registry_sidecar(
                    dataset_path=_p,
                    entries=active_export_entries,
                )
                if sidecar_result.ok:
                    success_message += f" {sidecar_result.message}"
                else:
                    enqueue_flash("warning", sidecar_result.message)
                enqueue_flash("success", success_message)
                st.session_state["export_save_path_pending"] = ""
                st.rerun()
            except Exception as exc:
                st.error(f"Export failed: {exc}")


def _resolve_export_scope(
    all_pairs: list[tuple[str, dict]],
) -> tuple[list[tuple[str, dict]], str, bool]:
    selected_uuids = set(st.session_state.get("selected_entry_uuids", set()) or set())
    stats_filter_uuids = set(st.session_state.get("stats_filter_uuids", set()) or set())
    filter_tags = list(st.session_state.get("filter_tags", []) or [])
    search_query = st.session_state.get(ENTRY_SEARCH_QUERY_KEY, "")
    search_active = is_entry_search_query_active(search_query)
    filters_active = bool(filter_tags or search_active or stats_filter_uuids)

    filtered_pairs = apply_manage_entry_filters(
        all_pairs,
        filter_tags=filter_tags,
        tag_match_mode=st.session_state.get("filter_match_mode", MATCH_MODE_ANY),
        search_query=search_query,
        search_options=get_entry_search_options(),
        stats_filter_uuids=stats_filter_uuids,
    )
    pairs, label = scoped_export_pairs(
        all_pairs,
        selected_uuids=selected_uuids,
        filtered_pairs=filtered_pairs,
        filters_active=filters_active,
    )
    return pairs, label, bool(selected_uuids or filters_active)
