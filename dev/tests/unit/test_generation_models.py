import pytest
from sqlalchemy import create_engine, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from core.models import Base, GenerationPromptChunk, GenerationTemplateChunk


@pytest.fixture
def generation_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'generation_models.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, session_factory


def test_generation_prompt_chunk_can_be_instantiated():
    chunk = GenerationPromptChunk(
        slug="rolethread_generation_task",
        title="RoleThread generation task",
        description="Task framing chunk.",
        chunk_text="[ROLETHREAD TASK CHUNK]\nTemplate: conversation_scenario",
        category="task",
    )

    assert chunk.slug == "rolethread_generation_task"
    assert chunk.title == "RoleThread generation task"
    assert "GenerationPromptChunk" in repr(chunk)


def test_generation_prompt_chunk_slug_unique_constraint(generation_db):
    _engine, session_factory = generation_db
    session = session_factory()
    try:
        session.add_all(
            [
                GenerationPromptChunk(
                    slug="chatml_jsonl_schema",
                    title="ChatML JSONL schema",
                    chunk_text="[CHATML FORMAT CHUNK]",
                ),
                GenerationPromptChunk(
                    slug="chatml_jsonl_schema",
                    title="Duplicate schema",
                    chunk_text="[CHATML FORMAT CHUNK]",
                ),
            ]
        )

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()


def test_generation_prompt_chunk_stores_multiline_text(generation_db):
    _engine, session_factory = generation_db
    session = session_factory()
    text = "[CHATML FORMAT CHUNK]\nFormat: ChatML JSONL\nRequired message order: system, user, assistant"
    try:
        session.add(
            GenerationPromptChunk(
                slug="chatml_jsonl_schema",
                title="ChatML JSONL schema",
                chunk_text=text,
            )
        )
        session.commit()

        stored = session.query(GenerationPromptChunk).filter_by(
            slug="chatml_jsonl_schema"
        ).one()
    finally:
        session.close()

    assert stored.chunk_text == text


def test_generation_template_chunk_maps_template_to_chunk(generation_db):
    _engine, session_factory = generation_db
    session = session_factory()
    try:
        chunk = GenerationPromptChunk(
            slug="system_prompt_auto",
            title="Automatic system prompt",
            chunk_text="[SYSTEM PROMPT MODE CHUNK]\nSystem prompt mode: auto",
        )
        mapping = GenerationTemplateChunk(
            template_id="conversation_scenario",
            chunk_slug="system_prompt_auto",
            sort_order=40,
        )
        session.add(chunk)
        session.add(mapping)
        session.commit()

        stored = session.query(GenerationTemplateChunk).one()
        related_slug = stored.chunk.slug
    finally:
        session.close()

    assert stored.template_id == "conversation_scenario"
    assert stored.chunk_slug == "system_prompt_auto"
    assert stored.sort_order == 40
    assert related_slug == "system_prompt_auto"


def test_generation_template_chunk_nullable_conditions(generation_db):
    _engine, session_factory = generation_db
    session = session_factory()
    try:
        chunk = GenerationPromptChunk(
            slug="output_download_file",
            title="Download output",
            chunk_text="[OUTPUT DELIVERY CHUNK]\nOutput delivery mode: download_file",
        )
        mapping = GenerationTemplateChunk(
            template_id="conversation_scenario",
            chunk_slug="output_download_file",
            sort_order=90,
            condition_key=None,
            condition_value=None,
        )
        session.add(chunk)
        session.add(mapping)
        session.commit()

        stored = session.query(GenerationTemplateChunk).one()
    finally:
        session.close()

    assert stored.condition_key is None
    assert stored.condition_value is None


def test_generation_model_defaults_and_timestamps_populate(generation_db):
    _engine, session_factory = generation_db
    session = session_factory()
    try:
        chunk = GenerationPromptChunk(
            slug="rolethread_generation_task",
            title="RoleThread generation task",
            chunk_text="[ROLETHREAD TASK CHUNK]",
        )
        mapping = GenerationTemplateChunk(
            template_id="conversation_scenario",
            chunk_slug="rolethread_generation_task",
            sort_order=10,
        )
        session.add(chunk)
        session.add(mapping)
        session.commit()

        stored_chunk = session.query(GenerationPromptChunk).one()
        stored_mapping = session.query(GenerationTemplateChunk).one()
    finally:
        session.close()

    assert stored_chunk.is_active is True
    assert stored_mapping.is_required is True
    assert stored_chunk.created_at is not None
    assert stored_chunk.updated_at is not None
    assert stored_mapping.created_at is not None
    assert stored_mapping.updated_at is not None


def test_generation_tables_register_in_metadata(generation_db):
    engine, _session_factory = generation_db
    inspector = sa_inspect(engine)

    assert "generation_prompt_chunks" in Base.metadata.tables
    assert "generation_template_chunks" in Base.metadata.tables
    assert "generation_prompt_chunks" in inspector.get_table_names()
    assert "generation_template_chunks" in inspector.get_table_names()

    chunk_indexes = {
        index["name"]
        for index in inspector.get_indexes("generation_prompt_chunks")
    }
    mapping_indexes = {
        index["name"]
        for index in inspector.get_indexes("generation_template_chunks")
    }
    assert "ix_generation_prompt_chunks_slug" in chunk_indexes
    assert "ix_generation_template_chunks_template_id" in mapping_indexes
    assert "ix_generation_template_chunks_chunk_slug" in mapping_indexes
