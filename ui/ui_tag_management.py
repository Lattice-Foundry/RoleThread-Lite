"""Tag Management page — additive-only custom tag and category creation."""
import streamlit as st

from core.tag_registry import (
    _MAX_ACTIVE_CATEGORIES,
    create_custom_category,
    create_custom_tag,
    get_full_tag_registry,
    get_visible_archived_tags,
    prettify_tag_name,
    slugify_tag_name,
)
from ui.tag_management_helpers import (
    selected_assignable_archived_slugs,
    validate_pending_archived_assignment,
)
from services.tag_lifecycle_service import assign_archived_imported_tags_to_category


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
    st.info(
        "Custom tag editing is additive-only for now. Rename, deactivate, delete, "
        "and migration tools will be added after mismatch detection is implemented."
    )

    # ── Flash message (shown at top, consumed on next render) ─────────────────
    if "tm_success" in st.session_state:
        st.success(st.session_state.pop("tm_success"))

    registry = get_full_tag_registry()
    total_categories = len(registry)

    # ── Section 1: Tag Registry Overview ──────────────────────────────────────
    st.divider()
    st.subheader("Tag Registry Overview")

    if not registry:
        st.info("No tags found. The tag registry may not be seeded yet.")
    else:
        for cat in registry:
            tag_count = len(cat["tags"])
            _plural = "s" if tag_count != 1 else ""
            with st.expander(f"{cat['name']} ({tag_count} tag{_plural})"):
                st.caption(f"slug: {cat['slug']}")
                if not cat["tags"]:
                    st.caption("No tags in this category yet.")
                else:
                    for tag in cat["tags"]:
                        _badge_color = "#888" if tag["is_builtin"] else "#1a73e8"
                        _badge_label = "built-in" if tag["is_builtin"] else "custom"
                        st.markdown(
                            f"**{tag['name']}** &nbsp; "
                            f"`{tag['slug']}` &nbsp; "
                            f"<span style='color:{_badge_color};"
                            f"font-size:0.82em'>{_badge_label}</span>",
                            unsafe_allow_html=True,
                        )

    # ── Section 1b: Archived lifecycle tags ───────────────────────────────────
    st.divider()
    st.subheader("Archived Tags")
    st.caption(
        "These tags are known to LoreForge but are not active or trusted. "
        "Imported tags need a category before they appear in normal tag pickers. "
        "Deleted tags can be restored later."
    )

    _archived_tags = get_visible_archived_tags()
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
                    st.empty()
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
                f"Assign {_pending_count} archived tag(s) to {_pending_category}? "
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
                        st.session_state["tm_success"] = _result.message
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

    # ── Section 2: Create Custom Category ─────────────────────────────────────
    st.divider()
    st.subheader("Create Custom Category")

    _at_limit = total_categories >= _MAX_ACTIVE_CATEGORIES

    if _at_limit:
        st.info(
            f"Category limit reached. "
            f"This version supports {_MAX_ACTIVE_CATEGORIES} active categories."
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
            st.session_state["tm_success"] = _msg
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
                st.session_state["tm_success"] = _msg
                st.session_state["_tm_clear_tag_name"] = True
                st.rerun()
            else:
                st.error(_msg)
