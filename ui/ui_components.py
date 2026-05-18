"""Reusable UI rendering helpers.

These functions have no side-effects beyond writing to the Streamlit UI.
They do not touch session state beyond reading speaker-name preferences
for render_conversation_preview().
"""
import json
import re

import streamlit as st

from core.tag_registry import prettify_tag_name
from ui.html_helpers import escape_html, escape_upper_html
from ui.theme import COLOR_ASSISTANT, COLOR_USER

_NON_STANDARD_ROLE_COLOR = "#c2185b"
_ROLE_COLOR = {"user": COLOR_USER, "assistant": COLOR_ASSISTANT}
_CODE_PREVIEW_BACKGROUND = "#0E1117"
_CODE_PREVIEW_BORDER = "rgba(232, 232, 232, 0.18)"
_CODE_PREVIEW_HEADING = COLOR_USER
_CODE_PREVIEW_BODY = COLOR_ASSISTANT
_PROMPT_CHUNK_HEADING_RE = re.compile(r"^\[[A-Z0-9 _-]+]$")


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
        escaped_part = escape_html(part)
        if part.startswith('"') and part.endswith('"') and len(part) >= 2:
            out += escaped_part
        else:
            out += (
                f"<span style='color:#e67e22;font-style:italic'>"
                f"{escaped_part}</span>"
            )
    return out


def render_json_preview(entry: dict, expanded: bool = False) -> None:
    """Render a collapsible JSON preview for a dataset entry."""
    with st.expander("Preview JSON", expanded=expanded):
        st.code(json.dumps(entry, ensure_ascii=False, indent=2), language="json")


def is_prompt_chunk_heading(line: str) -> bool:
    """Return True when a prompt preview line is a placeholder chunk heading."""

    return bool(_PROMPT_CHUNK_HEADING_RE.fullmatch(line.strip()))


def render_prompt_preview_html(prompt_text: str) -> str:
    """Return syntax-styled HTML for a compiled generation prompt preview."""

    rendered_lines: list[str] = []
    for line in prompt_text.splitlines():
        css_class = (
            "rolethread-preview-heading"
            if is_prompt_chunk_heading(line)
            else "rolethread-preview-body"
        )
        rendered_lines.append(
            f'<span class="{css_class}">{escape_html(line)}</span>'
        )
    return "\n".join(rendered_lines)


