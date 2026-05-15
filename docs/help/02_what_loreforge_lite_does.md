# What LoreForge Lite Does

LoreForge Lite is a local-first toolkit for crafting narrative AI training datasets. It focuses on the practical work around dataset creation: writing entries, editing conversations, validating structure, organizing metadata, merging files, searching entries, reviewing quality, and exporting clean training data.

It is built for creators working with roleplay, character-driven scenes, storytelling, worldbuilding, and other narrative interaction data.

## The Core Idea

A training dataset is more than a pile of messages. Over time, it also needs:

- consistent structure
- useful tags
- stable entry identity
- character information
- system prompts
- validation and repair
- backups and recovery paths
- safe import/export behavior

LoreForge Lite provides those tools while keeping the actual dataset files local and inspectable.

## Local-First Dataset Crafting

Local-first means the app is designed around your machine and your files.

LoreForge Lite stores and works with:

- JSONL dataset files
- local registry metadata
- sidecar metadata files
- local backups
- optional cloud backup copies only when configured

The app is not a hosted service. It does not require you to upload your writing to a central server to organize it.

## What You Can Do With It

### Create and Refine Entries

You can create new ChatML-style entries with:

- a system prompt
- user/assistant exchanges
- tags
- optional Group Chat character assignments

You can also quick edit, full edit, duplicate, split, join, and repair existing entries.

### Search and Filter

Entry Search helps you find text inside loaded entries. It can search:

- system messages
- user messages
- assistant messages

Tag filters and search work together, with pagination applied after filtering.

### Organize Metadata

LoreForge Lite includes local management for:

- tag categories
- custom tags
- archived/imported tags
- tag aliases after rename or merge
- character definitions
- character-to-turn mappings
- system prompt templates

This metadata helps you work with the dataset without forcing extra fields into clean training output.

### Validate and Repair

Validation checks loaded entries for common structural and content issues. Some repairs are automatic. Others are shown for manual review.

This helps prevent small format problems from quietly spreading through a dataset.

### Merge and Export

You can merge datasets while preserving useful metadata and creating a fresh merge output identity. You can export full datasets or selected/filtered subsets.

Clean export removes LoreForge metadata from records intended for training.

### Review Insights

Insights gives deterministic quality signals, including:

- response quality
- diversity
- structure
- metadata integrity
- narrative/dialogue balance
- response length distribution
- exchange depth distribution
- system prompt concentration

These are guidance tools. They help you notice patterns, but they do not replace creative judgment.

## What Lite Is Not

LoreForge Lite is intentionally not:

- a chatbot frontend
- a hosted dataset platform
- a social network
- a real-time cloud sync system
- an AI writing assistant
- a semantic/vector search engine
- a replacement for reviewing your own training data

It is a focused local tool for preparing narrative datasets.

## Where Studio Fits Later

Future Studio work may explore larger workflows, more orchestration, and heavier automation. Lite should still feel complete on its own. The purpose of Lite is local dataset craftsmanship: safe files, clear structure, useful metadata, and reliable export.

## A Good Mental Model

Think of LoreForge Lite as a careful workshop for your dataset.

It does not hide the files from you. It does not assume every imported file is safe to edit directly. It keeps metadata separate when that protects clean training data. It creates backups before risky operations. It tries to make problems visible before they become expensive.
