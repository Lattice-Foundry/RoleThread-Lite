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

    def rerun(self):
        self.rerun_count += 1


def _patch_navigation_state(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(navigation, "st", fake)
    monkeypatch.setattr(session_state, "st", fake)
    monkeypatch.setattr(stats_navigation, "st", fake)
    return fake


def test_page_registry_exposes_legacy_pages():
    registry = navigation.get_page_registry()

    assert navigation.PAGE_CREATE_ENTRY in registry
    assert navigation.PAGE_MANAGE_DATASET in registry
    assert navigation.PAGE_EDIT_ENTRIES in registry
    assert navigation.get_page_title("Statistics") == "Insights"
    assert navigation.is_known_page("Statistics") is True
    assert navigation.is_known_page("Not A Page") is False


def test_sidebar_sections_preserve_current_legacy_structure():
    sections = navigation.get_sidebar_sections()

    assert sections == [
        ("Create", [("New Entry", navigation.PAGE_CREATE_ENTRY)]),
        (
            "Dataset",
            [
                ("Manage", navigation.PAGE_MANAGE_DATASET),
                ("Merge", navigation.PAGE_MERGE_DATASETS),
                ("Edit Entries", navigation.PAGE_EDIT_ENTRIES),
            ],
        ),
        (
            "Tools",
            [
                ("Export", navigation.PAGE_EXPORT),
                ("Validate", navigation.PAGE_VALIDATION),
            ],
        ),
        (
            "Metadata",
            [
                ("Tag Management", navigation.PAGE_TAG_MANAGEMENT),
                ("Character Management", navigation.PAGE_CHARACTER_MANAGEMENT),
                ("System Prompts", navigation.PAGE_SYSTEM_PROMPTS),
            ],
        ),
        ("Data Analytics", [("Insights", navigation.PAGE_INSIGHTS)]),
        ("Settings", [("Preferences", navigation.PAGE_SETTINGS)]),
        (
            "Documentation",
            [("Help", navigation.PAGE_HELP), ("FAQ", navigation.PAGE_FAQ)],
        ),
    ]


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

    with pytest.raises(ValueError, match="Unknown LoreForge page"):
        navigation.set_current_page("Unknown")


def test_navigate_to_page_sets_legacy_page_and_reruns(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)

    page = navigation.navigate_to_page(navigation.PAGE_VALIDATION)

    assert page == navigation.PAGE_VALIDATION
    assert fake.session_state.page == navigation.PAGE_VALIDATION
    assert fake.rerun_count == 1


def test_navigate_to_page_can_skip_rerun_for_handoffs(monkeypatch):
    fake = _patch_navigation_state(monkeypatch)

    navigation.navigate_to_page(navigation.PAGE_EDIT_ENTRIES, rerun=False)

    assert fake.session_state.page == navigation.PAGE_EDIT_ENTRIES
    assert fake.rerun_count == 0


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
