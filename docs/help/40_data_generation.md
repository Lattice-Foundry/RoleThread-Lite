# Data Generation

The chapters from here through **Creator Ownership and Long-Term Workflow Philosophy** form the AI Training Fundamentals arc. They cover the concepts and practices behind building quality training data — including why dataset quality matters, how fine-tuning and LoRA workflows operate, and how to maintain a dataset over time. These articles complement RoleThread's tool documentation with the context behind the workflow decisions.

Data Generation compiles structured settings into prompts you can paste into an external AI system.

RoleThread Lite does not call an AI provider, generate responses internally, or require a cloud API key. It builds deterministic prompts for ChatML JSONL conversational dataset workflows while leaving model choice, execution, and review under your control.

The feature is provider-agnostic. You can use the compiled prompt with systems such as ChatGPT, Claude, Gemini, local models, or other tools that can follow structured dataset-generation instructions. RoleThread does not claim official integration with those providers.

## What Data Generation Is

Data Generation is a structured prompt orchestration workflow for conversational dataset engineering.

It provides:

- generation templates for repeatable dataset workflows
- a deterministic prompt compiler
- DB-backed prompt chunks
- conditional style, tone, system prompt, and output-delivery instructions
- ChatML JSONL-oriented generation guidance
- a copyable prompt preview for external AI workflows

The goal is workflow acceleration, not hidden automation. RoleThread gives the external model a clearer task shape, then you review and import or edit the result through normal dataset workflows.

This fits the broader RoleThread pattern: external AI can help scaffold the first 80%, while RoleThread helps you curate and control the final 20%.

## What Data Generation Is Not

Data Generation is not:

- a hosted inference platform
- a chatbot runtime
- a direct model provider integration
- an API client
- an automatic finished-dataset generator
- a replacement for reviewing generated data

RoleThread compiles the prompt. The external AI system generates the dataset content. You remain responsible for checking structure, style, safety, and training usefulness before using the result.

## Provider Output Expectations

Data Generation produces deterministic prompt text. External AI systems may
still interpret that prompt differently because model families vary in
instruction following, JSON discipline, long-output behavior, safety policy,
and formatting habits.

Treat the compiled prompt as a structured starting point. Review generated
results before importing or training on them, especially when changing models,
providers, style settings, or output-delivery options.

## Architecture Notes

Data Generation is built around a small set of responsibilities:

- templates define the workflow type
- DB-backed prompt chunks own prompt text
- template mappings define deterministic chunk order
- conditional mappings select style, tone, system prompt, and output-delivery chunks
- the compiler validates configuration, resolves chunks, renders variables, and assembles the final prompt

This keeps prompt content separate from compiler behavior. It also makes future refinement easier: prompt chunks can evolve without turning the compiler into a pile of hardcoded prose.

The current V1 workflow targets ChatML JSONL because that format fits RoleThread's dataset model and clean export expectations.

## Provider-Agnostic Workflow

Different providers and local models may respond differently to the same
compiled prompt. RoleThread can make the prompt deterministic; it cannot make
every external model behave identically.

Practical workflow:

1. Configure Data Generation.
2. Compile the prompt.
3. Paste the prompt into an external AI system.
4. Review the generated JSONL.
5. Bring useful results back into RoleThread for validation, cleanup, editing, and export.

## Lite and Studio Boundaries

In RoleThread Lite, Data Generation stays focused on deterministic prompt compilation and local dataset engineering.

Lite owns:

- structured prompt compilation
- provider-agnostic generation setup
- local review and cleanup workflows
- validation, repair, organization, and export after generation

Future RoleThread Studio work may be a better fit for heavier orchestration, provider coordination, automation, semantic refinement pipelines, or managed generation loops.

That split does not make Lite incomplete. Lite provides the deterministic tooling surface; Studio can eventually absorb workflows that need more runtime ownership.

## Practical Recommendation

Treat generated results as a draft source, not finished training data.

Run Validation, inspect the content, check formatting, and edit anything that does not match your dataset goals. Data Generation can speed up structured drafting, but dataset quality still comes from review and intentional curation.
