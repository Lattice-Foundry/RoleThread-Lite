"""Generation subsystem models and validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GenerationTemplateId(StrEnum):
    """Stable identifiers for generation prompt templates."""

    CONVERSATION_SCENARIO = "conversation_scenario"


class SystemPromptMode(StrEnum):
    """How generated entries should handle system prompts."""

    AUTO = "auto"
    CUSTOM = "custom"


class OutputDeliveryMode(StrEnum):
    """Expected delivery shape for externally generated output."""

    PASTE_JSONL = "paste_jsonl"
    DOWNLOAD_FILE = "download_file"


class ConversationStyle(StrEnum):
    """High-level style direction for conversation generation."""

    NATURAL_DIALOGUE = "natural_dialogue"
    ROLEPLAY_IMMERSIVE = "roleplay_immersive"
    INSTRUCTIONAL = "instructional"
    NARRATIVE_DIALOGUE = "narrative_dialogue"


class ConversationTone(StrEnum):
    """High-level tone direction for conversation generation."""

    NEUTRAL = "neutral"
    WARM = "warm"
    PROFESSIONAL = "professional"
    DRAMATIC = "dramatic"
    PLAYFUL = "playful"


@dataclass(frozen=True)
class ConversationScenarioGenerationConfig:
    """Configuration for the initial conversation scenario generation template."""

    entry_count: int = 10
    exchange_count: int = 3
    content_instructions: str = ""
    system_prompt_mode: SystemPromptMode = SystemPromptMode.AUTO
    custom_system_prompt: str | None = None
    style: ConversationStyle = ConversationStyle.NATURAL_DIALOGUE
    tone: ConversationTone = ConversationTone.NEUTRAL
    output_delivery_mode: OutputDeliveryMode = OutputDeliveryMode.PASTE_JSONL
    additional_instructions: str | None = None


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def validate_conversation_scenario_config(
    config: ConversationScenarioGenerationConfig,
) -> list[str]:
    """Return validation errors for a conversation scenario generation config."""

    errors: list[str] = []
    if config.entry_count < 1:
        errors.append("entry_count must be >= 1.")
    if config.exchange_count < 1:
        errors.append("exchange_count must be >= 1.")
    if not config.content_instructions.strip():
        errors.append("content_instructions must be non-empty.")
    if (
        config.system_prompt_mode == SystemPromptMode.CUSTOM
        and _is_blank(config.custom_system_prompt)
    ):
        errors.append(
            "custom_system_prompt must be non-empty when system_prompt_mode is custom."
        )
    return errors
