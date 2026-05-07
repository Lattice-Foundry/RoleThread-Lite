"""Edit Entries page — read-only dataset browser with filtering and pagination."""
import streamlit as st

from core.dataset import (
    count_exchanges,
    filter_entry_pairs_by_tags,
    get_available_filter_tags,
    get_entry_tags,
    get_tag_label_map,
    validate_entry,
)
from core.state import ensure_entry_registry, get_all_entry_pairs, get_loaded_entry_by_id
from ui.ui_components import render_message_preview

_UNTAGGED = "__untagged__"

# Filter/page keys that must survive the browser → workspace → browser round-trip.
# Snapshotted on entry, restored on exit so Streamlit widget state is correct
# even if the browser widgets were not rendered during workspace mode.
_BROWSER_STATE_KEYS = (
    "edit_filter_tags",
    "edit_filter_only_used",
    "edit_filter_match_mode",
    "edit_entry_page",
    "edit_entries_per_page",
)


# ── Full-edit mode helpers ─────────────────────────────────────────────────────

def start_full_edit(entry_id: str) -> None:
    """Snapshot browser filter/page state, enter workspace mode, and rerun."""
    st.session_state["_ee_browser_snapshot"] = {
        k: st.session_state.get(k) for k in _BROWSER_STATE_KEYS
    }
    st.session_state.editing_entry_id = entry_id
    st.session_state.edit_entries_mode = "workspace"
    st.rerun()


def cancel_full_edit() -> None:
    """Restore browser filter/page state, return to browser mode, and rerun."""
    snapshot = st.session_state.pop("_ee_browser_snapshot", {})
    for k, v in snapshot.items():
        if v is not None:
            st.session_state[k] = v
    st.session_state.editing_entry_id = None
    st.session_state.edit_entries_mode = "browser"
    st.rerun()


# ── Workspace placeholder ──────────────────────────────────────────────────────

def render_edit_workspace_placeholder() -> None:
    """Placeholder workspace shown while edit_entries_mode == 'workspace'.

    Full editor will be built in the next phase — this phase only confirms
    that mode routing, entry lookup, and the cancel flow all work correctly.
    """
    entry_id = st.session_state.get("editing_entry_id")

    if not entry_id:
        st.warning("No entry selected for editing.")
        if st.button("Back to Edit Entries", key="btn_back_no_id"):
            cancel_full_edit()
        return

    entry = get_loaded_entry_by_id(entry_id)

    if entry is None:
        st.error("Selected entry could not be found.")
        if st.button("Back to Edit Entries", key="btn_back_not_found"):
            cancel_full_edit()
        return

    st.subheader("Full Edit Entry")
    st.caption(f"Temp ID: {entry_id}")
    st.info("Full editor workspace will be built in the next phase.")
    render_message_preview(entry.get("messages", []), include_system=True)
    if st.button("Cancel / Back to Edit Entries", key="btn_cancel_full_edit",
                 width="stretch"):
        cancel_full_edit()


