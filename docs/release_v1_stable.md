# RoleThread Lite V1 Stable Release Gate

This checklist defines the stable-release gate for RoleThread Lite 1.0.

## Required Verification

- Run `python -m pytest`
- Confirm the suite passes from a clean workspace
- Confirm `core/version.py` reports the intended release version
- Confirm the runtime is Python `3.14.5`, the official supported V1 runtime
- Confirm `requirements.txt` keeps Streamlit on the tested `1.57.x` line
- Confirm direct Pandas, Plotly, and SQLAlchemy requirements match the tested
  V1 dependency lines
- Confirm OS compatibility docs describe Windows/Linux primary support and
  macOS beta support
- Confirm launch docs describe the installed Windows app path, the LitLaunch
  source profile path, and the normal Streamlit browser development path
- Confirm `litlaunch.toml` contains the expected source runtime profile
- Confirm Support -> Diagnostics and LitLaunch report instructions are
  documented for support
- Confirm fresh-install storage defaults are documented for Windows, Linux,
  and macOS
- Confirm README status describes the V1 stable surface
- Confirm Help and FAQ tests pass
- Confirm V1 limitations and future boundaries remain documented

## Release Surface

RoleThread Lite V1 is stable for local-first dataset craftsmanship:

- creating ChatML datasets
- importing and exporting ShareGPT and ChatML data
- editing, splitting, joining, searching, filtering, and validating entries
- managing tags, tag lifecycle metadata, character registry data, and system
  prompt templates
- writing portable sidecars for registry and mapping reconstruction
- merging datasets with hardened identity and sidecar behavior
- creating local backups and optional cloud-backup mirrors
- reviewing dataset quality through deterministic Insights
- installed Windows launch through the packaged RoleThread launcher
- source app-window launch through the `rolethread-webapp` LitLaunch profile
- source browser development through `streamlit run app.py`

## Deferred Beyond V1

The following are intentionally outside the Lite V1 release surface:

- semantic or vector search
- real-time collaboration
- hosted inference or training orchestration
- multi-user permissions, review queues, or cloud workers
- automatic creative rewriting or hidden AI-driven dataset generation
- RoleThread-owned browser, monitor, backend, or shutdown runtime orchestration
- duplicating LitLaunch internals in RoleThread docs

## Runtime Verification

The V1 runtime boundary is:

- RoleThread owns product behavior, data workflows, preferences, backups,
  cloud-sync policy, branding, and installer presentation.
- LitLaunch owns runtime profiles, command planning, monitored app-window
  launch, backend lifecycle, diagnostics, and shutdown coordination.
- `app.py` remains the Streamlit app entry point and should not know about
  app-window launch semantics.

Before release, verify:

- `python -m litlaunch.cli run --profile rolethread-webapp`
- Support -> Diagnostics opens in the app and shows runtime summary,
  operational snapshot, product diagnostics, support artifacts, and runtime
  event trail
- `python -m litlaunch report --profile rolethread-webapp --force`
- `.litlaunch/reports/` contains generated support reports/bundles and remains untracked
- advanced support output still works through `python -m litlaunch inspect --profile rolethread-webapp --json`
- advanced support bundles still work through `python -m litlaunch inspect --profile rolethread-webapp --bundle`
- packaged launcher smoke from the PyInstaller bundle
- installed-user launch/shutdown smoke from the setup executable
- cloud-sync closeout runs once on normal app-window close
- no backend remains listening on port `8501` after shutdown

These boundaries keep the stable release local, inspectable, deterministic,
supportable, and recoverable.

