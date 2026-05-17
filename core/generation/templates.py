"""Generation template registry."""

from __future__ import annotations

from dataclasses import dataclass

from core.generation.models import GenerationTemplateId


@dataclass(frozen=True)
class GenerationTemplate:
    """Metadata for one generation prompt template."""

    template_id: GenerationTemplateId
    display_name: str
    description: str
    output_format: str


_GENERATION_TEMPLATES: tuple[GenerationTemplate, ...] = (
    GenerationTemplate(
        template_id=GenerationTemplateId.CONVERSATION_SCENARIO,
        display_name="Conversation Scenario Generator",
        description=(
            "Compile a prompt for generating ChatML JSONL conversational dataset "
            "entries from structured instructions."
        ),
        output_format="chatml_jsonl",
    ),
)


def get_generation_templates() -> list[GenerationTemplate]:
    """Return registered generation template metadata."""

    return list(_GENERATION_TEMPLATES)


def get_generation_template(template_id: GenerationTemplateId) -> GenerationTemplate:
    """Return one generation template by ID."""

    for template in _GENERATION_TEMPLATES:
        if template.template_id == template_id:
            return template
    raise ValueError(f"Generation template not found: {template_id}")
