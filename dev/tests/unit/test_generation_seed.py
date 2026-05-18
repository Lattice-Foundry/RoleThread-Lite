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
        "style_natural_dialogue",
        "style_roleplay_immersive",
        "style_instructional",
        "style_narrative_dialogue",
        "tone_neutral",
        "tone_warm",
        "tone_professional",
        "tone_dramatic",
        "tone_playful",
        "output_delivery_paste_jsonl",
        "output_delivery_download_file",
        "additional_instructions",
    }
    assert chunks["rolethread_generation_task"].chunk_text == (
        "You are generating structured conversational training data for LLM fine-tuning.\n\n"
        "Your task is to generate high-quality ChatML JSONL dataset entries that can be imported directly into a conversational training dataset.\n\n"
        "You are generating training data, not interacting with the user directly.\n\n"
        "All output must follow the required formatting and structural rules exactly.\n\n"
        "Do not generate explanations, commentary, analysis, summaries, conversational framing, or metadata outside the requested dataset output.\n\n"
        "Prioritize:\n"
        "- structural correctness\n"
        "- conversational realism\n"
        "- coherent multi-turn continuity\n"
        "- consistent behavior within each dataset entry\n"
        "- import-safe JSONL formatting"
    )
    assert chunks["chatml_format"].chunk_text == (
        "Output valid ChatML JSONL only.\n\n"
        "Each dataset entry must be a single valid JSON object written on a single line.\n\n"
        "Do not wrap dataset entries in a JSON array.\n\n"
        "Each dataset entry must contain a top-level \"messages\" array.\n\n"
        "Each \"messages\" array must begin with exactly one system message.\n\n"
        "After the system message, messages must alternate in this exact order:\n"
        "user → assistant → user → assistant\n\n"
        "Do not break message ordering.\n\n"
        "Each message object must contain:\n"
        "- \"role\"\n"
        "- \"content\"\n\n"
        "Valid roles are:\n"
        "- \"system\"\n"
        "- \"user\"\n"
        "- \"assistant\"\n\n"
        "All JSON output must be syntactically valid.\n\n"
        "Correctly escape:\n"
        "- quotation marks\n"
        "- newline characters\n"
        "- special characters inside JSON strings\n\n"
        "Do not include:\n"
        "- comments\n"
        "- trailing commas\n"
        "- markdown explanations\n"
        "- metadata fields\n"
        "- tags\n"
        "- analysis text\n"
        "- conversational framing outside the dataset output"
    )
    assert chunks["entry_count"].chunk_text == (
        "Generate exactly {{ entry_count }} complete dataset entries.\n\n"
        "Each dataset entry must be:\n"
        "- structurally complete\n"
        "- independently valid\n"
        "- formatted as valid ChatML JSONL\n"
        "- written as a separate single-line JSON object\n\n"
        "Do not generate fewer than {{ entry_count }} dataset entries.\n\n"
        "Do not generate more than {{ entry_count }} dataset entries.\n\n"
        "Do not stop generation before all requested dataset entries are completed.\n\n"
        "Every generated dataset entry must fully comply with all formatting and structural requirements."
    )


