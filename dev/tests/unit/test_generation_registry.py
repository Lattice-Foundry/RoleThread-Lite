from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generation.registry as generation_registry
from core.models import Base, GenerationPromptChunk, GenerationTemplateChunk


def _generation_registry_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'generation_registry.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(generation_registry, "SessionLocal", session_factory)
    monkeypatch.setattr(
        generation_registry,
        "init_db",
        lambda: Base.metadata.create_all(bind=engine),
    )
    Base.metadata.create_all(engine)
    return session_factory


def _add_chunk(
    session,
    *,
    slug,
    text=None,
    active=True,
    title=None,
):
    chunk = GenerationPromptChunk(
        slug=slug,
        title=title or slug.replace("_", " ").title(),
        chunk_text=text or f"[{slug.upper()} CHUNK]",
        is_active=active,
    )
    session.add(chunk)
    session.flush()
    return chunk


def _add_mapping(
    session,
    *,
    slug,
    sort_order,
    template_id="conversation_scenario",
    required=True,
    condition_key=None,
    condition_value=None,
):
    mapping = GenerationTemplateChunk(
        template_id=template_id,
        chunk_slug=slug,
        sort_order=sort_order,
        is_required=required,
        condition_key=condition_key,
        condition_value=condition_value,
    )
    session.add(mapping)
    session.flush()
    return mapping


def _seed_registry_rows(session_factory):
    session = session_factory()
    try:
        _add_chunk(session, slug="rolethread_generation_task")
        _add_chunk(session, slug="chatml_format")
        _add_chunk(session, slug="custom_system_prompt")
        _add_chunk(session, slug="additional_instructions")
        _add_chunk(session, slug="inactive_chunk", active=False)
        _add_mapping(session, slug="chatml_format", sort_order=20)
        _add_mapping(session, slug="rolethread_generation_task", sort_order=10)
        _add_mapping(
            session,
            slug="custom_system_prompt",
            sort_order=30,
            required=False,
            condition_key="system_prompt_mode",
            condition_value="custom",
        )
        _add_mapping(
            session,
            slug="additional_instructions",
            sort_order=40,
            required=False,
            condition_key="has_additional_instructions",
            condition_value="true",
        )
        _add_mapping(session, slug="inactive_chunk", sort_order=50)
        session.commit()
    finally:
        session.close()


def test_get_generation_prompt_chunk_returns_active_chunk(tmp_path, monkeypatch):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    chunk = generation_registry.get_generation_prompt_chunk("chatml_format")

    assert chunk is not None
    assert chunk.slug == "chatml_format"
    assert chunk.chunk_text == "[CHATML_FORMAT CHUNK]"


def test_get_generation_prompt_chunk_excludes_inactive_and_unknown_chunks(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    assert generation_registry.get_generation_prompt_chunk("inactive_chunk") is None
    assert generation_registry.get_generation_prompt_chunk("missing") is None


def test_get_generation_template_chunks_returns_deterministic_active_order(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    chunks = generation_registry.get_generation_template_chunks(
        "conversation_scenario"
    )

    assert [chunk.slug for chunk in chunks] == [
        "rolethread_generation_task",
        "chatml_format",
        "custom_system_prompt",
        "additional_instructions",
    ]
    assert [chunk.sort_order for chunk in chunks] == [10, 20, 30, 40]


def test_resolve_generation_template_chunks_includes_unconditional_chunks(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    chunks = generation_registry.resolve_generation_template_chunks(
        "conversation_scenario",
        conditions={"system_prompt_mode": "auto"},
    )

    assert [chunk.slug for chunk in chunks] == [
        "rolethread_generation_task",
        "chatml_format",
    ]


def test_resolve_generation_template_chunks_includes_matching_conditional_chunks(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    chunks = generation_registry.resolve_generation_template_chunks(
        "conversation_scenario",
        conditions={
            "system_prompt_mode": "custom",
            "has_additional_instructions": "true",
        },
    )

    assert [chunk.slug for chunk in chunks] == [
        "rolethread_generation_task",
        "chatml_format",
        "custom_system_prompt",
        "additional_instructions",
    ]


def test_resolve_generation_template_chunks_excludes_non_matching_conditionals(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    chunks = generation_registry.resolve_generation_template_chunks(
        "conversation_scenario",
        conditions={
            "system_prompt_mode": "auto",
            "has_additional_instructions": "false",
        },
    )

    assert "custom_system_prompt" not in [chunk.slug for chunk in chunks]
    assert "additional_instructions" not in [chunk.slug for chunk in chunks]


def test_resolve_generation_template_chunks_excludes_inactive_chunks(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    chunks = generation_registry.resolve_generation_template_chunks(
        "conversation_scenario",
        conditions={"inactive": "true"},
    )

    assert "inactive_chunk" not in [chunk.slug for chunk in chunks]


def test_resolve_generation_template_chunks_preserves_sort_order_after_filtering(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    chunks = generation_registry.resolve_generation_template_chunks(
        "conversation_scenario",
        conditions={"has_additional_instructions": "true"},
    )

    assert [chunk.sort_order for chunk in chunks] == [10, 20, 40]


def test_generation_registry_unknown_template_returns_empty_list(tmp_path, monkeypatch):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    assert generation_registry.get_generation_template_chunks("unknown") == []
    assert generation_registry.resolve_generation_template_chunks("unknown") == []


def test_conditions_none_returns_unconditional_chunks(tmp_path, monkeypatch):
    session_factory = _generation_registry_db(tmp_path, monkeypatch)
    _seed_registry_rows(session_factory)

    chunks = generation_registry.resolve_generation_template_chunks(
        "conversation_scenario",
        conditions=None,
    )

    assert [chunk.slug for chunk in chunks] == [
        "rolethread_generation_task",
        "chatml_format",
    ]
