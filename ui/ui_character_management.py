"""Character Management page."""
from __future__ import annotations

import streamlit as st

from core.character_registry import (
    create_character,
    delete_characters,
    get_all_characters,
    get_character_usage_counts,
    get_inactive_characters,
    reactivate_character,
    update_character,
)
from core.text_helpers import count_phrase
from ui.flash_messages import enqueue_flash, render_flash_messages


def render_character_management_page() -> None:
    """Render character creation, editing, and bulk pruning controls."""

    st.subheader("Character Management")

    render_flash_messages()
    characters = get_all_characters()
    selected = st.session_state.setdefault("selected_character_slugs", set())
    selected.intersection_update({character.slug for character in characters})
    usage_counts = get_character_usage_counts([character.slug for character in characters])

    if characters:
        _render_bulk_actions(characters, selected)
        _render_character_list(characters, selected, usage_counts)
    else:
        st.info(
            "No characters yet. Characters are created automatically when custom "
            "role names are detected during dataset import, or you can add them "
            "manually below."
        )

    st.divider()
    _render_add_character()
    _render_inactive_characters()


def _render_bulk_actions(characters, selected: set[str]) -> None:
    col_select, col_clear, col_delete, _spacer = st.columns([1, 1, 1.2, 3])
    with col_select:
        if st.button("Select All", width="stretch"):
            st.session_state.selected_character_slugs = {
                character.slug for character in characters
            }
            st.rerun()
    with col_clear:
        if st.button("Deselect All", width="stretch"):
            st.session_state.selected_character_slugs = set()
            _clear_delete_confirmation()
            st.rerun()
    with col_delete:
        if st.button(
            "Delete Selected",
            disabled=not selected,
            width="stretch",
        ):
            st.session_state.pending_character_delete = sorted(selected)
            st.rerun()

    pending = st.session_state.get("pending_character_delete")
    if not pending:
        return

    pending = [slug for slug in pending if slug in {character.slug for character in characters}]
    if not pending:
        _clear_delete_confirmation()
        return

    st.warning(
        f"Delete {count_phrase(len(pending), 'character')}? Their display names "
        "will no longer appear in previews. Entry data is not affected."
    )
    confirm_col, cancel_col, _confirm_spacer = st.columns([1, 1, 4])
    with confirm_col:
        if st.button("Confirm Delete", type="primary"):
            deleted = delete_characters(pending)
            st.session_state.selected_character_slugs = set()
            _clear_delete_confirmation()
            enqueue_flash(
                "success",
                f"Deleted {count_phrase(len(deleted), 'character')}."
            )
            st.rerun()
    with cancel_col:
        if st.button("Cancel Delete"):
            _clear_delete_confirmation()
            st.rerun()


def _render_character_list(characters, selected: set[str], usage_counts: dict[str, int]) -> None:
    sort_choice = st.radio(
        "Sort characters",
        ["Display name", "Usage count"],
        horizontal=True,
        key="character_sort_order",
    )
    sorted_characters = sorted(
        characters,
        key=(
            (lambda character: (-usage_counts.get(character.slug, 0), character.display_name.lower()))
            if sort_choice == "Usage count"
            else (lambda character: character.display_name.lower())
        ),
    )

    st.caption(
        f"{count_phrase(len(sorted_characters), 'active character')} in the registry."
    )
    header = st.columns([0.6, 2, 1.6, 1.2, 1.4, 1])
    header[0].markdown("**Select**")
    header[1].markdown("**Display Name**")
    header[2].markdown("**Slug**")
    header[3].markdown("**Usage**")
    header[4].markdown("**Created**")
    header[5].markdown("**Actions**")

    for character in sorted_characters:
        _render_character_row(character, selected, usage_counts.get(character.slug, 0))


def _render_character_row(character, selected: set[str], usage_count: int) -> None:
    cols = st.columns([0.6, 2, 1.6, 1.2, 1.4, 1])
    with cols[0]:
        is_selected = st.checkbox(
            "Select",
            value=character.slug in selected,
            key=f"character_select_{character.slug}",
            label_visibility="collapsed",
        )
    if is_selected:
        selected.add(character.slug)
    else:
        selected.discard(character.slug)
    st.session_state.selected_character_slugs = selected

    cols[1].write(character.display_name)
    cols[2].markdown(f"`{character.slug}`")
    cols[3].write(count_phrase(usage_count, "entry", "entries"))
    cols[4].write(_format_date(character.created_at))
    with cols[5]:
        if st.button("Edit", key=f"character_edit_{character.slug}"):
            st.session_state.editing_character_slug = character.slug
            st.rerun()

    if st.session_state.get("editing_character_slug") == character.slug:
        _render_edit_character(character)


def _render_edit_character(character) -> None:
    with st.container(border=True):
        st.markdown(f"**Edit {character.display_name}**")
        name = st.text_input(
            "Display name",
            value=character.display_name,
            key=f"character_name_input_{character.slug}",
        )
        description = st.text_area(
            "Description",
            value=character.description or "",
            height=90,
            key=f"character_description_input_{character.slug}",
        )
        save_col, cancel_col, _spacer = st.columns([1, 1, 4])
        with save_col:
            if st.button("Save", type="primary", key=f"character_save_{character.slug}"):
                try:
                    update_character(
                        character.slug,
                        display_name=name,
                        description=description,
                    )
                except Exception as exc:
                    st.error(str(exc))
                    return
                enqueue_flash("success", "Character updated.")
                st.session_state.pop("editing_character_slug", None)
                st.rerun()
        with cancel_col:
            if st.button("Cancel", key=f"character_cancel_{character.slug}"):
                st.session_state.pop("editing_character_slug", None)
                st.rerun()


def _render_add_character() -> None:
    st.markdown("**Add Character**")
    name = st.text_input("Character name", key="new_character_name")
    description = st.text_area("Description", height=90, key="new_character_description")
    if st.button("Add Character", type="primary", disabled=not name.strip()):
        try:
            character = create_character(
                name,
                description=description.strip() or None,
            )
        except Exception as exc:
            st.error(str(exc))
            return
        enqueue_flash(
            "success",
            f"Added character \"{character.display_name}\"."
        )
        st.rerun()


def _render_inactive_characters() -> None:
    inactive = get_inactive_characters()
    if not inactive:
        return

    with st.expander("Inactive Characters", expanded=False):
        for character in inactive:
            cols = st.columns([2, 1.5, 1])
            cols[0].write(character.display_name)
            cols[1].markdown(f"`{character.slug}`")
            with cols[2]:
                if st.button("Reactivate", key=f"character_reactivate_{character.slug}"):
                    if reactivate_character(character.slug):
                        enqueue_flash(
                            "success",
                            f"Reactivated \"{character.display_name}\"."
                        )
                    st.rerun()


def _format_date(value) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)


def _clear_delete_confirmation() -> None:
    st.session_state.pop("pending_character_delete", None)