def test_seed_generation_prompt_chunks_creates_remaining_production_content(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_seed_db(tmp_path, monkeypatch)

    generation_seed.seed_generation_prompt_chunks()

    session = session_factory()
    try:
        chunks = _query_chunks(session)
    finally:
        session.close()

    assert chunks["exchange_count"].chunk_text == (
        "Each dataset entry must contain exactly {{ exchange_count }} user/assistant exchanges after the system message.\n\n"
        "One exchange means:\n"
        "- one user message\n"
        "- followed by one assistant message\n\n"
        "The required message order is:\n"
        "system \u2192 user \u2192 assistant \u2192 user \u2192 assistant\n\n"
        "Do not generate fewer than {{ exchange_count }} exchanges per dataset entry.\n\n"
        "Do not generate more than {{ exchange_count }} exchanges per dataset entry.\n\n"
        "Maintain correct role alternation throughout every dataset entry.\n\n"
        "Do not break message ordering or exchange structure."
    )
    assert chunks["content_instructions"].chunk_text == (
        "Generate dataset entries using the following scenario and behavioral requirements:\n\n"
        "{{ content_instructions }}"
    )
    assert chunks["system_prompt_mode"].chunk_text == (
        "Generate an appropriate system prompt for each dataset entry unless a custom system prompt is provided."
    )
    assert chunks["custom_system_prompt"].chunk_text == (
        "Use the following system prompt exactly:\n\n"
        "{{ custom_system_prompt }}"
    )
    assert chunks["style_natural_dialogue"].chunk_text == (
        "Conversation style requirements:\n\n"
        "Generate conversations that feel natural, grounded, and conversationally realistic.\n\n"
        "Prioritize believable conversational rhythm, context-aware responses, and realistic user/assistant interaction patterns.\n\n"
        "Avoid overly theatrical phrasing, exaggerated narration, or artificial dialogue unless the scenario explicitly calls for it."
    )
    assert chunks["style_roleplay_immersive"].chunk_text == (
        "Conversation style requirements:\n\n"
        "Generate immersive roleplay-style conversations with strong scene continuity, emotional presence, and interaction detail.\n\n"
        "Preserve environmental continuity, physical interaction awareness, emotional progression, and conversational pacing throughout each dataset entry.\n\n"
        "Use narration and dialogue in a way that supports immersion without breaking the required ChatML JSONL structure.\n\n"
        "Avoid abrupt scene resets, emotionally disconnected responses, or generic roleplay filler."
    )
    assert chunks["style_instructional"].chunk_text == (
        "Conversation style requirements:\n\n"
        "Generate conversations focused on clarity, instruction-following, and helpful information exchange.\n\n"
        "Prioritize clear explanations, useful guidance, coherent sequencing, and practical conversational flow.\n\n"
        "Keep responses focused on the instructional purpose of the scenario.\n\n"
        "Avoid unnecessary dramatic narration, excessive emotional embellishment, or conversational drift."
    )
    assert chunks["style_narrative_dialogue"].chunk_text == (
        "Conversation style requirements:\n\n"
        "Generate conversations that blend dialogue with narrative scene description and contextual narration.\n\n"
        "Use narration to support scene progression, character movement, setting continuity, and emotional context.\n\n"
        "Preserve readable conversational flow while maintaining clear user/assistant message alternation.\n\n"
        "Avoid long exposition blocks that overwhelm the dialogue or weaken the training usefulness of the exchange."
    )
    assert chunks["tone_neutral"].chunk_text == (
        "Conversation tone requirements:\n\n"
        "Maintain a balanced and emotionally neutral conversational tone.\n\n"
        "Keep interactions grounded, coherent, and contextually appropriate without excessive emotional exaggeration.\n\n"
        "Allow emotional nuance when appropriate to the scenario while preserving conversational realism."
    )
    assert chunks["tone_warm"].chunk_text == (
        "Conversation tone requirements:\n\n"
        "Maintain a warm, emotionally engaging, and personable conversational tone.\n\n"
        "Responses should feel emotionally attentive, socially natural, and interpersonally engaged without becoming overly exaggerated or artificial.\n\n"
        "Preserve conversational realism and believable emotional interaction patterns throughout each dataset entry."
    )
    assert chunks["tone_professional"].chunk_text == (
        "Conversation tone requirements:\n\n"
        "Maintain a professional, composed, and respectful conversational tone.\n\n"
        "Prioritize clarity, competence, emotional control, and context-appropriate communication.\n\n"
        "Avoid slang, excessive emotional volatility, or unprofessional conversational behavior unless explicitly required by the scenario."
    )
    assert chunks["tone_dramatic"].chunk_text == (
        "Conversation tone requirements:\n\n"
        "Maintain a dramatic, emotionally heightened, and tension-aware conversational tone.\n\n"
        "Allow emotional tension, suspense, anticipation, and heightened interpersonal stakes when appropriate to the scenario.\n\n"
        "Preserve coherence and conversational realism even during emotionally intense exchanges."
    )
    assert chunks["tone_playful"].chunk_text == (
        "Conversation tone requirements:\n\n"
        "Maintain a playful, lighthearted, and expressive conversational tone.\n\n"
        "Allow humor, teasing, expressive phrasing, and socially playful interaction patterns when appropriate to the scenario.\n\n"
        "Avoid breaking immersion or undermining conversational coherence with excessive randomness or forced humor."
    )
    assert chunks["output_delivery_paste_jsonl"].chunk_text == (
        "Return the generated dataset directly in a single fenced code block.\n\n"
        "Do not include explanation before or after the dataset output."
    )
    assert chunks["output_delivery_download_file"].chunk_text == (
        "If supported, provide the generated dataset as a downloadable `.jsonl` file.\n\n"
        "If downloadable file output is unavailable, return the generated dataset directly in a single fenced code block.\n\n"
        "Do not include explanation before or after the dataset output."
    )
    assert chunks["additional_instructions"].chunk_text == (
        "Additional instructions:\n\n"
        "{{ additional_instructions }}"
    )
    for chunk in chunks.values():
        assert "[ROLETHREAD" not in chunk.chunk_text
        assert " CHUNK]" not in chunk.chunk_text


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
        "style_natural_dialogue",
        "style_roleplay_immersive",
        "style_instructional",
        "style_narrative_dialogue",
        "tone_neutral",
        "tone_warm",
        "tone_professional",
        "tone_dramatic",
        "tone_playful",
        "output_delivery_paste_jsonl",
        "output_delivery_download_file",
        "additional_instructions",
    ]
    assert [mapping.sort_order for mapping in mappings] == list(range(1, 20))


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
    natural_dialogue = mappings["style_natural_dialogue"]
    roleplay_immersive = mappings["style_roleplay_immersive"]
    instructional = mappings["style_instructional"]
    narrative_dialogue = mappings["style_narrative_dialogue"]
    neutral = mappings["tone_neutral"]
    warm = mappings["tone_warm"]
    professional = mappings["tone_professional"]
    dramatic = mappings["tone_dramatic"]
    playful = mappings["tone_playful"]
    paste_jsonl = mappings["output_delivery_paste_jsonl"]
    download_file = mappings["output_delivery_download_file"]
    additional = mappings["additional_instructions"]
    assert custom_prompt.is_required is False
    assert custom_prompt.condition_key == "system_prompt_mode"
    assert custom_prompt.condition_value == "custom"
    assert natural_dialogue.is_required is False
    assert natural_dialogue.condition_key == "style"
    assert natural_dialogue.condition_value == "natural_dialogue"
    assert roleplay_immersive.is_required is False
    assert roleplay_immersive.condition_key == "style"
    assert roleplay_immersive.condition_value == "roleplay_immersive"
    assert instructional.is_required is False
    assert instructional.condition_key == "style"
    assert instructional.condition_value == "instructional"
    assert narrative_dialogue.is_required is False
    assert narrative_dialogue.condition_key == "style"
    assert narrative_dialogue.condition_value == "narrative_dialogue"
    assert neutral.is_required is False
    assert neutral.condition_key == "tone"
    assert neutral.condition_value == "neutral"
    assert warm.is_required is False
    assert warm.condition_key == "tone"
    assert warm.condition_value == "warm"
    assert professional.is_required is False
    assert professional.condition_key == "tone"
    assert professional.condition_value == "professional"
    assert dramatic.is_required is False
    assert dramatic.condition_key == "tone"
    assert dramatic.condition_value == "dramatic"
    assert playful.is_required is False
    assert playful.condition_key == "tone"
    assert playful.condition_value == "playful"
    assert paste_jsonl.is_required is False
    assert paste_jsonl.condition_key == "output_delivery_mode"
    assert paste_jsonl.condition_value == "paste_jsonl"
    assert download_file.is_required is False
    assert download_file.condition_key == "output_delivery_mode"
    assert download_file.condition_value == "download_file"
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
    assert entry_count.chunk_text.startswith(
        "Generate exactly {{ entry_count }} complete dataset entries."
    )
    assert "[ENTRY COUNT CHUNK]" not in entry_count.chunk_text
    assert entry_count.category == "quantity"
    assert entry_count.is_active is True
    assert task_mapping.sort_order == 1
    assert task_mapping.is_required is True
    assert task_mapping.condition_key is None
    assert task_mapping.condition_value is None


