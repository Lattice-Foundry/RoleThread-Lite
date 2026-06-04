"""Streamlit page for external prompt generation beta compilation."""

from __future__ import annotations

import streamlit as st

from core.generation import (
    ConversationScenarioGenerationConfig,
    ConversationStyle,
    ConversationTone,
    GenerationTemplateId,
    OutputDeliveryMode,
    SystemPromptMode,
    get_generation_templates,
)
from services.generation_service import compile_generation_prompt_service
from ui.ui_components import render_copyable_text_preview


GENERATION_COMPILED_PROMPT_KEY = "generation_compiled_prompt"
GENERATION_LAST_ERRORS_KEY = "generation_last_errors"
GENERATION_TEMPLATE_ID_KEY = "generation_template_id"
GENERATION_ENTRY_COUNT_KEY = "generation_entry_count"
GENERATION_EXCHANGE_COUNT_KEY = "generation_exchange_count"
GENERATION_CONTENT_INSTRUCTIONS_KEY = "generation_content_instructions"
GENERATION_AUTO_SYSTEM_PROMPT_KEY = "generation_auto_system_prompt"
GENERATION_CUSTOM_SYSTEM_PROMPT_KEY = "generation_custom_system_prompt"
GENERATION_STYLE_KEY = "generation_style"
GENERATION_TONE_KEY = "generation_tone"
GENERATION_OUTPUT_DELIVERY_MODE_KEY = "generation_output_delivery_mode"
GENERATION_ADDITIONAL_INSTRUCTIONS_KEY = "generation_additional_instructions"

_STYLE_LABELS = {
    ConversationStyle.NATURAL_DIALOGUE.value: "Natural dialogue",
    ConversationStyle.ROLEPLAY_IMMERSIVE.value: "Roleplay / immersive scene",
    ConversationStyle.INSTRUCTIONAL.value: "Instructional",
    ConversationStyle.NARRATIVE_DIALOGUE.value: "Narrative prose + dialogue",
}

_TONE_LABELS = {
    ConversationTone.NEUTRAL.value: "Neutral",
    ConversationTone.WARM.value: "Warm",
    ConversationTone.PROFESSIONAL.value: "Professional",
    ConversationTone.DRAMATIC.value: "Dramatic",
    ConversationTone.PLAYFUL.value: "Playful",
}

_OUTPUT_DELIVERY_LABELS = {
    OutputDeliveryMode.PASTE_JSONL.value: "Paste JSONL in chat",
    OutputDeliveryMode.DOWNLOAD_FILE.value: "Provide downloadable .jsonl file",
}


def _ensure_generation_defaults() -> None:
    st.session_state.setdefault(
        GENERATION_TEMPLATE_ID_KEY,
        GenerationTemplateId.CONVERSATION_SCENARIO.value,
    )
    st.session_state.setdefault(GENERATION_ENTRY_COUNT_KEY, 10)
    st.session_state.setdefault(GENERATION_EXCHANGE_COUNT_KEY, 3)
    st.session_state.setdefault(GENERATION_CONTENT_INSTRUCTIONS_KEY, "")
    st.session_state.setdefault(GENERATION_AUTO_SYSTEM_PROMPT_KEY, True)
    st.session_state.setdefault(GENERATION_CUSTOM_SYSTEM_PROMPT_KEY, "")
    st.session_state.setdefault(
        GENERATION_STYLE_KEY,
        ConversationStyle.NATURAL_DIALOGUE.value,
    )
    st.session_state.setdefault(GENERATION_TONE_KEY, ConversationTone.NEUTRAL.value)
    st.session_state.setdefault(
        GENERATION_OUTPUT_DELIVERY_MODE_KEY,
        OutputDeliveryMode.PASTE_JSONL.value,
    )
    st.session_state.setdefault(GENERATION_ADDITIONAL_INSTRUCTIONS_KEY, "")
    st.session_state.setdefault(GENERATION_COMPILED_PROMPT_KEY, "")
    st.session_state.setdefault(GENERATION_LAST_ERRORS_KEY, [])