def render_edit_entries_page() -> None:
    """Render the Edit Entries page.

    Routes to the full-edit workspace when edit_entries_mode == 'workspace',
    otherwise renders the existing browser view.
    """
    ensure_entry_registry()

    if st.session_state.get("edit_entries_mode") == "workspace":
        render_edit_workspace_placeholder()
        return

    _ee_entries = st.session_state.loaded_entries
    _ee_all_pairs = get_all_entry_pairs()

    if not _ee_all_pairs:
        st.info("Load a dataset in Manage Dataset to edit entries.")
        return

    st.subheader(f"Browse Entries ({len(_ee_all_pairs)})")

    # ── Filter controls ────────────────────────────────────────────────────────
    _ee_label_map = get_tag_label_map(untagged_key=_UNTAGGED)

    def _ee_reset_page() -> None:
        st.session_state.edit_entry_page = 0

    def _ee_reset_page_and_selection() -> None:
        st.session_state.edit_entry_page = 0
        st.session_state.edit_filter_tags = []

    _ee_only_used = st.checkbox(
        "Only show used tags",
        key="edit_filter_only_used",
        on_change=_ee_reset_page_and_selection,
    )

    _ee_available = get_available_filter_tags(
        _ee_entries, only_used=_ee_only_used, untagged_key=_UNTAGGED
    )

    # Apply pending correction before the multiselect widget renders
    if "edit_filter_tags_pending" in st.session_state:
        st.session_state["edit_filter_tags"] = st.session_state.pop(
            "edit_filter_tags_pending"
        )

    # Drop stale selections no longer in available options
    _ee_clamped = [
        t for t in st.session_state.get("edit_filter_tags", [])
        if t in _ee_available
    ]
    if _ee_clamped != st.session_state.get("edit_filter_tags", []):
        st.session_state["edit_filter_tags"] = _ee_clamped

    _ee_filter_col, _ee_mode_col = st.columns([3, 1])
    with _ee_filter_col:
        _ee_filter_tags = st.multiselect(
            "Filter entries by tag",
            options=_ee_available,
            format_func=lambda x: _ee_label_map.get(x, x),
            key="edit_filter_tags",
            on_change=_ee_reset_page,
        )

    # Guard against "Select all" accidentally including __untagged__
    _ee_available_real = [t for t in _ee_available if t != _UNTAGGED]
    _ee_selected_real = [t for t in _ee_filter_tags if t != _UNTAGGED]
    if (
        _UNTAGGED in _ee_filter_tags
        and _ee_available_real
        and set(_ee_selected_real) == set(_ee_available_real)
    ):
        st.session_state["edit_filter_tags_pending"] = _ee_selected_real
        st.rerun()

    with _ee_mode_col:
        _ee_match_mode = st.radio(
            "Match mode",
            options=["Any selected tags", "All selected tags", "Exact match"],
            key="edit_filter_match_mode",
            on_change=_ee_reset_page,
        )

    # ── Apply filter ───────────────────────────────────────────────────────────
    _ee_filtered_pairs = filter_entry_pairs_by_tags(
        _ee_all_pairs,
        selected_tags=_ee_filter_tags,
        match_mode=_ee_match_mode,
    )

    # ── Pagination ─────────────────────────────────────────────────────────────
    _ee_per_page_options = [10, 25, 50, 100, 500, "Show All"]
    _ee_saved_per_page = st.session_state.get("edit_entries_per_page", 25)
    _ee_default_idx = (
        _ee_per_page_options.index(_ee_saved_per_page)
        if _ee_saved_per_page in _ee_per_page_options
        else 1
    )
    _ee_col_per_page, _ee_col_per_page_spacer = st.columns([1, 3])
    with _ee_col_per_page:
        _ee_selected_per_page = st.selectbox(
            "Entries per page",
            options=_ee_per_page_options,
            index=_ee_default_idx,
            key="_ee_entries_per_page_select",
        )
    if _ee_selected_per_page != st.session_state.get("edit_entries_per_page"):
        st.session_state.edit_entries_per_page = _ee_selected_per_page
        st.session_state.edit_entry_page = 0
        st.rerun()

    _ee_total_filtered = len(_ee_filtered_pairs)
    _ee_total_all = len(_ee_all_pairs)

    if _ee_total_filtered == 0:
        st.info("No entries match the current filters.")
        return

    _ee_per_page_setting = st.session_state.edit_entries_per_page
    if _ee_per_page_setting == "Show All":
        _ee_per_page = _ee_total_filtered
        _ee_last_page = 0
        _ee_cur_page = 0
        _ee_start = 0
        _ee_end = _ee_total_filtered
    else:
        _ee_per_page = _ee_per_page_setting
        _ee_last_page = max(0, (_ee_total_filtered - 1) // _ee_per_page)
        _ee_cur_page = min(
            st.session_state.get("edit_entry_page", 0), _ee_last_page
        )
        _ee_start = _ee_cur_page * _ee_per_page
        _ee_end = min(_ee_start + _ee_per_page, _ee_total_filtered)
    _ee_visible_pairs = _ee_filtered_pairs[_ee_start:_ee_end]

    # ── Status line ────────────────────────────────────────────────────────────
    if _ee_filter_tags:
        st.caption(
            f"Showing {_ee_start + 1}–{_ee_end} of {_ee_total_filtered} "
            f"filtered entries ({_ee_total_all} total)"
        )
    else:
        st.caption(
            f"Showing {_ee_start + 1}–{_ee_end} of {_ee_total_all} entries"
        )

    # ── Entry list ─────────────────────────────────────────────────────────────
    for _ee_i, (_ee_entry_id, _ee_entry) in enumerate(
        _ee_visible_pairs, start=_ee_start
    ):
        _ee_errs = validate_entry(_ee_entry)
        _ee_entry_tags = get_entry_tags(_ee_entry)
        _ee_tag_part = ", ".join(_ee_entry_tags) if _ee_entry_tags else "untagged"
        _ee_fmt_part = st.session_state.dataset_format
        _ee_exc_part = count_exchanges(_ee_entry)
        _ee_label = (
            f"Entry {_ee_i + 1} | FORMAT: {_ee_fmt_part} | "
            f"TAGS: {_ee_tag_part} | EXCHANGES: {_ee_exc_part}"
        )
        if _ee_errs:
            _ee_label += " ⚠️"
        with st.expander(_ee_label):
            st.caption(f"Temp ID: {_ee_entry_id}")
            if st.button("Edit Entry", key=f"btn_full_edit_{_ee_entry_id}"):
                start_full_edit(_ee_entry_id)
            if _ee_errs:
                for _ee_err in _ee_errs:
                    st.error(_ee_err)
            render_message_preview(
                _ee_entry.get("messages", []), include_system=True
            )

    # ── Pagination buttons ─────────────────────────────────────────────────────
    _ee_col_prev, _ee_col_next = st.columns(2)
    with _ee_col_prev:
        if st.button(
            "Previous",
            disabled=(_ee_cur_page == 0),
            width="stretch",
            key="ee_btn_prev",
        ):
            st.session_state.edit_entry_page = _ee_cur_page - 1
            st.rerun()
    with _ee_col_next:
        if st.button(
            "Next",
            disabled=(_ee_cur_page >= _ee_last_page),
            width="stretch",
            key="ee_btn_next",
        ):
            st.session_state.edit_entry_page = _ee_cur_page + 1
            st.rerun()
