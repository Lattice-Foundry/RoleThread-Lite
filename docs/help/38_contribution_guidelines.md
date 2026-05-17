# Contribution Guidelines

RoleThread Lite contributions should be small, testable, and consistent with the existing layer boundaries.

## Scope

A good contribution usually does one thing:

- fixes a specific bug
- adds a focused workflow improvement
- improves a service or helper without changing public behavior
- clarifies documentation
- strengthens tests around a safety-critical path

Large rewrites should reduce real complexity or unlock a clearly scoped product direction.

## Preserve Layer Boundaries

Keep durable business logic out of the UI layer.

The `ui/` layer may render controls, read session state, and call services. Workflow rules, mutation behavior, validation, backups, persistence, and platform detection should live in `services/` or `core/`.

`core/` and `services/` should remain framework-independent. They should not import Streamlit.

## Mutation Safety

Dataset files, sidecars, backups, and registry metadata are safety-critical.

Be conservative around:

- deletes
- overwrites
- repairs
- tag lifecycle changes
- merge behavior
- cloud backup publishing
- preference changes

When in doubt, preserve data, report clearly, and avoid silent destructive behavior.

## Testing Expectations

Changes that affect behavior should usually include tests.

Prioritize tests for:

- dataset mutation workflows
- tag lifecycle and alias behavior
- validation and repair
- backup and cloud sync behavior
- preferences and platform paths
- launcher command construction
- Help/FAQ registry changes

Avoid brittle UI-heavy tests when a pure helper or service test can prove the rule more directly.

## Documentation Expectations

Update Help or developer docs when a change alters workflow semantics, setup expectations, or contributor-facing architecture.

Docs should stay practical and specific. Avoid marketing language and avoid implementation detail that does not help users or contributors make decisions.

## Naming and Style

Follow the Naming and Terminology Guide.

Use descriptive Python names, standard conventions, and clear side-effect naming. A workflow function that writes, saves, backs up, replaces, repairs, or deletes should make that behavior visible in its name or surrounding service result.

## What To Avoid

Avoid changes that:

- put business logic into Streamlit rendering code
- bypass service-layer safety behavior
- silently discard unknown metadata
- add platform-specific checks outside centralized helpers
- introduce generated build artifacts into Git
- make Lite carry workflows better suited to future Studio work

