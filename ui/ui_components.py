"""Reusable UI rendering helpers.

These functions have no side-effects beyond writing to the Streamlit UI.
They do not touch session state beyond reading speaker-name preferences
for render_conversation_preview().
"""
import json
import re

import streamlit as st

from core.tag_registry import get_tag_registry_dict, prettify_tag_name

_ROLE_COLOR = {"user": "#1a73e8", "assistant": "#188038"}


def _format_preview_content(text: str) -> str:
    """Split content into dialogue (plain) and narration (orange italic).

    Text inside double-quotes is treated as dialogue and left unstyled.
    Everything else is narration and rendered orange + italic.
    """
    parts = re.split(r'(".*?")', text, flags=re.DOTALL)
    out = ""
    for part in parts:
        if not part:
            continue
        if part.startswith('"') and part.endswith('"') and len(part) >= 2:
            out += part
        else:
            out += f"<span style='color:#e67e22;font-style:italic'>{part}</span>"
    return out


def render_json_preview(entry: dict, expanded: bool = False) -> None:
    """Render a collapsible JSON preview for a dataset entry."""
    with st.expander("Preview JSON", expanded=expanded):
        st.code(json.dumps(entry, ensure_ascii=False, indent=2), language="json")


def render_message_preview(
    messages: list[dict],
    include_system: bool = True,
) -> None:
    """Render a formatted read-only preview of saved entry messages."""
    _COLOR = {"system": "#555", "user": "#1a73e8", "assistant": "#188038"}
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        if role == "system" and not include_system:
            continue
        content = msg.get("content", "")
        color = _COLOR.get(role, "#000")
        if role == "system":
            body = f"<span style='color:#f1c40f'>{content}</span>"
        else:
            body = _format_preview_content(content)
        st.markdown(
            f"<span style='color:{color};font-weight:bold;"
            f"text-transform:uppercase'>{role or '?'}:</span> {body}",
            unsafe_allow_html=True,
        )
        st.write("")


def render_conversation_preview(turns_now: list[dict], prefix: str) -> None:  # noqa: ARG001
    """Render the read-only conversation preview for an editor instance."""
    # prefix is intentionally unused — reserved for future per-editor settings
    _ = prefix

    _SPEAKER_LABEL = {
        "user": st.session_state.preview_user_name,
        "assistant": st.session_state.preview_assistant_name,
    }

    _preview_turns = [t for t in turns_now if t["content"].strip()]
    if not _preview_turns:
        st.caption("Your conversation will appear here as you write…")
        return

    for _pt in _preview_turns:
        _role = _pt["role"]
        _color = _ROLE_COLOR.get(_role, "#000")
        _name = _SPEAKER_LABEL.get(_role, _role.upper())
        _body = _format_preview_content(_pt["content"])
        st.markdown(
            f"<span style='color:{_color};font-weight:bold'>{_name.upper()}:</span> {_body}",
            unsafe_allow_html=True,
        )
        st.write("")


def calculate_exchange_metrics(turns_now: list[dict], planned_exchanges: int) -> dict:
    """Compute editor planning counts for the current turn list."""
    total_slots = len(turns_now) // 2
    current_exchanges = sum(
        1
        for pi in range(0, len(turns_now), 2)
        if (
            pi + 1 < len(turns_now)
            and turns_now[pi]["content"].strip()
            and turns_now[pi + 1]["content"].strip()
        )
    )
    blank_pairs = sum(
        1
        for pi in range(0, len(turns_now), 2)
        if pi + 1 < len(turns_now) and (
            not turns_now[pi]["content"].strip()
            or not turns_now[pi + 1]["content"].strip()
        )
    )
    return {
        "current_exchanges": current_exchanges,
        "total_slots": total_slots,
        "blank_pairs": blank_pairs,
        "overage": max(0, total_slots - planned_exchanges),
    }


def render_tag_multiselects(prefix: str) -> list[str]:
    """Render tag multiselects and return the combined selected slugs."""
    _registry = get_tag_registry_dict()
    if not _registry:
        # Graceful fallback: DB not seeded yet — use hardcoded TAGS
        from core.dataset import TAGS as _TAGS  # local import avoids circular dep
        _registry = _TAGS

    _COLS_PER_ROW = 5
    selected_tags: list[str] = []
    _cat_items = list(_registry.items())
    for _row_start in range(0, max(1, len(_cat_items)), _COLS_PER_ROW):
        _chunk = _cat_items[_row_start : _row_start + _COLS_PER_ROW]
        _row_cols = st.columns(_COLS_PER_ROW)
        for col, (category, options) in zip(_row_cols, _chunk):
            with col:
                chosen = st.multiselect(
                    f"{category} tags",
                    options=options,
                    format_func=prettify_tag_name,
                    key=f"{prefix}_tags_{category}",
                )
                selected_tags.extend(chosen)
    return selected_tags
