"""Reusable UI actions for saving system prompts to the template library."""

from __future__ import annotations

import streamlit as st

from core.system_prompt_library import create_system_prompt_template


def render_save_system_prompt_template_action(
    *,
    prompt_text: str,
    prefix: str,
) -> None:
    """Render a small save-as-template flow for the current prompt text."""

    text = str(prompt_text or "").strip()
    pending_key = f"{prefix}_save_prompt_template_pending"
    name_key = f"{prefix}_save_prompt_template_name"

    button_col, _spacer = st.columns([1, 3])
    with button_col:
        if st.button(
            "Save as template",
            key=f"{prefix}_save_prompt_template_btn",
            disabled=not text,
            width="stretch",
        ):
            st.session_state[pending_key] = True
            st.session_state[name_key] = _default_template_name(text)
            st.rerun()

    if not st.session_state.get(pending_key):
        return

    st.text_input("Template name", key=name_key)
    save_col, cancel_col, _confirm_spacer = st.columns([1, 1, 3])
    with save_col:
        if st.button("Save Template", key=f"{prefix}_confirm_save_prompt_template"):
            try:
                create_system_prompt_template(
                    st.session_state.get(name_key, ""),
                    text,
                )
            except Exception as exc:
                st.error(str(exc))
                return
            st.session_state.pop(pending_key, None)
            st.session_state.pop(name_key, None)
            st.success("Prompt saved to library.")
            st.rerun()
    with cancel_col:
        if st.button("Cancel", key=f"{prefix}_cancel_save_prompt_template"):
            st.session_state.pop(pending_key, None)
            st.session_state.pop(name_key, None)
            st.rerun()


def _default_template_name(prompt_text: str) -> str:
    compact = " ".join(prompt_text.split())
    if len(compact) <= 30:
        return compact
    return compact[:30].rstrip()
