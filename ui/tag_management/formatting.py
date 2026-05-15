"""Formatting helpers for Tag Management UI."""

import streamlit as st

from ui.html_helpers import escape_html
from ui.theme import COLOR_SECONDARY_TEXT


def active_tag_detail_html(tag: dict, badge_label: str, badge_color: str) -> str:
    """Return escaped HTML for one active tag detail row."""

    return (
        f"<strong>{escape_html(tag.get('name', ''))}</strong> &nbsp; "
        f"<code>{escape_html(tag.get('slug', ''))}</code> &nbsp; "
        f"<span style='color:{badge_color};font-size:0.82em'>"
        f"{escape_html(badge_label)}</span>"
    )


def archived_tag_label_html(tag: dict, badge: str) -> str:
    """Return escaped HTML for one archived tag row."""

    return (
        "<div style='padding-top:0.52rem;line-height:1.5'>"
        f"<strong>{escape_html(tag.get('display_name', ''))}</strong> &nbsp; "
        f"<span style='color:{COLOR_SECONDARY_TEXT};font-size:0.82em'>"
        f"{escape_html(badge)}</span></div>"
    )


def inject_tag_management_styles() -> None:
    """Inject small Tag Management action-link overrides."""

    st.markdown(
        """
        <style>
        div[data-testid="stButton"] button[kind="tertiary"] {
            padding: 0;
            min-height: 1.25rem;
            line-height: 1.25rem;
            color: #b7791f;
            text-decoration: underline;
            background: transparent;
            border: 0;
            box-shadow: none;
        }
        div[data-testid="stButton"] button[kind="tertiary"] p {
            color: #b7791f;
            text-decoration: underline;
            font-size: 0.92rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

