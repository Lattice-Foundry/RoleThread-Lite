# Codebase Architecture

RoleThread Lite is a layered Python application with a Streamlit presentation shell.

Durable behavior lives in framework-independent modules. Streamlit owns rendering and interaction, not the application model.

## The Main Layers

The main source areas map to runtime responsibilities.

### `ui/`

The `ui/` layer owns Streamlit rendering and interaction.

It handles:

- page layout
- widgets
- session-state coordination
- user-facing controls
- visual presentation
- Help and FAQ browser rendering

The UI layer may call services and core helpers. It should not own durable mutation, validation, persistence, or platform rules.

### `services/`

The `services/` layer owns workflow orchestration.

It coordinates multi-step operations such as dataset mutations, registry sidecar updates, backup-before-write flows, tag lifecycle changes, and result assembly.

Services are workflow-aware but framework-independent. They should be testable without Streamlit.

### `core/`

The `core/` layer owns reusable application logic.

It includes:

- dataset parsing and normalization
- validation and repair helpers
- storage and backup behavior
- platform and runtime detection
- tag registry logic
- character and metadata handling
- cloud sync primitives
- local persistence utilities

Core modules should not import Streamlit. They are the most reusable part of the app.

### `installer/`

The `installer/` area contains Windows packaging and launcher work.

It includes the Windows launcher, PyInstaller bundle configuration, Inno Setup planning, and packaging documentation. The launcher is separate from the Streamlit app because it owns startup orchestration, runtime selection, and installed-user behavior.

### `docs/`

The `docs/` folder contains user Help articles, FAQ content, setup notes, and developer-facing documentation.

Help content is registered explicitly so the in-app documentation browser can provide category navigation, search, related links, and stable article IDs.

## Boundary Model

Streamlit is a replaceable UI shell.

Dataset mutation, sidecar synchronization, registry metadata, platform paths, launch planning, and export workflows need deterministic behavior outside a live UI session.

This boundary keeps service/core behavior reusable by tests, launchers, and future product surfaces.

## Service Pipelines

Several workflows follow a repeated pattern:

- validate input
- prepare proposed changes
- create backups
- write dataset files
- update sidecars or registry metadata
- return a structured result

Service pipelines centralize the repeated mutation flow where the workflow shape is stable. They reduce duplication without hiding the operation being performed.

## Future Portability

RoleThread Lite is currently served through Streamlit, but the service/core split keeps future UI surfaces possible.

A future RoleThread Studio surface, native shell, or different UI technology should be able to reuse much of the Python core and service logic.

The practical requirement is simple: important rules should not depend on one UI framework.
