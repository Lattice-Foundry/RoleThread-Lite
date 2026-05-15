"""Edit Entries browser/list rendering."""

import streamlit as st

from core.character_display import build_character_display_cache, get_turn_display_names
from core.dataset import validate_entry
from core.format_conversion import FORMAT_SHAREGPT
from core.tag_registry import prettify_tag_name
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
from ui.edit_entries.filters import (
    UNTAGGED_FILTER_KEY,
    apply_edit_entry_filters,
    clear_edit_filters,
    edit_filters_active,
)
from ui.edit_entries.state import start_full_edit
from ui.entry_edit_helpers import has_entry_notification_issue
from ui.entry_search_controls import (
    entry_search_has_enabled_scope,
    format_entry_search_no_results_message,
    is_entry_search_query_active,
    render_entry_search_controls,
)
from ui.entry_search_state import ENTRY_SEARCH_QUERY_KEY, get_entry_search_options
from ui.guidance import render_manage_dataset_cta
from ui.session_state import get_all_entry_pairs
from ui.ui_components import render_message_preview


def render_edit_entries_browser(tag_snapshot) -> None:
    """Render the Edit Entries browser view."""

    entries = st.session_state.loaded_entries
    all_pairs = get_all_entry_pairs()

    if not all_pairs:
        st.info("Load a dataset in Manage Dataset to edit entries.")
        render_manage_dataset_cta(key="edit_entries_go_to_manage_empty")
        return

    st.subheader(f"Browse Entries ({len(all_pairs)})")

    label_map = tag_snapshot.tag_label_map_with_untagged
    all_known_slugs = tag_snapshot.active_tag_slugs

    def reset_page() -> None:
        st.session_state.edit_entry_page = 0

    def reset_page_and_selection() -> None:
        st.session_state.edit_entry_page = 0
        st.session_state.edit_filter_tags = []

    only_used = st.checkbox(
        "Only show used tags",
        key="edit_filter_only_used",
        on_change=reset_page_and_selection,
    )

    if "edit_filter_tags_pending" in st.session_state:
        st.session_state["edit_filter_tags"] = st.session_state.pop(
            "edit_filter_tags_pending"
        )

    filter_state = build_filter_tag_state(
        entries=entries,
        selected_tags=st.session_state.get("edit_filter_tags", []),
        only_used_tags=only_used,
        all_known_tags=all_known_slugs,
        untagged_key=UNTAGGED_FILTER_KEY,
    )
    available_tags = filter_state.available_tags
    if filter_state.selected_tags_changed:
        st.session_state["edit_filter_tags"] = filter_state.clamped_selected_tags

    filter_col, mode_col, _filter_spacer = st.columns([1, 1, 2])
    with filter_col:
        filter_tags = st.multiselect(
            "Filter entries by tag",
            options=available_tags,
            format_func=lambda x: label_map.get(x, prettify_tag_name(x)),
            key="edit_filter_tags",
            on_change=reset_page,
        )

    normalized_filter_tags = normalize_untagged_selection(
        selected_tags=filter_tags,
        available_tags=available_tags,
        untagged_key=UNTAGGED_FILTER_KEY,
    )
    if normalized_filter_tags != filter_tags:
        st.session_state["edit_filter_tags_pending"] = normalized_filter_tags
        st.rerun()

    with mode_col:
        match_mode = st.radio(
            "Match mode",
            options=MATCH_MODE_OPTIONS,
            key="edit_filter_match_mode",
            on_change=reset_page,
        )

    render_entry_search_controls(on_change=reset_page, compact_layout=True)
    search_query = st.session_state.get(ENTRY_SEARCH_QUERY_KEY, "")
    search_options = get_entry_search_options()

    if edit_filters_active(
        filter_tags=filter_tags,
        match_mode=match_mode,
        search_query=search_query,
    ):
        clear_col, _clear_spacer = st.columns([1, 5])
        with clear_col:
            if st.button(
                "Clear all filters",
                key="btn_edit_clear_all_filters",
                width="stretch",
            ):
                clear_edit_filters()
                st.rerun()

    filtered_pairs = apply_edit_entry_filters(
        all_pairs,
        filter_tags=filter_tags,
        tag_match_mode=match_mode,
        search_query=search_query,
        search_options=search_options,
    )

    saved_per_page = st.session_state.get("edit_entries_per_page", DEFAULT_PAGE_SIZE)
    default_idx = (
        PAGE_SIZE_OPTIONS.index(saved_per_page)
        if saved_per_page in PAGE_SIZE_OPTIONS
        else PAGE_SIZE_OPTIONS.index(DEFAULT_PAGE_SIZE)
    )
    col_per_page, _col_per_page_spacer = st.columns([1, 3])
    with col_per_page:
        selected_per_page = st.selectbox(
            "Entries per page",
            options=PAGE_SIZE_OPTIONS,
            index=default_idx,
            key="_ee_entries_per_page_select",
        )
    if selected_per_page != st.session_state.get("edit_entries_per_page"):
        st.session_state.edit_entries_per_page = selected_per_page
        st.session_state.edit_entry_page = 0
        st.rerun()

    total_filtered = len(filtered_pairs)
    total_all = len(all_pairs)

    search_active = is_entry_search_query_active(search_query)
    if total_filtered == 0:
        st.info(
            format_entry_search_no_results_message(
                has_tag_filters=bool(filter_tags),
                search_active=search_active,
                scopes_enabled=entry_search_has_enabled_scope(search_options),
            )
        )
        return

    pagination = calculate_pagination(
        total_items=total_filtered,
        requested_page=st.session_state.get("edit_entry_page", 0),
        per_page_setting=st.session_state.edit_entries_per_page,
    )
    visible_pairs = slice_visible_pairs(filtered_pairs, pagination)
    character_display_cache = build_character_display_cache([
        entry for _entry_uuid, entry in visible_pairs
    ])
    if pagination.is_show_all_capped:
        st.warning(
            f"Showing first 1,000 of {pagination.total_items} entries. "
            "Use pagination or filters to narrow results."
        )

    st.caption(
        format_browser_status_caption(
            start=pagination.start,
            end=pagination.end,
            total_filtered=total_filtered,
            total_all=total_all,
            filtered=bool(filter_tags) or search_active,
            filtered_label=(
                "matching entries" if search_active else "filtered entries"
            ),
        )
    )

    for display_index, (entry_uuid, entry) in enumerate(
        visible_pairs,
        start=pagination.start,
    ):
        errors = validate_entry(entry)
        has_notification_issue = has_entry_notification_issue(entry, errors)
        label = format_entry_summary_label(
            display_index=display_index,
            entry=entry,
            errors=errors,
            has_issues=has_notification_issue,
            tag_label_map=label_map,
        )
        with st.expander(label):
            st.caption(f"Entry UUID: {entry_uuid}")
            if st.button("Edit Entry", key=f"btn_full_edit_{entry_uuid}"):
                start_full_edit(entry_uuid, tag_snapshot.active_registry)
            if errors:
                for error in errors:
                    st.error(error)
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

    col_prev, col_next, _pagination_spacer = st.columns([1, 1, 2])
    with col_prev:
        if st.button(
            "Previous",
            disabled=(pagination.page == 0),
            width="stretch",
            key="ee_btn_prev",
        ):
            st.session_state.edit_entry_page = pagination.page - 1
            st.rerun()
    with col_next:
        if st.button(
            "Next",
            disabled=(pagination.page >= pagination.last_page),
            width="stretch",
            key="ee_btn_next",
        ):
            st.session_state.edit_entry_page = pagination.page + 1
            st.rerun()
