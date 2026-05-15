# V1 Limitations and Future Boundaries

LoreForge Lite is intentionally focused.

It is built for local dataset craftsmanship: creating, organizing, validating, editing, analyzing, merging, backing up, and exporting datasets with clear user control.

This page explains what Lite is optimized for and what it does not try to be in V1.

## What Lite Is Optimized For

LoreForge Lite is optimized for:

- local-first dataset work
- JSONL, ChatML, and ShareGPT workflows
- structured entry creation and editing
- metadata organization
- tags, characters, and system prompt templates
- validation and deterministic repair
- Insights and dataset quality review
- merge, split, join, and export workflows
- backups and portable metadata

The app is designed around creator ownership and predictable tools.

## Local-First by Design

LoreForge Lite keeps working data local unless you configure cloud backup.

Normal app use does not depend on a cloud service.

Your datasets, sidecars, registry database, settings, and local backups remain on your machine.

## No Semantic or Vector Search

V1 search is deterministic entry search.

It supports:

- text queries
- message scopes
- contains, all-words, and exact-phrase matching
- tag filters

It does not include semantic search, vector search, fuzzy search, or embedding-based discovery.

That boundary keeps search predictable and local.

## No Real-Time Collaborative Editing

LoreForge Lite is a single-user local app.

Cloud sync is for backup mirroring, not multi-user editing.

Do not open and edit the same dataset from multiple machines at the same time through a cloud folder. Use export, backup, and careful file handoff instead.

## No Hosted Inference

LoreForge Lite does not host models or run inference as part of the V1 workflow.

It helps you prepare datasets. It does not train, serve, or evaluate a hosted model for you.

## No Multi-User Orchestration

Lite does not manage teams, job queues, cloud workers, hosted datasets, permissions, or multi-user review pipelines.

Those are larger orchestration concerns. Lite stays focused on local dataset work.

## No Live Cloud Sync

Cloud sync is batch backup.

It can mirror latest backup material to a configured sync folder, but it is not live file synchronization controlled by LoreForge.

Your cloud provider may sync the folder afterward, but LoreForge treats that as backup transport, not active collaboration.

## No Automatic Dataset Building

LoreForge Lite does not generate a finished dataset for you automatically.

It gives you tools to write, inspect, organize, repair, analyze, and export your own dataset.

The creator remains responsible for the quality, intent, and content of the training examples.

## No Hidden "AI Does Everything" Workflow

V1 tools are deterministic and reviewable.

Validation and Insights can surface issues, but they do not replace creator judgment. Repair tools handle safe predictable fixes, not creative rewriting.

This keeps the workflow understandable.

## Lite and Future Studio Boundaries

LoreForge Lite is complete as a local-first dataset crafting tool.

Future Studio work may explore larger orchestration, hosted workflows, AI-assisted tooling, or team-scale systems. Those boundaries are separate from the Lite V1 surface.

Lite should not feel like an incomplete product because it does not do those things. It is intentionally scoped around careful local work.

## Why These Boundaries Exist

Boundaries keep the app reliable.

They help LoreForge Lite stay:

- understandable
- local-first
- recoverable
- deterministic
- practical for solo creators
- focused on dataset quality instead of platform complexity

More automation is not always better if it makes the workflow harder to trust.

## Practical Recommendation

Use LoreForge Lite when you want hands-on control over a local dataset.

Use clean export when another tool needs training records.

Use sidecars when you want portable metadata.

Use backups and cloud sync for recovery, not collaboration.
