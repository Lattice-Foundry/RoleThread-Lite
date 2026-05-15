"""Tag Management confirmation flows."""

import streamlit as st

from core.dataset import build_uuid_index
from ui.flash_messages import enqueue_flash
from ui.session_state import apply_dataset_operation_result
from ui.tag_management_helpers import (
    validate_pending_category_delete,
    validate_pending_category_rename,
    validate_pending_tag_delete,
    validate_pending_tag_edit,
)
from services.tag_lifecycle_service import (
    delete_active_tag,
    delete_empty_custom_category,
    edit_active_tag,
    rename_custom_category,
)


def render_pending_tag_edit(
    *,
    active_custom_slugs: set[str],
    category_slug_to_name: dict[str, str],
) -> None:
    pending_edit = st.session_state.get("tm_pending_tag_edit")
    validated_pending_edit = validate_pending_tag_edit(
        pending_edit=pending_edit,
        current_edit_slug=st.session_state.get("tm_editing_tag_slug"),
        active_custom_slugs=active_custom_slugs,
        active_category_slugs=set(category_slug_to_name),
    )
    if pending_edit and not validated_pending_edit:
        st.session_state.pop("tm_pending_tag_edit", None)
        st.warning("Tag edit was refreshed because the row changed.")
    pending_edit = validated_pending_edit
    if not pending_edit:
        return

    name_changed = pending_edit["new_slug"] != pending_edit["old_slug"]
    category_changed = pending_edit["category_slug"] != pending_edit["old_category_slug"]
    if name_changed and category_changed:
        confirmation = (
            f"Edit tag \"{pending_edit['old_display_name']}\":\n\n"
            f"- Name: \"{pending_edit['new_display_name']}\"\n"
            f"- Category: {pending_edit['old_category_name']} -> "
            f"{pending_edit['category_name']}\n\n"
            "Existing dataset entries using this tag will also be updated."
        )
    elif name_changed:
        confirmation = (
            f"Edit tag \"{pending_edit['old_display_name']}\" to "
            f"\"{pending_edit['new_display_name']}\"?\n\n"
            "Existing dataset entries using this tag will also be updated."
        )
    else:
        confirmation = (
            f"Move tag \"{pending_edit['old_display_name']}\" from "
            f"\"{pending_edit['old_category_name']}\" to "
            f"\"{pending_edit['category_name']}\"?"
        )
    st.warning(confirmation)
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm Edit", key="btn_tm_confirm_tag_edit", type="primary"):
            result = edit_active_tag(
                old_slug=pending_edit["old_slug"],
                new_display_name=pending_edit["new_display_name"],
                category_slug=pending_edit["category_slug"],
                dataset_path=st.session_state.get("loaded_path", ""),
                entries=st.session_state.get("loaded_entries", []),
            )
            if result.ok:
                _adopt_dataset_result(result)
                enqueue_flash("success", result.message)
                st.session_state.pop("tm_editing_tag_slug", None)
                st.session_state.pop("tm_pending_tag_edit", None)
                st.rerun()
            else:
                st.error(result.message)
                for error in result.errors:
                    st.caption(error)
                st.session_state.pop("tm_pending_tag_edit", None)
    with cancel_col:
        if st.button("Cancel", key="btn_tm_cancel_tag_edit"):
            st.session_state.pop("tm_pending_tag_edit", None)
            st.rerun()


