"""Session helpers for Insights-to-Manage entry deep links."""

import streamlit as st


STATS_FILTER_UUIDS_KEY = "stats_filter_uuids"
STATS_FILTER_LABEL_KEY = "stats_filter_label"


def navigate_to_entries(entry_uuids: list[str] | tuple[str, ...], label: str) -> None:
    """Open Manage Dataset focused on the given entry UUIDs."""

    st.session_state[STATS_FILTER_UUIDS_KEY] = set(entry_uuids)
    st.session_state[STATS_FILTER_LABEL_KEY] = label
    st.session_state.entry_page = 0
    st.session_state["manage_select_all_mode"] = False
    st.session_state.page = "Manage Dataset"
    st.rerun()


def clear_stats_entry_filter() -> None:
    """Clear any active Insights deep-link filter."""

    st.session_state.pop(STATS_FILTER_UUIDS_KEY, None)
    st.session_state.pop(STATS_FILTER_LABEL_KEY, None)
    st.session_state.entry_page = 0
