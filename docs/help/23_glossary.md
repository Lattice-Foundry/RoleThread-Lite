# Glossary

This glossary defines the main terms used across RoleThread Lite.

## RoleThread Lite

The local-first app for creating, organizing, validating, editing, merging, analyzing, and exporting narrative training datasets.

## Dataset

A collection of training entries, usually stored as a JSONL file.

## JSONL

JSON Lines. A file format where each line is one JSON object. Many training datasets use this format.

## ChatML

A message-based dataset shape built around roles such as `system`, `user`, and `assistant`.

## ShareGPT

A conversation dataset format used by some tools. RoleThread can import and export ShareGPT-style data.

## Entry

One training example in a dataset. In RoleThread, an entry usually contains a system prompt and one or more user/assistant exchanges.

## Exchange

A user message paired with an assistant response.

## System Prompt

The instruction or setup message at the beginning of an entry.

## System Prompt Template

A reusable saved system prompt that can be loaded into Create Entry or Full Edit, then customized before saving.

## Tag

Metadata used to organize entries. Tags help with filtering, search, export, review, and Insights.

## Category

A group for related tags.

## Built-In Tag

A RoleThread-provided tag that is locked to preserve consistent meaning across datasets.

## Custom Tag

A user-created tag that can be edited, renamed, or deleted.

## Archived/Imported Tag

An unknown or inactive tag preserved from imported data or older metadata. It is kept for review instead of being silently discarded.

## Alias

A remembered relationship between an older tag name and its current meaning.

## Sidecar

A `.registry.json` companion file that stores portable metadata beside a dataset.

## Working Copy

A protected local copy of an untrusted dataset that RoleThread can safely edit without changing the original source file.

## Trusted Dataset

A dataset RoleThread recognizes as carrying stable RoleThread identity metadata, such as dataset UUID and entry UUID information.

## Untrusted Dataset

A dataset that does not clearly carry RoleThread identity metadata. It may still be valid data, but RoleThread treats it carefully before writing to it.

## Clean Export

An export mode that removes RoleThread metadata from training records.

## Group Chat Mode

An entry editing mode that lets you assign characters to individual turns while keeping exported roles as standard `system`, `user`, and `assistant`.

## Character

A named person or persona stored in the Character registry for previews, Group Chat mode, and metadata.

## Character Mapping

Metadata that connects a character to a specific message turn in an entry.

## Dataset UUID

A stable identifier for a RoleThread-native dataset.

## Entry UUID

A stable identifier for a specific entry.

## Validation

The process of checking entries for structural issues, cleanup concerns, and quality-related diagnostics.

## Repair

A safe automatic or manual fix for a validation issue.

## Insights

The dataset quality and analysis page that reports scores, distributions, recommendations, and focused review links.

## Cloud Sync

Optional batch backup mirroring to a configured cloud sync folder. It is not live collaboration.

## Local Backup

A backup stored on the local machine before protected operations.

## DB Backup

A backup of the local database that stores tags, characters, prompt templates, settings, and related metadata.

## Portable Metadata

Metadata that can travel with a dataset, usually through a sidecar, without being inserted into clean training records.