def render_pending_tag_delete(*, active_custom_slugs: set[str]) -> None:
    pending_delete = st.session_state.get("tm_pending_tag_delete")
    validated_pending_delete = validate_pending_tag_delete(
        pending_delete=pending_delete,
        active_custom_slugs=active_custom_slugs,
    )
    if pending_delete and not validated_pending_delete:
        st.session_state.pop("tm_pending_tag_delete", None)
        st.warning("Tag delete was refreshed because the row changed.")
    pending_delete = validated_pending_delete
    if not pending_delete:
        return

    delete_count = int(pending_delete.get("usage_count", 0) or 0)
    delete_entry_word = "entry" if delete_count == 1 else "entries"
    st.warning(
        f"Delete tag \"{pending_delete['display_name']}\"?\n\n"
        "This will remove the tag from active use and remove it from "
        "loaded dataset entries. The tag will move to Archived Tags as "
        f"Deleted.\n\nThis tag is currently used by {delete_count} "
        f"loaded {delete_entry_word}."
    )
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm Delete", key="btn_tm_confirm_tag_delete", type="primary"):
            result = delete_active_tag(
                tag_slug=pending_delete["tag_slug"],
                dataset_path=st.session_state.get("loaded_path", ""),
                entries=st.session_state.get("loaded_entries", []),
            )
            if result.ok:
                _adopt_dataset_result(result)
                enqueue_flash("success", result.message)
                st.session_state.pop("tm_pending_tag_delete", None)
                st.rerun()
            else:
                st.error(result.message)
                for error in result.errors:
                    st.caption(error)
                st.session_state.pop("tm_pending_tag_delete", None)
    with cancel_col:
        if st.button("Cancel", key="btn_tm_cancel_tag_delete"):
            st.session_state.pop("tm_pending_tag_delete", None)
            st.rerun()


def render_pending_category_rename(
    *,
    active_custom_category_slugs: set[str],
) -> None:
    pending_rename = st.session_state.get("tm_pending_category_rename")
    validated_pending_rename = validate_pending_category_rename(
        pending_rename=pending_rename,
        current_rename_slug=st.session_state.get("tm_renaming_category_slug"),
        active_custom_category_slugs=active_custom_category_slugs,
    )
    if pending_rename and not validated_pending_rename:
        st.session_state.pop("tm_pending_category_rename", None)
        st.warning("Category rename was refreshed because the category changed.")
    pending_rename = validated_pending_rename
    if not pending_rename:
        return

    st.warning(
        f"Rename category \"{pending_rename['old_display_name']}\" "
        f"to \"{pending_rename['new_display_name']}\"?\n\n"
        "Tags in this category will stay attached. Dataset entries will "
        "not be rewritten."
    )
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm Rename", key="btn_tm_confirm_category_rename", type="primary"):
            result = rename_custom_category(
                category_slug=pending_rename["old_slug"],
                new_display_name=pending_rename["new_display_name"],
            )
            if result.ok:
                enqueue_flash("success", result.message)
                st.session_state.pop("tm_renaming_category_slug", None)
                st.session_state.pop("tm_pending_category_rename", None)
                st.rerun()
            else:
                st.error(result.message)
                for error in result.errors:
                    st.caption(error)
                st.session_state.pop("tm_pending_category_rename", None)
    with cancel_col:
        if st.button("Cancel", key="btn_tm_cancel_category_confirm_rename"):
            st.session_state.pop("tm_pending_category_rename", None)
            st.rerun()


def render_pending_category_delete(
    *,
    active_empty_custom_category_slugs: set[str],
) -> None:
    pending_delete = st.session_state.get("tm_pending_category_delete")
    validated_pending_delete = validate_pending_category_delete(
        pending_delete=pending_delete,
        active_empty_custom_category_slugs=active_empty_custom_category_slugs,
    )
    if pending_delete and not validated_pending_delete:
        st.session_state.pop("tm_pending_category_delete", None)
        st.warning("Category delete was refreshed because the category changed.")
    pending_delete = validated_pending_delete
    if not pending_delete:
        return

    st.warning(
        f"Delete category \"{pending_delete['display_name']}\"?\n\n"
        "This category is empty and will be removed from the active registry."
    )
    confirm_col, cancel_col = st.columns(2)
    with confirm_col:
        if st.button("Confirm Delete", key="btn_tm_confirm_category_delete", type="primary"):
            result = delete_empty_custom_category(
                category_slug=pending_delete["category_slug"],
            )
            if result.ok:
                enqueue_flash("success", result.message)
                st.session_state.pop("tm_pending_category_delete", None)
                st.rerun()
            else:
                st.error(result.message)
                for error in result.errors:
                    st.caption(error)
                st.session_state.pop("tm_pending_category_delete", None)
    with cancel_col:
        if st.button("Cancel", key="btn_tm_cancel_category_delete"):
            st.session_state.pop("tm_pending_category_delete", None)
            st.rerun()


def _adopt_dataset_result(result) -> None:
    apply_dataset_operation_result(result)
    if result.entries is not None:
        st.session_state.loaded_entries = result.entries
        st.session_state.uuid_to_index = build_uuid_index(result.entries)

