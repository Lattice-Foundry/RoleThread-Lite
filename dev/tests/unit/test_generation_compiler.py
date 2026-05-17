from pathlib import Path

import pytest

from core.generation import (
    ConversationScenarioGenerationConfig,
    ConversationStyle,
    ConversationTone,
    GenerationTemplateId,
    OutputDeliveryMode,
    SystemPromptMode,
    compile_conversation_scenario_prompt,
    get_generation_template,
    get_generation_templates,
    validate_conversation_scenario_config,
)


def _valid_config(**overrides):
    values = {
        "content_instructions": "Generate practical support conversations.",
    }
    values.update(overrides)
    return ConversationScenarioGenerationConfig(**values)


def test_default_valid_config_compiles_successfully():
    prompt = compile_conversation_scenario_prompt(_valid_config())

    assert isinstance(prompt, str)
    assert prompt.startswith("[ROLETHREAD TASK CHUNK]")
    assert "Template: conversation_scenario" in prompt


def test_compiled_prompt_includes_placeholder_chunk_labels():
    prompt = compile_conversation_scenario_prompt(_valid_config())

    expected_labels = (
        "[ROLETHREAD TASK CHUNK]",
        "[CHATML FORMAT CHUNK]",
        "[ENTRY COUNT CHUNK]",
        "[EXCHANGE COUNT CHUNK]",
        "[CONTENT INSTRUCTIONS CHUNK]",
        "[SYSTEM PROMPT MODE CHUNK]",
        "[STYLE CHUNK]",
        "[TONE CHUNK]",
        "[OUTPUT DELIVERY CHUNK]",
    )
    for label in expected_labels:
        assert label in prompt


def test_compiled_prompt_uses_blank_lines_between_chunks():
    prompt = compile_conversation_scenario_prompt(_valid_config())

    assert "\n\n[CHATML FORMAT CHUNK]" in prompt
    assert "\n\n[ENTRY COUNT CHUNK]" in prompt


def test_entry_count_appears_correctly():
    prompt = compile_conversation_scenario_prompt(_valid_config(entry_count=17))

    assert "[ENTRY COUNT CHUNK]\nEntry count: 17" in prompt


def test_exchange_count_appears_correctly():
    prompt = compile_conversation_scenario_prompt(_valid_config(exchange_count=5))

    assert "[EXCHANGE COUNT CHUNK]\nExchange count per entry: 5" in prompt


def test_content_instructions_appears_correctly():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(content_instructions="  Generate customer handoff examples.  ")
    )

    assert (
        "[CONTENT INSTRUCTIONS CHUNK]\n"
        "Content instructions:\n"
        "Generate customer handoff examples."
    ) in prompt


def test_auto_system_prompt_mode_skips_custom_system_prompt_chunk():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(
            system_prompt_mode=SystemPromptMode.AUTO,
            custom_system_prompt="Ignored for auto mode.",
        )
    )

    assert "[SYSTEM PROMPT MODE CHUNK]\nSystem prompt mode: auto" in prompt
    assert "[CUSTOM SYSTEM PROMPT CHUNK]" not in prompt
    assert "Ignored for auto mode." not in prompt


def test_custom_system_prompt_mode_includes_custom_chunk_and_text():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(
            system_prompt_mode=SystemPromptMode.CUSTOM,
            custom_system_prompt="  Stay concise and grounded.  ",
        )
    )

    assert "[SYSTEM PROMPT MODE CHUNK]\nSystem prompt mode: custom" in prompt
    assert (
        "[CUSTOM SYSTEM PROMPT CHUNK]\n"
        "Custom system prompt:\n"
        "Stay concise and grounded."
    ) in prompt


@pytest.mark.parametrize("additional_instructions", [None, "", "   "])
def test_additional_instructions_chunk_is_skipped_when_blank(additional_instructions):
    prompt = compile_conversation_scenario_prompt(
        _valid_config(additional_instructions=additional_instructions)
    )

    assert "[ADDITIONAL INSTRUCTIONS CHUNK]" not in prompt


def test_additional_instructions_chunk_is_included_when_provided():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(additional_instructions="  Avoid duplicate setups.  ")
    )

    assert (
        "[ADDITIONAL INSTRUCTIONS CHUNK]\n"
        "Additional instructions:\n"
        "Avoid duplicate setups."
    ) in prompt


def test_blank_content_instructions_returns_validation_error_and_raises():
    config = _valid_config(content_instructions="  ")

    assert validate_conversation_scenario_config(config) == [
        "content_instructions must be non-empty."
    ]
    with pytest.raises(ValueError, match="content_instructions must be non-empty"):
        compile_conversation_scenario_prompt(config)


def test_custom_mode_with_blank_custom_system_prompt_invalid():
    config = _valid_config(
        system_prompt_mode=SystemPromptMode.CUSTOM,
        custom_system_prompt=" ",
    )

    errors = validate_conversation_scenario_config(config)
    assert errors == [
        "custom_system_prompt must be non-empty when system_prompt_mode is custom."
    ]
    with pytest.raises(ValueError, match="custom_system_prompt must be non-empty"):
        compile_conversation_scenario_prompt(config)


def test_entry_count_less_than_one_invalid():
    config = _valid_config(entry_count=0)

    assert "entry_count must be >= 1." in validate_conversation_scenario_config(config)
    with pytest.raises(ValueError, match="entry_count must be >= 1"):
        compile_conversation_scenario_prompt(config)


def test_exchange_count_less_than_one_invalid():
    config = _valid_config(exchange_count=0)

    assert "exchange_count must be >= 1." in validate_conversation_scenario_config(config)
    with pytest.raises(ValueError, match="exchange_count must be >= 1"):
        compile_conversation_scenario_prompt(config)


def test_templates_registry_returns_conversation_scenario_generator():
    templates = get_generation_templates()
    template = get_generation_template(GenerationTemplateId.CONVERSATION_SCENARIO)

    assert templates == [template]
    assert template.template_id == GenerationTemplateId.CONVERSATION_SCENARIO
    assert template.display_name == "Conversation Scenario Generator"
    assert template.output_format == "chatml_jsonl"


def test_compiler_renders_style_tone_and_output_delivery_values():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(
            style=ConversationStyle.ROLEPLAY_IMMERSIVE,
            tone=ConversationTone.PLAYFUL,
            output_delivery_mode=OutputDeliveryMode.DOWNLOAD_FILE,
        )
    )

    assert "[STYLE CHUNK]\nStyle: roleplay_immersive" in prompt
    assert "[TONE CHUNK]\nTone: playful" in prompt
    assert "[OUTPUT DELIVERY CHUNK]\nOutput delivery mode: download_file" in prompt


def test_generation_core_package_does_not_import_streamlit():
    import core.generation as generation

    generation_root = next(iter(generation.__path__))
    for path in Path(generation_root).glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert "streamlit" not in source
