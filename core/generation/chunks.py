"""Reusable placeholder chunks for generation prompt compilation."""

from __future__ import annotations

from core.generation.models import (
    ConversationStyle,
    ConversationTone,
    GenerationTemplateId,
    OutputDeliveryMode,
    SystemPromptMode,
)


def _value(value: object) -> str:
    return getattr(value, "value", str(value))


def render_task_chunk(template_id: GenerationTemplateId) -> str:
    return "\n".join((
        "[ROLETHREAD TASK CHUNK]",
        f"Template: {_value(template_id)}",
    ))


def render_chatml_format_chunk() -> str:
    return "\n".join((
        "[CHATML FORMAT CHUNK]",
        "Format: ChatML JSONL",
        "Required message order: system, user, assistant",
    ))


def render_entry_count_chunk(entry_count: int) -> str:
    return "\n".join((
        "[ENTRY COUNT CHUNK]",
        f"Entry count: {entry_count}",
    ))


def render_exchange_count_chunk(exchange_count: int) -> str:
    return "\n".join((
        "[EXCHANGE COUNT CHUNK]",
        f"Exchange count per entry: {exchange_count}",
    ))


def render_content_instructions_chunk(content_instructions: str) -> str:
    return "\n".join((
        "[CONTENT INSTRUCTIONS CHUNK]",
        "Content instructions:",
        content_instructions.strip(),
    ))


def render_system_prompt_mode_chunk(system_prompt_mode: SystemPromptMode) -> str:
    return "\n".join((
        "[SYSTEM PROMPT MODE CHUNK]",
        f"System prompt mode: {_value(system_prompt_mode)}",
    ))


def render_custom_system_prompt_chunk(custom_system_prompt: str) -> str:
    return "\n".join((
        "[CUSTOM SYSTEM PROMPT CHUNK]",
        "Custom system prompt:",
        custom_system_prompt.strip(),
    ))


def render_style_chunk(style: ConversationStyle) -> str:
    return "\n".join((
        "[STYLE CHUNK]",
        f"Style: {_value(style)}",
    ))


def render_tone_chunk(tone: ConversationTone) -> str:
    return "\n".join((
        "[TONE CHUNK]",
        f"Tone: {_value(tone)}",
    ))


def render_output_delivery_chunk(output_delivery_mode: OutputDeliveryMode) -> str:
    return "\n".join((
        "[OUTPUT DELIVERY CHUNK]",
        f"Output delivery mode: {_value(output_delivery_mode)}",
    ))


def render_additional_instructions_chunk(additional_instructions: str) -> str:
    return "\n".join((
        "[ADDITIONAL INSTRUCTIONS CHUNK]",
        "Additional instructions:",
        additional_instructions.strip(),
    ))
