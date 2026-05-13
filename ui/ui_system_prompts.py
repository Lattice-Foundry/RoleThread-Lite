"""System Prompt Library management page."""
from __future__ import annotations

import streamlit as st

from core.system_prompt_library import (
    create_system_prompt_template,
    delete_system_prompt_templates,
    get_all_system_prompt_templates,
    reactivate_system_prompt_template,
    update_system_prompt_template,
)
from core.text_helpers import count_phrase
from ui.flash_messages import enqueue_flash, render_flash_messages


def render_system_prompts_page() -> None:
    """Render system prompt template creation and management controls."""

    st.subheader("System Prompts")

    render_flash_messages()
    all_templates = get_all_system_prompt_templates(active_only=False)
    active_templates = [template for template in all_templates if template.is_active]
    inactive_templates = [template for template in all_templates if not template.is_active]
    selected = st.session_state.setdefault("selected_system_prompt_slugs", set())
    selected.intersection_update({template.slug for template in active_templates})

    if active_templates:
        _render_bulk_actions(active_templates, selected)
        _render_template_list(active_templates, selected)
    else:
        st.info(
            "No system prompt templates yet. Create reusable prompts to speed "
            "up entry creation."
        )

    st.divider()
    _render_create_template()
    _render_inactive_templates(inactive_templates)


def _render_bulk_actions(templates, selected: set[str]) -> None:
    col_select, col_clear, col_delete, _spacer = st.columns([1, 1, 1.2, 3])
    with col_select:
        if st.button("Select All", width="stretch"):
            st.session_state.selected_system_prompt_slugs = {
                template.slug for template in templates
            }
            st.rerun()
    with col_clear:
        if st.button("Deselect All", width="stretch"):
            st.session_state.selected_system_prompt_slugs = set()
            _clear_delete_confirmation()
            st.rerun()
    with col_delete:
        if st.button(
            "Delete Selected",
            disabled=not selected,
            width="stretch",
        ):
            st.session_state.pending_system_prompt_delete = sorted(selected)
            st.rerun()

    pending = st.session_state.get("pending_system_prompt_delete")
    if not pending:
        return

    active_slugs = {template.slug for template in templates}
    pending = [slug for slug in pending if slug in active_slugs]
    if not pending:
        _clear_delete_confirmation()
        return

    st.warning(
        f"Delete {count_phrase(len(pending), 'system prompt template')}? "
        "The template will be hidden from selectors, but existing entries are "
        "not affected."
    )
    confirm_col, cancel_col, _confirm_spacer = st.columns([1, 1, 4])
    with confirm_col:
        if st.button("Confirm Delete", type="primary"):
            deleted = delete_system_prompt_templates(pending)
            st.session_state.selected_system_prompt_slugs = set()
            _clear_delete_confirmation()
            enqueue_flash(
                "success",
                f"Deleted {count_phrase(len(deleted), 'system prompt template')}.",
            )
            st.rerun()
    with cancel_col:
        if st.button("Cancel Delete"):
            _clear_delete_confirmation()
            st.rerun()


def _render_template_list(templates, selected: set[str]) -> None:
    sorted_templates = sorted(
        templates,
        key=lambda template: template.name.lower(),
    )
    st.caption(
        f"{count_phrase(len(sorted_templates), 'active system prompt template')} "
        "in the library."
    )

    header = st.columns([0.5, 1.5, 1.3, 2.4, 1.4, 1])
    header[0].markdown("**Select**")
    header[1].markdown("**Name**")
    header[2].markdown("**Slug**")
    header[3].markdown("**Content Preview**")
    header[4].markdown("**Created**")
    header[5].markdown("**Actions**")

    for template in sorted_templates:
        _render_template_row(template, selected)


