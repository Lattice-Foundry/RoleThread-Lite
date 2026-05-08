"""Reusable UI rendering helpers.

These functions have no side-effects beyond writing to the Streamlit UI.
They do not touch session state beyond reading speaker-name preferences
for render_conversation_preview().
"""
import json
import re

import streamlit as st

from core.tag_registry import get_tag_registry_dict, prettify_tag_name

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


# ── Editor planning metrics ───────────────────────────────────────────────────

def calculate_exchange_metrics(turns_now: list[dict], planned_exchanges: int) -> dict:
    """Compute planning metrics for an entry editor's current turn list.

    Pure function — no Streamlit dependency.  Used by both Create Entry and
    Full Edit to drive planning warnings and save-button gating.

    Returns:
        {
            "current_exchanges": int,  # fully-filled user/assistant pairs
            "total_slots":       int,  # total pair slots (filled or blank)
            "blank_pairs":       int,  # pairs with at least one empty side
            "overage":           int,  # slots beyond planned_exchanges
        }
    """
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


# ── Tag selector helper ───────────────────────────────────────────────────────

def render_tag_multiselects(prefix: str) -> list[str]:
    """Render per-category tag multiselects and return the combined selected tags.

    Renders one ``st.multiselect`` per category using widget keys
    ``{prefix}_tags_{category}``.  Options are tag slugs; the ``format_func``
    displays pretty human-readable names (e.g. "Emotional Awareness").

    Falls back to the hardcoded ``core.dataset.TAGS`` dict if the DB registry
    is empty (e.g. before the first successful seed).

    Safe to call multiple times in the same render pass — Streamlit
    deduplicates by key.
    """
    _registry = get_tag_registry_dict()
    if not _registry:
        # Graceful fallback: DB not seeded yet — use hardcoded TAGS
        from core.dataset import TAGS as _TAGS  # local import avoids circular dep
        _registry = _TAGS

    selected_tags: list[str] = []
    tag_cols = st.columns(max(1, len(_registry)))
    for col, (category, options) in zip(tag_cols, _registry.items()):
        with col:
            chosen = st.multiselect(
                f"{category} tags",
                options=options,
                format_func=prettify_tag_name,
                key=f"{prefix}_tags_{category}",
            )
            selected_tags.extend(chosen)
    return selected_tags
