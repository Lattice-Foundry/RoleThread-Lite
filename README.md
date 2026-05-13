# LoreForge Lite

### Local-First Dataset Crafting for Narrative AI

LoreForge Lite is a local-first tool for creating, validating, repairing,
organizing, merging, and exporting narrative AI training datasets.

Built for writers, roleplay dataset builders, and fine-tuning creators,
LoreForge Lite keeps your JSONL files, registry database, backups, and sidecar
metadata on your machine while giving you practical tools for structured
dataset engineering.

---

## Current Features

* ChatML dataset creation and management
* ShareGPT import/export with ChatML conversion support
* Quick edit and full edit workflows for multi-turn entries
* Validation page with auto-fixable repairs and character role mapping
* Custom tag categories, active/archived tag lifecycle handling, and alias repair
* Character registry and per-entry character-to-turn metadata
* Portable registry sidecars for tags, aliases, characters, and mappings
* Protected working copies for foreign files so originals stay untouched
* Dataset merge tools with dataset UUID, entry UUID, sidecar, and tag hardening
* Bulk tag edits, system prompt tools, statistics, and diagnostics
* Local preferences, dataset backups, and database backups

---

## Design Philosophy

LoreForge Lite is designed around:

* local-first, privacy-first workflows
* maintainable JSONL training data
* deterministic validation and repair before subjective scoring
* portable sidecar metadata for registry and character reconstruction
* a clear core/service/UI architecture that can support future Studio work

Lite stays focused on dataset craftsmanship. Larger orchestration, cloud, and
AI-assisted workflow systems belong in future Studio work rather than the Lite
release surface.

---

## Backup & Recovery

LoreForge Lite creates local backups before important dataset and registry
changes.

For tag edit/delete operations, there is a small known recovery window: the
JSONL dataset is saved atomically before the tag database commit finishes. If
the JSONL save succeeds but the database commit fails, the dataset may contain
the updated tag state while the database still contains the previous registry
state.

This is rare in normal local single-user use, and both recovery materials are
created before the operation:

* Dataset backups live under `backups/datasets/<dataset_name>/`
* SQLite database backups live under `backups/database/`

To recover, close LoreForge Lite, choose the matching backup file, and copy it
over the current dataset or database file. Dataset backups restore the JSONL
data. Database backups restore the tag registry, lifecycle metadata, character
registry, and local app metadata.

This limitation is known and may be tightened in a future version with stronger
SQLite sync/transaction handling or a revised persistence order.

---

## Near-Term Work

* Final UI polish and wording cleanup
* In-app Help and onboarding documentation
* Additional statistics and dataset health views
* More workflow documentation and troubleshooting guidance
* Continued regression coverage for merge, sidecar, validation, and lifecycle paths

---

## Vision

High-quality narrative AI experiences begin with high-quality narrative data.
LoreForge Lite focuses on the local, inspectable, repairable dataset workflow
needed to build that data with confidence.

Local-first. Creator-focused. Built for narrative AI datasets.
