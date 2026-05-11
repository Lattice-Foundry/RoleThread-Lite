# LoreForge

### Narrative Intelligence Studio

LoreForge is a local-first Narrative Intelligence Studio designed for creating, managing, refining, and analyzing AI roleplay training datasets.

Built for writers, roleplay enthusiasts, and fine-tuning creators, LoreForge provides powerful tools for structured dataset creation, multi-turn conversation management, tagging, validation, bulk editing, statistics, and dataset engineering workflows — all through a streamlined desktop-style interface.

---

## Current Features

* ChatML dataset creation and management
* Multi-turn exchange planning
* Quick and deep editing workflows
* Bulk tag and system prompt management
* Dataset merging and export tools
* Validation and error detection
* Dataset statistics and visualization
* Persistent local preferences and workspace management

---

## Design Philosophy

LoreForge is designed with a strong focus on:

* Local AI workflows
* Maintainable JSONL datasets
* High-quality narrative training data
* Extensible dataset engineering tools
* Future AI-assisted refinement and scoring systems

---

## Backup & Recovery

LoreForge creates local backups before important dataset and registry changes.

For tag edit/delete operations, there is a small known V1 recovery window: the JSONL dataset is saved atomically before the tag database commit finishes. If the JSONL save succeeds but the database commit fails, the dataset may contain the updated tag state while the database still contains the previous registry state.

This is rare in normal local single-user use, and both recovery materials are created before the operation:

* Dataset backups live under `backups/datasets/<dataset_name>/`
* SQLite database backups live under `backups/database/`

To recover, close LoreForge, choose the matching backup file, and copy it over the current dataset or database file. Dataset backups restore the JSONL data. Database backups restore the tag registry, lifecycle metadata, and local app metadata.

This limitation is known and may be tightened in a future version with stronger SQLite sync/transaction handling or a revised persistence order.

---

## Planned Features

* ShareGPT export support
* Advanced validation and scoring systems
* Custom tag and category management
* AI-assisted dataset refinement
* Lore and character knowledge integration
* Local model orchestration and RAG workflows
* Narrative consistency analysis
* Dataset balancing and variation tooling

---

## Vision

LoreForge is built around the idea that high-quality AI roleplay experiences begin with high-quality narrative data.

Rather than acting as just another chatbot frontend, LoreForge aims to become a complete narrative dataset engineering platform — helping creators design, refine, validate, and evolve training data for local and custom AI systems.

Local-first. Creator-focused. Built for narrative intelligence.