def test_generation_seed_removes_obsolete_template_mappings(
    tmp_path,
    monkeypatch,
):
    session_factory = _generation_seed_db(tmp_path, monkeypatch)
    session = session_factory()
    try:
        session.add(
            GenerationPromptChunk(
                slug="output_delivery",
                title="Old output delivery",
                chunk_text="old combined output delivery text",
                category="output",
            )
        )
        session.add(
            GenerationPromptChunk(
                slug="style",
                title="Old style",
                chunk_text="old generic style text",
                category="style",
            )
        )
        session.add(
            GenerationPromptChunk(
                slug="tone",
                title="Old tone",
                chunk_text="old generic tone text",
                category="style",
            )
        )
        session.add(
            GenerationTemplateChunk(
                template_id="conversation_scenario",
                chunk_slug="output_delivery",
                sort_order=10,
            )
        )
        session.add(
            GenerationTemplateChunk(
                template_id="conversation_scenario",
                chunk_slug="style",
                sort_order=8,
            )
        )
        session.add(
            GenerationTemplateChunk(
                template_id="conversation_scenario",
                chunk_slug="tone",
                sort_order=12,
            )
        )
        session.commit()
    finally:
        session.close()

    generation_seed.initialize_generation_registry()

    session = session_factory()
    try:
        obsolete_mapping = session.query(GenerationTemplateChunk).filter_by(
            template_id="conversation_scenario",
            chunk_slug="output_delivery",
        ).first()
        obsolete_style_mapping = session.query(GenerationTemplateChunk).filter_by(
            template_id="conversation_scenario",
            chunk_slug="style",
        ).first()
        obsolete_tone_mapping = session.query(GenerationTemplateChunk).filter_by(
            template_id="conversation_scenario",
            chunk_slug="tone",
        ).first()
        obsolete_chunk = session.query(GenerationPromptChunk).filter_by(
            slug="output_delivery"
        ).one()
        obsolete_style_chunk = session.query(GenerationPromptChunk).filter_by(
            slug="style"
        ).one()
        obsolete_tone_chunk = session.query(GenerationPromptChunk).filter_by(
            slug="tone"
        ).one()
    finally:
        session.close()

    assert obsolete_mapping is None
    assert obsolete_style_mapping is None
    assert obsolete_tone_mapping is None
    assert obsolete_chunk.chunk_text == "old combined output delivery text"
    assert obsolete_style_chunk.chunk_text == "old generic style text"
    assert obsolete_tone_chunk.chunk_text == "old generic tone text"


def test_generation_template_chunk_mapping_unique_constraint_exists():
    table = GenerationTemplateChunk.__table__

    assert any(
        constraint.name == "uq_generation_template_chunk_mapping"
        for constraint in table.constraints
    )
