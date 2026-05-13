"""Filter and pagination controls for the Manage Dataset page."""
from dataclasses import dataclass
from typing import Any

import streamlit as st

from core.character_display import build_character_display_cache
from core.dataset import filter_entry_pairs_by_tags
from core.entry_search import EntrySearchOptions, filter_entries_by_search
from core.tag_registry import prettify_tag_name
from ui.browser_helpers import (
    DEFAULT_PAGE_SIZE,
    MATCH_MODE_OPTIONS,
    PAGE_SIZE_OPTIONS,
    build_filter_tag_state,
    calculate_pagination,
    normalize_untagged_selection,
    slice_visible_pairs,
)
from ui.entry_search_controls import (
    entry_search_has_enabled_scope,
    format_entry_search_no_results_message,
    is_entry_search_query_active,
    render_entry_search_controls,
)
from ui.entry_search_state import (
    ENTRY_SEARCH_QUERY_KEY,
    get_entry_search_options,
)


@dataclass(frozen=True)
class ManageFilterResult:
    """Current Manage Dataset filter and pagination state."""

    filter_tags: list[str]
    match_mode: str
    total_filtered: int
    total_all: int
    per_page: int
    last_page: int
    current_page: int
    start: int
    end: int
    filtered_pairs: list[tuple[str, dict]]
    visible_pairs: list[tuple[str, dict]]
    character_display_cache: dict[str, dict[int, str]]
    search_query: str
    search_active: bool
    search_options: EntrySearchOptions

    @property
    def has_entries(self) -> bool:
        return bool(self.visible_pairs)


def apply_manage_entry_filters(
    entry_pairs: list[tuple[str, dict]],
    *,
    filter_tags: list[str],
    tag_match_mode: str,
    search_query: str,
    search_options: EntrySearchOptions,
) -> list[tuple[str, dict]]:
    """Apply Manage filters in order: tags first, then entry search."""

    tag_filtered_pairs = filter_entry_pairs_by_tags(
        entry_pairs,
        selected_tags=filter_tags,
        match_mode=tag_match_mode,
    )
    return filter_entries_by_search(
        tag_filtered_pairs,
        search_query,
        search_options,
    )


def render_filters(
    *,
    entries: list[dict],
    all_pairs: list[tuple[str, dict]],
    tag_snapshot: Any,
    untagged_key: str,
) -> ManageFilterResult | None:
    """Render filter controls and return the current visible page."""

    label_map = tag_snapshot.tag_label_map_with_untagged
    all_known_slugs = tag_snapshot.active_tag_slugs

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

    if "filter_tags_pending" in st.session_state:
        st.session_state["filter_tags"] = st.session_state.pop("filter_tags_pending")

    filter_state = build_filter_tag_state(
        entries=entries,
        selected_tags=st.session_state.get("filter_tags", []),
        only_used_tags=only_used,
        all_known_tags=all_known_slugs,
        untagged_key=untagged_key,
    )
    available = filter_state.available_tags
    if filter_state.selected_tags_changed:
        st.session_state["filter_tags"] = filter_state.clamped_selected_tags

    filter_col, mode_col = st.columns([3, 1])
    with filter_col:
        filter_tags = st.multiselect(
            "Filter entries by tag",
            options=available,
            format_func=lambda x: label_map.get(x, prettify_tag_name(x)),
            key="filter_tags",
            on_change=_reset_page,
        )

    normalized_filter_tags = normalize_untagged_selection(
        selected_tags=filter_tags,
        available_tags=available,
        untagged_key=untagged_key,
    )
    if normalized_filter_tags != filter_tags:
        st.session_state["filter_tags_pending"] = normalized_filter_tags
        st.rerun()

    with mode_col:
        match_mode = st.radio(
            "Match mode",
            options=MATCH_MODE_OPTIONS,
            key="filter_match_mode",
            on_change=_reset_page,
        )

    render_entry_search_controls(on_change=_reset_page)
    search_query = st.session_state.get(ENTRY_SEARCH_QUERY_KEY, "")
    search_options = get_entry_search_options()

    filtered_pairs = apply_manage_entry_filters(
        all_pairs,
        filter_tags=filter_tags,
        tag_match_mode=match_mode,
        search_query=search_query,
        search_options=search_options,
    )

    saved_per_page = st.session_state.get("entries_per_page", DEFAULT_PAGE_SIZE)
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
            key="_entries_per_page_select",
        )
    if selected_per_page != st.session_state.get("entries_per_page"):
        st.session_state.entries_per_page = selected_per_page
        st.session_state.entry_page = 0
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
        return None

    pagination = calculate_pagination(
        total_items=total_filtered,
        requested_page=st.session_state.get("entry_page", 0),
        per_page_setting=st.session_state.entries_per_page,
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

    return ManageFilterResult(
        filter_tags=filter_tags,
        match_mode=match_mode,
        total_filtered=total_filtered,
        total_all=total_all,
        per_page=pagination.per_page,
        last_page=pagination.last_page,
        current_page=pagination.page,
        start=pagination.start,
        end=pagination.end,
        filtered_pairs=filtered_pairs,
        visible_pairs=visible_pairs,
        character_display_cache=character_display_cache,
        search_query=search_query,
        search_active=search_active,
        search_options=search_options,
    )
