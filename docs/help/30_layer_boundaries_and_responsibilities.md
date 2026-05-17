# Layer Boundaries and Responsibilities

RoleThread Lite keeps a practical boundary between UI code, workflow services, and core logic.

The boundary is not meant to be ceremonial. It exists so dataset behavior stays testable, reusable, and easier to reason about.

## `ui/`: Presentation and Interaction

The `ui/` layer owns the Streamlit experience.

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

RoleThread Lite intentionally avoids putting durable business logic in the UI layer.

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

The service layer is where the app says, "This is the workflow."

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

The core layer is where the app says, "This is the rule."

## Why The Boundary Matters

RoleThread Lite works with files users care about.

When a feature can change dataset content, registry metadata, sidecars, backups, or export output, it should be possible to test that behavior without clicking through the UI.

Separating the layers helps:

- reduce accidental UI-driven behavior changes
- make service tests faster and clearer
- preserve local-first safety rules
- support future launcher and installer work
- keep future Studio options open

## Practical, Not Rigid

The goal is not to build a heavy enterprise architecture.

The goal is to keep important behavior in the smallest layer that can own it responsibly. UI code can stay expressive. Services can stay workflow-focused. Core logic can stay portable.

That balance lets RoleThread Lite remain approachable while still being serious about data safety and maintainability.

