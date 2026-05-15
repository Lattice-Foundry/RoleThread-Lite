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
    url_path: str


_PAGE_DEFINITIONS: tuple[PageDefinition, ...] = (
    PageDefinition(PAGE_CREATE_ENTRY, "Create Entry", "Dataset", "Create", "New Entry", ":material/add_circle:", "create-entry"),
    PageDefinition(PAGE_MANAGE_DATASET, "Manage Dataset", "Dataset", "Dataset", "Manage", ":material/folder_open:", "manage-dataset"),
    PageDefinition(PAGE_MERGE_DATASETS, "Merge Datasets", "Output", "Dataset", "Merge", ":material/merge:", "merge-datasets"),
    PageDefinition(PAGE_EDIT_ENTRIES, "Edit Entries", "Dataset", "Dataset", "Edit Entries", ":material/edit_note:", "edit-entries"),
    PageDefinition(PAGE_EXPORT, "Export", "Output", "Tools", "Export", ":material/download:", "export"),
    PageDefinition(PAGE_VALIDATION, "Validation", "Quality", "Tools", "Validate", ":material/rule:", "validation"),
    PageDefinition(PAGE_TAG_MANAGEMENT, "Tag Management", "Metadata", "Metadata", "Tag Management", ":material/sell:", "tag-management"),
    PageDefinition(PAGE_CHARACTER_MANAGEMENT, "Character Management", "Metadata", "Metadata", "Character Management", ":material/groups:", "character-management"),
    PageDefinition(PAGE_SYSTEM_PROMPTS, "System Prompts", "Metadata", "Metadata", "System Prompts", ":material/text_fields:", "system-prompts"),
    PageDefinition(PAGE_INSIGHTS, "Insights", "Quality", "Data Analytics", "Insights", ":material/analytics:", "insights"),
    PageDefinition(PAGE_SETTINGS, "Settings", "Support", "Settings", "Preferences", ":material/settings:", "settings"),
    PageDefinition(PAGE_HELP, "Help", "Support", "Documentation", "Help", ":material/help:", "help"),
    PageDefinition(PAGE_FAQ, "FAQ", "Support", "Documentation", "FAQ", ":material/contact_support:", "faq"),
)

_PAGE_ALIASES = {
    "Statistics": PAGE_INSIGHTS,
}

_TOP_NAVIGATION_ORDER = {
    "Dataset": (PAGE_MANAGE_DATASET, PAGE_CREATE_ENTRY, PAGE_EDIT_ENTRIES),
    "Metadata": (
        PAGE_TAG_MANAGEMENT,
        PAGE_CHARACTER_MANAGEMENT,
        PAGE_SYSTEM_PROMPTS,
    ),
    "Quality": (PAGE_VALIDATION, PAGE_INSIGHTS),
    "Output": (PAGE_MERGE_DATASETS, PAGE_EXPORT),
    "Support": (PAGE_HELP, PAGE_FAQ, PAGE_SETTINGS),
}

_QUICK_NAVIGATION_PRIMARY = (
    PAGE_MANAGE_DATASET,
    PAGE_CREATE_ENTRY,
    PAGE_EDIT_ENTRIES,
    PAGE_VALIDATION,
    PAGE_INSIGHTS,
    PAGE_EXPORT,
)

_QUICK_NAVIGATION_SECONDARY = (
    PAGE_SETTINGS,
    PAGE_HELP,
)

_PENDING_NATIVE_PAGE_KEY = "_pending_native_page"
_NATIVE_PAGES: dict[str, object] = {}


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


def get_top_navigation_sections() -> dict[str, list[str]]:
    """Return the native top-navigation page groups in workflow order."""

    return {
        category: list(page_ids)
        for category, page_ids in _TOP_NAVIGATION_ORDER.items()
    }


def get_quick_navigation_pages() -> dict[str, list[str]]:
    """Return sidebar quick-rail groups in display order."""

    return {
        "Quick Navigation": list(_QUICK_NAVIGATION_PRIMARY),
        "Secondary": list(_QUICK_NAVIGATION_SECONDARY),
    }


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


def register_native_pages(native_pages: dict[str, object]) -> None:
    """Register StreamlitPage objects for programmatic native navigation."""

    _NATIVE_PAGES.clear()
    _NATIVE_PAGES.update(native_pages)


def get_native_page_id(native_page: object) -> str | None:
    """Return the legacy page ID for a registered StreamlitPage object."""

    for page_id, page in _NATIVE_PAGES.items():
        if page is native_page or page == native_page:
            return page_id
    return None


def activate_page(page_id: str, *, clear_edit_state: bool = True) -> str:
    """Synchronize legacy state for the page Streamlit is about to render."""

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
    if st.session_state.get(_PENDING_NATIVE_PAGE_KEY) == target_page:
        st.session_state.pop(_PENDING_NATIVE_PAGE_KEY, None)
    return target_page


def switch_to_pending_native_page() -> bool:
    """Switch to a queued native page after st.navigation registers pages."""

    pending_page = resolve_page(st.session_state.get(_PENDING_NATIVE_PAGE_KEY))
    if not pending_page:
        return False
    native_page = _NATIVE_PAGES.get(pending_page)
    if native_page is None:
        return False
    st.session_state.pop(_PENDING_NATIVE_PAGE_KEY, None)
    st.switch_page(native_page)
    return True


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

    activate_page(target_page, clear_edit_state=clear_edit_state)
    if rerun:
        native_page = _NATIVE_PAGES.get(target_page)
        if native_page is not None:
            st.switch_page(native_page)
        else:
            st.rerun()
    elif _NATIVE_PAGES:
        st.session_state[_PENDING_NATIVE_PAGE_KEY] = target_page
    return target_page


def sync_legacy_page_state(page_id: str) -> str:
    """Mirror a known page into st.session_state.page without rerunning."""

    return set_current_page(page_id)
