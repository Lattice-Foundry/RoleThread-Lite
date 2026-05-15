"""Central navigation metadata and legacy routing helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
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
    icon: str
    url_path: str


_PAGE_DEFINITIONS: tuple[PageDefinition, ...] = (
    PageDefinition(
        PAGE_CREATE_ENTRY,
        "Create Entry",
        "Dataset",
        ":material/add_circle:",
        "create-entry",
    ),
    PageDefinition(
        PAGE_MANAGE_DATASET,
        "Manage Dataset",
        "Dataset",
        ":material/folder_open:",
        "manage-dataset",
    ),
    PageDefinition(
        PAGE_MERGE_DATASETS,
        "Merge Datasets",
        "Output",
        ":material/merge:",
        "merge-datasets",
    ),
    PageDefinition(
        PAGE_EDIT_ENTRIES,
        "Edit Entries",
        "Dataset",
        ":material/edit_note:",
        "edit-entries",
    ),
    PageDefinition(
        PAGE_EXPORT,
        "Export",
        "Output",
        ":material/download:",
        "export",
    ),
    PageDefinition(
        PAGE_VALIDATION,
        "Validation",
        "Quality",
        ":material/rule:",
        "validation",
    ),
    PageDefinition(
        PAGE_TAG_MANAGEMENT,
        "Tag Management",
        "Metadata",
        ":material/sell:",
        "tag-management",
    ),
    PageDefinition(
        PAGE_CHARACTER_MANAGEMENT,
        "Character Management",
        "Metadata",
        ":material/groups:",
        "character-management",
    ),
    PageDefinition(
        PAGE_SYSTEM_PROMPTS,
        "System Prompts",
        "Metadata",
        ":material/text_fields:",
        "system-prompts",
    ),
    PageDefinition(
        PAGE_INSIGHTS,
        "Insights",
        "Quality",
        ":material/analytics:",
        "insights",
    ),
    PageDefinition(
        PAGE_SETTINGS,
        "Settings",
        "Support",
        ":material/settings:",
        "settings",
    ),
    PageDefinition(
        PAGE_HELP,
        "Help",
        "Support",
        ":material/help:",
        "help",
    ),
    PageDefinition(
        PAGE_FAQ,
        "FAQ",
        "Support",
        ":material/contact_support:",
        "faq",
    ),
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

_PAGES_WITH_OWN_SIDEBAR = frozenset({PAGE_HELP})
_PENDING_NATIVE_PAGE_KEY = "_pending_native_page"
_NATIVE_PAGES: dict[str, object] = {}
PageRenderer = Callable[[], None]


def get_page_registry() -> dict[str, PageDefinition]:
    """Return page metadata keyed by legacy page name."""

    return {page.page_id: page for page in _PAGE_DEFINITIONS}


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


def page_owns_sidebar(page_id: str | None) -> bool:
    """Return whether a page replaces the global quick-navigation rail."""

    return resolve_page(page_id) in _PAGES_WITH_OWN_SIDEBAR


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


def validate_page_renderers(page_renderers: Mapping[str, PageRenderer]) -> None:
    """Ensure app-shell page callables stay aligned with the page registry."""

    registered_pages = set(get_page_registry())
    renderer_pages = set(page_renderers)
    missing_pages = registered_pages - renderer_pages
    extra_pages = renderer_pages - registered_pages
    if missing_pages or extra_pages:
        details: list[str] = []
        if missing_pages:
            details.append(f"missing: {', '.join(sorted(missing_pages))}")
        if extra_pages:
            details.append(f"unknown: {', '.join(sorted(extra_pages))}")
        raise ValueError(f"Page renderer registry mismatch ({'; '.join(details)})")


def _make_page_runner(
    page_id: str,
    page_renderers: Mapping[str, PageRenderer],
) -> PageRenderer:
    def _run_page() -> None:
        activate_page(page_id)
        page_renderers[page_id]()

    return _run_page


def build_native_pages(
    page_renderers: Mapping[str, PageRenderer],
) -> dict[str, object]:
    """Build Streamlit Page objects for the registered LoreForge pages."""

    validate_page_renderers(page_renderers)
    page_registry = get_page_registry()
    return {
        page_id: st.Page(
            _make_page_runner(page_id, page_renderers),
            title=page_registry[page_id].title,
            icon=page_registry[page_id].icon,
            url_path=page_registry[page_id].url_path,
            default=(page_id == get_default_page()),
        )
        for page_id in page_renderers
    }


def _render_quick_navigation_rail(active_page: str) -> None:
    page_registry = get_page_registry()
    for section_label, page_ids in get_quick_navigation_pages().items():
        st.sidebar.markdown(f"**{section_label}**")
        for page_id in page_ids:
            page_def = page_registry[page_id]
            if st.sidebar.button(
                page_def.title,
                key=f"_quick_nav_{page_id}",
                width="stretch",
                type="primary" if active_page == page_id else "secondary",
                icon=page_def.icon,
            ):
                navigate_to_page(page_id)


def render_navigation(page_renderers: Mapping[str, PageRenderer]) -> None:
    """Render top navigation, quick rail, and the selected page."""

    if "page" not in st.session_state:
        set_current_page(get_default_page())

    native_pages = build_native_pages(page_renderers)
    register_native_pages(native_pages)
    native_nav_sections = {
        category: [native_pages[page_id] for page_id in page_ids]
        for category, page_ids in get_top_navigation_sections().items()
    }

    selected_native_page = st.navigation(native_nav_sections, position="top")
    switch_to_pending_native_page()
    selected_page = get_native_page_id(selected_native_page) or get_current_page()
    activate_page(selected_page)
    active_page = get_current_page()
    if not page_owns_sidebar(active_page):
        _render_quick_navigation_rail(active_page)
    selected_native_page.run()


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
