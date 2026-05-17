"""Framework-independent services for data generation prompt compilation."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.generation import (
    ConversationScenarioGenerationConfig,
    compile_conversation_scenario_prompt,
    validate_conversation_scenario_config,
)


@dataclass(frozen=True)
class GenerationCompileResult:
    """Result returned by generation prompt compilation services."""

    ok: bool
    compiled_prompt: str | None = None
    errors: list[str] = field(default_factory=list)


def compile_generation_prompt_service(
    config: ConversationScenarioGenerationConfig,
) -> GenerationCompileResult:
    """Validate and compile a data generation prompt without UI side effects."""

    errors = validate_conversation_scenario_config(config)
    if errors:
        return GenerationCompileResult(ok=False, errors=errors)

    try:
        compiled_prompt = compile_conversation_scenario_prompt(config)
    except ValueError as exc:
        message = str(exc).strip() or "Invalid generation configuration."
        return GenerationCompileResult(ok=False, errors=[message])

    return GenerationCompileResult(ok=True, compiled_prompt=compiled_prompt)
