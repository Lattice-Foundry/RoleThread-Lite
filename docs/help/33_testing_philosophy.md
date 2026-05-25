# Testing Philosophy

RoleThread Lite uses tests to protect behavior at the service and core boundaries.

The most important tests prove deterministic behavior for datasets, sidecars,
tags, backups, preferences, platform capabilities, and RoleThread's LitLaunch
configuration boundaries.

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
- given this profile state, this runtime configuration is exposed
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
- LitLaunch profile and packaged-provider wiring
- preferences and settings helpers
- Help and FAQ registries

## UI Testing Boundaries

RoleThread avoids overloading the suite with brittle UI tests where pure tests can prove the same behavior.

Streamlit interaction can be tested when the user flow itself matters, especially for navigation, Help search, FAQ behavior, and state transitions. But if a pure helper can carry the rule, prefer testing that helper directly.

The target is confidence without turning the suite into a slow visual automation project.

## Runtime and Platform Tests

Runtime and platform behavior should be tested through profile configuration,
path resolution, capability metadata, packaged-provider wiring, and safe status
messages.

RoleThread tests should not spawn real browsers or require a real installer.
They should prove that RoleThread supplies the right product configuration to
LitLaunch:

- source profile versus plain Streamlit development
- Windows app-window support messaging
- unsupported platform behavior
- bundled path detection
- packaged backend provider construction
- product logging and failure reporting
- diagnostics page integration and product support context

LitLaunch has its own runtime/platform test suite. RoleThread should not mirror
those internals. Browser, package, installer, and installed-user workflows still
need smoke testing; RoleThread's unit tests should cover the decisions and
adapter edges it actually owns.

## Packaging Smoke Tests

Packaging verification is partly manual by design:

- build the PyInstaller bundle
- run the packaged launcher from `dist`
- confirm the LitLaunch profile loads
- confirm the backend starts on `127.0.0.1:8501`
- confirm the app window opens
- optionally smoke `python -m litlaunch.cli run --profile rolethread-browser` when testing regular-browser LitLaunch behavior
- close the app window and confirm shutdown/cloud-sync closeout
- build the Inno installer
- install, launch, uninstall, and verify user data behavior

For command-line diagnostics, use:

```bat
python -m litlaunch report --profile rolethread-webapp --force
```

The running app also exposes **Support -> Diagnostics**. That page should be
smoked when diagnostics UI changes: runtime summary, operational snapshot,
RoleThread product panels, support artifacts, runtime event trail, and raw
runtime event trail should all remain usable.

Generated diagnostics reports and bundles live under `.litlaunch/reports/`.
They are support artifacts, not telemetry or source files. A generic
redaction/privacy warning is expected when reports may contain local paths.

## Contributor Guidance

When adding behavior, prefer tests that protect data integrity, launch decisions, and service contracts.

Useful tests are usually:

- small
- deterministic
- close to the service or core behavior
- clear about the failure they prevent
- not dependent on local machine state unless explicitly mocked

The suite should make refactoring safer without freezing implementation details.
