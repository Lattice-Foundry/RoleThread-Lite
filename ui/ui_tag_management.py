"""Tag Management page — additive-only custom tag and category creation."""
import streamlit as st

from core.tag_registry import (
    _MAX_ACTIVE_CATEGORIES,
    create_custom_category,
    create_custom_tag,
    get_full_tag_registry,
    prettify_tag_name,
    slugify_tag_name,
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
