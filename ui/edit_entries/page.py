"""Edit Entries page coordinator."""

import streamlit as st

from core.dataset import clear_validate_entry_cache
from core.tag_registry import get_tag_registry_snapshot
from ui.edit_entries.browser import render_edit_entries_browser
from ui.edit_entries.filters import UNTAGGED_FILTER_KEY
from ui.edit_entries.workspace import render_full_edit_workspace
from ui.flash_messages import render_flash_messages
from ui.session_state import ensure_entry_indexes


def render_edit_entries_page() -> None:
    """Render the Edit Entries browser or full-edit workspace."""

    clear_validate_entry_cache()
    ensure_entry_indexes()
    tag_snapshot = get_tag_registry_snapshot(untagged_key=UNTAGGED_FILTER_KEY)
    render_flash_messages()

    if st.session_state.get("edit_entries_mode") == "workspace":
        render_full_edit_workspace(tag_snapshot.active_registry)
        return

    render_edit_entries_browser(tag_snapshot)

