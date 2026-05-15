from ui.html_helpers import escape_html, escape_upper_html
from ui.ui_components import _format_preview_content
from ui.ui_tag_management import _active_tag_detail_html, _archived_tag_label_html


def test_escape_html_escapes_script_like_display_values():
    assert escape_html("<script>alert(1)</script>") == (
        "&lt;script&gt;alert(1)&lt;/script&gt;"
    )
    assert escape_upper_html("<b>Injected</b>") == "&lt;B&gt;INJECTED&lt;/B&gt;"


def test_preview_content_escapes_user_content_inside_html_wrapper():
    rendered = _format_preview_content('<b>Injected</b> "quoted <script>x</script>"')

    assert "&lt;b&gt;Injected&lt;/b&gt;" in rendered
    assert "&lt;script&gt;x&lt;/script&gt;" in rendered
    assert "<b>Injected</b>" not in rendered
    assert "<script>x</script>" not in rendered


def test_tag_management_html_helpers_escape_user_tag_values():
    active_html = _active_tag_detail_html(
        {"name": "<b>Injected</b>", "slug": "<script>x</script>"},
        "<custom>",
        "#ffffff",
    )
    archived_html = _archived_tag_label_html(
        {"display_name": "<script>alert(1)</script>"},
        "<deleted>",
    )

    assert "&lt;b&gt;Injected&lt;/b&gt;" in active_html
    assert "&lt;script&gt;x&lt;/script&gt;" in active_html
    assert "&lt;custom&gt;" in active_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in archived_html
    assert "&lt;deleted&gt;" in archived_html
    assert "<script>" not in active_html
    assert "<script>" not in archived_html
