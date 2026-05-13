"""Tag Management page — additive-only custom tag and category creation."""
import streamlit as st

from core.dataset import build_entry_registry, get_entry_tags
from core.tag_registry import (
    get_tag_registry_snapshot,
    prettify_tag_name,
    slugify_tag_name,
)
from core.text_helpers import count_phrase
from ui.flash_messages import enqueue_flash, render_flash_messages
from ui.session_state import apply_dataset_operation_result
from ui.tag_management_helpers import (
    selected_assignable_archived_slugs,
    validate_pending_archived_assignment,
    validate_pending_category_delete,
    validate_pending_category_rename,
    validate_pending_tag_delete,
    validate_pending_tag_edit,
)
from services.tag_lifecycle_service import (
    assign_archived_imported_tags_to_category,
    create_custom_category,
    create_custom_tag,
    delete_active_tag,
    delete_empty_custom_category,
    edit_active_tag,
    rename_custom_category,
)


def render_tag_management_page() -> None:
    """Render the Tag Management page."""
    # ── Pending field clears (must run before any widget renders) ─────────────
    # Direct session-state writes to a widget key are illegal after that widget
    # has already rendered in the same pass.  We set a flag before rerun and
    # apply the actual clear here, at the top, before the widgets exist.
    if st.session_state.pop("_tm_clear_cat_name", False):
        st.session_state["tm_new_cat_name"] = ""
    if st.session_state.pop("_tm_clear_tag_name", False):
        st.session_state["tm_new_tag_name"] = ""

    st.subheader("Tag Management")
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] button[kind="tertiary"] {
            padding: 0;
            min-height: 1.25rem;
            line-height: 1.25rem;
            color: #b7791f;
            text-decoration: underline;
            background: transparent;
            border: 0;
            box-shadow: none;
        }
        div[data-testid="stButton"] button[kind="tertiary"] p {
            color: #b7791f;
            text-decoration: underline;
            font-size: 0.92rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "Custom tag editing is intentionally conservative. Edit and Delete are "
        "available for custom active tags; merge and migration tools will come later."
    )

    # ── Flash message (shown at top, consumed on next render) ─────────────────
    render_flash_messages()

    _tag_snapshot = get_tag_registry_snapshot()
    registry = _tag_snapshot.active_categories
    total_categories = len(registry)

    # ── Section 1: Tag Registry ───────────────────────────────────────────────
    st.divider()
    st.subheader("Tag Registry")

    if not registry:
        st.info("No tags found. The tag registry may not be seeded yet.")
    else:
        _active_custom_slugs = {
            tag["slug"]
            for category in registry
            for tag in category["tags"]
            if not tag["is_builtin"]
        }
        _category_name_to_slug: dict[str, str] = {
            category["name"]: category["slug"] for category in registry
        }
        _category_slug_to_name: dict[str, str] = {
            category["slug"]: category["name"] for category in registry
        }
        _default_category_slugs = _tag_snapshot.default_category_slugs
        _active_custom_category_slugs = {
            category["slug"]
            for category in registry
            if category["slug"] not in _default_category_slugs
        }
        _active_empty_custom_category_slugs = {
            category["slug"]
            for category in registry
            if category["slug"] in _active_custom_category_slugs
            and not category["tags"]
        }
        for cat in registry:
            tag_count = len(cat["tags"])
            _plural = "s" if tag_count != 1 else ""
            _is_custom_category = cat["slug"] in _active_custom_category_slugs
            _is_category_renaming = (
                st.session_state.get("tm_renaming_category_slug") == cat["slug"]
            )
            with st.expander(
                f"{cat['name']} ({tag_count} tag{_plural})",
                expanded=_is_category_renaming,
            ):
                st.caption(f"slug: {cat['slug']}")
                if _is_custom_category:
                    _cat_action_rename_col, _cat_action_delete_col, _cat_action_spacer = st.columns(
                        [1.35, 1.35, 7.3],
                        gap="small",
                    )
                    with _cat_action_rename_col:
                        if st.button(
                            "Rename Category",
                            key=f"btn_tm_rename_category_{cat['slug']}",
                        ):
                            st.session_state["tm_renaming_category_slug"] = cat["slug"]
                            st.session_state[
                                f"tm_category_rename_input_{cat['slug']}"
                            ] = cat["name"]
                            st.session_state.pop("tm_pending_category_rename", None)
                            st.rerun()
                    with _cat_action_delete_col:
                        if st.button(
                            "Delete Category",
                            key=f"btn_tm_delete_category_{cat['slug']}",
                        ):
                            if cat["tags"]:
                                st.warning(
                                    "Move or delete all tags in this category "
                                    "before deleting it."
                                )
                            else:
                                st.session_state["tm_pending_category_delete"] = {
                                    "category_slug": cat["slug"],
                                    "display_name": cat["name"],
                                }
                                st.session_state.pop(
                                    "tm_pending_category_rename", None
                                )
                                st.session_state.pop(
                                    "tm_renaming_category_slug", None
                                )
                                st.rerun()
                    with _cat_action_spacer:
                        st.empty()
                if _is_category_renaming:
                    _category_rename_key = f"tm_category_rename_input_{cat['slug']}"
                    if _category_rename_key not in st.session_state:
                        st.session_state[_category_rename_key] = cat["name"]
                    _new_category_name = st.text_input(
                        "Rename category:",
                        key=_category_rename_key,
                    )
                    _new_category_slug = slugify_tag_name(_new_category_name)
                    _new_category_pretty = prettify_tag_name(_new_category_slug)
                    st.caption(f"Canonical ID Preview: `{_new_category_slug}`")
                    _cat_save_col, _cat_cancel_col, _cat_action_spacer = st.columns(
                        [1.1, 0.8, 7.1],
                        gap="small",
                    )
                    with _cat_save_col:
                        if st.button(
                            "Save Rename",
                            key=f"btn_tm_save_category_rename_{cat['slug']}",
                            type="primary",
                            disabled=not _new_category_slug,
                        ):
                            if _new_category_slug == cat["slug"]:
                                enqueue_flash(
                                    "success",
                                    "Rename canceled; category name is unchanged.",
                                )
                                st.session_state.pop(
                                    "tm_renaming_category_slug", None
                                )
                                st.session_state.pop(
                                    "tm_pending_category_rename", None
                                )
                                st.rerun()
                            st.session_state["tm_pending_category_rename"] = {
                                "old_slug": cat["slug"],
                                "old_display_name": cat["name"],
                                "new_slug": _new_category_slug,
                                "new_display_name": _new_category_pretty,
                            }
                            st.rerun()
                    with _cat_cancel_col:
                        if st.button(
                            "Cancel",
                            key=f"btn_tm_cancel_category_rename_{cat['slug']}",
                        ):
                            st.session_state.pop("tm_renaming_category_slug", None)
                            st.session_state.pop("tm_pending_category_rename", None)
                            st.rerun()
                    with _cat_action_spacer:
                        st.empty()
                if not cat["tags"]:
                    st.caption("No tags in this category yet.")
                else:
                    for tag in cat["tags"]:
                        _badge_color = "#888" if tag["is_builtin"] else "#1a73e8"
                        _badge_label = "built-in" if tag["is_builtin"] else "custom"
                        _is_editing = (
                            st.session_state.get("tm_editing_tag_slug")
                            == tag["slug"]
                        )
                        if _is_editing:
                            _edit_name_key = f"tm_edit_name_input_{tag['slug']}"
                            _edit_category_key = f"tm_edit_category_select_{tag['slug']}"
                            if _edit_name_key not in st.session_state:
                                st.session_state[_edit_name_key] = tag["name"]
                            if _edit_category_key not in st.session_state:
                                st.session_state[_edit_category_key] = cat["name"]
                            _new_display_name = st.text_input(
                                "Display Name",
                                key=_edit_name_key,
                            )
                            _category_names = list(_category_name_to_slug.keys())
                            _current_category_index = (
                                _category_names.index(cat["name"])
                                if cat["name"] in _category_names
                                else 0
                            )
                            _selected_category_name = st.selectbox(
                                "Category",
                                options=_category_names,
                                index=_current_category_index,
                                key=_edit_category_key,
                            )
                            _new_slug = slugify_tag_name(_new_display_name)
                            _new_pretty = prettify_tag_name(_new_slug)
                            st.caption(f"Canonical ID Preview: `{_new_slug}`")

                            _save_col, _cancel_col, _edit_action_spacer = st.columns(
                                [1.1, 0.8, 7.1],
                                gap="small",
                            )
                            with _save_col:
                                if st.button(
                                    "Save Edit",
                                    key=f"btn_tm_save_edit_{tag['slug']}",
                                    type="primary",
                                    disabled=not _new_slug,
                                ):
                                    _selected_category_slug = _category_name_to_slug[
                                        _selected_category_name
                                    ]
                                    if (
                                        _new_slug == tag["slug"]
                                        and _selected_category_slug == cat["slug"]
                                    ):
                                        enqueue_flash(
                                            "success",
                                            "Edit canceled; tag is unchanged.",
                                        )
                                        st.session_state.pop(
                                            "tm_editing_tag_slug", None
                                        )
                                        st.session_state.pop(
                                            "tm_pending_tag_edit", None
                                        )
                                        st.rerun()
                                    st.session_state["tm_pending_tag_edit"] = {
                                        "old_slug": tag["slug"],
                                        "old_display_name": tag["name"],
                                        "old_category_slug": cat["slug"],
                                        "old_category_name": cat["name"],
                                        "new_slug": _new_slug,
                                        "new_display_name": _new_pretty,
                                        "category_slug": _selected_category_slug,
                                        "category_name": _selected_category_name,
                                    }
                                    st.rerun()
                            with _cancel_col:
                                if st.button(
                                    "Cancel",
                                    key=f"btn_tm_cancel_edit_{tag['slug']}",
                                ):
                                    st.session_state.pop("tm_editing_tag_slug", None)
                                    st.session_state.pop("tm_pending_tag_edit", None)
                                    st.rerun()
                            with _edit_action_spacer:
                                st.empty()
                            continue

                        _rename_col, _pipe_col, _delete_col, _detail_col = st.columns(
                            [0.42, 0.06, 0.42, 9.1],
                            gap="small",
                        )
                        with _rename_col:
                            if not tag["is_builtin"] and st.button(
                                "Edit",
                                key=f"btn_tm_edit_{tag['slug']}",
                                type="tertiary",
                            ):
                                st.session_state["tm_editing_tag_slug"] = tag["slug"]
                                st.session_state[
                                    f"tm_edit_name_input_{tag['slug']}"
                                ] = tag["name"]
                                st.session_state[
                                    f"tm_edit_category_select_{tag['slug']}"
                                ] = cat["name"]
                                st.session_state.pop("tm_pending_tag_edit", None)
                                st.session_state.pop("tm_pending_tag_delete", None)
                                st.rerun()
                        with _pipe_col:
                            if tag["is_builtin"]:
                                st.empty()
                            else:
                                st.markdown(
                                    "<span style='color:#999'>|</span>",
                                    unsafe_allow_html=True,
                                )
                        with _delete_col:
                            if tag["is_builtin"]:
                                st.empty()
                            else:
                                if st.button(
                                    ":red[Delete]",
                                    key=f"btn_tm_delete_{tag['slug']}",
                                    type="tertiary",
                                ):
                                    _usage_count = sum(
                                        1
                                        for entry in st.session_state.get(
                                            "loaded_entries", []
                                        )
                                        if tag["slug"] in get_entry_tags(entry)
                                    )
                                    st.session_state["tm_pending_tag_delete"] = {
                                        "tag_slug": tag["slug"],
                                        "display_name": tag["name"],
                                        "usage_count": _usage_count,
                                    }
                                    st.session_state.pop("tm_pending_tag_edit", None)
                                    st.session_state.pop("tm_editing_tag_slug", None)
                                    st.rerun()
                        with _detail_col:
                            st.markdown(
                                f"**{tag['name']}** &nbsp; "
                                f"`{tag['slug']}` &nbsp; "
                                f"<span style='color:{_badge_color};"
                                f"font-size:0.82em'>{_badge_label}</span>",
                                unsafe_allow_html=True,
                            )

        _pending_edit = st.session_state.get("tm_pending_tag_edit")
        _validated_pending_edit = validate_pending_tag_edit(
            pending_edit=_pending_edit,
            current_edit_slug=st.session_state.get("tm_editing_tag_slug"),
            active_custom_slugs=_active_custom_slugs,
            active_category_slugs=set(_category_slug_to_name),
        )
        if _pending_edit and not _validated_pending_edit:
            st.session_state.pop("tm_pending_tag_edit", None)
            st.warning("Tag edit was refreshed because the row changed.")
        _pending_edit = _validated_pending_edit
        if _pending_edit:
            _name_changed = _pending_edit["new_slug"] != _pending_edit["old_slug"]
            _category_changed = (
                _pending_edit["category_slug"] != _pending_edit["old_category_slug"]
            )
            if _name_changed and _category_changed:
                _confirmation = (
                    f"Edit tag \"{_pending_edit['old_display_name']}\":\n\n"
                    f"- Name: \"{_pending_edit['new_display_name']}\"\n"
                    f"- Category: {_pending_edit['old_category_name']} -> "
                    f"{_pending_edit['category_name']}\n\n"
                    "Existing dataset entries using this tag will also be updated."
                )
            elif _name_changed:
                _confirmation = (
                    f"Edit tag \"{_pending_edit['old_display_name']}\" to "
                    f"\"{_pending_edit['new_display_name']}\"?\n\n"
                    "Existing dataset entries using this tag will also be updated."
                )
            else:
                _confirmation = (
                    f"Move tag \"{_pending_edit['old_display_name']}\" from "
                    f"\"{_pending_edit['old_category_name']}\" to "
                    f"\"{_pending_edit['category_name']}\"?"
                )
            st.warning(_confirmation)
            _confirm_col, _cancel_col = st.columns(2)
            with _confirm_col:
                if st.button(
                    "Confirm Edit",
                    key="btn_tm_confirm_tag_edit",
                    type="primary",
                ):
                    _result = edit_active_tag(
                        old_slug=_pending_edit["old_slug"],
                        new_display_name=_pending_edit["new_display_name"],
                        category_slug=_pending_edit["category_slug"],
                        dataset_path=st.session_state.get("loaded_path", ""),
                        entries=st.session_state.get("loaded_entries", []),
                    )
                    if _result.ok:
                        apply_dataset_operation_result(_result)
                        if _result.entries is not None:
                            st.session_state.loaded_entries = _result.entries
                            st.session_state.entry_registry = build_entry_registry(
                                _result.entries
                            )
                        enqueue_flash("success", _result.message)
                        st.session_state.pop("tm_editing_tag_slug", None)
                        st.session_state.pop("tm_pending_tag_edit", None)
                        st.rerun()
                    else:
                        st.error(_result.message)
                        for _error in _result.errors:
                            st.caption(_error)
                        st.session_state.pop("tm_pending_tag_edit", None)
            with _cancel_col:
                if st.button("Cancel", key="btn_tm_cancel_tag_edit"):
                    st.session_state.pop("tm_pending_tag_edit", None)
                    st.rerun()

        _pending_delete = st.session_state.get("tm_pending_tag_delete")
        _validated_pending_delete = validate_pending_tag_delete(
            pending_delete=_pending_delete,
            active_custom_slugs=_active_custom_slugs,
        )
        if _pending_delete and not _validated_pending_delete:
            st.session_state.pop("tm_pending_tag_delete", None)
            st.warning("Tag delete was refreshed because the row changed.")
        _pending_delete = _validated_pending_delete
        if _pending_delete:
            _delete_count = int(_pending_delete.get("usage_count", 0) or 0)
            _delete_entry_word = "entry" if _delete_count == 1 else "entries"
            st.warning(
                f"Delete tag \"{_pending_delete['display_name']}\"?\n\n"
                "This will remove the tag from active use and remove it from "
                "loaded dataset entries. The tag will move to Archived Tags as "
                f"Deleted.\n\nThis tag is currently used by {_delete_count} "
                f"loaded {_delete_entry_word}."
            )
            _delete_confirm_col, _delete_cancel_col = st.columns(2)
            with _delete_confirm_col:
                if st.button(
                    "Confirm Delete",
                    key="btn_tm_confirm_tag_delete",
                    type="primary",
                ):
                    _result = delete_active_tag(
                        tag_slug=_pending_delete["tag_slug"],
                        dataset_path=st.session_state.get("loaded_path", ""),
                        entries=st.session_state.get("loaded_entries", []),
                    )
                    if _result.ok:
                        apply_dataset_operation_result(_result)
                        if _result.entries is not None:
                            st.session_state.loaded_entries = _result.entries
                            st.session_state.entry_registry = build_entry_registry(
                                _result.entries
                            )
                        enqueue_flash("success", _result.message)
                        st.session_state.pop("tm_pending_tag_delete", None)
                        st.rerun()
                    else:
                        st.error(_result.message)
                        for _error in _result.errors:
                            st.caption(_error)
                        st.session_state.pop("tm_pending_tag_delete", None)
            with _delete_cancel_col:
                if st.button("Cancel", key="btn_tm_cancel_tag_delete"):
                    st.session_state.pop("tm_pending_tag_delete", None)
                    st.rerun()

        _pending_category_rename = st.session_state.get("tm_pending_category_rename")
        _validated_pending_category_rename = validate_pending_category_rename(
            pending_rename=_pending_category_rename,
            current_rename_slug=st.session_state.get("tm_renaming_category_slug"),
            active_custom_category_slugs=_active_custom_category_slugs,
        )
        if _pending_category_rename and not _validated_pending_category_rename:
            st.session_state.pop("tm_pending_category_rename", None)
            st.warning("Category rename was refreshed because the category changed.")
        _pending_category_rename = _validated_pending_category_rename
        if _pending_category_rename:
            st.warning(
                f"Rename category \"{_pending_category_rename['old_display_name']}\" "
                f"to \"{_pending_category_rename['new_display_name']}\"?\n\n"
                "Tags in this category will stay attached. Dataset entries will "
                "not be rewritten."
            )
            _cat_confirm_col, _cat_cancel_col = st.columns(2)
            with _cat_confirm_col:
                if st.button(
                    "Confirm Rename",
                    key="btn_tm_confirm_category_rename",
                    type="primary",
                ):
                    _result = rename_custom_category(
                        category_slug=_pending_category_rename["old_slug"],
                        new_display_name=_pending_category_rename["new_display_name"],
                    )
                    if _result.ok:
                        enqueue_flash("success", _result.message)
                        st.session_state.pop("tm_renaming_category_slug", None)
                        st.session_state.pop("tm_pending_category_rename", None)
                        st.rerun()
                    else:
                        st.error(_result.message)
                        for _error in _result.errors:
                            st.caption(_error)
                        st.session_state.pop("tm_pending_category_rename", None)
            with _cat_cancel_col:
                if st.button("Cancel", key="btn_tm_cancel_category_confirm_rename"):
                    st.session_state.pop("tm_pending_category_rename", None)
                    st.rerun()

    if registry:
        _pending_category_delete = st.session_state.get("tm_pending_category_delete")
        _validated_pending_category_delete = validate_pending_category_delete(
            pending_delete=_pending_category_delete,
            active_empty_custom_category_slugs=_active_empty_custom_category_slugs,
        )
        if _pending_category_delete and not _validated_pending_category_delete:
            st.session_state.pop("tm_pending_category_delete", None)
            st.warning("Category delete was refreshed because the category changed.")
        _pending_category_delete = _validated_pending_category_delete
        if _pending_category_delete:
            st.warning(
                f"Delete category \"{_pending_category_delete['display_name']}\"?\n\n"
                "This category is empty and will be removed from the active registry."
            )
            _cat_delete_confirm_col, _cat_delete_cancel_col = st.columns(2)
            with _cat_delete_confirm_col:
                if st.button(
                    "Confirm Delete",
                    key="btn_tm_confirm_category_delete",
                    type="primary",
                ):
                    _result = delete_empty_custom_category(
                        category_slug=_pending_category_delete["category_slug"],
                    )
                    if _result.ok:
                        enqueue_flash("success", _result.message)
                        st.session_state.pop("tm_pending_category_delete", None)
                        st.rerun()
                    else:
                        st.error(_result.message)
                        for _error in _result.errors:
                            st.caption(_error)
                        st.session_state.pop("tm_pending_category_delete", None)
            with _cat_delete_cancel_col:
                if st.button("Cancel", key="btn_tm_cancel_category_delete"):
                    st.session_state.pop("tm_pending_category_delete", None)
                    st.rerun()

    # ── Section 2: Create Custom Category ─────────────────────────────────────
    st.divider()
    st.subheader("Create Custom Category")

    _at_limit = total_categories >= _tag_snapshot.max_active_categories

    if _at_limit:
        st.info(
            f"Category limit reached. "
            f"This version supports {_tag_snapshot.max_active_categories} active categories."
        )

    _new_cat_name: str = st.text_input(
        "Category Name",
        key="tm_new_cat_name",
        placeholder="e.g. Tone",
        disabled=_at_limit,
    )

    # Live slug / display-name preview
    if _new_cat_name.strip():
        _cat_slug_preview = slugify_tag_name(_new_cat_name)
        _cat_name_preview = prettify_tag_name(_cat_slug_preview)
        st.caption(
            f"slug: `{_cat_slug_preview}` · display name will be saved as: **{_cat_name_preview}**"
        )

    if st.button(
        "Create Category",
        key="btn_tm_create_cat",
        type="primary",
        disabled=_at_limit or not _new_cat_name.strip(),
        width="stretch",
    ):
        _ok, _msg = create_custom_category(_new_cat_name)
        if _ok:
            enqueue_flash("success", _msg)
            st.session_state["_tm_clear_cat_name"] = True
            st.rerun()
        else:
            st.error(_msg)

    # ── Section 3: Add Custom Tag ──────────────────────────────────────────────
    st.divider()
    st.subheader("Add Custom Tag")

    if not registry:
        st.info("No active categories available. Create a category first.")
    else:
        _cat_name_to_id: dict[str, int] = {cat["name"]: cat["id"] for cat in registry}
        _cat_names = list(_cat_name_to_id.keys())

        _selected_cat_name: str | None = st.selectbox(
            "Category",
            options=_cat_names,
            key="tm_tag_cat_select",
        )
        _selected_cat_id: int | None = (
            _cat_name_to_id.get(_selected_cat_name) if _selected_cat_name else None
        )

        _new_tag_name: str = st.text_input(
            "Tag Name",
            key="tm_new_tag_name",
            placeholder="e.g. Playful Banter",
        )

        # Live slug / display-name preview
        if _new_tag_name.strip():
            _tag_slug_preview = slugify_tag_name(_new_tag_name)
            _tag_name_preview = prettify_tag_name(_tag_slug_preview)
            st.caption(
                f"slug: `{_tag_slug_preview}` · display name will be saved as: **{_tag_name_preview}**"
            )

        if st.button(
            "Add Tag",
            key="btn_tm_add_tag",
            type="primary",
            disabled=_selected_cat_id is None or not _new_tag_name.strip(),
            width="stretch",
        ):
            _ok, _msg = create_custom_tag(_selected_cat_id, _new_tag_name)
            if _ok:
                enqueue_flash("success", _msg)
                st.session_state["_tm_clear_tag_name"] = True
                st.rerun()
            else:
                st.error(_msg)

    # Archived lifecycle tags
    st.divider()
    st.subheader("Archived Tags")
    st.caption(
        "These tags are known to LoreForge but are not active or trusted. "
        "Imported tags need a category before they appear in normal tag pickers. "
        "Deleted tags can be restored later."
    )

    _archived_tags = _tag_snapshot.visible_archived_tags
    if st.session_state.pop("_tm_clear_archived_selection", False):
        for tag in _archived_tags:
            st.session_state[f"tm_archived_select_{tag['slug']}"] = False

    if not _archived_tags:
        st.info("No archived tags.")
    else:
        _assignable_archived_tags = [
            tag for tag in _archived_tags if tag.get("can_assign_to_category")
        ]

        for tag in _archived_tags:
            _select_col, _label_col, _action_col = st.columns(
                [0.35, 7.65, 3],
                gap="small",
            )
            _badge = tag["visible_badge"]
            with _select_col:
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
            with _label_col:
                st.markdown(
                    f"<div style='padding-top:0.52rem;line-height:1.5'>"
                    f"<strong>{tag['display_name']}</strong> &nbsp; "
                    f"<span style='color:#777;font-size:0.82em'>"
                    f"{_badge}</span></div>",
                    unsafe_allow_html=True,
                )
            with _action_col:
                st.empty()

        if _assignable_archived_tags:
            _category_name_to_slug: dict[str, str] = {
                cat["name"]: cat["slug"] for cat in registry
            }
            if not _category_name_to_slug:
                st.info("Create an active category before assigning archived tags.")
            else:
                _selected_assign_category: str | None = st.selectbox(
                    "Assign selected archived tags to",
                    options=list(_category_name_to_slug.keys()),
                    key="tm_archived_assign_category",
                )
                _selected_archived_slugs = selected_assignable_archived_slugs(
                    archived_tags=_archived_tags,
                    selected_by_slug={
                        tag["slug"]: st.session_state.get(
                            f"tm_archived_select_{tag['slug']}",
                            False,
                        )
                        for tag in _archived_tags
                    },
                )

                if st.button(
                    "Assign Selected",
                    key="btn_tm_assign_archived",
                    disabled=not _selected_archived_slugs
                    or _selected_assign_category is None,
                ):
                    st.session_state["tm_pending_archived_assignment"] = {
                        "tag_slugs": _selected_archived_slugs,
                        "category_slug": _category_name_to_slug[
                            _selected_assign_category
                        ],
                        "category_name": _selected_assign_category,
                    }
                    st.rerun()

        _pending_assignment = st.session_state.get("tm_pending_archived_assignment")
        _selected_archived_slugs = selected_assignable_archived_slugs(
            archived_tags=_archived_tags,
            selected_by_slug={
                tag["slug"]: st.session_state.get(
                    f"tm_archived_select_{tag['slug']}",
                    False,
                )
                for tag in _archived_tags
            },
        )
        _category_slugs = {cat["slug"] for cat in registry}
        _validated_pending_assignment = validate_pending_archived_assignment(
            pending_assignment=_pending_assignment,
            selected_slugs=_selected_archived_slugs,
            category_slugs=_category_slugs,
        )
        if _pending_assignment and not _validated_pending_assignment:
            st.session_state.pop("tm_pending_archived_assignment", None)
            st.warning(
                "Archived tag assignment was refreshed because the selection changed."
            )
        _pending_assignment = _validated_pending_assignment
        if _pending_assignment:
            _pending_count = len(_pending_assignment["tag_slugs"])
            _pending_category = _pending_assignment["category_name"]
            st.warning(
                f"Assign {count_phrase(_pending_count, 'archived tag')} "
                f"to {_pending_category}? "
                "These tags will become active and appear in normal tag pickers."
            )
            _confirm_col, _cancel_col = st.columns(2)
            with _confirm_col:
                if st.button(
                    "Confirm Assignment",
                    key="btn_tm_confirm_archived_assignment",
                    type="primary",
                ):
                    _result = assign_archived_imported_tags_to_category(
                        tag_slugs=_pending_assignment["tag_slugs"],
                        category_slug=_pending_assignment["category_slug"],
                    )
                    if _result.ok:
                        enqueue_flash("success", _result.message)
                        st.session_state.pop("tm_pending_archived_assignment", None)
                        st.session_state["_tm_clear_archived_selection"] = True
                        st.rerun()
                    else:
                        st.error(_result.message)
                        for _error in _result.errors:
                            st.caption(_error)
                        st.session_state.pop("tm_pending_archived_assignment", None)
            with _cancel_col:
                if st.button("Cancel", key="btn_tm_cancel_archived_assignment"):
                    st.session_state.pop("tm_pending_archived_assignment", None)
                    st.rerun()
