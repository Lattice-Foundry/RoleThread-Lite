"""Archived/imported tag display and assignment flows."""

import streamlit as st

from core.text_helpers import count_phrase
from ui.flash_messages import enqueue_flash
from ui.tag_management.formatting import archived_tag_label_html
from ui.tag_management_helpers import (
    selected_assignable_archived_slugs,
    validate_pending_archived_assignment,
)
from services.tag_lifecycle_service import assign_archived_imported_tags_to_category


def render_archived_tags(tag_snapshot, registry: list[dict]) -> None:
    """Render archived/imported tag assignment UI."""

    st.divider()
    st.subheader("Archived Tags")
    st.caption(
        "These tags are known to LoreForge but are not active or trusted. "
        "Imported tags need a category before they appear in normal tag pickers. "
        "Deleted tags can be restored later."
    )

    archived_tags = tag_snapshot.visible_archived_tags
    if st.session_state.pop("_tm_clear_archived_selection", False):
        for tag in archived_tags:
            st.session_state[f"tm_archived_select_{tag['slug']}"] = False

    if not archived_tags:
        st.info("No archived tags.")
        return

    assignable_archived_tags = [
        tag for tag in archived_tags if tag.get("can_assign_to_category")
    ]

    for tag in archived_tags:
        select_col, label_col, action_col = st.columns([0.35, 7.65, 3], gap="small")
        badge = tag["visible_badge"]
        with select_col:
            if tag.get("selectable"):
                st.checkbox(
                    "Select archived tag",
                    key=f"tm_archived_select_{tag['slug']}",
                    label_visibility="collapsed",
                )
            else:
                st.checkbox(
                    "Archived tag is not assignable",
                    key=f"tm_archived_select_disabled_{tag['slug']}",
                    value=False,
                    disabled=True,
                    label_visibility="collapsed",
                )
        with label_col:
            st.markdown(
                archived_tag_label_html(tag, badge),
                unsafe_allow_html=True,
            )
        with action_col:
            st.empty()

    if assignable_archived_tags:
        _render_assignment_controls(archived_tags=archived_tags, registry=registry)

    _render_pending_assignment(archived_tags=archived_tags, registry=registry)


def _render_assignment_controls(*, archived_tags: list[dict], registry: list[dict]) -> None:
    category_name_to_slug: dict[str, str] = {
        cat["name"]: cat["slug"] for cat in registry
    }
    if not category_name_to_slug:
        st.info("Create an active category before assigning archived tags.")
        return

    assign_select_col, _assign_select_spacer = st.columns([1, 3])
    with assign_select_col:
        selected_assign_category: str | None = st.selectbox(
            "Assign selected archived tags to",
            options=list(category_name_to_slug.keys()),
            key="tm_archived_assign_category",
        )
    selected_archived_slugs = selected_assignable_archived_slugs(
        archived_tags=archived_tags,
        selected_by_slug={
            tag["slug"]: st.session_state.get(f"tm_archived_select_{tag['slug']}", False)
            for tag in archived_tags
        },
    )

    assign_button_col, _assign_button_spacer = st.columns([1, 5])
    with assign_button_col:
        if st.button(
            "Assign Selected",
            key="btn_tm_assign_archived",
            disabled=not selected_archived_slugs or selected_assign_category is None,
            width="stretch",
        ):
            st.session_state["tm_pending_archived_assignment"] = {
                "tag_slugs": selected_archived_slugs,
                "category_slug": category_name_to_slug[selected_assign_category],
                "category_name": selected_assign_category,
            }
            st.rerun()


def _render_pending_assignment(*, archived_tags: list[dict], registry: list[dict]) -> None:
    pending_assignment = st.session_state.get("tm_pending_archived_assignment")
    selected_archived_slugs = selected_assignable_archived_slugs(
        archived_tags=archived_tags,
        selected_by_slug={
            tag["slug"]: st.session_state.get(f"tm_archived_select_{tag['slug']}", False)
            for tag in archived_tags
        },
    )
    category_slugs = {cat["slug"] for cat in registry}
    validated_pending_assignment = validate_pending_archived_assignment(
        pending_assignment=pending_assignment,
        selected_slugs=selected_archived_slugs,
        category_slugs=category_slugs,
    )
    if pending_assignment and not validated_pending_assignment:
        st.session_state.pop("tm_pending_archived_assignment", None)
        st.warning("Archived tag assignment was refreshed because the selection changed.")
    pending_assignment = validated_pending_assignment
    if not pending_assignment:
        return

    pending_count = len(pending_assignment["tag_slugs"])
    pending_category = pending_assignment["category_name"]
    st.warning(
        f"Assign {count_phrase(pending_count, 'archived tag')} "
        f"to {pending_category}? "
        "These tags will become active and appear in normal tag pickers."
    )
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button(
            "Confirm Assignment",
            key="btn_tm_confirm_archived_assignment",
            type="primary",
        ):
            result = assign_archived_imported_tags_to_category(
                tag_slugs=pending_assignment["tag_slugs"],
                category_slug=pending_assignment["category_slug"],
            )
            if result.ok:
                enqueue_flash("success", result.message)
                st.session_state.pop("tm_pending_archived_assignment", None)
                st.session_state["_tm_clear_archived_selection"] = True
                st.rerun()
            else:
                st.error(result.message)
                for error in result.errors:
                    st.caption(error)
                st.session_state.pop("tm_pending_archived_assignment", None)
    with cancel_col:
        if st.button("Cancel", key="btn_tm_cancel_archived_assignment"):
            st.session_state.pop("tm_pending_archived_assignment", None)
            st.rerun()

