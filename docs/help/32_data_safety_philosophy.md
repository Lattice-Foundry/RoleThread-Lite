# Data Safety Philosophy

RoleThread Lite's mutation model is built around preserving authored dataset files and adjacent metadata.

Entries, sidecars, tags, character mappings, backups, and exports are workflow state. Mutation services should preserve that state across failed operations, older metadata, and unreliable sync folders.

## Local-First by Default

RoleThread works from local files first.

Cloud folders can be useful as backup or sync targets, but they are not the preferred active working directory. Consumer sync tools can create file locks, partial uploads, timestamp churn, conflict copies, or unexpected restore behavior. RoleThread keeps the active source of truth local and publishes backup copies through staged workflows.

## Deterministic Mutations

Dataset mutations should be deterministic.

Before a service writes changed data, it should know:

- which dataset is being changed
- what proposed entries will be written
- whether validation passed
- whether a backup is needed
- which sidecar or metadata records must stay aligned
- what result should be reported to the caller

Mutation services should return structured operation results instead of relying on silent side effects.

## Fail-Closed Behavior

When a destructive operation cannot be classified as safe, it should fail closed.

Delete, overwrite, repair, merge, and rename behavior should be conservative by default. If the app cannot resolve an alias chain safely, validate proposed data, or determine the target path, the operation should preserve the current dataset state.

## Backup Before Write

Mutations that rewrite user datasets should create backups before changing the active file.

Backup-before-write protects edit flows, validation repairs, merges, tag lifecycle changes, and other multi-entry transformations.

## Atomic and Staged Writes

Where practical, RoleThread uses staged writes and atomic replace semantics rather than exposing partial final files.

For cloud sync, backup copies are staged under temporary names and published to the final destination only after the copy succeeds. This reduces the chance that OneDrive, Dropbox, Google Drive, iCloud, or another sync tool sees a half-written backup as the official copy.

The same principle applies broadly: prepare first, publish last.

## Validation Before Save

Validation should run before save when an operation can produce invalid data.

Validation should not silently rewrite entries. Repair flows should be explicit and report what changed.

## Preserve Unknown Metadata

Unknown metadata should not be discarded only because the current registry does not recognize it.

Unknown or orphan tags are preserved instead of silently thrown away. Imported tags can remain archived until the user decides whether to adopt, categorize, or ignore them. Sidecars preserve portable metadata so datasets can move between machines without losing workflow context.

Datasets may come from older versions, other tools, collaborators, or custom workflows.

## Rust-Inspired, Not Rust

RoleThread Lite is a Python application, not a Rust codebase.

Some of the safety model mirrors Rust-style engineering habits:

- make mutation paths explicit
- avoid silent destructive behavior
- prefer known states over ambiguous states
- preserve data when resolution is unsafe
- keep failure behavior visible
- make repair a deliberate workflow

This is about explicit mutation and conservative failure behavior, not Rust syntax.

## Practical Examples

Examples:

- dataset services create backups before rewriting files
- cloud sync publishes completed copies rather than partial destinations
- validation reports problems without silently mutating entries
- unknown imported tags are preserved for review
- sidecar metadata is kept aligned with dataset changes
- alias and lifecycle logic avoids infinite resolution loops
- destructive actions require explicit user intent

