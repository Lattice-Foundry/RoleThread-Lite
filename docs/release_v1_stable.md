# LoreForge Lite V1 Stable Release Gate

This checklist defines the stable-release gate for LoreForge Lite 1.0.

## Required Verification

- Run `python -m pytest`
- Confirm the suite passes from a clean workspace
- Confirm `core/version.py` reports the intended release version
- Confirm the runtime is Python `3.14.4`, the official supported V1 runtime
- Confirm README status describes the V1 stable surface
- Confirm Help and FAQ tests pass
- Confirm V1 limitations and future boundaries remain documented

## Release Surface

LoreForge Lite V1 is stable for local-first dataset craftsmanship:

- creating ChatML datasets
- importing and exporting ShareGPT and ChatML data
- editing, splitting, joining, searching, filtering, and validating entries
- managing tags, tag lifecycle metadata, character registry data, and system
  prompt templates
- writing portable sidecars for registry and mapping reconstruction
- merging datasets with hardened identity and sidecar behavior
- creating local backups and optional cloud-backup mirrors
- reviewing dataset quality through deterministic Insights

## Deferred Beyond V1

The following are intentionally outside the Lite V1 release surface:

- semantic or vector search
- real-time collaboration
- hosted inference or training orchestration
- multi-user permissions, review queues, or cloud workers
- automatic creative rewriting or hidden AI-driven dataset generation

These boundaries keep the stable release local, inspectable, deterministic, and
recoverable.
