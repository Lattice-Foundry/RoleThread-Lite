"""Deterministic prompt compilers for generation workflows."""

from __future__ import annotations

from core.generation.chunks import (
    render_additional_instructions_chunk,
    render_chatml_format_chunk,
    render_content_instructions_chunk,
    render_custom_system_prompt_chunk,
    render_entry_count_chunk,
    render_exchange_count_chunk,
    render_output_delivery_chunk,
    render_style_chunk,
    render_system_prompt_mode_chunk,
    render_task_chunk,
    render_tone_chunk,
)
from core.generation.models import (
    ConversationScenarioGenerationConfig,
    GenerationTemplateId,
    SystemPromptMode,
    validate_conversation_scenario_config,
)


def compile_conversation_scenario_prompt(
    config: ConversationScenarioGenerationConfig,
) -> str:
    """Compile a deterministic placeholder prompt for conversation scenarios."""

    errors = validate_conversation_scenario_config(config)
    if errors:
        raise ValueError("Invalid conversation scenario generation config: " + "; ".join(errors))

    chunks = [
        render_task_chunk(GenerationTemplateId.CONVERSATION_SCENARIO),
        render_chatml_format_chunk(),
        render_entry_count_chunk(config.entry_count),
        render_exchange_count_chunk(config.exchange_count),
        render_content_instructions_chunk(config.content_instructions),
        render_system_prompt_mode_chunk(config.system_prompt_mode),
    ]

    if config.system_prompt_mode == SystemPromptMode.CUSTOM:
        chunks.append(render_custom_system_prompt_chunk(config.custom_system_prompt or ""))

    chunks.extend([
        render_style_chunk(config.style),
        render_tone_chunk(config.tone),
        render_output_delivery_chunk(config.output_delivery_mode),
    ])

    if config.additional_instructions and config.additional_instructions.strip():
        chunks.append(render_additional_instructions_chunk(config.additional_instructions))

    return "\n\n".join(chunks)
