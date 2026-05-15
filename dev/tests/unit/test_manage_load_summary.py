from types import SimpleNamespace

import ui.manage.load_summary as load_summary
from core.format_conversion import FORMAT_CHATML


class FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.info_messages: list[str] = []
        self.success_messages: list[str] = []

    def info(self, message):
        self.info_messages.append(message)

    def success(self, message):
        self.success_messages.append(message)


def test_untagged_load_summary_does_not_render_manage_dataset_cta(monkeypatch):
    fake = FakeStreamlit()
    recommended_actions: list[dict] = []
    normalization = SimpleNamespace(
        source_format=FORMAT_CHATML,
        diagnostics=SimpleNamespace(entries_analyzed=1, valid_entries=1),
        entries=[{"messages": [], "tags": []}],
        parse_error_count=0,
        role_values_normalized=0,
        message_content_trimmed=0,
        alias_rewrites={},
        format_warnings=[],
    )
    monkeypatch.setattr(load_summary, "st", fake)
    monkeypatch.setattr(
        load_summary,
        "render_recommended_action",
        lambda *args, **kwargs: recommended_actions.append(kwargs),
    )

    load_summary.render_load_format_summary(
        normalization,
        loaded_dataset_path="dataset.jsonl",
        loaded_entry_count=1,
    )

    assert "1 entry are untagged." in fake.info_messages
    assert recommended_actions == []
