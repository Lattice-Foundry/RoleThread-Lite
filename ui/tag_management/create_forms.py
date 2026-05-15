"""Custom category and tag creation forms."""

import streamlit as st

from core.tag_registry import prettify_tag_name, slugify_tag_name
from ui.flash_messages import enqueue_flash
from services.tag_lifecycle_service import create_custom_category, create_custom_tag


def render_create_category_form(tag_snapshot, total_categories: int) -> None:
    """Render the Create Custom Category section."""

    st.divider()
    st.subheader("Create Custom Category")

    at_limit = total_categories >= tag_snapshot.max_active_categories
    if at_limit:
        st.info(
            f"Category limit reached. "
            f"This version supports {tag_snapshot.max_active_categories} active categories."
        )

    cat_name_col, _cat_name_spacer = st.columns([1, 1])
    with cat_name_col:
        new_cat_name: str = st.text_input(
            "Category Name",
            key="tm_new_cat_name",
            placeholder="e.g. Tone",
            disabled=at_limit,
        )

    if new_cat_name.strip():
        cat_slug_preview = slugify_tag_name(new_cat_name)
        cat_name_preview = prettify_tag_name(cat_slug_preview)
        st.caption(
            f"slug: `{cat_slug_preview}` - display name will be saved as: "
            f"**{cat_name_preview}**"
        )

    cat_button_col, _cat_button_spacer = st.columns([1, 5])
    with cat_button_col:
        if st.button(
            "Create Category",
            key="btn_tm_create_cat",
            type="primary",
            disabled=at_limit or not new_cat_name.strip(),
            width="stretch",
        ):
            ok, msg = create_custom_category(new_cat_name)
            if ok:
                enqueue_flash("success", msg)
                st.session_state["_tm_clear_cat_name"] = True
                st.rerun()
            else:
                st.error(msg)


def render_add_custom_tag_form(registry: list[dict]) -> None:
    """Render the Add Custom Tag section."""

    st.divider()
    st.subheader("Add Custom Tag")

    if not registry:
        st.info("No active categories available. Create a category first.")
        return

    cat_name_to_id: dict[str, int] = {cat["name"]: cat["id"] for cat in registry}
    cat_names = list(cat_name_to_id.keys())

    cat_select_col, _cat_select_spacer = st.columns([1, 3])
    with cat_select_col:
        selected_cat_name: str | None = st.selectbox(
            "Category",
            options=cat_names,
            key="tm_tag_cat_select",
        )
    selected_cat_id: int | None = (
        cat_name_to_id.get(selected_cat_name) if selected_cat_name else None
    )

    tag_name_col, _tag_name_spacer = st.columns([1, 1])
    with tag_name_col:
        new_tag_name: str = st.text_input(
            "Tag Name",
            key="tm_new_tag_name",
            placeholder="e.g. Playful Banter",
        )

    if new_tag_name.strip():
        tag_slug_preview = slugify_tag_name(new_tag_name)
        tag_name_preview = prettify_tag_name(tag_slug_preview)
        st.caption(
            f"slug: `{tag_slug_preview}` - display name will be saved as: "
            f"**{tag_name_preview}**"
        )

    tag_button_col, _tag_button_spacer = st.columns([1, 5])
    with tag_button_col:
        if st.button(
            "Add Tag",
            key="btn_tm_add_tag",
            type="primary",
            disabled=selected_cat_id is None or not new_tag_name.strip(),
            width="stretch",
        ):
            ok, msg = create_custom_tag(selected_cat_id, new_tag_name)
            if ok:
                enqueue_flash("success", msg)
                st.session_state["_tm_clear_tag_name"] = True
                st.rerun()
            else:
                st.error(msg)
