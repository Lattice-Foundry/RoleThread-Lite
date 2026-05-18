"""Database seeding for generation prompt chunk defaults."""

from __future__ import annotations

from dataclasses import dataclass

from core.db import SessionLocal, init_db
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
from core.generation.models import GenerationTemplateId
from core.models import GenerationPromptChunk, GenerationTemplateChunk


@dataclass(frozen=True)
class GenerationPromptChunkSeed:
    """Built-in placeholder chunk seed data."""

    slug: str
    title: str
    chunk_text: str
    category: str
    description: str | None = None


@dataclass(frozen=True)
class GenerationTemplateChunkSeed:
    """Built-in template-to-chunk seed data."""

    template_id: str
    chunk_slug: str
    sort_order: int
    is_required: bool = True
    condition_key: str | None = None
    condition_value: str | None = None


DEFAULT_GENERATION_PROMPT_CHUNKS: tuple[GenerationPromptChunkSeed, ...] = (
    GenerationPromptChunkSeed(
        slug="rolethread_generation_task",
        title="RoleThread generation task",
        chunk_text=render_task_chunk("{{ template_id }}"),
        category="task",
    ),
    GenerationPromptChunkSeed(
        slug="chatml_format",
        title="ChatML format",
        chunk_text=render_chatml_format_chunk(),
        category="format",
    ),
    GenerationPromptChunkSeed(
        slug="entry_count",
        title="Entry count",
        chunk_text=render_entry_count_chunk("{{ entry_count }}"),
        category="quantity",
    ),
    GenerationPromptChunkSeed(
        slug="exchange_count",
        title="Exchange count",
        chunk_text=render_exchange_count_chunk("{{ exchange_count }}"),
        category="quantity",
    ),
    GenerationPromptChunkSeed(
        slug="content_instructions",
        title="Content instructions",
        chunk_text=render_content_instructions_chunk("{{ content_instructions }}"),
        category="instructions",
    ),
    GenerationPromptChunkSeed(
        slug="system_prompt_mode",
        title="System prompt mode",
        chunk_text=render_system_prompt_mode_chunk("{{ system_prompt_mode }}"),
        category="system_prompt",
    ),
    GenerationPromptChunkSeed(
        slug="custom_system_prompt",
        title="Custom system prompt",
        chunk_text=render_custom_system_prompt_chunk("{{ custom_system_prompt }}"),
        category="system_prompt",
    ),
    GenerationPromptChunkSeed(
        slug="style",
        title="Style",
        chunk_text=render_style_chunk("{{ style }}"),
        category="style",
    ),
    GenerationPromptChunkSeed(
        slug="tone",
        title="Tone",
        chunk_text=render_tone_chunk("{{ tone }}"),
        category="style",
    ),
    GenerationPromptChunkSeed(
        slug="output_delivery",
        title="Output delivery",
        chunk_text=render_output_delivery_chunk("{{ output_delivery_mode }}"),
        category="output",
    ),
    GenerationPromptChunkSeed(
        slug="additional_instructions",
        title="Additional instructions",
        chunk_text=render_additional_instructions_chunk(
            "{{ additional_instructions }}"
        ),
        category="instructions",
    ),
)

CONVERSATION_SCENARIO_TEMPLATE_ID = GenerationTemplateId.CONVERSATION_SCENARIO.value

DEFAULT_GENERATION_TEMPLATE_CHUNKS: tuple[GenerationTemplateChunkSeed, ...] = (
    GenerationTemplateChunkSeed(
        CONVERSATION_SCENARIO_TEMPLATE_ID,
        "rolethread_generation_task",
        1,
    ),
    GenerationTemplateChunkSeed(CONVERSATION_SCENARIO_TEMPLATE_ID, "chatml_format", 2),
    GenerationTemplateChunkSeed(CONVERSATION_SCENARIO_TEMPLATE_ID, "entry_count", 3),
    GenerationTemplateChunkSeed(CONVERSATION_SCENARIO_TEMPLATE_ID, "exchange_count", 4),
    GenerationTemplateChunkSeed(
        CONVERSATION_SCENARIO_TEMPLATE_ID,
        "content_instructions",
        5,
    ),
    GenerationTemplateChunkSeed(
        CONVERSATION_SCENARIO_TEMPLATE_ID,
        "system_prompt_mode",
        6,
    ),
    GenerationTemplateChunkSeed(
        CONVERSATION_SCENARIO_TEMPLATE_ID,
        "custom_system_prompt",
        7,
        is_required=False,
        condition_key="system_prompt_mode",
        condition_value="custom",
    ),
    GenerationTemplateChunkSeed(CONVERSATION_SCENARIO_TEMPLATE_ID, "style", 8),
    GenerationTemplateChunkSeed(CONVERSATION_SCENARIO_TEMPLATE_ID, "tone", 9),
    GenerationTemplateChunkSeed(
        CONVERSATION_SCENARIO_TEMPLATE_ID,
        "output_delivery",
        10,
    ),
    GenerationTemplateChunkSeed(
        CONVERSATION_SCENARIO_TEMPLATE_ID,
        "additional_instructions",
        11,
        is_required=False,
        condition_key="has_additional_instructions",
        condition_value="true",
    ),
)


def seed_generation_prompt_chunks() -> None:
    """Idempotently seed built-in placeholder generation prompt chunks."""

    init_db()
    session = SessionLocal()
    try:
        for seed in DEFAULT_GENERATION_PROMPT_CHUNKS:
            chunk = session.query(GenerationPromptChunk).filter_by(
                slug=seed.slug
            ).first()
            if chunk is None:
                chunk = GenerationPromptChunk(slug=seed.slug)
                session.add(chunk)
            chunk.title = seed.title
            chunk.description = seed.description
            chunk.chunk_text = seed.chunk_text
            chunk.category = seed.category
            chunk.is_active = True
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_generation_template_chunks() -> None:
    """Idempotently seed built-in generation template chunk mappings."""

    init_db()
    session = SessionLocal()
    try:
        for seed in DEFAULT_GENERATION_TEMPLATE_CHUNKS:
            mapping = (
                session.query(GenerationTemplateChunk)
                .filter_by(template_id=seed.template_id, chunk_slug=seed.chunk_slug)
                .first()
            )
            if mapping is None:
                mapping = GenerationTemplateChunk(
                    template_id=seed.template_id,
                    chunk_slug=seed.chunk_slug,
                )
                session.add(mapping)
            mapping.sort_order = seed.sort_order
            mapping.is_required = seed.is_required
            mapping.condition_key = seed.condition_key
            mapping.condition_value = seed.condition_value
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize_generation_registry() -> None:
    """Create and seed generation prompt chunk registry defaults."""

    seed_generation_prompt_chunks()
    seed_generation_template_chunks()
