# Naming and Terminology Guide

RoleThread Lite uses consistent terminology across UI labels, services, metadata, docs, and tests.

Prefer workflow-oriented names over abstract internal jargon. Names should describe the operation, data shape, or side effect being represented.

## Product Names

Use `RoleThread Lite` for this application.

Use `RoleThread` when referring to the broader ecosystem or shared product philosophy.

Use `RoleThread Studio` for the reserved advanced environment. Lite documentation should not imply that Studio features already exist.

## Interaction, Not Scene

Use `Interaction` for the default tag category that describes the shape of an exchange.

Older prototype language used `Scene` in some places, but the V1 taxonomy is broader than roleplay scenes. Interaction covers greetings, question-answer exchanges, task completion, explanations, feedback, corrections, and roleplay without making narrative roleplay the only mental model.

## Entry

An `entry` is one dataset item.

Depending on the format, an entry may contain a single prompt/response pair, a multi-message exchange, or a group-chat-style interaction. The word is intentionally generic because RoleThread supports more than one dataset shape.

## Exchange

An `exchange` is the conversational unit inside or represented by an entry.

Use this term when the discussion is about back-and-forth conversational structure rather than the stored JSON object itself.

## Working Copy

A `working copy` is the editable local copy RoleThread uses while protecting the original imported file.

The working copy is where active changes happen; the original file should remain recoverable.

## Sidecar

A `sidecar` is portable metadata stored next to a dataset.

Sidecars can preserve registry IDs, character mapping data, workflow metadata, and other context that may not belong directly inside every dataset row. Sidecars help datasets travel between machines without losing RoleThread-specific context.

## Validation and Repair

`Validation` means finding structural or workflow issues.

`Repair` means applying explicit changes to fix those issues.

Do not use repair language for passive detection. RoleThread should not imply that it changed a dataset unless it actually did.

## Imported and Archived Tags

An `imported tag` is a tag found in loaded data that is not currently part of the active tag registry.

An `archived tag` is preserved but not active for normal assignment.

This distinction preserves unknown metadata without forcing every imported or old tag into the active taxonomy.

## Dataset Mutation

A `dataset mutation` is any workflow that changes dataset content or related metadata.

Examples include quick edits, full edits, deletes, duplicates, joins, splits, tag replacement, system prompt replacement, and merges. Mutation language is useful in developer docs because these workflows need validation, backups, saves, sidecar alignment, and structured results.

## Group Chat Mode

`Group Chat Mode` refers to entries with multiple named participants or assistant roles.

Use this term for the workflow shape, not as a generic replacement for every multi-message dataset. It should stay connected to character mapping, participant review, and multi-speaker refinement.

## Slugs and Labels

Tag slugs should be lowercase `snake_case`, stable, and machine-friendly. Human-readable labels can be separate from slugs and should be used when the UI needs friendlier text.

Good examples:

- `needs_review`
- `no_user_control`
- `question_answer`
- `ai_generated`

Avoid making slugs depend on capitalization, punctuation, or display styling.

## Python Naming and Style

RoleThread follows PEP 8 where practical.

The goal is readable code, not rigid style-lawyering. Contributors should prefer names that make workflows and side effects clear.

Use standard Python conventions:

- `snake_case` for variables, functions, and modules
- `PascalCase` for classes and dataclasses
- `ALL_CAPS` for constants
- lowercase `snake_case` for tag slugs and stable metadata keys

Prefer descriptive workflow-oriented names over clever abbreviations or vague internal jargon.

Good examples:

- `save_dataset()`
- `create_dataset_backup()`
- `replace_tags_bulk_service()`

Service names may be longer when the name clarifies the workflow. A function that writes files, creates backups, replaces tags, or updates sidecars should not hide those side effects behind an overly generic name.

Small pragmatic deviations from PEP 8 are acceptable when they make a workflow easier to read; consistency and explicitness remain the default.

## Why Naming Discipline Matters

Consistent terminology lowers the cost of contribution and review.

When UI labels, Help docs, tests, service names, and metadata concepts use the same words, contributors spend less time translating between mental models.
