from types import SimpleNamespace

from ui.ui_system_prompts import (
    _content_preview,
    _format_date,
    reconcile_system_prompt_selection_state,
    set_system_prompt_selection_state,
    system_prompt_checkbox_key,
)


def test_content_preview_collapses_whitespace_and_truncates():
    content = "Line one\n\nLine two with     extra spaces " + "x" * 140

    preview = _content_preview(content, limit=40)

    assert preview == "Line one Line two with extra spaces..."
    assert len(preview) <= 40


def test_content_preview_returns_short_prompt_unchanged_after_whitespace_cleanup():
    assert _content_preview("  Stay in character.\nUse vivid prose.  ") == (
        "Stay in character. Use vivid prose."
    )


def test_format_date_handles_missing_and_date_like_values():
    class DateLike:
        def strftime(self, _format):
            return "2026-05-13"

    assert _format_date(None) == "-"
    assert _format_date(DateLike()) == "2026-05-13"
    assert _format_date("already formatted") == "already formatted"


def test_system_prompt_selection_reconciles_unchecked_rows():
    templates = [
        SimpleNamespace(slug="group_scene"),
        SimpleNamespace(slug="solo_scene"),
    ]
    state = {
        "selected_system_prompt_slugs": {"group_scene", "solo_scene"},
        system_prompt_checkbox_key("group_scene"): True,
        system_prompt_checkbox_key("solo_scene"): False,
    }

    selected = reconcile_system_prompt_selection_state(state, templates)

    assert selected == {"group_scene"}
    assert state["selected_system_prompt_slugs"] == {"group_scene"}


def test_set_system_prompt_selection_state_updates_checkbox_keys():
    templates = [
        SimpleNamespace(slug="group_scene"),
        SimpleNamespace(slug="solo_scene"),
    ]
    state = {}

    set_system_prompt_selection_state(state, templates, {"solo_scene", "stale"})

    assert state["selected_system_prompt_slugs"] == {"solo_scene"}
    assert state[system_prompt_checkbox_key("group_scene")] is False
    assert state[system_prompt_checkbox_key("solo_scene")] is True
