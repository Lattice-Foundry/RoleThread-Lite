"""Reusable system prompt template selector controls."""
from __future__ import annotations

from collections.abc import Callable, Iterable

import streamlit as st

from core.system_prompt_library import get_all_system_prompt_templates

_CUSTOM_OPTION = ""
_CUSTOM_LABEL = "Custom"


def render_system_prompt_template_selector(
    *,
    target_key: str,
    select_key: str,
    label: str = "Load from library",
    mirror_keys: Iterable[str] = (),
    on_apply: Callable[[str], None] | None = None,
) -> bool:
    """Render a template dropdown that fills one prompt text-area state key."""

    templates = get_all_system_prompt_templates()
    if not templates:
        return False

    options = [_CUSTOM_OPTION] + [template.slug for template in templates]
    template_by_slug = {template.slug: template for template in templates}
    selected_slug = st.selectbox(
        label,
        options=options,
        format_func=lambda slug: _format_template_option(slug, template_by_slug),
        key=select_key,
    )

    applied_key = f"_{select_key}_last_applied"
    if selected_slug == _CUSTOM_OPTION:
        st.session_state[applied_key] = _CUSTOM_OPTION
        return False

    if selected_slug == st.session_state.get(applied_key):
        return False

    template = template_by_slug.get(selected_slug)
    if template is None:
        return False

    st.session_state[target_key] = template.content
    for mirror_key in mirror_keys:
        st.session_state[mirror_key] = template.content
    st.session_state[applied_key] = selected_slug
    if on_apply is not None:
        on_apply(template.content)
    st.caption(f"Loaded \"{template.name}\". You can edit the prompt below.")
    return True


def _format_template_option(slug: str, template_by_slug: dict) -> str:
    if slug == _CUSTOM_OPTION:
        return _CUSTOM_LABEL
    template = template_by_slug.get(slug)
    return template.name if template is not None else slug
