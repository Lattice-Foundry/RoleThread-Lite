"""Reusable UI rendering helpers.

These functions have no side-effects beyond writing to the Streamlit UI.
They do not touch session state beyond reading speaker-name preferences
for render_conversation_preview().
"""
import json
import re

import streamlit as st

from dataset import TAGS

# ── Role colors (shared with render_turn_builder in ui_create.py) ────────────
_ROLE_COLOR = {"user": "#1a73e8", "assistant": "#188038"}


# ── Narration / dialogue formatter ────────────────────────────────────────────

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
            out += part  # dialogue — plain/default color
        else:
            out += f"<span style='color:#e67e22;font-style:italic'>{part}</span>"
    return out


# ── Preview render helpers ────────────────────────────────────────────────────

def render_json_preview(entry: dict, expanded: bool = False) -> None:
    """Render a collapsible JSON preview for a dataset entry."""
    with st.expander("Preview JSON", expanded=expanded):
        st.code(json.dumps(entry, ensure_ascii=False, indent=2), language="json")


def render_message_preview(
    messages: list[dict],
    include_system: bool = True,
) -> None:
    """Render a formatted read-only preview of a saved entry's message list.

    System messages are rendered in yellow; user and assistant messages use
    their respective role colors with narration/dialogue formatting applied
    via _format_preview_content().  Unknown or malformed messages are
    rendered safely without raising.
    """
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
    """Render the read-only conversation preview for an editor instance.

    Iterates turns_now, applying narration/dialogue formatting via
    _format_preview_content and speaker labels from preferences.
    Shows an empty-state caption when no turns have content.

    prefix is reserved for future use (e.g. per-editor preview settings).
    """
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


# ── Tag selector helper ───────────────────────────────────────────────────────

def render_tag_multiselects(prefix: str) -> list[str]:
    """Render per-category tag multiselects and return the combined selected tags.

    Renders one st.multiselect per category using widget keys
    ``{prefix}_tags_{category}``.  Safe to call multiple times in the same
    render pass — Streamlit deduplicates by key.
    """
    selected_tags: list[str] = []
    tag_cols = st.columns(len(TAGS))
    for col, (category, options) in zip(tag_cols, TAGS.items()):
        with col:
            chosen = st.multiselect(
                f"{category} tags", options=options, key=f"{prefix}_tags_{category}"
            )
            selected_tags.extend(chosen)
    return selected_tags
