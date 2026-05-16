"""Small shared search form helpers for documentation-style pages."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class DocumentSearchState:
    """Current query and result visibility for a documentation search form."""

    query: str
    results_visible: bool


def show_document_search_results(query_key: str, results_visible_key: str) -> None:
    """Show results when the current search query has visible text."""

    query = str(st.session_state.get(query_key) or "").strip()
    st.session_state[results_visible_key] = bool(query)


def clear_document_search(query_key: str, results_visible_key: str) -> None:
    """Clear a documentation search query and hide its result list."""

    st.session_state[query_key] = ""
    st.session_state[results_visible_key] = False


def render_document_search_controls(
    *,
    form_key: str,
    input_label: str,
    query_key: str,
    results_visible_key: str,
    search_button_key: str,
    clear_button_key: str,
) -> DocumentSearchState:
    """Render the shared Help/FAQ search form and return its state."""

    with st.form(form_key, clear_on_submit=False):
        query = st.text_input(input_label, key=query_key)
        search_col, clear_col, _ = st.columns([0.125, 0.125, 0.75])
        with search_col:
            st.form_submit_button(
                "Search",
                key=search_button_key,
                type="primary",
                width="stretch",
                on_click=show_document_search_results,
                args=(query_key, results_visible_key),
            )
        with clear_col:
            st.form_submit_button(
                "Clear",
                key=clear_button_key,
                width="stretch",
                on_click=clear_document_search,
                args=(query_key, results_visible_key),
            )

    return DocumentSearchState(
        query=str(query or ""),
        results_visible=bool(st.session_state.get(results_visible_key)),
    )
