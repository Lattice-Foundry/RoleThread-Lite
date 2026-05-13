"""Reusable Streamlit controls for shared entry search state."""
from __future__ import annotations

import streamlit as st

from core.entry_search import (
    SEARCH_MATCH_ALL_WORDS,
    SEARCH_MATCH_CONTAINS,
    SEARCH_MATCH_EXACT_PHRASE,
    SEARCH_MATCH_MODES,
)
from ui.entry_search_state import (
    ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY,
    ENTRY_SEARCH_INCLUDE_SYSTEM_KEY,
    ENTRY_SEARCH_INCLUDE_USER_KEY,
    ENTRY_SEARCH_MATCH_MODE_KEY,
    ENTRY_SEARCH_QUERY_KEY,
    clear_entry_search_query,
    init_entry_search_state,
)

MATCH_MODE_LABELS = {
    SEARCH_MATCH_CONTAINS: "Contains",
    SEARCH_MATCH_ALL_WORDS: "All Words",
    SEARCH_MATCH_EXACT_PHRASE: "Exact Phrase",
}


def format_entry_search_match_mode(match_mode: str) -> str:
    """Return the UI label for an entry-search match mode."""

    return MATCH_MODE_LABELS.get(match_mode, match_mode)


def render_entry_search_controls() -> None:
    """Render reusable entry-search controls bound to shared session state."""

    init_entry_search_state()
    _repair_invalid_match_mode()

    st.markdown("**Search Entries**")
    st.caption("Search applies after tag filters and before pagination.")

    query_col, clear_col = st.columns([4, 1])
    with query_col:
        st.text_input(
            "Search query",
            key=ENTRY_SEARCH_QUERY_KEY,
            placeholder="Find conversation text...",
        )
    with clear_col:
        st.button(
            "Clear Search",
            key="entry_search_clear_button",
            disabled=not bool(st.session_state.get(ENTRY_SEARCH_QUERY_KEY, "")),
            on_click=clear_entry_search_query,
        )

    scope_cols = st.columns(3)
    with scope_cols[0]:
        st.checkbox("Include System", key=ENTRY_SEARCH_INCLUDE_SYSTEM_KEY)
    with scope_cols[1]:
        st.checkbox("Include User", key=ENTRY_SEARCH_INCLUDE_USER_KEY)
    with scope_cols[2]:
        st.checkbox("Include Assistant", key=ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY)

    st.radio(
        "Match mode",
        options=SEARCH_MATCH_MODES,
        format_func=format_entry_search_match_mode,
        horizontal=True,
        key=ENTRY_SEARCH_MATCH_MODE_KEY,
    )

    render_entry_search_summary()


def render_entry_search_summary() -> None:
    """Render a small status line for the current shared search state."""

    init_entry_search_state()
    query = str(st.session_state.get(ENTRY_SEARCH_QUERY_KEY, "") or "").strip()
    if query:
        st.caption(f'Search active: "{query}"')
    else:
        st.caption("No entry search query active.")


def _repair_invalid_match_mode() -> None:
    if st.session_state.get(ENTRY_SEARCH_MATCH_MODE_KEY) not in SEARCH_MATCH_MODES:
        st.session_state[ENTRY_SEARCH_MATCH_MODE_KEY] = SEARCH_MATCH_CONTAINS
