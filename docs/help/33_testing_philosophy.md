# Testing Philosophy

RoleThread Lite uses tests to protect behavior at the service and core boundaries.

The most important tests prove deterministic behavior for datasets, sidecars, tags, backups, preferences, platform capabilities, and launch decisions.

## Lightweight and Deterministic

The test suite is built around `pytest` and small deterministic cases.

Tests should be deterministic and focused on observable behavior. A good test usually answers one bounded question:

- Does this mutation preserve data?
- Does this helper normalize input correctly?
- Does this platform branch produce the right path or message?
- Does this lifecycle operation preserve history?
- Does this workflow fail safely?

## Core and Services First

Most behavior lives in `core/` and `services/` so it can be tested without a live Streamlit session.

Core and service tests are faster and less brittle than UI-heavy tests. They also keep launcher, packaging, and future surface reuse realistic.

The UI still matters, but the durable rules should not depend on widget rendering.

## Behavior Over Implementation

Tests should prefer public helpers, service functions, and meaningful outputs over private implementation details.

It is fine to test a private helper when it protects a narrow safety rule or complicated transformation. But the suite should mostly describe expected behavior:

- given this dataset, this service returns this result
- given this preference state, this launcher command is built
- given this platform, these defaults are resolved
- given this alias history, this tag resolves safely

This keeps tests useful during refactors and pipeline extraction.

## What Gets Heavy Coverage

Coverage is heaviest around data integrity and startup behavior:

- dataset mutation services
- tag lifecycle and alias resolution
- backups and cloud sync staging
- validation and repair helpers
- platform and runtime detection
- path default resolution
- launcher command construction
- preferences and settings helpers
- Help and FAQ registries

## UI Testing Boundaries

RoleThread avoids overloading the suite with brittle UI tests where pure tests can prove the same behavior.

Streamlit interaction can be tested when the user flow itself matters, especially for navigation, Help search, FAQ behavior, and state transitions. But if a pure helper can carry the rule, prefer testing that helper directly.

The target is confidence without turning the suite into a slow visual automation project.

## Launcher and Platform Tests

Launcher and platform behavior should be tested through command construction, path resolution, capability metadata, and safe fallback statuses.

Tests should not spawn real browsers or require a real installer. They should prove that RoleThread decides correctly:

- normal mode versus webapp mode
- Windows Edge support versus fallback
- unsupported platform behavior
- bundled path detection
- launcher logging and failure reporting

Browser and installer workflows still need manual smoke testing; the decision logic should stay covered.

## Contributor Guidance

When adding behavior, prefer tests that protect data integrity, launch decisions, and service contracts.

Useful tests are usually:

- small
- deterministic
- close to the service or core behavior
- clear about the failure they prevent
- not dependent on local machine state unless explicitly mocked

The suite should make refactoring safer without freezing implementation details.
