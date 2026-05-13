from types import SimpleNamespace

import ui.system_prompt_selector as selector
from ui.system_prompt_selector import render_system_prompt_template_selector


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.selectbox_calls = []
        self.captions = []

    def selectbox(self, label, options, format_func, key):
        self.selectbox_calls.append({
            "label": label,
            "options": options,
            "labels": [format_func(option) for option in options],
            "key": key,
        })
        return self.session_state.get(key, options[0])

    def caption(self, text):
        self.captions.append(text)


def _template(slug, name, content):
    return SimpleNamespace(slug=slug, name=name, content=content)


def test_system_prompt_selector_hides_when_no_templates(monkeypatch):
    fake = FakeStreamlit()
    monkeypatch.setattr(selector, "st", fake)
    monkeypatch.setattr(selector, "get_all_system_prompt_templates", lambda: [])

    applied = render_system_prompt_template_selector(
        target_key="prompt",
        select_key="selector",
    )

    assert applied is False
    assert fake.selectbox_calls == []


def test_system_prompt_selector_applies_template_once(monkeypatch):
    fake = FakeStreamlit()
    fake.session_state["selector"] = "group_scene"
    monkeypatch.setattr(selector, "st", fake)
    monkeypatch.setattr(
        selector,
        "get_all_system_prompt_templates",
        lambda: [_template("group_scene", "Group Scene", "Prompt text")],
    )
    applied_contents = []

    first_apply = render_system_prompt_template_selector(
        target_key="prompt",
        select_key="selector",
        mirror_keys=("mirror_prompt",),
        on_apply=applied_contents.append,
    )
    fake.session_state["prompt"] = "Customized prompt"
    second_apply = render_system_prompt_template_selector(
        target_key="prompt",
        select_key="selector",
        mirror_keys=("mirror_prompt",),
        on_apply=applied_contents.append,
    )

    assert first_apply is True
    assert second_apply is False
    assert fake.session_state["prompt"] == "Customized prompt"
    assert fake.session_state["mirror_prompt"] == "Prompt text"
    assert applied_contents == ["Prompt text"]
    assert fake.selectbox_calls[0]["labels"] == ["Custom", "Group Scene"]


def test_system_prompt_selector_custom_option_leaves_prompt_unchanged(monkeypatch):
    fake = FakeStreamlit()
    fake.session_state["selector"] = ""
    fake.session_state["prompt"] = "Handwritten prompt"
    monkeypatch.setattr(selector, "st", fake)
    monkeypatch.setattr(
        selector,
        "get_all_system_prompt_templates",
        lambda: [_template("solo_scene", "Solo Scene", "Library prompt")],
    )

    applied = render_system_prompt_template_selector(
        target_key="prompt",
        select_key="selector",
    )

    assert applied is False
    assert fake.session_state["prompt"] == "Handwritten prompt"
