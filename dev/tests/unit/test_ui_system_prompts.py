from ui.ui_system_prompts import _content_preview, _format_date


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
