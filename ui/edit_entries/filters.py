"""Filtering helpers for the Edit Entries browser."""

import streamlit as st

from core.entry_search import (
    EntrySearchOptions,
    SEARCH_MATCH_CONTAINS,
    filter_entries_by_search,
)
from core.dataset import filter_entry_pairs_by_tags
from ui.browser_helpers import MATCH_MODE_ANY
from ui.entry_search_state import (
    ENTRY_SEARCH_DATASET_KEY,
    ENTRY_SEARCH_MATCH_MODE_KEY,
    reset_entry_search_state,
)


UNTAGGED_FILTER_KEY = "__untagged__"


def apply_edit_entry_filters(
    entry_pairs: list[tuple[str, dict]],
    *,
    filter_tags: list[str],
    tag_match_mode: str,
    search_query: str,
    search_options: EntrySearchOptions,
) -> list[tuple[str, dict]]:
    """Apply Edit Entries filters in order: tags first, then entry search."""

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


def clear_edit_filters() -> None:
    st.session_state.edit_filter_tags = []
    st.session_state.edit_filter_match_mode = MATCH_MODE_ANY
    st.session_state.edit_entry_page = 0
    reset_entry_search_state(st.session_state.get(ENTRY_SEARCH_DATASET_KEY, ""))


def edit_filters_active(
    *,
    filter_tags: list[str],
    match_mode: str,
    search_query: str,
) -> bool:
    return bool(
        filter_tags
        or match_mode != MATCH_MODE_ANY
        or search_query.strip()
        or st.session_state.get(ENTRY_SEARCH_MATCH_MODE_KEY) != SEARCH_MATCH_CONTAINS
    )

