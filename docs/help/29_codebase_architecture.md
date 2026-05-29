# Codebase Architecture

RoleThread Lite is a layered Python application with a Streamlit presentation shell.

Durable behavior lives in framework-independent modules. Streamlit owns rendering and interaction, not the application model.

## The Main Layers

The main source areas map to product responsibilities. Runtime/platform
behavior is deliberately pushed out to LitLaunch.

### `ui/`

The `ui/` layer owns Streamlit rendering and interaction.

It handles:

- page layout
- widgets
- session-state coordination
- user-facing controls
- visual presentation
- Help and FAQ browser rendering
- the app-owned LitLaunch diagnostics page integration

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

The `installer/` area contains Windows packaging and product launcher work.

It includes the Windows launcher, PyInstaller bundle configuration, Inno Setup
script, build helpers, and packaging documentation.

The packaged launcher is separate from the Streamlit app because installed
users should not need Python, virtual environments, pip, or manual Streamlit
commands. It remains a product wrapper: frozen path resolution, packaged
backend provider wiring, RoleThread log paths, and branded failure messages.

Installer code should not duplicate dataset, UI, or LitLaunch runtime logic.
Browser/window observation, command planning, backend lifecycle, diagnostics,
runtime event logging, and shutdown protocol belong to LitLaunch.

### `docs/`

The `docs/` folder contains user Help articles, FAQ content, setup notes, and developer-facing documentation.

Help Markdown files own article content. `docs/help_manifest.json` owns the Help
taxonomy: stable article IDs, source paths, categories, ordering, summaries,
related articles, and public metadata. The in-app Help browser consumes that
manifest, and external documentation sync jobs can consume the same repo-owned
taxonomy directly from JSON without importing RoleThread Python code or
becoming the source of truth.

## Boundary Model

Streamlit is a replaceable UI shell.

Dataset mutation, sidecar synchronization, registry metadata, platform paths,
cloud backup policy, and export workflows need deterministic behavior outside a
live UI session.

This boundary keeps service/core behavior reusable by tests, the packaged
launcher, and future product surfaces.

## Runtime Boundary

RoleThread uses LitLaunch instead of carrying its own runtime platform.

RoleThread owns:

- datasets, validation, repair, imports, exports, and registry metadata
- preferences, storage locations, backups, and cloud sync policy
- branding, help text, support wording, and installer presentation
- packaged/frozen path resolution and backend provider wiring
- product shutdown hooks, such as cloud-sync closeout

LitLaunch owns:

- `litlaunch.toml` profile loading
- command planning
- monitored app-window runtime
- browser/window observation
- backend lifecycle
- runtime diagnostics, support artifacts, and runtime event logging
- shutdown protocol

`app.py` should remain launch-semantics-blind. It is the Streamlit app entry
point, not a launcher.

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
