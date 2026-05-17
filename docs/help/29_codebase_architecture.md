# Codebase Architecture

RoleThread Lite is organized as a layered local application, not as a single Streamlit script.

Streamlit is the current UI shell. The durable behavior lives in framework-independent modules so the project can stay maintainable, testable, and portable as the RoleThread ecosystem grows.

## The Main Layers

The codebase is split into a few practical areas.

### `ui/`

The `ui/` layer owns Streamlit rendering and interaction.

It handles:

- page layout
- widgets
- session-state coordination
- user-facing controls
- visual presentation
- Help and FAQ browser rendering

The UI layer may call services and core helpers, but it should not become the place where durable business rules live.

### `services/`

The `services/` layer owns workflow orchestration.

It coordinates multi-step operations such as dataset mutations, registry sidecar updates, backup-before-write behavior, tag lifecycle changes, and result reporting.

Services are allowed to know about workflows. They should stay framework-independent so they can be tested without Streamlit and reused by future launchers or product surfaces.

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

It includes the Windows launcher prototype, PyInstaller bundle configuration, Inno Setup planning, and packaging documentation. The launcher is separate from the Streamlit app because it will eventually own startup, bundled runtime selection, and installed-user behavior.

### `docs/`

The `docs/` folder contains user Help articles, FAQ content, setup notes, and developer-facing documentation.

Help content is registered explicitly so the in-app documentation browser can provide category navigation, search, related links, and stable article IDs.

## Architectural Philosophy

RoleThread Lite treats Streamlit as a UI shell, not the whole application architecture.

That split matters because the project is handling user data, backups, sidecars, registry metadata, platform paths, launch behavior, and export workflows. Those pieces need tests and predictable behavior outside a live UI session.

The goal is not architecture for its own sake. The goal is to keep the app understandable as it grows.

## Service Pipelines

Several workflows follow a repeated pattern:

- validate input
- prepare proposed changes
- create backups
- write dataset files
- update sidecars or registry metadata
- return a structured result

Service pipelines centralize those patterns where it is safe. They reduce duplication and make failure behavior more consistent without hiding the workflow itself.

## Future Portability

RoleThread Lite is currently a Streamlit app, but the core design keeps future options open.

A future RoleThread Studio surface, native shell, or different UI technology should be able to reuse much of the Python core and service logic. That does not mean Lite is already Studio. It means Lite avoids tying every important rule to one UI framework.

This is why the project is careful about boundaries: local-first behavior, deterministic workflows, and reusable service logic are easier to preserve when the layers have clear responsibilities.