def _script_json_string(value: str) -> str:
    """Return JSON text safe to embed in an inline script block."""

    return (
        json.dumps(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def build_copyable_text_preview_document(
    title: str,
    text: str,
    *,
    copy_button_label: str = "Copy",
    copied_label: str = "Copied.",
) -> tuple[str, int]:
    """Return the HTML document and height for a copyable prompt preview."""

    escaped_title = escape_html(title)
    escaped_copy_label = escape_html(copy_button_label)
    escaped_copied_label = escape_html(copied_label)
    prompt_json = _script_json_string(text)
    preview_html = render_prompt_preview_html(text)
    line_count = max(1, text.count("\n") + 1)
    height = min(620, max(220, line_count * 22 + 92))
    document = f"""
        <div class="rolethread-copyable-preview">
          <div class="rolethread-copyable-preview-toolbar">
            <span>{escaped_title}</span>
            <button
              class="rolethread-copyable-preview-copy"
              type="button"
              onclick="copyRoleThreadPreviewText()"
            >
              {escaped_copy_label}
            </button>
            <span
              id="rolethread-copyable-preview-status"
              class="rolethread-copyable-preview-status"
              aria-live="polite"
            ></span>
          </div>
          <pre class="rolethread-copyable-preview-body"><code>{preview_html}</code></pre>
        </div>
        <script>
        const roleThreadPreviewText = {prompt_json};
        async function copyRoleThreadPreviewText() {{
          const status = document.getElementById("rolethread-copyable-preview-status");
          try {{
            await navigator.clipboard.writeText(roleThreadPreviewText);
            status.textContent = "{escaped_copied_label}";
          }} catch (error) {{
            status.textContent = "Copy failed.";
          }}
          window.setTimeout(() => {{
            status.textContent = "";
          }}, 2400);
        }}
        </script>
        <style>
        .rolethread-copyable-preview {{
          background: {_CODE_PREVIEW_BACKGROUND};
          border: 1px solid {_CODE_PREVIEW_BORDER};
          border-radius: 0.45rem;
          color: {_CODE_PREVIEW_BODY};
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
            "Liberation Mono", "Courier New", monospace;
          overflow: hidden;
        }}
        .rolethread-copyable-preview-toolbar {{
          align-items: center;
          border-bottom: 1px solid {_CODE_PREVIEW_BORDER};
          color: {_CODE_PREVIEW_HEADING};
          display: flex;
          font-size: 0.86rem;
          font-weight: 650;
          gap: 0.65rem;
          justify-content: flex-start;
          padding: 0.55rem 0.75rem;
        }}
        .rolethread-copyable-preview-copy {{
          background: transparent;
          border: 1px solid {_CODE_PREVIEW_BORDER};
          border-radius: 0.35rem;
          color: #E8E8E8;
          cursor: pointer;
          font: inherit;
          font-weight: 600;
          margin-left: auto;
          padding: 0.25rem 0.7rem;
        }}
        .rolethread-copyable-preview-copy:hover {{
          border-color: {_CODE_PREVIEW_HEADING};
          color: {_CODE_PREVIEW_HEADING};
        }}
        .rolethread-copyable-preview-status {{
          color: {_CODE_PREVIEW_BODY};
          min-width: 4.5rem;
        }}
        .rolethread-copyable-preview-body {{
          background: {_CODE_PREVIEW_BACKGROUND};
          box-sizing: border-box;
          line-height: 1.48;
          margin: 0;
          max-height: 520px;
          overflow: auto;
          padding: 0.8rem 0.9rem;
          white-space: pre-wrap;
        }}
        .rolethread-preview-heading {{
          color: {_CODE_PREVIEW_HEADING};
          font-weight: 700;
        }}
        .rolethread-preview-body {{
          color: {_CODE_PREVIEW_BODY};
        }}
        </style>
        """
    return document, height


def render_copyable_text_preview(
    title: str,
    text: str,
    *,
    expanded: bool = True,
    copy_button_label: str = "Copy",
    copied_label: str = "Copied.",
) -> None:
    """Render a themed, copyable non-JSON text preview."""

    with st.expander(title, expanded=expanded):
        document, height = build_copyable_text_preview_document(
            title,
            text,
            copy_button_label=copy_button_label,
            copied_label=copied_label,
        )
        st.iframe(
            document,
            height=height,
        )


def render_message_preview(
    messages: list[dict],
    include_system: bool = True,
    display_names: dict[int, str] | None = None,
) -> None:
    """Render a formatted read-only preview of saved entry messages."""
    _COLOR = {"system": "#555", "user": COLOR_USER, "assistant": COLOR_ASSISTANT}
    display_names = display_names or {}
    for turn_index, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "")
        if role == "system" and not include_system:
            continue
        display_name = display_names.get(turn_index, role or "?")
        content = msg.get("content", "")
        color = _COLOR.get(role, _NON_STANDARD_ROLE_COLOR)
        if role == "system":
            body = f"<span style='color:#f1c40f'>{escape_html(content)}</span>"
        else:
            body = _format_preview_content(content)
        st.markdown(
            f"<span style='color:{color};font-weight:bold;"
            f"text-transform:uppercase'>{escape_upper_html(display_name)}:</span> "
            f"{body}",
            unsafe_allow_html=True,
        )
        st.write("")


def render_conversation_preview(
    turns_now: list[dict],
    prefix: str,  # noqa: ARG001
    display_names: dict[int, str] | None = None,
) -> None:
    """Render the read-only conversation preview for an editor instance."""
    # prefix is intentionally unused — reserved for future per-editor settings
    _ = prefix
    display_names = display_names or {}

    _SPEAKER_LABEL = {
        "user": st.session_state.preview_user_name,
        "assistant": st.session_state.preview_assistant_name,
    }

    _preview_turns = [
        (turn_index, turn)
        for turn_index, turn in enumerate(turns_now)
        if turn["content"].strip()
    ]
    if not _preview_turns:
        st.caption("Your conversation will appear here as you write…")
        return

    for _turn_index, _pt in _preview_turns:
        _role = _pt["role"]
        _color = _ROLE_COLOR.get(_role, _NON_STANDARD_ROLE_COLOR)
        _name = display_names.get(_turn_index, _SPEAKER_LABEL.get(_role, _role.upper()))
        _body = _format_preview_content(_pt["content"])
        st.markdown(
            f"<span style='color:{_color};font-weight:bold'>"
            f"{escape_upper_html(_name)}:</span> {_body}",
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


def render_tag_multiselects(
    prefix: str,
    active_registry: dict[str, list[str]],
) -> list[str]:
    """Render tag multiselects and return the combined selected slugs."""
    _registry = active_registry
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
