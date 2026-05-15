"""Compatibility wrapper for the Edit Entries page package."""

from ui.edit_entries.filters import apply_edit_entry_filters
from ui.edit_entries.page import render_edit_entries_page
from ui.edit_entries.state import (
    apply_existing_character_mappings_to_full_edit_state,
    cancel_full_edit,
    entry_to_edit_buffer,
    load_full_edit_buffer,
    reset_full_edit_to_browser,
    set_full_edit_mode_state,
    start_full_edit,
)
from ui.edit_entries.workspace import (
    render_full_edit_workspace,
    save_full_edit,
    split_button_visible as _split_button_visible,
    split_complete_message as _split_complete_message,
)

__all__ = [
    "apply_edit_entry_filters",
    "apply_existing_character_mappings_to_full_edit_state",
    "cancel_full_edit",
    "entry_to_edit_buffer",
    "load_full_edit_buffer",
    "render_edit_entries_page",
    "render_full_edit_workspace",
    "reset_full_edit_to_browser",
    "save_full_edit",
    "set_full_edit_mode_state",
    "start_full_edit",
    "_split_button_visible",
    "_split_complete_message",
]

