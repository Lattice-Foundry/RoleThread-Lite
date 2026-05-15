"""Active tag/category display and confirmation flows."""

import streamlit as st

from core.dataset import get_entry_tags
from core.tag_registry import prettify_tag_name, slugify_tag_name
from ui.flash_messages import enqueue_flash
from ui.tag_management.confirmations import (
    render_pending_category_delete,
    render_pending_category_rename,
    render_pending_tag_delete,
    render_pending_tag_edit,
)
from ui.tag_management.formatting import active_tag_detail_html
from ui.theme import COLOR_BUILT_IN_BADGE, COLOR_CUSTOM_BADGE


def render_tag_registry(tag_snapshot, registry: list[dict]) -> None:
    """Render active tag/category registry and pending confirmations."""

    st.divider()
    st.subheader("Tag Registry")

    if not registry:
        st.info("No tags found. The tag registry may not be seeded yet.")
        return

    active_custom_slugs = {
        tag["slug"]
        for category in registry
        for tag in category["tags"]
        if not tag["is_builtin"]
    }
    category_name_to_slug: dict[str, str] = {
        category["name"]: category["slug"] for category in registry
    }
    category_slug_to_name: dict[str, str] = {
        category["slug"]: category["name"] for category in registry
    }
    default_category_slugs = tag_snapshot.default_category_slugs
    active_custom_category_slugs = {
        category["slug"]
        for category in registry
        if category["slug"] not in default_category_slugs
    }
    active_empty_custom_category_slugs = {
        category["slug"]
        for category in registry
        if category["slug"] in active_custom_category_slugs
        and not category["tags"]
    }

    for cat in registry:
        tag_count = len(cat["tags"])
        plural = "s" if tag_count != 1 else ""
        is_custom_category = cat["slug"] in active_custom_category_slugs
        is_category_renaming = (
            st.session_state.get("tm_renaming_category_slug") == cat["slug"]
        )
        with st.expander(
            f"{cat['name']} ({tag_count} tag{plural})",
            expanded=is_category_renaming,
            width=700,
        ):
            _render_category_header(cat, is_custom_category)
            if is_category_renaming:
                _render_category_rename_editor(cat)
            if not cat["tags"]:
                st.caption("No tags in this category yet.")
            else:
                for tag in cat["tags"]:
                    _render_active_tag_row(
                        tag=tag,
                        cat=cat,
                        category_name_to_slug=category_name_to_slug,
                    )

    render_pending_tag_edit(
        active_custom_slugs=active_custom_slugs,
        category_slug_to_name=category_slug_to_name,
    )
    render_pending_tag_delete(active_custom_slugs=active_custom_slugs)
    render_pending_category_rename(
        active_custom_category_slugs=active_custom_category_slugs,
    )
    render_pending_category_delete(
        active_empty_custom_category_slugs=active_empty_custom_category_slugs,
    )


def _render_category_header(cat: dict, is_custom_category: bool) -> None:
    st.caption(f"slug: {cat['slug']}")
    if not is_custom_category:
        return

    rename_col, delete_col, spacer = st.columns([1.35, 1.35, 7.3], gap="small")
    with rename_col:
        if st.button("Rename Category", key=f"btn_tm_rename_category_{cat['slug']}"):
            st.session_state["tm_renaming_category_slug"] = cat["slug"]
            st.session_state[f"tm_category_rename_input_{cat['slug']}"] = cat["name"]
            st.session_state.pop("tm_pending_category_rename", None)
            st.rerun()
    with delete_col:
        if st.button("Delete Category", key=f"btn_tm_delete_category_{cat['slug']}"):
            if cat["tags"]:
                st.warning("Move or delete all tags in this category before deleting it.")
            else:
                st.session_state["tm_pending_category_delete"] = {
                    "category_slug": cat["slug"],
                    "display_name": cat["name"],
                }
                st.session_state.pop("tm_pending_category_rename", None)
                st.session_state.pop("tm_renaming_category_slug", None)
                st.rerun()
    with spacer:
        st.empty()


def _render_category_rename_editor(cat: dict) -> None:
    category_rename_key = f"tm_category_rename_input_{cat['slug']}"
    if category_rename_key not in st.session_state:
        st.session_state[category_rename_key] = cat["name"]
    new_category_name = st.text_input("Rename category:", key=category_rename_key)
    new_category_slug = slugify_tag_name(new_category_name)
    new_category_pretty = prettify_tag_name(new_category_slug)
    st.caption(f"Canonical ID Preview: `{new_category_slug}`")
    save_col, cancel_col, spacer = st.columns([1.1, 0.8, 7.1], gap="small")
    with save_col:
        if st.button(
            "Save Rename",
            key=f"btn_tm_save_category_rename_{cat['slug']}",
            type="primary",
            disabled=not new_category_slug,
        ):
            if new_category_slug == cat["slug"]:
                enqueue_flash("success", "Rename canceled; category name is unchanged.")
                st.session_state.pop("tm_renaming_category_slug", None)
                st.session_state.pop("tm_pending_category_rename", None)
                st.rerun()
            st.session_state["tm_pending_category_rename"] = {
                "old_slug": cat["slug"],
                "old_display_name": cat["name"],
                "new_slug": new_category_slug,
                "new_display_name": new_category_pretty,
            }
            st.rerun()
    with cancel_col:
        if st.button("Cancel", key=f"btn_tm_cancel_category_rename_{cat['slug']}"):
            st.session_state.pop("tm_renaming_category_slug", None)
            st.session_state.pop("tm_pending_category_rename", None)
            st.rerun()
    with spacer:
        st.empty()


