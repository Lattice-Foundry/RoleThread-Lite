# Loading Datasets and Working Copies

Loading is one of the places where RoleThread Lite is deliberately careful. The app tries to protect original source files, preserve useful metadata, and make imported data safe to edit.

The most important idea is simple:

**If a dataset did not clearly come from RoleThread Lite, RoleThread may create a protected working copy before modifying it.**

That is intentional.

## Included Example Datasets

RoleThread Lite includes three curated example datasets intended for safe exploration.

One example dataset may load automatically on first launch. The examples are practical reference material, not hidden defaults or disposable samples.

They are meant to show different parts of the workflow, such as:

- clean native dataset organization
- imported cleanup and validation review
- advanced Group Chat and character mapping workflows

You can inspect, edit, duplicate, validate, merge, export, and search these datasets like normal loaded datasets. If you want to keep an original example untouched, duplicate or export a copy before experimenting heavily.

## Trusted and Untrusted Datasets

RoleThread Lite treats datasets differently depending on whether they carry a complete RoleThread-native identity.

A **trusted dataset** is a dataset previously saved by RoleThread Lite with stable metadata such as entry UUIDs and a shared dataset UUID.

An **untrusted dataset** is any dataset that does not clearly carry that identity. It may still be perfectly valid data. "Untrusted" does not mean bad. It only means RoleThread should be careful before writing back to it.

Examples of untrusted data include:

- files exported from another tool
- ShareGPT datasets
- manually edited JSONL
- older RoleThread files from before current metadata existed
- mixed or partial metadata files

## Why Working Copies Exist

Working copies protect your original files.

When you load an untrusted dataset from outside the default training data area, RoleThread copies it into its local training data folder and works on that copy. The original file is left alone.

This prevents a common problem: opening an outside dataset, clicking save, and accidentally changing the only original copy.

Working copies are not a hidden trick or a temporary hack. They are a safety feature.

## What Happens During Load

When you load a dataset, RoleThread may:

1. Read the file.
2. Detect whether it is ChatML, ShareGPT, or another supported JSON shape.
3. Convert ShareGPT records into ChatML-style entries.
4. Normalize safe basics such as roles, whitespace, and tag shape.
5. Check whether the dataset is trusted.
6. Create a working copy if the dataset is untrusted and should not be edited in place.
7. Look for a sibling sidecar file.
8. Import safe registry metadata from the sidecar when it matches the dataset.
9. Preserve unknown tags as archived/imported tags instead of throwing them away.
10. Show warnings or summaries when something needs attention.

You do not need to run these steps manually. The load summary tells you what happened.

## Where Working Copies Go

Working copies are stored under the configured dataset folder, usually inside `training_data`.

RoleThread uses a folder-per-dataset layout, for example:

```text
training_data/
  my_dataset/
    my_dataset.jsonl
    my_dataset.registry.json
```

If a folder name already exists, RoleThread chooses a non-colliding copy name rather than overwriting the existing folder.

## Sidecars During Load

A **sidecar** is a registry metadata file stored beside the dataset. It usually has a name like:

```text
my_dataset.registry.json
```

Sidecars can preserve:

- tag categories
- tags and aliases
- archived/imported tag information
- character definitions
- character-to-turn mappings
- system prompt templates
- dataset identity information

Sidecars let metadata travel with a dataset without forcing that metadata into clean training records.

## Sidecar Warnings

If RoleThread shows a sidecar warning, it is usually being cautious.

Examples:

- The sidecar file could not be read.
- The sidecar schema is newer than this version of RoleThread understands.
- The sidecar dataset UUID does not match the loaded dataset.
- Some registry metadata already exists locally and was skipped instead of overwritten.

A sidecar warning does not always mean the dataset itself failed to load. It often means RoleThread loaded the entries but refused to trust questionable metadata.

## Trusted Does Not Mean Perfect

A trusted dataset can still contain content issues. It only means RoleThread recognizes the dataset identity and can safely preserve entry identity across edits.

You should still use:

- Validation
- Insights
- Search
- manual review

## Practical Guidance

- Let RoleThread create working copies when it wants to. That is the safe path.
- Keep source datasets somewhere separate if they are originals you do not want changed.
- Use the loaded path shown in Manage Dataset to see which file you are actually editing.
- Keep `.registry.json` sidecars near their matching `.jsonl` files when moving datasets.
- Do not manually copy a sidecar from one dataset onto another unless you understand the metadata relationship.

## Common Mistake

**Mistake:** Loading an outside dataset, then expecting RoleThread to edit that original file directly.

**Better mental model:** RoleThread protects outside/untrusted files by creating a working copy. You edit the working copy. If you want a final file somewhere else, use Export.

