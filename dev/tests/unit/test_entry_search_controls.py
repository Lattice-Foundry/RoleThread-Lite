from types import SimpleNamespace

import ui.entry_search_controls as controls
import ui.entry_search_state as search_state
from core.entry_search import SEARCH_MATCH_ALL_WORDS, SEARCH_MATCH_CONTAINS


class FakeSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _Column:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeStreamlit:
    def __init__(self):
        self.session_state = FakeSessionState()
        self.button_clicks = set()
        self.checkbox_values = {}
        self.radio_values = {}
        self.text_input_values = {}
        self.captions = []
        self.markdowns = []
        self.on_change_calls = 0

    def markdown(self, value):
        self.markdowns.append(value)

    def caption(self, value):
        self.captions.append(value)

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [_Column() for _index in range(count)]

    def text_input(self, _label, *, key, placeholder=None, on_change=None):
        if key in self.text_input_values:
            self.session_state[key] = self.text_input_values[key]
            if on_change:
                on_change()
        return self.session_state.get(key, "")

    def button(self, _label, *, key, disabled=False, on_click=None, args=()):
        clicked = key in self.button_clicks and not disabled
        if clicked and on_click:
            on_click(*args)
        return clicked

    def checkbox(self, _label, *, key, on_change=None):
        if key in self.checkbox_values:
            self.session_state[key] = self.checkbox_values[key]
            if on_change:
                on_change()
        return self.session_state.get(key, False)

    def radio(self, _label, *, options, format_func, horizontal, key, on_change=None):
        assert horizontal is True
        assert [format_func(option) for option in options] == [
            "Contains",
            "All Words",
            "Exact Phrase",
        ]
        if key in self.radio_values:
            self.session_state[key] = self.radio_values[key]
            if on_change:
                on_change()
        return self.session_state.get(key)


def _patch_streamlit(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(controls, "st", fake)
    monkeypatch.setattr(search_state, "st", SimpleNamespace(session_state=fake.session_state))
    return fake


def test_render_entry_search_controls_initializes_default_state(monkeypatch):
    fake = _patch_streamlit(monkeypatch)

    controls.render_entry_search_controls()

    assert fake.markdowns == ["**Search Entries**"]
    assert fake.session_state.entry_search_query == ""
    assert fake.session_state.entry_search_include_system is False
    assert fake.session_state.entry_search_include_user is True
    assert fake.session_state.entry_search_include_assistant is True
    assert fake.session_state.entry_search_match_mode == SEARCH_MATCH_CONTAINS
    assert "No entry search query active." not in fake.captions


def test_clear_search_button_clears_query_only(monkeypatch):
    fake = _patch_streamlit(monkeypatch)
    fake.session_state.entry_search_query = "lantern"
    fake.session_state.entry_search_include_system = True
    fake.session_state.entry_search_include_user = False
    fake.session_state.entry_search_include_assistant = True
    fake.session_state.entry_search_match_mode = SEARCH_MATCH_ALL_WORDS
    fake.button_clicks.add("entry_search_clear_button")

    controls.render_entry_search_controls()

    assert fake.session_state.entry_search_query == ""
    assert fake.session_state.entry_search_include_system is True
    assert fake.session_state.entry_search_include_user is False
    assert fake.session_state.entry_search_include_assistant is True
    assert fake.session_state.entry_search_match_mode == SEARCH_MATCH_ALL_WORDS


def test_clear_search_button_calls_change_callback(monkeypatch):
    fake = _patch_streamlit(monkeypatch)
    fake.session_state.entry_search_query = "lantern"
    fake.button_clicks.add("entry_search_clear_button")

    def _on_change():
        fake.on_change_calls += 1

    controls.render_entry_search_controls(on_change=_on_change)

    assert fake.session_state.entry_search_query == ""
    assert fake.on_change_calls == 1


def test_whitespace_query_is_inactive_and_clear_button_disabled(monkeypatch):
    fake = _patch_streamlit(monkeypatch)
    fake.session_state.entry_search_query = "   "
    fake.button_clicks.add("entry_search_clear_button")

    controls.render_entry_search_controls()

    assert fake.session_state.entry_search_query == "   "
    assert fake.captions == ["Search applies after tag filters and before pagination."]


def test_scope_toggles_update_shared_state(monkeypatch):
    fake = _patch_streamlit(monkeypatch)
    fake.checkbox_values = {
        "entry_search_include_system": True,
        "entry_search_include_user": False,
        "entry_search_include_assistant": False,
    }

    controls.render_entry_search_controls()

    assert fake.session_state.entry_search_include_system is True
    assert fake.session_state.entry_search_include_user is False
    assert fake.session_state.entry_search_include_assistant is False


def test_match_mode_control_updates_shared_state(monkeypatch):
    fake = _patch_streamlit(monkeypatch)
    fake.radio_values = {"entry_search_match_mode": SEARCH_MATCH_ALL_WORDS}

    controls.render_entry_search_controls()

    assert fake.session_state.entry_search_match_mode == SEARCH_MATCH_ALL_WORDS


def test_query_input_updates_shared_state_and_summary(monkeypatch):
    fake = _patch_streamlit(monkeypatch)
    fake.text_input_values = {"entry_search_query": "archive"}

    controls.render_entry_search_controls()

    assert fake.session_state.entry_search_query == "archive"
    assert 'Search active: "archive" | Contains | User, Assistant' in fake.captions


def test_active_summary_shows_no_roles_selected(monkeypatch):
    fake = _patch_streamlit(monkeypatch)
    fake.text_input_values = {"entry_search_query": "archive"}
    fake.checkbox_values = {
        "entry_search_include_user": False,
        "entry_search_include_assistant": False,
    }

    controls.render_entry_search_controls()

    assert 'Search active: "archive" | Contains | no roles selected' in fake.captions


def test_invalid_match_mode_is_repaired_before_render(monkeypatch):
    fake = _patch_streamlit(monkeypatch)
    fake.session_state.entry_search_match_mode = "regex"

    controls.render_entry_search_controls()

    assert fake.session_state.entry_search_match_mode == SEARCH_MATCH_CONTAINS


def test_no_results_copy_distinguishes_search_filter_and_scope_cases():
    assert (
        controls.format_entry_search_no_results_message(
            has_tag_filters=False,
            search_active=True,
            scopes_enabled=False,
        )
        == "Enable at least one message role to search."
    )
    assert (
        controls.format_entry_search_no_results_message(
            has_tag_filters=False,
            search_active=True,
            scopes_enabled=True,
        )
        == "No entries match the current search."
    )
    assert (
        controls.format_entry_search_no_results_message(
            has_tag_filters=True,
            search_active=True,
            scopes_enabled=True,
        )
        == "No entries match the current filters and search."
    )
    assert (
        controls.format_entry_search_no_results_message(
            has_tag_filters=True,
            search_active=False,
            scopes_enabled=False,
        )
        == "No entries match the current filters."
    )
