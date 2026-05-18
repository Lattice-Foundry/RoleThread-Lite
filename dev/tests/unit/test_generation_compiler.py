from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.generation.registry as generation_registry
import core.generation.seed as generation_seed
from core.generation import (
    ConversationScenarioGenerationConfig,
    ConversationStyle,
    ConversationTone,
    GenerationTemplateId,
    OutputDeliveryMode,
    SystemPromptMode,
    compile_conversation_scenario_prompt,
    get_generation_template,
    get_generation_templates,
    validate_conversation_scenario_config,
)
from core.generation.compiler import render_generation_chunk_text
from core.models import Base, GenerationTemplateChunk


def _valid_config(**overrides):
    values = {
        "content_instructions": "Generate practical support conversations.",
    }
    values.update(overrides)
    return ConversationScenarioGenerationConfig(**values)


@pytest.fixture(autouse=True)
def generation_compiler_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'generation_compiler.db'}",
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
    return session_factory


def test_default_valid_config_compiles_successfully():
    prompt = compile_conversation_scenario_prompt(_valid_config())

    assert isinstance(prompt, str)
    assert prompt.startswith(
        "You are generating structured conversational training data for LLM fine-tuning."
    )
    assert "high-quality ChatML JSONL dataset entries" in prompt


def test_compiled_prompt_includes_production_generation_instructions():
    prompt = compile_conversation_scenario_prompt(_valid_config())

    expected_phrases = (
        "Output valid ChatML JSONL only.",
        "Generate exactly 10 complete dataset entries.",
        "Each dataset entry must contain exactly 3 user/assistant exchanges",
        "Generate dataset entries using the following scenario and behavioral requirements:",
        "Generate an appropriate system prompt for each dataset entry unless a custom system prompt is provided.",
        "Conversation style requirements:",
        "Conversation tone requirements:",
        "If output_delivery_mode is \"paste_jsonl\":",
    )
    for phrase in expected_phrases:
        assert phrase in prompt


def test_old_placeholder_chunk_labels_are_not_present():
    prompt = compile_conversation_scenario_prompt(_valid_config())

    old_labels = (
        "[ROLETHREAD TASK CHUNK]",
        "[CHATML FORMAT CHUNK]",
        "[ENTRY COUNT CHUNK]",
        "[EXCHANGE COUNT CHUNK]",
        "[CONTENT INSTRUCTIONS CHUNK]",
        "[SYSTEM PROMPT MODE CHUNK]",
        "[STYLE CHUNK]",
        "[TONE CHUNK]",
        "[OUTPUT DELIVERY CHUNK]",
    )
    for label in old_labels:
        assert label not in prompt


def test_compiled_prompt_uses_blank_lines_between_chunks():
    prompt = compile_conversation_scenario_prompt(_valid_config())

    assert "\n\nOutput valid ChatML JSONL only." in prompt
    assert "\n\nGenerate exactly 10 complete dataset entries." in prompt


def test_entry_count_appears_correctly():
    prompt = compile_conversation_scenario_prompt(_valid_config(entry_count=17))

    assert "Generate exactly 17 complete dataset entries." in prompt
    assert "Do not generate fewer than 17 dataset entries." in prompt
    assert "Do not generate more than 17 dataset entries." in prompt


def test_exchange_count_appears_correctly():
    prompt = compile_conversation_scenario_prompt(_valid_config(exchange_count=5))

    assert (
        "Each dataset entry must contain exactly 5 user/assistant exchanges after the system message."
        in prompt
    )
    assert "Do not generate fewer than 5 exchanges per dataset entry." in prompt
    assert "Do not generate more than 5 exchanges per dataset entry." in prompt


def test_content_instructions_appears_correctly():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(content_instructions="  Generate customer handoff examples.  ")
    )

    assert (
        "Generate dataset entries using the following scenario and behavioral requirements:\n\n"
        "Generate customer handoff examples."
    ) in prompt


def test_auto_system_prompt_mode_skips_custom_system_prompt_chunk():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(
            system_prompt_mode=SystemPromptMode.AUTO,
            custom_system_prompt="Ignored for auto mode.",
        )
    )

    assert "Generate an appropriate system prompt for each dataset entry" in prompt
    assert "Use the following system prompt exactly:" not in prompt
    assert "Ignored for auto mode." not in prompt


def test_custom_system_prompt_mode_includes_custom_chunk_and_text():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(
            system_prompt_mode=SystemPromptMode.CUSTOM,
            custom_system_prompt="  Stay concise and grounded.  ",
        )
    )

    assert "Generate an appropriate system prompt for each dataset entry" in prompt
    assert (
        "Use the following system prompt exactly:\n\n"
        "Stay concise and grounded."
    ) in prompt


@pytest.mark.parametrize("additional_instructions", [None, "", "   "])
def test_additional_instructions_chunk_is_skipped_when_blank(additional_instructions):
    prompt = compile_conversation_scenario_prompt(
        _valid_config(additional_instructions=additional_instructions)
    )

    assert "Additional instructions:" not in prompt


