# Data Safety Philosophy

RoleThread Lite treats user datasets as important authored work product.

The app is local-first because training data is not disposable. Entries, sidecars, tags, character mappings, backups, and exports represent creative labor and workflow history. RoleThread should preserve that work even when an operation fails, a dataset contains older metadata, or a cloud folder behaves unpredictably.

## Local-First by Default

RoleThread works from local files first.

Cloud folders can be useful as backup or sync targets, but they are not the preferred active working directory. Consumer sync tools can create file locks, partial uploads, timestamp churn, conflict copies, or unexpected restore behavior. RoleThread's job is to keep the local source of truth clear and then publish safe backup copies when requested.

## Deterministic Mutations

Dataset mutations should be explicit and predictable.

Before a service writes changed data, it should know:

- which dataset is being changed
- what proposed entries will be written
- whether validation passed
- whether a backup is needed
- which sidecar or metadata records must stay aligned
- what result should be reported to the caller

This is why mutation services prefer structured operation results instead of silent side effects.

## Fail-Closed Behavior

When RoleThread cannot prove that a destructive operation is safe, it should stop rather than guess.

That does not mean every warning blocks every workflow. It means delete, overwrite, repair, merge, and rename behavior should be conservative by default. If the app cannot resolve an alias chain safely, cannot validate proposed data, or cannot determine the right target path, preserving the user's current data is more important than completing the operation.

## Backup Before Write

Mutations that rewrite user datasets should create backups before changing the active file.

This protects against mistakes in edit flows, unexpected crashes, invalid input, and bugs in transformation logic. Backup-before-write is one of RoleThread's core safety patterns because it keeps recovery possible even when a workflow needs to change many entries at once.

## Atomic and Staged Writes

Where practical, RoleThread prefers staged writes over exposing partial final files.

For cloud sync, backup copies are staged under temporary names and then published to the final destination after the copy succeeds. This reduces the chance that OneDrive, Dropbox, Google Drive, iCloud, or another sync tool sees a half-written backup as the official copy.

The same principle applies broadly: prepare first, publish last.

## Validation Before Save

Validation should happen before save when an operation can produce invalid data.

RoleThread validation is not meant to secretly rewrite entries. It is meant to tell the app and the user what is wrong, what is repairable, and what should be reviewed. Repair flows should be explicit so users understand what changed.

## Preserve Unknown Metadata

RoleThread should not discard metadata just because it does not recognize it yet.

Unknown or orphan tags are preserved instead of silently thrown away. Imported tags can remain archived until the user decides whether to adopt, categorize, or ignore them. Sidecars preserve portable metadata so datasets can move between machines without losing workflow context.

This matters because datasets may come from older versions, other tools, collaborators, or custom workflows.

## Rust-Inspired, Not Rust

RoleThread Lite is a Python application, not a Rust codebase.

Some of the safety philosophy is Rust-inspired in a practical sense:

- make mutation paths explicit
- avoid silent destructive behavior
- prefer known states over ambiguous states
- preserve data when resolution is unsafe
- keep failure behavior visible
- make repair a deliberate workflow

The point is not to imitate Rust syntax. The point is to bring the same respect for data integrity into a local dataset tool.

## Practical Examples

RoleThread applies this philosophy in ordinary workflows:

- dataset services create backups before rewriting files
- cloud sync publishes completed copies rather than partial destinations
- validation reports problems without silently mutating entries
- unknown imported tags are preserved for review
- sidecar metadata is kept aligned with dataset changes
- alias and lifecycle logic avoids infinite resolution loops
- destructive actions require explicit user intent

The result should feel boring in the best way: user data survives normal mistakes, edge cases, and interrupted workflows.

