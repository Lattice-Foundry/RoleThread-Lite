"""Manage Dataset page dispatcher."""

import streamlit as st

from core.dataset import clear_validate_entry_cache
from core.tag_registry import get_tag_registry_snapshot
from ui.manage.actions import render_actions
from ui.manage.entry_list import render_entry_list
from ui.manage.filters import render_filters
from ui.manage.load_section import render_load_section
from ui.manage.load_summary import render_entry_issue_summary
from ui.session_state import (
    ensure_entry_indexes,
    ensure_selection_state,
    get_all_entry_pairs,
)

_UNTAGGED = "__untagged__"


def render_manage_page() -> None:
    """Render the Manage Dataset page."""
    clear_validate_entry_cache()
    ensure_entry_indexes()
    ensure_selection_state()
    tag_snapshot = get_tag_registry_snapshot(untagged_key=_UNTAGGED)

    render_load_section()

    entries = st.session_state.loaded_entries
    all_pairs = get_all_entry_pairs()
    if not all_pairs:
        return

    st.divider()
    st.subheader(f"Entries ({len(all_pairs)})")
    render_entry_issue_summary(entries)

    filter_result = render_filters(
        entries=entries,
        all_pairs=all_pairs,
        tag_snapshot=tag_snapshot,
        untagged_key=_UNTAGGED,
    )
    if filter_result is None:
        return

    render_actions(
        visible_pairs=filter_result.visible_pairs,
        filter_tags=filter_result.filter_tags,
        match_mode=filter_result.match_mode,
        per_page=filter_result.per_page,
        current_page=filter_result.current_page,
        start=filter_result.start,
        end=filter_result.end,
        total_filtered=filter_result.total_filtered,
        total_all=filter_result.total_all,
        tag_snapshot=tag_snapshot,
    )
    render_entry_list(
        visible_pairs=filter_result.visible_pairs,
        start=filter_result.start,
        tag_snapshot=tag_snapshot,
        tag_label_map=tag_snapshot.tag_label_map_with_untagged,
        character_display_cache=filter_result.character_display_cache,
        last_page=filter_result.last_page,
        current_page=filter_result.current_page,
    )
