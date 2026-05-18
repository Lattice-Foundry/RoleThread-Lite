"""Database seeding for generation prompt chunk defaults."""

from __future__ import annotations

from dataclasses import dataclass

from core.db import SessionLocal, init_db
from core.generation.models import GenerationTemplateId
from core.models import GenerationPromptChunk, GenerationTemplateChunk


@dataclass(frozen=True)
class GenerationPromptChunkSeed:
    """Built-in generation prompt chunk seed data."""

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
        chunk_text="""You are generating structured conversational training data for LLM fine-tuning.

Your task is to generate high-quality ChatML JSONL dataset entries that can be imported directly into a conversational training dataset.

You are generating training data, not interacting with the user directly.

All output must follow the required formatting and structural rules exactly.

Do not generate explanations, commentary, analysis, summaries, conversational framing, or metadata outside the requested dataset output.

Prioritize:
- structural correctness
- conversational realism
- coherent multi-turn continuity
- consistent behavior within each dataset entry
- import-safe JSONL formatting""",
        category="task",
    ),
    GenerationPromptChunkSeed(
        slug="chatml_format",
        title="ChatML format",
        chunk_text="""Output valid ChatML JSONL only.

Each dataset entry must be a single valid JSON object written on a single line.

Do not wrap dataset entries in a JSON array.

Each dataset entry must contain a top-level "messages" array.

Each "messages" array must begin with exactly one system message.

After the system message, messages must alternate in this exact order:
user → assistant → user → assistant

Do not break message ordering.

Each message object must contain:
- "role"
- "content"

Valid roles are:
- "system"
- "user"
- "assistant"

All JSON output must be syntactically valid.

Correctly escape:
- quotation marks
- newline characters
- special characters inside JSON strings

Do not include:
- comments
- trailing commas
- markdown explanations
- metadata fields
- tags
- analysis text
- conversational framing outside the dataset output""",
        category="format",
    ),
    GenerationPromptChunkSeed(
        slug="entry_count",
        title="Entry count",
        chunk_text="""Generate exactly {{ entry_count }} complete dataset entries.

Each dataset entry must be:
- structurally complete
- independently valid
- formatted as valid ChatML JSONL
- written as a separate single-line JSON object

Do not generate fewer than {{ entry_count }} dataset entries.

Do not generate more than {{ entry_count }} dataset entries.

Do not stop generation before all requested dataset entries are completed.

Every generated dataset entry must fully comply with all formatting and structural requirements.""",
        category="quantity",
    ),
    GenerationPromptChunkSeed(
        slug="exchange_count",
        title="Exchange count",
        chunk_text="""Each dataset entry must contain exactly {{ exchange_count }} user/assistant exchanges after the system message.

One exchange means:
- one user message
- followed by one assistant message

The required message order is:
system → user → assistant → user → assistant

Do not generate fewer than {{ exchange_count }} exchanges per dataset entry.

Do not generate more than {{ exchange_count }} exchanges per dataset entry.

Maintain correct role alternation throughout every dataset entry.

Do not break message ordering or exchange structure.""",
        category="quantity",
    ),
    GenerationPromptChunkSeed(
        slug="content_instructions",
        title="Content instructions",
        chunk_text="""Generate dataset entries using the following scenario and behavioral requirements:

{{ content_instructions }}""",
        category="instructions",
    ),
    GenerationPromptChunkSeed(
        slug="system_prompt_mode",
        title="System prompt mode",
        chunk_text="Generate an appropriate system prompt for each dataset entry unless a custom system prompt is provided.",
        category="system_prompt",
    ),
    GenerationPromptChunkSeed(
        slug="custom_system_prompt",
        title="Custom system prompt",
        chunk_text="""Use the following system prompt exactly:

{{ custom_system_prompt }}""",
        category="system_prompt",
    ),
    GenerationPromptChunkSeed(
        slug="style",
        title="Style",
        chunk_text="""Conversation style requirements:

{{ style }}""",
        category="style",
    ),
    GenerationPromptChunkSeed(
        slug="tone",
        title="Tone",
        chunk_text="""Conversation tone requirements:

{{ tone }}""",
        category="style",
    ),
    GenerationPromptChunkSeed(
        slug="output_delivery",
        title="Output delivery",
        chunk_text="""If output_delivery_mode is "paste_jsonl":

- Return the generated dataset directly in a single fenced code block.
- Do not include explanation before or after the dataset output.

If output_delivery_mode is "download_file":

- If supported, provide the generated dataset as a downloadable `.jsonl` file.
- If downloadable file output is unavailable, return the dataset directly in a single fenced code block.""",
        category="output",
    ),
    GenerationPromptChunkSeed(
        slug="additional_instructions",
        title="Additional instructions",
        chunk_text="""Additional instructions:

{{ additional_instructions }}""",
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
    """Idempotently seed built-in generation prompt chunks."""

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
