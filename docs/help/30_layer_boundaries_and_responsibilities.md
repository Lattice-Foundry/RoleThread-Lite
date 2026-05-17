# Layer Boundaries and Responsibilities

RoleThread Lite separates presentation, workflow orchestration, and reusable core logic.

The boundary exists to keep mutation behavior testable without a live Streamlit session.

## `ui/`: Presentation and Interaction

The `ui/` layer owns the Streamlit runtime surface.

Good fits for `ui/` include:

- rendering pages and panels
- creating widgets
- arranging columns and expanders
- reading and writing Streamlit session state
- displaying success, warning, and error messages
- calling services in response to user actions
- formatting user-facing previews

Poor fits for `ui/` include:

- backup policy
- mutation safety rules
- database lifecycle behavior
- canonical tag resolution
- dataset repair rules
- platform detection logic
- file format conversion internals

The UI layer should not own durable business logic.

## `services/`: Workflow Orchestration

The `services/` layer coordinates operations that involve several steps.

Good fits for `services/` include:

- create, edit, delete, duplicate, split, join, and merge workflows
- backup-before-write coordination
- dataset save orchestration
- sidecar refresh behavior
- tag lifecycle workflows
- structured operation results
- consistency checks around persistence

Services may call core modules and return results that the UI can display. They should not import Streamlit or depend on live widgets.

The service layer owns sequencing and operation-level error handling.

## `core/`: Reusable Logic and Persistence

The `core/` layer owns framework-independent behavior.

Good fits for `core/` include:

- dataset reading and writing
- validation logic
- role and tag normalization
- storage paths and platform defaults
- runtime compatibility checks
- SQLite models and registry helpers
- cloud sync primitives
- backup mechanics
- text and metadata helpers

Core modules should be usable from tests, services, launchers, or future surfaces without Streamlit.

The core layer owns reusable rules and persistence primitives.

## Why The Boundary Matters

When a feature can change dataset content, registry metadata, sidecars, backups, or export output, it should be possible to test that behavior without clicking through the UI.

Separating the layers helps:

- reduce accidental UI-driven behavior changes
- make service tests faster and clearer
- preserve data-safety rules
- support launcher and installer work without moving runtime logic into UI code
- keep future Studio options open

## Practical, Not Rigid

This is not a heavy enterprise layering model.

Important behavior should live in the smallest layer that can own it responsibly. UI code can stay expressive; services can stay workflow-focused; core logic can stay portable.