def _render_template_row(template, selected: set[str]) -> None:
    cols = st.columns([0.5, 1.5, 1.3, 2.4, 1.4, 1])
    with cols[0]:
        is_selected = st.checkbox(
            "Select",
            value=template.slug in selected,
            key=f"system_prompt_select_{template.slug}",
            label_visibility="collapsed",
        )
    if is_selected:
        selected.add(template.slug)
    else:
        selected.discard(template.slug)
    st.session_state.selected_system_prompt_slugs = selected

    cols[1].write(template.name)
    if template.description:
        cols[1].caption(template.description)
    cols[2].markdown(f"`{template.slug}`")
    cols[3].write(_content_preview(template.content))
    cols[4].write(_format_date(template.created_at))
    with cols[5]:
        if st.button("Edit", key=f"system_prompt_edit_{template.slug}"):
            st.session_state.editing_system_prompt_slug = template.slug
            st.rerun()

    if st.session_state.get("editing_system_prompt_slug") == template.slug:
        _render_edit_template(template)


def _render_edit_template(template) -> None:
    with st.container(border=True):
        st.markdown(f"**Edit {template.name}**")
        name = st.text_input(
            "Name",
            value=template.name,
            key=f"system_prompt_name_input_{template.slug}",
        )
        content = st.text_area(
            "Content",
            value=template.content,
            height=180,
            key=f"system_prompt_content_input_{template.slug}",
        )
        description = st.text_input(
            "Description",
            value=template.description or "",
            key=f"system_prompt_description_input_{template.slug}",
        )
        save_col, cancel_col, _spacer = st.columns([1, 1, 4])
        with save_col:
            if st.button("Save", type="primary", key=f"system_prompt_save_{template.slug}"):
                try:
                    update_system_prompt_template(
                        template.slug,
                        name=name,
                        content=content,
                        description=description,
                    )
                except Exception as exc:
                    st.error(str(exc))
                    return
                enqueue_flash("success", "System prompt template updated.")
                st.session_state.pop("editing_system_prompt_slug", None)
                st.rerun()
        with cancel_col:
            if st.button("Cancel", key=f"system_prompt_cancel_{template.slug}"):
                st.session_state.pop("editing_system_prompt_slug", None)
                st.rerun()


def _render_create_template() -> None:
    st.markdown("**Create System Prompt Template**")
    name = st.text_input("Template name", key="new_system_prompt_name")
    content = st.text_area(
        "Content",
        height=180,
        key="new_system_prompt_content",
    )
    description = st.text_input(
        "Description",
        key="new_system_prompt_description",
    )
    if st.button(
        "Create",
        type="primary",
        disabled=not name.strip() or not content.strip(),
    ):
        try:
            template = create_system_prompt_template(
                name,
                content,
                description=description.strip() or None,
            )
        except Exception as exc:
            st.error(str(exc))
            return
        enqueue_flash(
            "success",
            f"Created system prompt template \"{template.name}\".",
        )
        st.rerun()


def _render_inactive_templates(inactive_templates) -> None:
    if not inactive_templates:
        return

    with st.expander("Inactive System Prompt Templates", expanded=False):
        for template in sorted(inactive_templates, key=lambda item: item.name.lower()):
            cols = st.columns([1.6, 1.4, 2.4, 1])
            cols[0].write(template.name)
            cols[1].markdown(f"`{template.slug}`")
            cols[2].write(_content_preview(template.content, limit=100))
            with cols[3]:
                if st.button("Reactivate", key=f"system_prompt_reactivate_{template.slug}"):
                    if reactivate_system_prompt_template(template.slug):
                        enqueue_flash(
                            "success",
                            f"Reactivated \"{template.name}\".",
                        )
                    st.rerun()


def _content_preview(content: str, *, limit: int = 140) -> str:
    text = " ".join((content or "").split())
    if len(text) <= limit:
        return text
    cutoff = text[: max(0, limit - 3)].rstrip()
    if " " in cutoff:
        cutoff = cutoff.rsplit(" ", 1)[0]
    return f"{cutoff}..."


def _format_date(value) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)


def _clear_delete_confirmation() -> None:
    st.session_state.pop("pending_system_prompt_delete", None)
