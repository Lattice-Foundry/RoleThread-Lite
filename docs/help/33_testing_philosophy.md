# Testing Philosophy

RoleThread Lite uses tests to protect behavior, not to create ceremony.

The project is data-oriented, so the most important tests are the ones that prove datasets, sidecars, tags, backups, preferences, and launch decisions behave predictably.

## Lightweight and Deterministic

The test suite is built around `pytest` and small deterministic cases.

Tests should be easy to run locally, easy to understand, and focused on behavior that matters. A good RoleThread test usually answers one practical question:

- Does this mutation preserve data?
- Does this helper normalize input correctly?
- Does this platform branch produce the right path or message?
- Does this lifecycle operation preserve history?
- Does this workflow fail safely?

## Core and Services First

RoleThread puts most behavior in `core/` and `services/` so it can be tested without a live Streamlit session.

That is intentional. Core and service tests are faster, more stable, and less brittle than UI-heavy tests. They also make the code easier to reuse in launchers, packaging flows, and future product surfaces.

The UI still matters, but the durable rules should not depend on widget rendering.

## Behavior Over Implementation

Tests should prefer public helpers, service functions, and meaningful outputs over private implementation details.

It is fine to test a private helper when it protects a narrow safety rule or complicated transformation. But the suite should mostly describe expected behavior:

- given this dataset, this service returns this result
- given this preference state, this launcher command is built
- given this platform, these defaults are resolved
- given this alias history, this tag resolves safely

This keeps tests useful during refactors.

## What Gets Heavy Coverage

RoleThread gives extra coverage to areas where regressions can damage user work or make the app hard to launch:

- dataset mutation services
- tag lifecycle and alias resolution
- backups and cloud sync staging
- validation and repair helpers
- platform and runtime detection
- path default resolution
- launcher command construction
- preferences and settings helpers
- Help and FAQ registries

These are the pieces contributors should treat as safety-critical.

## UI Testing Boundaries

RoleThread avoids overloading the suite with brittle UI tests where pure tests can prove the same behavior.

Streamlit interaction can be tested when the user flow itself matters, especially for navigation, Help search, FAQ behavior, and state transitions. But if a pure helper can carry the rule, prefer testing that helper directly.

The practical target is confidence without turning the suite into a slow visual automation project.

## Launcher and Platform Tests

Launcher and platform behavior should be tested through command construction, path resolution, capability metadata, and safe fallback statuses.

Tests should not spawn real browsers or require a real installer. They should prove that RoleThread decides correctly:

- normal mode versus webapp mode
- Windows Edge support versus fallback
- unsupported platform behavior
- bundled path detection
- launcher logging and failure reporting

The real browser and installer workflows still need manual smoke testing, but the decision logic should stay covered.

## Contributor Guidance

When adding behavior, prefer tests that protect the user's data and the contributor's future sanity.

Useful tests are usually:

- small
- deterministic
- close to the service or core behavior
- clear about the failure they prevent
- not dependent on local machine state unless explicitly mocked

RoleThread's test suite should make refactoring safer, not make the codebase afraid to move.
