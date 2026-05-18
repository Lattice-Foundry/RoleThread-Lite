"""Read-only database access for generation prompt chunk registries."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import selectinload

from core.db import SessionLocal, init_db
from core.models import GenerationPromptChunk, GenerationTemplateChunk


@dataclass(frozen=True)
class GenerationPromptChunkRecord:
    """Immutable read model for one active generation prompt chunk."""

    slug: str
    title: str
    chunk_text: str
    description: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class ResolvedGenerationChunk:
    """Immutable read model for one ordered template chunk mapping."""

    slug: str
    title: str
    chunk_text: str
    sort_order: int
    is_required: bool
    condition_key: str | None = None
    condition_value: str | None = None
    description: str | None = None
    category: str | None = None


def _chunk_record_from_model(
    chunk: GenerationPromptChunk,
) -> GenerationPromptChunkRecord:
    return GenerationPromptChunkRecord(
        slug=chunk.slug,
        title=chunk.title,
        description=chunk.description,
        chunk_text=chunk.chunk_text,
        category=chunk.category,
    )


def _resolved_chunk_from_mapping(
    mapping: GenerationTemplateChunk,
) -> ResolvedGenerationChunk:
    return ResolvedGenerationChunk(
        slug=mapping.chunk_slug,
        title=mapping.chunk.title,
        description=mapping.chunk.description,
        chunk_text=mapping.chunk.chunk_text,
        category=mapping.chunk.category,
        sort_order=mapping.sort_order,
        is_required=mapping.is_required,
        condition_key=mapping.condition_key,
        condition_value=mapping.condition_value,
    )


def get_generation_prompt_chunk(
    slug: str,
) -> GenerationPromptChunkRecord | None:
    """Return one active generation prompt chunk by slug."""

    init_db()
    session = SessionLocal()
    try:
        chunk = (
            session.query(GenerationPromptChunk)
            .filter(
                GenerationPromptChunk.slug == slug,
                GenerationPromptChunk.is_active.is_(True),
            )
            .first()
        )
        if chunk is None:
            return None
        return _chunk_record_from_model(chunk)
    finally:
        session.close()


def get_generation_template_chunks(template_id: str) -> list[ResolvedGenerationChunk]:
    """Return active chunks for a template in deterministic mapping order."""

    init_db()
    session = SessionLocal()
    try:
        mappings = (
            session.query(GenerationTemplateChunk)
            .options(selectinload(GenerationTemplateChunk.chunk))
            .join(GenerationPromptChunk)
            .filter(
                GenerationTemplateChunk.template_id == template_id,
                GenerationPromptChunk.is_active.is_(True),
            )
            .order_by(
                GenerationTemplateChunk.sort_order.asc(),
                GenerationTemplateChunk.id.asc(),
            )
            .all()
        )
        return [_resolved_chunk_from_mapping(mapping) for mapping in mappings]
    finally:
        session.close()


def resolve_generation_template_chunks(
    template_id: str,
    conditions: dict[str, str] | None = None,
) -> list[ResolvedGenerationChunk]:
    """Resolve active template chunks whose conditions match exactly."""

    condition_map = conditions or {}
    resolved: list[ResolvedGenerationChunk] = []
    for chunk in get_generation_template_chunks(template_id):
        if chunk.condition_key is None:
            resolved.append(chunk)
            continue
        if condition_map.get(chunk.condition_key) == chunk.condition_value:
            resolved.append(chunk)
    return resolved
