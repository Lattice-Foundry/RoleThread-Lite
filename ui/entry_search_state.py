"""Shared entry-search session state for loaded dataset pages."""
from __future__ import annotations

import streamlit as st

from core.entry_search import (
    DEFAULT_SEARCH_SCOPES,
    EntrySearchOptions,
    SEARCH_MATCH_CONTAINS,
    SEARCH_MATCH_MODES,
    SEARCH_SCOPE_ASSISTANT,
    SEARCH_SCOPE_SYSTEM,
    SEARCH_SCOPE_USER,
)

ENTRY_SEARCH_QUERY_KEY = "entry_search_query"
ENTRY_SEARCH_INCLUDE_SYSTEM_KEY = "entry_search_include_system"
ENTRY_SEARCH_INCLUDE_USER_KEY = "entry_search_include_user"
ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY = "entry_search_include_assistant"
ENTRY_SEARCH_MATCH_MODE_KEY = "entry_search_match_mode"
ENTRY_SEARCH_DATASET_KEY = "entry_search_dataset_identifier"


def init_entry_search_state() -> None:
    """Initialize shared entry-search state without overwriting user choices."""

    st.session_state.setdefault(ENTRY_SEARCH_QUERY_KEY, "")
    st.session_state.setdefault(
        ENTRY_SEARCH_INCLUDE_SYSTEM_KEY,
        SEARCH_SCOPE_SYSTEM in DEFAULT_SEARCH_SCOPES,
    )
    st.session_state.setdefault(
        ENTRY_SEARCH_INCLUDE_USER_KEY,
        SEARCH_SCOPE_USER in DEFAULT_SEARCH_SCOPES,
    )
    st.session_state.setdefault(
        ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY,
        SEARCH_SCOPE_ASSISTANT in DEFAULT_SEARCH_SCOPES,
    )
    st.session_state.setdefault(ENTRY_SEARCH_MATCH_MODE_KEY, SEARCH_MATCH_CONTAINS)
    st.session_state.setdefault(ENTRY_SEARCH_DATASET_KEY, "")


def reset_entry_search_state(dataset_identifier: str = "") -> None:
    """Reset query, scopes, and match mode for a newly loaded dataset."""

    st.session_state[ENTRY_SEARCH_QUERY_KEY] = ""
    st.session_state[ENTRY_SEARCH_INCLUDE_SYSTEM_KEY] = (
        SEARCH_SCOPE_SYSTEM in DEFAULT_SEARCH_SCOPES
    )
    st.session_state[ENTRY_SEARCH_INCLUDE_USER_KEY] = (
        SEARCH_SCOPE_USER in DEFAULT_SEARCH_SCOPES
    )
    st.session_state[ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY] = (
        SEARCH_SCOPE_ASSISTANT in DEFAULT_SEARCH_SCOPES
    )
    st.session_state[ENTRY_SEARCH_MATCH_MODE_KEY] = SEARCH_MATCH_CONTAINS
    st.session_state[ENTRY_SEARCH_DATASET_KEY] = dataset_identifier or ""


def sync_entry_search_state_for_dataset(dataset_identifier: str | None) -> None:
    """Reset search state only when the loaded dataset identifier changes."""

    init_entry_search_state()
    normalized_identifier = dataset_identifier or ""
    if st.session_state.get(ENTRY_SEARCH_DATASET_KEY) != normalized_identifier:
        reset_entry_search_state(normalized_identifier)


def get_entry_search_options() -> EntrySearchOptions:
    """Return core search options from shared session state."""

    init_entry_search_state()
    scopes: list[str] = []
    if st.session_state.get(ENTRY_SEARCH_INCLUDE_SYSTEM_KEY):
        scopes.append(SEARCH_SCOPE_SYSTEM)
    if st.session_state.get(ENTRY_SEARCH_INCLUDE_USER_KEY):
        scopes.append(SEARCH_SCOPE_USER)
    if st.session_state.get(ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY):
        scopes.append(SEARCH_SCOPE_ASSISTANT)

    match_mode = st.session_state.get(ENTRY_SEARCH_MATCH_MODE_KEY)
    if match_mode not in SEARCH_MATCH_MODES:
        match_mode = SEARCH_MATCH_CONTAINS
        st.session_state[ENTRY_SEARCH_MATCH_MODE_KEY] = match_mode
    return EntrySearchOptions(scopes=tuple(scopes), match_mode=match_mode)


def set_entry_search_query(query: str) -> None:
    """Store the shared entry-search query."""

    init_entry_search_state()
    st.session_state[ENTRY_SEARCH_QUERY_KEY] = query or ""


def clear_entry_search_query() -> None:
    """Clear only the search query, preserving scope and match settings."""

    init_entry_search_state()
    st.session_state[ENTRY_SEARCH_QUERY_KEY] = ""


def set_entry_search_scope(
    *,
    include_system: bool | None = None,
    include_user: bool | None = None,
    include_assistant: bool | None = None,
) -> None:
    """Update one or more shared entry-search scope toggles."""

    init_entry_search_state()
    if include_system is not None:
        st.session_state[ENTRY_SEARCH_INCLUDE_SYSTEM_KEY] = bool(include_system)
    if include_user is not None:
        st.session_state[ENTRY_SEARCH_INCLUDE_USER_KEY] = bool(include_user)
    if include_assistant is not None:
        st.session_state[ENTRY_SEARCH_INCLUDE_ASSISTANT_KEY] = bool(include_assistant)


def set_entry_search_match_mode(match_mode: str) -> None:
    """Store a valid shared entry-search match mode."""

    init_entry_search_state()
    if match_mode not in SEARCH_MATCH_MODES:
        raise ValueError(f"Unsupported entry search match mode: {match_mode}")
    st.session_state[ENTRY_SEARCH_MATCH_MODE_KEY] = match_mode