def _render_active_tag_row(
    *,
    tag: dict,
    cat: dict,
    category_name_to_slug: dict[str, str],
) -> None:
    badge_color = COLOR_BUILT_IN_BADGE if tag["is_builtin"] else COLOR_CUSTOM_BADGE
    badge_label = "built-in" if tag["is_builtin"] else "custom"
    is_editing = st.session_state.get("tm_editing_tag_slug") == tag["slug"]
    if is_editing:
        _render_active_tag_editor(
            tag=tag,
            cat=cat,
            category_name_to_slug=category_name_to_slug,
        )
        return

    action_col, detail_col = st.columns([1.5, 8.5], gap="small")
    with action_col:
        if tag["is_builtin"]:
            st.empty()
        else:
            edit_link_col, delete_link_col = st.columns([0.7, 1], gap="small")
            with edit_link_col:
                if st.button("Edit", key=f"btn_tm_edit_{tag['slug']}", type="tertiary"):
                    st.session_state["tm_editing_tag_slug"] = tag["slug"]
                    st.session_state[f"tm_edit_name_input_{tag['slug']}"] = tag["name"]
                    st.session_state[f"tm_edit_category_select_{tag['slug']}"] = cat["name"]
                    st.session_state.pop("tm_pending_tag_edit", None)
                    st.session_state.pop("tm_pending_tag_delete", None)
                    st.rerun()
            with delete_link_col:
                if st.button(
                    ":red[Delete]",
                    key=f"btn_tm_delete_{tag['slug']}",
                    type="tertiary",
                ):
                    usage_count = sum(
                        1
                        for entry in st.session_state.get("loaded_entries", [])
                        if tag["slug"] in get_entry_tags(entry)
                    )
                    st.session_state["tm_pending_tag_delete"] = {
                        "tag_slug": tag["slug"],
                        "display_name": tag["name"],
                        "usage_count": usage_count,
                    }
                    st.session_state.pop("tm_pending_tag_edit", None)
                    st.session_state.pop("tm_editing_tag_slug", None)
                    st.rerun()
    with detail_col:
        st.markdown(
            active_tag_detail_html(tag, badge_label, badge_color),
            unsafe_allow_html=True,
        )


def _render_active_tag_editor(
    *,
    tag: dict,
    cat: dict,
    category_name_to_slug: dict[str, str],
) -> None:
    edit_name_key = f"tm_edit_name_input_{tag['slug']}"
    edit_category_key = f"tm_edit_category_select_{tag['slug']}"
    if edit_name_key not in st.session_state:
        st.session_state[edit_name_key] = tag["name"]
    if edit_category_key not in st.session_state:
        st.session_state[edit_category_key] = cat["name"]
    new_display_name = st.text_input("Display Name", key=edit_name_key)
    category_names = list(category_name_to_slug.keys())
    current_category_index = (
        category_names.index(cat["name"]) if cat["name"] in category_names else 0
    )
    selected_category_name = st.selectbox(
        "Category",
        options=category_names,
        index=current_category_index,
        key=edit_category_key,
    )
    new_slug = slugify_tag_name(new_display_name)
    new_pretty = prettify_tag_name(new_slug)
    st.caption(f"Canonical ID Preview: `{new_slug}`")

    save_col, cancel_col, spacer = st.columns([1.1, 0.8, 7.1], gap="small")
    with save_col:
        if st.button(
            "Save Edit",
            key=f"btn_tm_save_edit_{tag['slug']}",
            type="primary",
            disabled=not new_slug,
        ):
            selected_category_slug = category_name_to_slug[selected_category_name]
            if new_slug == tag["slug"] and selected_category_slug == cat["slug"]:
                enqueue_flash("success", "Edit canceled; tag is unchanged.")
                st.session_state.pop("tm_editing_tag_slug", None)
                st.session_state.pop("tm_pending_tag_edit", None)
                st.rerun()
            st.session_state["tm_pending_tag_edit"] = {
                "old_slug": tag["slug"],
                "old_display_name": tag["name"],
                "old_category_slug": cat["slug"],
                "old_category_name": cat["name"],
                "new_slug": new_slug,
                "new_display_name": new_pretty,
                "category_slug": selected_category_slug,
                "category_name": selected_category_name,
            }
            st.rerun()
    with cancel_col:
        if st.button("Cancel", key=f"btn_tm_cancel_edit_{tag['slug']}"):
            st.session_state.pop("tm_editing_tag_slug", None)
            st.session_state.pop("tm_pending_tag_edit", None)
            st.rerun()
    with spacer:
        st.empty()
