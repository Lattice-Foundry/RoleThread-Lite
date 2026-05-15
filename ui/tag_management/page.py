"""Tag Management page coordinator."""

import streamlit as st

from core.tag_registry import get_tag_registry_snapshot
from ui.flash_messages import render_flash_messages
from ui.tag_management.active_tags import render_tag_registry
from ui.tag_management.archived_tags import render_archived_tags
from ui.tag_management.create_forms import (
    render_add_custom_tag_form,
    render_create_category_form,
)
from ui.tag_management.formatting import inject_tag_management_styles


def render_tag_management_page() -> None:
    """Render the Tag Management page."""

    if st.session_state.pop("_tm_clear_cat_name", False):
        st.session_state["tm_new_cat_name"] = ""
    if st.session_state.pop("_tm_clear_tag_name", False):
        st.session_state["tm_new_tag_name"] = ""

    st.subheader("Tag Management")
    inject_tag_management_styles()
    st.info(
        "Custom tags can be edited, renamed, or deleted. Built-in tags are "
        "locked to maintain consistency across datasets."
    )
    render_flash_messages()

    tag_snapshot = get_tag_registry_snapshot()
    registry = tag_snapshot.active_categories
    total_categories = len(registry)

    render_tag_registry(tag_snapshot, registry)
    render_create_category_form(tag_snapshot, total_categories)
    render_add_custom_tag_form(registry)
    render_archived_tags(tag_snapshot, registry)

