from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generation.registry as generation_registry
import core.generation.seed as generation_seed
from core.generation import (
    ConversationScenarioGenerationConfig,
    SystemPromptMode,
)
from core.models import Base
from services.generation_service import compile_generation_prompt_service


def _valid_config(**overrides):
    values = {
        "content_instructions": "Generate compact coaching conversations.",
    }
    values.update(overrides)
    return ConversationScenarioGenerationConfig(**values)


@pytest.fixture(autouse=True)
def generation_service_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'generation_service.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(generation_seed, "SessionLocal", session_factory)
    monkeypatch.setattr(generation_registry, "SessionLocal", session_factory)
    monkeypatch.setattr(
        generation_seed,
        "init_db",
        lambda: Base.metadata.create_all(bind=engine),
    )
    monkeypatch.setattr(
        generation_registry,
        "init_db",
        lambda: Base.metadata.create_all(bind=engine),
    )
    Base.metadata.create_all(engine)
    generation_seed.initialize_generation_registry()


def test_generation_service_returns_ok_for_valid_config():
    result = compile_generation_prompt_service(_valid_config())

    assert result.ok is True
    assert result.errors == []
    assert result.compiled_prompt is not None


def test_generation_service_returns_compiled_placeholder_prompt():
    result = compile_generation_prompt_service(_valid_config(entry_count=12))

    assert result.compiled_prompt is not None
    assert "[ROLETHREAD TASK CHUNK]" in result.compiled_prompt
    assert "[ENTRY COUNT CHUNK]\nEntry count: 12" in result.compiled_prompt


def test_generation_service_returns_error_for_blank_content_instructions():
    result = compile_generation_prompt_service(
        _valid_config(content_instructions="   ")
    )

    assert result.ok is False
    assert result.compiled_prompt is None
    assert result.errors == ["content_instructions must be non-empty."]


def test_generation_service_returns_error_for_blank_custom_system_prompt():
    result = compile_generation_prompt_service(
        _valid_config(
            system_prompt_mode=SystemPromptMode.CUSTOM,
            custom_system_prompt="  ",
        )
    )

    assert result.ok is False
    assert result.compiled_prompt is None
    assert result.errors == [
        "custom_system_prompt must be non-empty when system_prompt_mode is custom."
    ]


def test_generation_service_does_not_import_streamlit():
    source = Path("services/generation_service.py").read_text(encoding="utf-8").lower()

    assert "streamlit" not in source
