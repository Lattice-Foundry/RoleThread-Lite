"""Small reusable guidance banners and page navigation CTAs."""

from __future__ import annotations

import streamlit as st


def navigate_to_page(page: str) -> None:
    """Switch the sidebar page and rerun."""

    st.session_state.page = page
    st.rerun()


def render_page_cta(label: str, target_page: str, *, key: str) -> None:
    """Render a compact navigation button."""

    if st.button(label, key=key):
        navigate_to_page(target_page)


def render_manage_dataset_cta(*, key: str) -> None:
    """Render the standard empty-state Manage Dataset CTA."""

    render_page_cta("Go to Manage Dataset →", "Manage Dataset", key=key)


def render_recommended_action(
    message: str,
    *,
    button_label: str,
    target_page: str,
    key: str,
) -> None:
    """Render a non-blocking next-action banner with a page switch button."""

    st.info(message)
    action_col, _spacer = st.columns([1, 4])
    with action_col:
        render_page_cta(button_label, target_page, key=key)
