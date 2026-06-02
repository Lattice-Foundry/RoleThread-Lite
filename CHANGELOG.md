# Changelog

Meaningful changes to RoleThread Lite are summarized here for users,
maintainers, and release reviewers. Git history remains the granular record for
development patch-by-patch detail.

## 1.0.0 - Stable Release

Summary:

- First stable public release of RoleThread Lite.
- Local-first AI roleplay dataset engineering application for creators,
  dataset builders, and fine-tuning preparation workflows.
- Powered by LitLaunch 1.0.0 for runtime orchestration, diagnostics, support
  artifacts, app-window lifecycle, and shutdown coordination.

Highlights:

- ChatML dataset creation, loading, editing, repair, merge, and export
  workflows.
- ShareGPT import/export with ChatML conversion support.
- Validation, quality checks, deterministic repair paths, and dataset insights.
- Tag categories, tag lifecycle metadata, aliases, archived/imported tag
  handling, and bulk tag workflows.
- Character registry, per-entry character-turn mappings, and system prompt
  library support.
- Portable registry sidecars for reconstructing tags, aliases, characters,
  mappings, and prompt metadata beside dataset files.
- Protected working copies for untrusted or imported files.
- Local database, dataset backups, optional cloud backup mirrors, and
  documented recovery guidance.
- Data Generation workflow for provider-agnostic prompt compilation.
- Local-first privacy posture with no hidden hosted runtime requirement.
- Support -> Diagnostics page with RoleThread product context, LitLaunch
  runtime posture, support artifacts, and runtime event trail.
- Windows installer and packaged launcher support for the primary Windows
  app-window experience.
- In-app Help, FAQ, release-gate, architecture, platform, testing, and
  packaging documentation.

## Stabilization Era

Condensed summary of the pre-1.0 stabilization work:

- Completed the RoleThread/LoreForge naming transition and settled the
  RoleThread Lite product identity.
- Matured the local-first dataset workflow around ChatML/ShareGPT handling,
  trusted metadata, working copies, merge behavior, backups, and sidecars.
- Built out validation, repair, dataset quality, tag lifecycle, character
  mapping, system prompt, search/filter, and export tooling.
- Added the Data Generation surface and educational AI training
  fundamentals for roleplay dataset preparation.
- Expanded user Help, FAQ, developer docs, architecture notes, platform docs,
  testing guidance, and release checklists.
- Moved runtime/platform ownership to LitLaunch and removed RoleThread-owned
  browser lifecycle, shutdown orchestration, launcher governance, and legacy
  app-owned webapp behavior.
- Hardened diagnostics and support artifacts around product state, storage,
  cloud backup posture, LitLaunch runtime events, report generation, and
  privacy review guidance.
- Hardened Windows packaging, PyInstaller bundling, Inno setup flow, launcher
  logging, stale-bundle validation, and installed app-window shutdown behavior.
- Extracted the Help taxonomy into `docs/help_manifest.json` so RoleThread Lite
  and external documentation renderers can share the same repo-owned Help
  structure.

## Alpha Development Era

Condensed early groundwork:

- Created the initial local Streamlit app for roleplay dataset creation and
  inspection.
- Added JSONL import/export foundations, ChatML-oriented entry handling, and
  early validation.
- Established core/service/UI layering so mutation logic could be tested
  without a live Streamlit session.
- Built the first navigation, Help, settings, backup, tag, and editing
  surfaces.
- Explored early launcher/runtime ideas that were later retired or moved into
  LitLaunch.