def _build_generation_config() -> ConversationScenarioGenerationConfig:
    auto_system_prompt = bool(st.session_state[GENERATION_AUTO_SYSTEM_PROMPT_KEY])
    system_prompt_mode = (
        SystemPromptMode.AUTO if auto_system_prompt else SystemPromptMode.CUSTOM
    )
    return ConversationScenarioGenerationConfig(
        entry_count=int(st.session_state[GENERATION_ENTRY_COUNT_KEY]),
        exchange_count=int(st.session_state[GENERATION_EXCHANGE_COUNT_KEY]),
        content_instructions=st.session_state[GENERATION_CONTENT_INSTRUCTIONS_KEY],
        system_prompt_mode=system_prompt_mode,
        custom_system_prompt=st.session_state[GENERATION_CUSTOM_SYSTEM_PROMPT_KEY],
        style=ConversationStyle(st.session_state[GENERATION_STYLE_KEY]),
        tone=ConversationTone(st.session_state[GENERATION_TONE_KEY]),
        output_delivery_mode=OutputDeliveryMode(
            st.session_state[GENERATION_OUTPUT_DELIVERY_MODE_KEY]
        ),
        additional_instructions=st.session_state[
            GENERATION_ADDITIONAL_INSTRUCTIONS_KEY
        ],
    )


def _render_template_selector() -> None:
    templates = get_generation_templates()
    templates_by_id = {template.template_id.value: template for template in templates}
    st.selectbox(
        "Template",
        options=list(templates_by_id),
        format_func=lambda template_id: templates_by_id[template_id].display_name,
        key=GENERATION_TEMPLATE_ID_KEY,
    )


def _render_compile_errors() -> None:
    for error in st.session_state.get(GENERATION_LAST_ERRORS_KEY, []):
        st.error(error)


def _compile_prompt() -> None:
    result = compile_generation_prompt_service(_build_generation_config())
    if result.ok and result.compiled_prompt is not None:
        st.session_state[GENERATION_COMPILED_PROMPT_KEY] = result.compiled_prompt
        st.session_state[GENERATION_LAST_ERRORS_KEY] = []
        st.success("Prompt compiled.")
        return

    st.session_state[GENERATION_COMPILED_PROMPT_KEY] = ""
    st.session_state[GENERATION_LAST_ERRORS_KEY] = result.errors


def _render_prompt_preview() -> None:
    compiled_prompt = st.session_state.get(GENERATION_COMPILED_PROMPT_KEY, "")
    if not compiled_prompt:
        return

    render_copyable_text_preview(
        "Generated Prompt Preview",
        compiled_prompt,
        copy_button_label="Copy Prompt",
        copied_label="Prompt copied.",
    )


def render_generation_page() -> None:
    """Render the Output > Prompt Generation (Beta) page."""

    _ensure_generation_defaults()

    st.subheader("Prompt Generation (Beta)")
    st.write(
        "Prompt Generation (Beta) compiles structured settings into a prompt you "
        "can paste into an external AI. RoleThread does not call an AI provider "
        "or generate dataset content directly."
    )

    _render_template_selector()

    entry_col, exchange_col = st.columns(2)
    with entry_col:
        st.number_input(
            "Number of entries",
            min_value=1,
            step=1,
            key=GENERATION_ENTRY_COUNT_KEY,
        )
    with exchange_col:
        st.number_input(
            "Number of exchanges per entry",
            min_value=1,
            step=1,
            key=GENERATION_EXCHANGE_COUNT_KEY,
        )

    st.text_area(
        "Dataset Content Instructions",
        placeholder=(
            "Describe the conversations you want generated. Include the scenario, "
            "roles, behavior, subject matter, constraints, or examples of what the "
            "dataset should teach."
        ),
        height=180,
        key=GENERATION_CONTENT_INSTRUCTIONS_KEY,
    )

    auto_system_prompt = st.checkbox(
        "Generate system prompt automatically",
        key=GENERATION_AUTO_SYSTEM_PROMPT_KEY,
    )
    if not auto_system_prompt:
        st.text_area(
            "Custom System Prompt",
            height=140,
            key=GENERATION_CUSTOM_SYSTEM_PROMPT_KEY,
        )

    style_col, tone_col = st.columns(2)
    with style_col:
        st.selectbox(
            "Style",
            options=list(_STYLE_LABELS),
            format_func=lambda value: _STYLE_LABELS[value],
            key=GENERATION_STYLE_KEY,
        )
    with tone_col:
        st.selectbox(
            "Tone",
            options=list(_TONE_LABELS),
            format_func=lambda value: _TONE_LABELS[value],
            key=GENERATION_TONE_KEY,
        )

    st.radio(
        "Output delivery",
        options=list(_OUTPUT_DELIVERY_LABELS),
        format_func=lambda value: _OUTPUT_DELIVERY_LABELS[value],
        key=GENERATION_OUTPUT_DELIVERY_MODE_KEY,
    )

    with st.expander("Advanced", expanded=False):
        st.text_area(
            "Additional Instructions",
            height=140,
            key=GENERATION_ADDITIONAL_INSTRUCTIONS_KEY,
        )

    if st.button("Compile Prompt", type="primary"):
        _compile_prompt()

    _render_compile_errors()
    _render_prompt_preview()
