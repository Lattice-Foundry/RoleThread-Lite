"""Central navigation metadata and legacy routing helpers."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from ui.session_state import clear_entry_edit_state


PAGE_CREATE_ENTRY = "Create Entry"
PAGE_MANAGE_DATASET = "Manage Dataset"
PAGE_EDIT_ENTRIES = "Edit Entries"
PAGE_MERGE_DATASETS = "Merge Datasets"
PAGE_EXPORT = "Export"
PAGE_VALIDATION = "Validation"
PAGE_TAG_MANAGEMENT = "Tag Management"
PAGE_CHARACTER_MANAGEMENT = "Character Management"
PAGE_SYSTEM_PROMPTS = "System Prompts"
PAGE_INSIGHTS = "Insights"
PAGE_SETTINGS = "Settings"
PAGE_HELP = "Help"
PAGE_FAQ = "FAQ"


@dataclass(frozen=True)
class PageDefinition:
    """Navigation metadata for one legacy LoreForge page."""

    page_id: str
    title: str
    category: str
    sidebar_section: str
    sidebar_label: str
    icon: str


_PAGE_DEFINITIONS: tuple[PageDefinition, ...] = (
    PageDefinition(PAGE_CREATE_ENTRY, "Create Entry", "Dataset", "Create", "New Entry", ":material/add_circle:"),
    PageDefinition(PAGE_MANAGE_DATASET, "Manage Dataset", "Dataset", "Dataset", "Manage", ":material/folder_open:"),
    PageDefinition(PAGE_MERGE_DATASETS, "Merge Datasets", "Output", "Dataset", "Merge", ":material/merge:"),
    PageDefinition(PAGE_EDIT_ENTRIES, "Edit Entries", "Dataset", "Dataset", "Edit Entries", ":material/edit_note:"),
    PageDefinition(PAGE_EXPORT, "Export", "Output", "Tools", "Export", ":material/download:"),
    PageDefinition(PAGE_VALIDATION, "Validation", "Quality", "Tools", "Validate", ":material/rule:"),
    PageDefinition(PAGE_TAG_MANAGEMENT, "Tag Management", "Metadata", "Metadata", "Tag Management", ":material/sell:"),
    PageDefinition(PAGE_CHARACTER_MANAGEMENT, "Character Management", "Metadata", "Metadata", "Character Management", ":material/groups:"),
    PageDefinition(PAGE_SYSTEM_PROMPTS, "System Prompts", "Metadata", "Metadata", "System Prompts", ":material/text_fields:"),
    PageDefinition(PAGE_INSIGHTS, "Insights", "Quality", "Data Analytics", "Insights", ":material/analytics:"),
    PageDefinition(PAGE_SETTINGS, "Settings", "Support", "Settings", "Preferences", ":material/settings:"),
    PageDefinition(PAGE_HELP, "Help", "Support", "Documentation", "Help", ":material/help:"),
    PageDefinition(PAGE_FAQ, "FAQ", "Support", "Documentation", "FAQ", ":material/contact_support:"),
)

_PAGE_ALIASES = {
    "Statistics": PAGE_INSIGHTS,
}


def get_page_registry() -> dict[str, PageDefinition]:
    """Return page metadata keyed by legacy page name."""

    return {page.page_id: page for page in _PAGE_DEFINITIONS}


def get_sidebar_sections() -> list[tuple[str, list[tuple[str, str]]]]:
    """Return the current sidebar sections in legacy display order."""

    sections: list[tuple[str, list[tuple[str, str]]]] = []
    section_index: dict[str, list[tuple[str, str]]] = {}
    for page in _PAGE_DEFINITIONS:
        if page.sidebar_section not in section_index:
            section_items: list[tuple[str, str]] = []
            section_index[page.sidebar_section] = section_items
            sections.append((page.sidebar_section, section_items))
        section_index[page.sidebar_section].append((page.sidebar_label, page.page_id))
    return sections


def resolve_page(page_id: str | None) -> str | None:
    """Resolve aliases to canonical legacy page names."""

    if page_id is None:
        return None
    return _PAGE_ALIASES.get(page_id, page_id)


def is_known_page(page_id: str | None) -> bool:
    """Return True if page_id identifies a registered page."""

    return resolve_page(page_id) in get_page_registry()


def get_page_title(page_id: str) -> str:
    """Return the display title for a registered page."""

    page = resolve_page(page_id)
    registry = get_page_registry()
    if page not in registry:
        raise ValueError(f"Unknown LoreForge page: {page_id}")
    return registry[page].title


def get_default_page() -> str:
    """Return the legacy default page."""

    return PAGE_CREATE_ENTRY


def get_current_page() -> str:
    """Return the current known page, falling back safely to the default."""

    page = resolve_page(st.session_state.get("page"))
    if page in get_page_registry():
        return page
    return get_default_page()


def set_current_page(page_id: str) -> str:
    """Set the legacy session-state page after validating it."""

    page = resolve_page(page_id)
    if page not in get_page_registry():
        raise ValueError(f"Unknown LoreForge page: {page_id}")
    st.session_state.page = page
    return page


def navigate_to_page(
    page_id: str,
    *,
    clear_edit_state: bool = True,
    rerun: bool = True,
) -> str:
    """Navigate through the legacy page state with edit-workspace cleanup."""

    target_page = resolve_page(page_id)
    if target_page not in get_page_registry():
        raise ValueError(f"Unknown LoreForge page: {page_id}")

    current_page = get_current_page()
    if (
        clear_edit_state
        and current_page == PAGE_EDIT_ENTRIES
        and target_page != PAGE_EDIT_ENTRIES
    ):
        clear_entry_edit_state()

    st.session_state.page = target_page
    if rerun:
        st.rerun()
    return target_page


def sync_legacy_page_state(page_id: str) -> str:
    """Mirror a known page into st.session_state.page without rerunning."""

    return set_current_page(page_id)
