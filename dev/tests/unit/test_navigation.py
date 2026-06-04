import pytest

import ui.navigation as navigation
import ui.session_state as session_state
import ui.stats_navigation as stats_navigation


class FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class FakeStreamlit:
    def __init__(self):
        self.session_state = FakeSessionState()
        self.rerun_count = 0
        self.switched_page = None

    def rerun(self):
        self.rerun_count += 1

    def switch_page(self, page):
        self.switched_page = page

    def Page(self, page, title, icon, url_path, default=False):
        return {
            "page": page,
            "title": title,
            "icon": icon,
            "url_path": url_path,
            "default": default,
        }


def _patch_navigation_state(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(navigation, "st", fake)
    monkeypatch.setattr(session_state, "st", fake)
    monkeypatch.setattr(stats_navigation, "st", fake)
    navigation.register_native_pages({})
    return fake


def test_page_registry_exposes_legacy_pages():
    registry = navigation.get_page_registry()

    assert navigation.PAGE_CREATE_ENTRY in registry
    assert navigation.PAGE_MANAGE_DATASET in registry
    assert navigation.PAGE_DATA_GENERATION in registry
    assert navigation.PAGE_DIAGNOSTICS in registry
    assert navigation.PAGE_EDIT_ENTRIES in registry
    assert navigation.PAGE_EDIT_ENTRIES == "Edit Entries"
    assert navigation.get_page_title(navigation.PAGE_DATA_GENERATION) == (
        "Prompt Generation (Beta)"
    )
    assert navigation.get_page_title(navigation.PAGE_EDIT_ENTRIES) == "Deep Edit"
    assert navigation.get_page_title("Deep Edit") == "Deep Edit"
    assert navigation.get_page_title("Statistics") == "Insights"
    assert navigation.is_known_page("Statistics") is True
    assert navigation.is_known_page("Deep Edit") is True
    assert navigation.is_known_page("Not A Page") is False


def test_sidebar_branding_metadata_is_compact_shell_identity():
    assert navigation.APP_BRAND_TITLE == "RoleThread Lite"
    assert navigation.APP_BRAND_SUBTITLE == "Narrative Intelligence"


def test_sidebar_brand_logo_is_available_as_png_data_uri():
    logo_data_uri = navigation.get_sidebar_brand_logo_data_uri()

    assert logo_data_uri.startswith("data:image/png;base64,")


def test_page_registry_has_unique_titles_and_paths():
    registry = navigation.get_page_registry()
    titles = [page.title for page in registry.values()]
    paths = [page.url_path for page in registry.values()]

    assert len(titles) == len(set(titles))
    assert len(paths) == len(set(paths))
    assert all(page.category for page in registry.values())
    assert all(page.icon.startswith(":material/") for page in registry.values())


def test_top_navigation_sections_follow_workflow_categories():
    assert navigation.get_top_navigation_sections() == {
        "Dataset": [
            navigation.PAGE_MANAGE_DATASET,
            navigation.PAGE_CREATE_ENTRY,
            navigation.PAGE_EDIT_ENTRIES,
        ],
        "Metadata": [
            navigation.PAGE_TAG_MANAGEMENT,
            navigation.PAGE_CHARACTER_MANAGEMENT,
            navigation.PAGE_SYSTEM_PROMPTS,
        ],
        "Quality": [
            navigation.PAGE_VALIDATION,
            navigation.PAGE_INSIGHTS,
        ],
        "Output": [
            navigation.PAGE_DATA_GENERATION,
            navigation.PAGE_MERGE_DATASETS,
            navigation.PAGE_EXPORT,
        ],
        "Support": [
            navigation.PAGE_HELP,
            navigation.PAGE_FAQ,
            navigation.PAGE_SUPPORT_ROLETHREAD,
            navigation.PAGE_DIAGNOSTICS,
            navigation.PAGE_SETTINGS,
        ],
    }


def test_quick_navigation_pages_use_curated_rail_groups():
    assert navigation.get_quick_navigation_pages() == {
        "Quick Navigation": [
            navigation.PAGE_MANAGE_DATASET,
            navigation.PAGE_CREATE_ENTRY,
            navigation.PAGE_EDIT_ENTRIES,
            navigation.PAGE_VALIDATION,
            navigation.PAGE_INSIGHTS,
            navigation.PAGE_EXPORT,
        ],
        "Secondary": [
            navigation.PAGE_SETTINGS,
            navigation.PAGE_HELP,
            navigation.PAGE_SUPPORT_ROLETHREAD,
        ],
    }


def test_help_page_owns_sidebar_and_other_pages_use_quick_rail():
    assert navigation.page_owns_sidebar(navigation.PAGE_HELP) is True
    assert navigation.page_owns_sidebar(navigation.PAGE_FAQ) is True
    assert navigation.page_owns_sidebar(navigation.PAGE_DIAGNOSTICS) is False
    assert navigation.page_owns_sidebar(navigation.PAGE_MANAGE_DATASET) is False
    assert navigation.page_owns_sidebar("Unknown") is False


def test_top_navigation_and_quick_rail_cover_registered_pages():
    registry_pages = set(navigation.get_page_registry())
    top_nav_pages = {
        page_id
        for page_ids in navigation.get_top_navigation_sections().values()
        for page_id in page_ids
    }
    quick_rail_pages = {
        page_id
        for page_ids in navigation.get_quick_navigation_pages().values()
        for page_id in page_ids
    }

    assert top_nav_pages == registry_pages
    assert "Tools" not in navigation.get_top_navigation_sections()
    assert navigation.get_page_registry()[navigation.PAGE_DATA_GENERATION].category == (
        "Output"
    )
    assert quick_rail_pages < registry_pages


def test_validate_page_renderers_accepts_complete_registry():
    renderers = {
        page_id: (lambda: None)
        for page_id in navigation.get_page_registry()
    }

    navigation.validate_page_renderers(renderers)


def test_validate_page_renderers_rejects_mismatch():
    renderers = {
        page_id: (lambda: None)
        for page_id in navigation.get_page_registry()
        if page_id != navigation.PAGE_FAQ
    }
    renderers["Not A Page"] = lambda: None

    with pytest.raises(ValueError, match="Page renderer registry mismatch"):
        navigation.validate_page_renderers(renderers)


def test_build_native_pages_uses_registry_metadata(monkeypatch):
    _patch_navigation_state(monkeypatch)
    renderers = {
        page_id: (lambda: None)
        for page_id in navigation.get_page_registry()
    }

    native_pages = navigation.build_native_pages(renderers)

    assert set(native_pages) == set(navigation.get_page_registry())
    assert native_pages[navigation.PAGE_CREATE_ENTRY]["default"] is True
    assert native_pages[navigation.PAGE_CREATE_ENTRY]["url_path"] == "create-entry"
    assert native_pages[navigation.PAGE_MANAGE_DATASET]["icon"] == ":material/folder_open:"
    assert native_pages[navigation.PAGE_EDIT_ENTRIES]["title"] == "Deep Edit"
    assert native_pages[navigation.PAGE_EDIT_ENTRIES]["url_path"] == "edit-entries"


def test_current_page_defaults_and_set_current_page(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)

    assert navigation.get_current_page() == navigation.PAGE_CREATE_ENTRY

    navigation.set_current_page(navigation.PAGE_MANAGE_DATASET)

    assert fake.session_state.page == navigation.PAGE_MANAGE_DATASET
    assert navigation.get_current_page() == navigation.PAGE_MANAGE_DATASET

    fake.session_state.page = "Unknown"
    assert navigation.get_current_page() == navigation.PAGE_CREATE_ENTRY


def test_set_current_page_rejects_unknown_page(monkeypatch):
    _patch_navigation_state(monkeypatch)

    with pytest.raises(ValueError, match="Unknown RoleThread page"):
        navigation.set_current_page("Unknown")


def test_navigate_to_page_sets_legacy_page_and_reruns(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)

    page = navigation.navigate_to_page(navigation.PAGE_VALIDATION)

    assert page == navigation.PAGE_VALIDATION
    assert fake.session_state.page == navigation.PAGE_VALIDATION
    assert fake.rerun_count == 1


def test_navigate_to_page_uses_native_switch_when_registered(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)
    native_page = object()
    navigation.register_native_pages({navigation.PAGE_EXPORT: native_page})

    page = navigation.navigate_to_page(navigation.PAGE_EXPORT)

    assert page == navigation.PAGE_EXPORT
    assert fake.session_state.page == navigation.PAGE_EXPORT
    assert fake.switched_page is native_page
    assert fake.rerun_count == 0


def test_navigate_to_page_can_skip_rerun_for_handoffs(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)

    navigation.navigate_to_page(navigation.PAGE_EDIT_ENTRIES, rerun=False)

    assert fake.session_state.page == navigation.PAGE_EDIT_ENTRIES
    assert fake.rerun_count == 0


def test_navigate_without_rerun_queues_native_switch_for_handoff(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)
    native_page = object()
    navigation.register_native_pages({navigation.PAGE_EDIT_ENTRIES: native_page})

    navigation.navigate_to_page(navigation.PAGE_EDIT_ENTRIES, rerun=False)

    assert fake.session_state.page == navigation.PAGE_EDIT_ENTRIES
    assert fake.session_state["_pending_native_page"] == navigation.PAGE_EDIT_ENTRIES
    assert fake.switched_page is None


def test_switch_to_pending_native_page_consumes_pending_switch(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)
    native_page = object()
    navigation.register_native_pages({navigation.PAGE_EDIT_ENTRIES: native_page})
    fake.session_state["_pending_native_page"] = navigation.PAGE_EDIT_ENTRIES

    switched = navigation.switch_to_pending_native_page()

    assert switched is True
    assert fake.switched_page is native_page
    assert "_pending_native_page" not in fake.session_state


def test_activate_page_clears_edit_state_for_native_top_nav_change(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)
    fake.session_state.page = navigation.PAGE_EDIT_ENTRIES
    fake.session_state.edit_entries_mode = "workspace"
    fake.session_state.full_edit_entry_uuid = "entry-1"

    navigation.activate_page(navigation.PAGE_EXPORT)

    assert fake.session_state.page == navigation.PAGE_EXPORT
    assert fake.session_state.edit_entries_mode == "browser"
    assert "full_edit_entry_uuid" not in fake.session_state


def test_navigate_away_from_edit_entries_clears_edit_state(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)
    fake.session_state.page = navigation.PAGE_EDIT_ENTRIES
    fake.session_state.quick_edit_entry_uuid = "entry-1"
    fake.session_state.edit_entries_mode = "workspace"
    fake.session_state.full_edit_entry_uuid = "entry-1"
    fake.session_state.full_edit_turn_0 = "draft"

    navigation.navigate_to_page(navigation.PAGE_MANAGE_DATASET, rerun=False)

    assert fake.session_state.page == navigation.PAGE_MANAGE_DATASET
    assert fake.session_state.edit_entries_mode == "browser"
    assert "quick_edit_entry_uuid" not in fake.session_state
    assert "full_edit_entry_uuid" not in fake.session_state
    assert "full_edit_turn_0" not in fake.session_state


def test_navigate_to_edit_entries_does_not_clear_handoff_state(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)
    fake.session_state.page = navigation.PAGE_MANAGE_DATASET
    fake.session_state.quick_edit_entry_uuid = "entry-1"

    navigation.navigate_to_page(
        navigation.PAGE_EDIT_ENTRIES,
        clear_edit_state=False,
        rerun=False,
    )

    assert fake.session_state.page == navigation.PAGE_EDIT_ENTRIES
    assert fake.session_state.quick_edit_entry_uuid == "entry-1"


def test_stats_navigation_preserves_focused_filter_and_routes(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)

    stats_navigation.navigate_to_entries(["a", "b"], "Needs review")

    assert fake.session_state[stats_navigation.STATS_FILTER_UUIDS_KEY] == {"a", "b"}
    assert fake.session_state[stats_navigation.STATS_FILTER_LABEL_KEY] == "Needs review"
    assert fake.session_state.entry_page == 0
    assert fake.session_state["manage_select_all_mode"] is False
    assert fake.session_state.page == navigation.PAGE_MANAGE_DATASET
    assert fake.rerun_count == 1

