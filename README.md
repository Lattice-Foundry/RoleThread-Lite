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
* Entry search across Manage Dataset and Edit Entries with role scopes and match modes
* Validation page with auto-fixable repairs and character role mapping
* Custom tag categories, active/archived tag lifecycle handling, and alias repair
* Character registry and per-entry character-to-turn metadata
* Portable registry sidecars for tags, aliases, characters, and mappings
* Protected working copies for untrusted files so originals stay untouched
* Dataset merge tools with dataset UUID, entry UUID, sidecar, and tag hardening
* Bulk tag edits, system prompt tools, dataset insights, and diagnostics
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

## Data Safety and Recovery

LoreForge Lite keeps working data local and creates recovery points before
important dataset and registry changes.

* JSONL dataset writes use local backups and atomic file replacement where
  practical.
* SQLite database backups protect tag, character, prompt-template, settings,
  and lifecycle metadata.
* Registry sidecars are refreshed alongside dataset saves so portable metadata
  stays close to the JSONL file.
* Optional cloud backup mirrors the latest local backup material to a configured
  sync folder after staging the output locally.

There is one known partial-failure recovery window in some durable operations:
the JSONL dataset save may succeed before a later SQLite commit fails. For
example, a tag lifecycle edit can update the dataset file and then fail while
committing registry metadata. In that case, the JSONL and database may briefly
reflect different states.

This is rare in normal local single-user use, and both recovery materials are
created before the operation:

* Dataset backups live under `backups/datasets/<dataset_name>/`
* SQLite database backups live under `backups/database/`

To recover, close LoreForge Lite and restore the most recent consistent dataset
and database backup pair. Dataset backups restore the JSONL data. Database
backups restore the tag registry, lifecycle metadata, character registry,
system prompt templates, local settings, and other app metadata.

LoreForge Lite does not claim one global transaction across JSONL files,
sidecars, SQLite, and cloud-sync folders. The recovery design is instead:
backup first, write carefully, refresh sidecars, and keep enough local material
available for a clear restore if the machine or process fails mid-operation.

---

## Version 1 Stable Status

LoreForge Lite 1.0 is the stable local-first release surface for dataset
craftsmanship.

## Supported Runtime

LoreForge Lite V1 officially supports Python `3.14.4`.

Other Python versions may run, but they are not guaranteed for V1 unless they
are tested later. Python versions below `3.14.4` are unsupported. Windows
installer work will bundle or target the supported runtime later; manual
Linux/macOS setup should use `python3.14`.

Linux/macOS manual setup:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Windows/dev setup:

```bat
py -3.14 -m venv trainer
trainer\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The V1 stability gate is:

* Full unit and service suite passes with `python -m pytest`
* Help and FAQ content are present in-app
* Lite and future Studio boundaries are documented
* Local backups, sidecars, validation, merge, tag lifecycle, character mapping,
  export, and settings flows remain covered by regression tests
* Known limitations are documented rather than implied as missing V1 work

---

## Vision

High-quality narrative AI experiences begin with high-quality narrative data.
LoreForge Lite focuses on the local, inspectable, repairable dataset workflow
needed to build that data with confidence.

Local-first. Creator-focused. Built for narrative AI datasets.
