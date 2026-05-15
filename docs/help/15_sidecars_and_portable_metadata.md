# Sidecars and Portable Metadata

Sidecars are how LoreForge Lite lets metadata travel with a dataset without stuffing that metadata into the training records themselves.

They are intentional, readable companion files.

They are not mysterious hidden files.

## What a Sidecar Is

A sidecar is a registry metadata file stored next to a dataset.

It usually looks like this:

```text
my_dataset.jsonl
my_dataset.registry.json
```

The JSONL file contains the training entries.

The sidecar contains LoreForge metadata that helps preserve organization, identity, and editing context.

## Why Sidecars Exist

Training records should stay clean.

Most training tools expect entries built around `system`, `user`, and `assistant` messages. They do not need LoreForge's full registry metadata inside every record.

Sidecars let LoreForge keep useful metadata nearby without making clean export messy.

They support both goals:

- clean training data
- portable project context

## What Metadata Sidecars Store

Sidecars can store metadata such as:

- dataset identity
- tag categories
- active tags
- tag aliases
- archived/imported tag information
- character definitions
- character-to-turn mappings
- system prompt templates
- entry character mappings
- non-authoritative tag usage snapshots

The exact contents may depend on what the dataset uses.

## Training Records vs Metadata

The dataset JSONL is the training record.

The sidecar is the project context.

For example, a Group Chat entry may preview with character names, but the training messages still use standard roles. The sidecar is where the extra character metadata can travel.

This separation helps LoreForge preserve creative structure while keeping exported records compatible.

## Portable Metadata

If you move or share a dataset and want LoreForge metadata to move with it, keep the sidecar beside the JSONL file.

Together, the pair can preserve:

- how tags were organized
- which unknown tags were imported
- which characters existed
- which turns belonged to which characters
- which prompt templates were available

Without the sidecar, the JSONL entries can still be useful, but some LoreForge-specific context may be missing.

## Sidecars During Load

When you load a dataset, LoreForge looks for a matching sibling sidecar.

If it can safely read and trust the sidecar, it may import useful registry metadata.

If something looks wrong, LoreForge is conservative. It may load the dataset entries while skipping the sidecar metadata and showing a warning.

## Dataset UUID Safety

Modern LoreForge datasets have a dataset UUID. The sidecar can also carry that identity.

When both are present, LoreForge checks that they agree.

If the dataset UUID and sidecar UUID do not match, LoreForge does not trust that sidecar for the loaded dataset. This protects against accidentally pairing one dataset with another dataset's metadata.

The entries can still load. The questionable sidecar metadata is skipped.

## Sidecar Warnings

A sidecar warning is usually a caution message, not a disaster.

Common reasons include:

- the sidecar is missing
- the sidecar could not be parsed
- the sidecar schema is newer than this app version understands
- the dataset UUID does not match
- a tag or character already exists locally and was skipped instead of overwritten

LoreForge avoids silently trusting metadata when it cannot verify that metadata belongs.

## Clean Export

Clean export removes LoreForge metadata from the training records.

This is useful when you want a plain training file for another tool.

Clean export does not mean LoreForge's metadata was bad. It only means the exported training records should not include project management fields.

Normal exports can still write sidecar metadata alongside the JSONL so project context remains portable.

## Should You Edit Sidecars Manually?

Usually, no.

Sidecars are meant to be managed by LoreForge. Manual edits can break relationships between dataset identity, tags, characters, and mappings.

If you need to change tags, characters, prompts, or mappings, use the app pages designed for those systems.

## Practical Guidance

- Keep `.registry.json` files beside their matching `.jsonl` datasets.
- Move dataset and sidecar together when sharing or archiving.
- Do not copy a sidecar from one dataset onto another.
- Treat sidecar warnings as review prompts, not panic signals.
- Use clean export when another tool only needs the training records.

## Common Mistake

**Mistake:** Deleting the sidecar because it looks like extra clutter.

**Better mental model:** The JSONL is the training data. The sidecar is the portable LoreForge context. If you want to keep tags, characters, prompt templates, and mappings, keep both files together.

