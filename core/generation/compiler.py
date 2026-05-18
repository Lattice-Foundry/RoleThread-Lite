"""Deterministic prompt compilers for generation workflows."""

from __future__ import annotations

from core.generation.models import (
    ConversationScenarioGenerationConfig,
    ConversationStyle,
    ConversationTone,
    GenerationTemplateId,
    validate_conversation_scenario_config,
)
from core.generation.registry import (
    ResolvedGenerationChunk,
    resolve_generation_template_chunks,
)


def _value(value: object | None) -> str:
    if value is None:
        return ""
    return getattr(value, "value", str(value))


STYLE_INSTRUCTIONS: dict[ConversationStyle, str] = {
    ConversationStyle.NATURAL_DIALOGUE: (
        "Generate conversations that feel natural, grounded, and conversationally realistic."
    ),
    ConversationStyle.ROLEPLAY_IMMERSIVE: (
        "Generate immersive roleplay-style conversations with strong scene continuity, emotional presence, and interaction detail."
    ),
    ConversationStyle.INSTRUCTIONAL: (
        "Generate conversations focused on clarity, instruction-following, and helpful information exchange."
    ),
    ConversationStyle.NARRATIVE_DIALOGUE: (
        "Generate conversations that blend dialogue with narrative scene description and contextual narration."
    ),
}

TONE_INSTRUCTIONS: dict[ConversationTone, str] = {
    ConversationTone.NEUTRAL: (
        "Maintain a balanced and emotionally neutral conversational tone."
    ),
    ConversationTone.WARM: (
        "Maintain a warm, emotionally engaging, and personable conversational tone."
    ),
    ConversationTone.PROFESSIONAL: (
        "Maintain a professional, composed, and respectful conversational tone."
    ),
    ConversationTone.DRAMATIC: (
        "Maintain a dramatic, emotionally heightened, and tension-aware conversational tone."
    ),
    ConversationTone.PLAYFUL: (
        "Maintain a playful, lighthearted, and expressive conversational tone."
    ),
}


def _style_instruction(style: ConversationStyle) -> str:
    return STYLE_INSTRUCTIONS[style]


def _tone_instruction(tone: ConversationTone) -> str:
    return TONE_INSTRUCTIONS[tone]


def render_generation_chunk_text(
    chunk_text: str,
    variables: dict[str, str],
) -> str:
    """Render one DB-backed generation chunk with deterministic placeholders."""

    rendered = chunk_text
    for key, value in sorted(variables.items()):
        rendered = rendered.replace("{{ " + key + " }}", value)
    return rendered


def _condition_map(config: ConversationScenarioGenerationConfig) -> dict[str, str]:
    conditions = {
        "system_prompt_mode": _value(config.system_prompt_mode),
        "output_delivery_mode": _value(config.output_delivery_mode),
    }
    if config.additional_instructions and config.additional_instructions.strip():
        conditions["has_additional_instructions"] = "true"
    return conditions


def _template_variables(
    config: ConversationScenarioGenerationConfig,
) -> dict[str, str]:
    return {
        "template_id": GenerationTemplateId.CONVERSATION_SCENARIO.value,
        "entry_count": str(config.entry_count),
        "exchange_count": str(config.exchange_count),
        "content_instructions": config.content_instructions.strip(),
        "system_prompt_mode": _value(config.system_prompt_mode),
        "custom_system_prompt": (config.custom_system_prompt or "").strip(),
        "style": _style_instruction(config.style),
        "tone": _tone_instruction(config.tone),
        "output_delivery_mode": _value(config.output_delivery_mode),
        "additional_instructions": (config.additional_instructions or "").strip(),
    }


def _validate_resolved_chunks(chunks: list[ResolvedGenerationChunk]) -> None:
    if not chunks:
        raise ValueError(
            "Generation template registry is missing mappings for "
            f"{GenerationTemplateId.CONVERSATION_SCENARIO.value}."
        )
    missing_required = [
        chunk.slug for chunk in chunks if chunk.is_required and not chunk.chunk_text
    ]
    if missing_required:
        raise ValueError(
            "Generation template registry has required chunks without text: "
            + ", ".join(missing_required)
        )


def compile_conversation_scenario_prompt(
    config: ConversationScenarioGenerationConfig,
) -> str:
    """Compile a deterministic prompt for conversation scenarios."""

    errors = validate_conversation_scenario_config(config)
    if errors:
        raise ValueError("Invalid conversation scenario generation config: " + "; ".join(errors))

    chunks = resolve_generation_template_chunks(
        GenerationTemplateId.CONVERSATION_SCENARIO.value,
        conditions=_condition_map(config),
    )
    _validate_resolved_chunks(chunks)
    variables = _template_variables(config)
    return "\n\n".join(
        render_generation_chunk_text(chunk.chunk_text, variables)
        for chunk in chunks
    )
