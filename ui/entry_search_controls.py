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
    get_entry_search_options,
    init_entry_search_state,
)

MATCH_MODE_LABELS = {
    SEARCH_MATCH_CONTAINS: "Contains",
    SEARCH_MATCH_ALL_WORDS: "All Words",
    SEARCH_MATCH_EXACT_PHRASE: "Exact Phrase",
}

SCOPE_LABELS = {
    ENTRY_SEARCH_INCLUDE_SYSTEM_KEY: "System",
    ENTRY_SEARCH_INCLUDE_USER_KEY: "User",
    ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY: "Assistant",
}


def format_entry_search_match_mode(match_mode: str) -> str:
    """Return the UI label for an entry-search match mode."""

    return MATCH_MODE_LABELS.get(match_mode, match_mode)


def render_entry_search_controls(on_change=None, *, compact_layout: bool = False) -> None:
    """Render reusable entry-search controls bound to shared session state."""

    init_entry_search_state()
    _repair_invalid_match_mode()

    st.markdown("**Search Entries**")
    st.caption("Search applies after tag filters and before pagination.")

    if compact_layout:
        _render_stacked_scope_controls(on_change)
        _render_compact_search_query_controls(on_change)
        render_entry_search_summary()
        return

    query_col, clear_col = st.columns([4, 1])
    with query_col:
        st.text_input(
            "Search query",
            key=ENTRY_SEARCH_QUERY_KEY,
            placeholder="Find conversation text...",
            on_change=on_change,
        )
    with clear_col:
        st.button(
            "Clear Search",
            key="entry_search_clear_button",
            disabled=not is_entry_search_query_active(),
            on_click=_clear_query_and_notify,
            args=(on_change,),
        )

    _render_horizontal_scope_controls(on_change)

    st.radio(
        "Match mode",
        options=SEARCH_MATCH_MODES,
        format_func=format_entry_search_match_mode,
        horizontal=True,
        key=ENTRY_SEARCH_MATCH_MODE_KEY,
        on_change=on_change,
    )

    render_entry_search_summary()


def _render_compact_search_query_controls(on_change) -> None:
    query_col, mode_col, _query_spacer = st.columns([3, 1, 2])
    with query_col:
        st.text_input(
            "Search query",
            key=ENTRY_SEARCH_QUERY_KEY,
            placeholder="Find conversation text...",
            on_change=on_change,
        )
        clear_col, _clear_spacer = st.columns([1, 2])
        with clear_col:
            st.button(
                "Clear Search",
                key="entry_search_clear_button",
                disabled=not is_entry_search_query_active(),
                on_click=_clear_query_and_notify,
                args=(on_change,),
                width="stretch",
            )
    with mode_col:
        st.radio(
            "Match mode",
            options=SEARCH_MATCH_MODES,
            format_func=format_entry_search_match_mode,
            horizontal=False,
            key=ENTRY_SEARCH_MATCH_MODE_KEY,
            on_change=on_change,
        )


def _render_stacked_scope_controls(on_change) -> None:
    st.checkbox(
        "Include System",
        key=ENTRY_SEARCH_INCLUDE_SYSTEM_KEY,
        on_change=on_change,
    )
    st.checkbox(
        "Include User",
        key=ENTRY_SEARCH_INCLUDE_USER_KEY,
        on_change=on_change,
    )
    st.checkbox(
        "Include Assistant",
        key=ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY,
        on_change=on_change,
    )


def _render_horizontal_scope_controls(on_change) -> None:
    scope_cols = st.columns(3)
    with scope_cols[0]:
        st.checkbox(
            "Include System",
            key=ENTRY_SEARCH_INCLUDE_SYSTEM_KEY,
            on_change=on_change,
        )
    with scope_cols[1]:
        st.checkbox(
            "Include User",
            key=ENTRY_SEARCH_INCLUDE_USER_KEY,
            on_change=on_change,
        )
    with scope_cols[2]:
        st.checkbox(
            "Include Assistant",
            key=ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY,
            on_change=on_change,
        )


def render_entry_search_summary() -> None:
    """Render a small status line for the current shared search state."""

    init_entry_search_state()
    query = normalized_entry_search_query()
    if not query:
        return

    match_mode = format_entry_search_match_mode(
        st.session_state.get(ENTRY_SEARCH_MATCH_MODE_KEY, SEARCH_MATCH_CONTAINS)
    )
    scopes = _format_enabled_scope_summary()
    st.caption(f'Search active: "{query}" | {match_mode} | {scopes}')


def normalized_entry_search_query(query: str | None = None) -> str:
    """Return the stripped user-facing entry-search query."""

    if query is None:
        query = st.session_state.get(ENTRY_SEARCH_QUERY_KEY, "")
    return str(query or "").strip()


def is_entry_search_query_active(query: str | None = None) -> bool:
    """Return True when the entry-search query contains non-whitespace text."""

    return bool(normalized_entry_search_query(query))


def entry_search_has_enabled_scope(options=None) -> bool:
    """Return True when at least one entry-search message role is enabled."""

    options = options or get_entry_search_options()
    return bool(options.scopes)


def format_entry_search_no_results_message(
    *,
    has_tag_filters: bool,
    search_active: bool,
    scopes_enabled: bool,
) -> str:
    """Return consistent no-results copy for entry search and tag filters."""

    if search_active and not scopes_enabled:
        return "Enable at least one message role to search."
    if search_active and has_tag_filters:
        return "No entries match the current filters and search."
    if search_active:
        return "No entries match the current search."
    return "No entries match the current filters."


def _repair_invalid_match_mode() -> None:
    if st.session_state.get(ENTRY_SEARCH_MATCH_MODE_KEY) not in SEARCH_MATCH_MODES:
        st.session_state[ENTRY_SEARCH_MATCH_MODE_KEY] = SEARCH_MATCH_CONTAINS


def _clear_query_and_notify(on_change) -> None:
    clear_entry_search_query()
    if on_change:
        on_change()


def _format_enabled_scope_summary() -> str:
    enabled = [
        label
        for key, label in SCOPE_LABELS.items()
        if st.session_state.get(key)
    ]
    return ", ".join(enabled) if enabled else "no roles selected"
