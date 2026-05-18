# Merging Datasets

Merge lets you combine datasets into a new output dataset while preserving as much safe metadata as possible.

It is designed to be conservative. Source datasets are not silently overwritten.

## When to Merge

Use merge when you want to combine:

- related dataset files
- cleaned subsets
- work from different sessions
- imported data and native RoleThread data
- separate scene or tag groups

If you only need to export a filtered slice, use Export instead. Merge is for creating a new combined dataset.

## Merge Workflow

A normal merge workflow:

1. Choose the source dataset files.
2. Choose the output path.
3. Decide whether to shuffle the merged entries.
4. Run the merge.
5. Review the output dataset.
6. Run Validation on the merge output.
7. Use Insights to check structure, metadata, and duplicates.

Validation after merge is mostly a review and cleanup step. Merge is designed to preserve safe structure and metadata, but source datasets may bring in older formats, imported tags, duplicate content, or sidecar conflicts that deserve a pass.

## New Output Identity

A merged dataset receives a fresh dataset UUID.

This matters because the merge output is a new dataset, even when it was built from existing sources.

Entries that survive the merge keep stable entry identity where appropriate, but the merged dataset itself gets its own identity.

This prevents the output from pretending to be one of the sources.

## Duplicate Handling

Merge uses deterministic duplicate handling.

When entries are considered duplicates, the first matching content wins for the saved entry content and entry UUID.

This means merge results are predictable. Source order matters.

## First-Wins Content Policy

First-wins means the first duplicate entry keeps the canonical content.

Later duplicates do not replace the survivor's message text or UUID. This avoids unstable merge results where later files unexpectedly rewrite earlier entries.

If you want a later version to win, place that dataset earlier in the merge order or edit the output after merging.

## Tag Merging

Duplicate entries may carry different tags.

RoleThread preserves useful organization by merging and deduplicating tags from duplicate entries into the surviving entry where safe.

This avoids losing metadata just because the content was deduplicated.

## Sidecar Import During Merge

Merge can inspect sibling sidecars near source datasets.

Safe metadata may be imported, including:

- tag categories
- tags and aliases
- archived/imported tag metadata
- character definitions
- character mappings
- system prompt templates

Conflicts are handled conservatively. RoleThread avoids overwriting existing registry meaning without a clear reason.

## Character Mapping Preservation

Character mappings are preserved only for entries that survive the merge.

If a duplicate entry is discarded, its mappings are not copied as orphan metadata. If tags from that duplicate are merged into the survivor, the entry content and character mappings still follow the surviving entry.

This keeps mappings tied to real entries.

## Source Dataset Safety

Merge writes a new output dataset.

It does not silently overwrite source datasets. You should still choose your output path carefully, but the merge workflow is built around producing a separate result.

## After Merge

After a merge, run:

- Validation to catch structural or imported-data issues
- Insights to inspect quality, depth, duplication, and metadata coverage
- Manage Dataset filters to review imported tags or untagged entries

## Common Mistake

**Mistake:** Assuming merge edits the source datasets.

**Better mental model:** Merge creates a new output dataset with its own dataset UUID. The sources are inputs, not the final working file.

## Practical Tip

For predictable duplicate handling, put your preferred source file first.

## Related Articles

- **Loading Datasets and Working Copies**
- **Exporting Datasets**
- **Validation and Repair**
- **Dataset Scaling and Maintenance**

