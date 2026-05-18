from ui.ui_components import (
    build_copyable_text_preview_document,
    is_prompt_chunk_heading,
    render_prompt_preview_html,
)


def test_prompt_chunk_heading_detection_accepts_placeholder_chunk_labels():
    assert is_prompt_chunk_heading("[ROLETHREAD TASK CHUNK]") is True
    assert is_prompt_chunk_heading("  [CHATML FORMAT CHUNK]  ") is True


def test_prompt_chunk_heading_detection_rejects_body_lines():
    assert is_prompt_chunk_heading("Template: conversation_scenario") is False
    assert is_prompt_chunk_heading("[Not final prompt prose]") is False
    assert is_prompt_chunk_heading("Required message order: system, user, assistant") is False


def test_prompt_preview_html_marks_heading_and_body_lines():
    html = render_prompt_preview_html(
        "[ROLETHREAD TASK CHUNK]\nTemplate: conversation_scenario"
    )

    assert '<span class="rolethread-preview-heading">[ROLETHREAD TASK CHUNK]</span>' in html
    assert (
        '<span class="rolethread-preview-body">Template: conversation_scenario</span>'
        in html
    )


def test_prompt_preview_html_escapes_visible_text_without_mutating_source():
    html = render_prompt_preview_html("[ROLETHREAD TASK CHUNK]\nUse <safe> & grounded text")

    assert "Use &lt;safe&gt; &amp; grounded text" in html
    assert "Use <safe> & grounded text" not in html


def test_copyable_preview_document_preserves_original_text_for_clipboard():
    prompt = "[ROLETHREAD TASK CHUNK]\nUse <safe> & grounded text"

    document, height = build_copyable_text_preview_document(
        "Generated Prompt Preview",
        prompt,
        copy_button_label="Copy Prompt",
        copied_label="Prompt copied.",
    )

    assert 'const roleThreadPreviewText = "[ROLETHREAD TASK CHUNK]\\nUse \\u003csafe\\u003e \\u0026 grounded text";' in document
    assert "Copy Prompt" in document
    assert "Prompt copied." in document
    assert height >= 220