def test_additional_instructions_chunk_is_included_when_provided():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(additional_instructions="  Avoid duplicate setups.  ")
    )

    assert (
        "Additional instructions:\n\n"
        "Avoid duplicate setups."
    ) in prompt


def test_blank_content_instructions_returns_validation_error_and_raises():
    config = _valid_config(content_instructions="  ")

    assert validate_conversation_scenario_config(config) == [
        "content_instructions must be non-empty."
    ]
    with pytest.raises(ValueError, match="content_instructions must be non-empty"):
        compile_conversation_scenario_prompt(config)


def test_custom_mode_with_blank_custom_system_prompt_invalid():
    config = _valid_config(
        system_prompt_mode=SystemPromptMode.CUSTOM,
        custom_system_prompt=" ",
    )

    errors = validate_conversation_scenario_config(config)
    assert errors == [
        "custom_system_prompt must be non-empty when system_prompt_mode is custom."
    ]
    with pytest.raises(ValueError, match="custom_system_prompt must be non-empty"):
        compile_conversation_scenario_prompt(config)


def test_entry_count_less_than_one_invalid():
    config = _valid_config(entry_count=0)

    assert "entry_count must be >= 1." in validate_conversation_scenario_config(config)
    with pytest.raises(ValueError, match="entry_count must be >= 1"):
        compile_conversation_scenario_prompt(config)


def test_exchange_count_less_than_one_invalid():
    config = _valid_config(exchange_count=0)

    assert "exchange_count must be >= 1." in validate_conversation_scenario_config(config)
    with pytest.raises(ValueError, match="exchange_count must be >= 1"):
        compile_conversation_scenario_prompt(config)


def test_templates_registry_returns_conversation_scenario_generator():
    templates = get_generation_templates()
    template = get_generation_template(GenerationTemplateId.CONVERSATION_SCENARIO)

    assert templates == [template]
    assert template.template_id == GenerationTemplateId.CONVERSATION_SCENARIO
    assert template.display_name == "Conversation Scenario Generator"
    assert template.output_format == "chatml_jsonl"


def test_compiler_renders_style_tone_and_output_delivery_values():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(
            style=ConversationStyle.ROLEPLAY_IMMERSIVE,
            tone=ConversationTone.PLAYFUL,
            output_delivery_mode=OutputDeliveryMode.DOWNLOAD_FILE,
        )
    )

    assert "Conversation style requirements:\n\nroleplay_immersive" in prompt
    assert "Conversation tone requirements:\n\nplayful" in prompt
    assert "If output_delivery_mode is \"download_file\":" in prompt


def test_compiler_preserves_multiline_content_instructions():
    prompt = compile_conversation_scenario_prompt(
        _valid_config(content_instructions=" First line\nSecond line ")
    )

    assert (
        "Generate dataset entries using the following scenario and behavioral requirements:\n\n"
        "First line\nSecond line"
    ) in prompt


def test_compiler_loads_chunks_through_db_registry(monkeypatch):
    calls = []
    real_resolver = generation_registry.resolve_generation_template_chunks

    def tracking_resolver(template_id, conditions=None):
        calls.append((template_id, conditions))
        return real_resolver(template_id, conditions)

    monkeypatch.setattr(
        "core.generation.compiler.resolve_generation_template_chunks",
        tracking_resolver,
    )

    prompt = compile_conversation_scenario_prompt(_valid_config())

    assert prompt.startswith(
        "You are generating structured conversational training data"
    )
    assert calls == [
        (
            "conversation_scenario",
            {"system_prompt_mode": "auto"},
        )
    ]


def test_render_generation_chunk_text_replaces_placeholders():
    rendered = render_generation_chunk_text(
        "Template: {{ template_id }}\nCount: {{ entry_count }}",
        {"template_id": "conversation_scenario", "entry_count": "12"},
    )

    assert rendered == "Template: conversation_scenario\nCount: 12"


def test_compiler_raises_when_template_mappings_missing(generation_compiler_db):
    session = generation_compiler_db()
    try:
        session.query(GenerationTemplateChunk).delete()
        session.commit()
    finally:
        session.close()

    with pytest.raises(ValueError, match="missing mappings"):
        compile_conversation_scenario_prompt(_valid_config())


def test_compiler_raises_when_required_chunk_text_missing(generation_compiler_db):
    session = generation_compiler_db()
    try:
        mapping = session.query(GenerationTemplateChunk).filter_by(
            chunk_slug="rolethread_generation_task"
        ).one()
        mapping.chunk.chunk_text = ""
        session.commit()
    finally:
        session.close()

    with pytest.raises(ValueError, match="required chunks without text"):
        compile_conversation_scenario_prompt(_valid_config())


def test_generation_core_package_does_not_import_streamlit():
    import core.generation as generation

    generation_root = next(iter(generation.__path__))
    for path in Path(generation_root).glob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert "streamlit" not in source
