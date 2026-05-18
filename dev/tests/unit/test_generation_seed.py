from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generation.seed as generation_seed
from core.models import Base, GenerationPromptChunk, GenerationTemplateChunk


def _generation_seed_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'generation_seed.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(generation_seed, "SessionLocal", session_factory)
    monkeypatch.setattr(
        generation_seed,
        "init_db",
        lambda: Base.metadata.create_all(bind=engine),
    )
    Base.metadata.create_all(engine)
    return session_factory


def _query_chunks(session):
    return {
        chunk.slug: chunk
        for chunk in session.query(GenerationPromptChunk).order_by(
            GenerationPromptChunk.slug
        )
    }


def _query_mappings(session):
    return (
        session.query(GenerationTemplateChunk)
        .filter_by(template_id="conversation_scenario")
        .order_by(GenerationTemplateChunk.sort_order)
        .all()
    )


def test_seed_generation_prompt_chunks_creates_expected_records(tmp_path, monkeypatch):
    session_factory = _generation_seed_db(tmp_path, monkeypatch)

    generation_seed.seed_generation_prompt_chunks()

    session = session_factory()
    try:
        chunks = _query_chunks(session)
    finally:
        session.close()

    assert set(chunks) == {
        "rolethread_generation_task",
        "chatml_format",
        "entry_count",
        "exchange_count",
        "content_instructions",
        "system_prompt_mode",
        "custom_system_prompt",
        "style",
        "tone",
        "output_delivery",
        "additional_instructions",
    }
    assert chunks["rolethread_generation_task"].chunk_text == (
        "[ROLETHREAD TASK CHUNK]\nTemplate: {{ template_id }}"
    )
    assert chunks["chatml_format"].chunk_text == (
        "[CHATML FORMAT CHUNK]\n"
        "Format: ChatML JSONL\n"
        "Required message order: system, user, assistant"
    )
    assert chunks["entry_count"].chunk_text == (
        "[ENTRY COUNT CHUNK]\nEntry count: {{ entry_count }}"
    )


def test_seed_generation_template_chunks_creates_expected_mappings(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_seed_db(tmp_path, monkeypatch)

    generation_seed.initialize_generation_registry()

    session = session_factory()
    try:
        mappings = _query_mappings(session)
    finally:
        session.close()

    assert [mapping.chunk_slug for mapping in mappings] == [
        "rolethread_generation_task",
        "chatml_format",
        "entry_count",
        "exchange_count",
        "content_instructions",
        "system_prompt_mode",
        "custom_system_prompt",
        "style",
        "tone",
        "output_delivery",
        "additional_instructions",
    ]
    assert [mapping.sort_order for mapping in mappings] == list(range(1, 12))


def test_seed_generation_template_chunks_persists_conditional_mappings(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_seed_db(tmp_path, monkeypatch)

    generation_seed.initialize_generation_registry()

    session = session_factory()
    try:
        mappings = {
            mapping.chunk_slug: mapping
            for mapping in session.query(GenerationTemplateChunk).all()
        }
    finally:
        session.close()

    custom_prompt = mappings["custom_system_prompt"]
    additional = mappings["additional_instructions"]
    assert custom_prompt.is_required is False
    assert custom_prompt.condition_key == "system_prompt_mode"
    assert custom_prompt.condition_value == "custom"
    assert additional.is_required is False
    assert additional.condition_key == "has_additional_instructions"
    assert additional.condition_value == "true"


def test_generation_seed_is_idempotent(tmp_path, monkeypatch):
    session_factory = _generation_seed_db(tmp_path, monkeypatch)

    generation_seed.initialize_generation_registry()
    generation_seed.initialize_generation_registry()

    session = session_factory()
    try:
        chunk_count = session.query(GenerationPromptChunk).count()
        mapping_count = session.query(GenerationTemplateChunk).count()
    finally:
        session.close()

    assert chunk_count == len(generation_seed.DEFAULT_GENERATION_PROMPT_CHUNKS)
    assert mapping_count == len(generation_seed.DEFAULT_GENERATION_TEMPLATE_CHUNKS)


def test_generation_seed_updates_existing_placeholder_records(tmp_path, monkeypatch):
    session_factory = _generation_seed_db(tmp_path, monkeypatch)
    session = session_factory()
    try:
        session.add(
            GenerationPromptChunk(
                slug="entry_count",
                title="Old title",
                chunk_text="stale",
                category="old",
                is_active=False,
            )
        )
        session.add(
            GenerationPromptChunk(
                slug="rolethread_generation_task",
                title="RoleThread generation task",
                chunk_text="[ROLETHREAD TASK CHUNK]",
            )
        )
        session.add(
            GenerationTemplateChunk(
                template_id="conversation_scenario",
                chunk_slug="rolethread_generation_task",
                sort_order=99,
                is_required=False,
                condition_key="old",
                condition_value="old",
            )
        )
        session.commit()
    finally:
        session.close()

    generation_seed.initialize_generation_registry()

    session = session_factory()
    try:
        entry_count = session.query(GenerationPromptChunk).filter_by(
            slug="entry_count"
        ).one()
        task_mapping = session.query(GenerationTemplateChunk).filter_by(
            template_id="conversation_scenario",
            chunk_slug="rolethread_generation_task",
        ).one()
    finally:
        session.close()

    assert entry_count.title == "Entry count"
    assert entry_count.chunk_text == "[ENTRY COUNT CHUNK]\nEntry count: {{ entry_count }}"
    assert entry_count.category == "quantity"
    assert entry_count.is_active is True
    assert task_mapping.sort_order == 1
    assert task_mapping.is_required is True
    assert task_mapping.condition_key is None
    assert task_mapping.condition_value is None


def test_generation_template_chunk_mapping_unique_constraint_exists():
    table = GenerationTemplateChunk.__table__

    assert any(
        constraint.name == "uq_generation_template_chunk_mapping"
        for constraint in table.constraints
    )
