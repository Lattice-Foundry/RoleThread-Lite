# Editing Entries

Editing is where LoreForge Lite becomes a practical workshop instead of only a file viewer. You can make small corrections, reshape conversations, duplicate useful entries, and repair issues found by Validation or Insights.

The important idea: entries keep stable identity through edits. LoreForge uses entry UUIDs so filtering, searching, sidecars, character mappings, and metadata can stay tied to the right entry.

## Where Editing Happens

You can start editing from:

- **Manage Dataset**, using entry actions in the browser list.
- **Edit Entries**, using the dedicated editing browser.
- **Validation** or **Insights**, when they link you to entries that need review.

Manage Dataset is the primary operational workspace for most dataset work. It is where many users spend most of their time: browsing, filtering, searching, tagging, selecting, quick editing, duplicating, joining, deleting, and preparing entries for export.

Edit Entries is the deeper editing workspace. Use it when the job needs Full Edit, multi-turn restructuring, Group Chat refinement, detailed character mapping work, split operations, or a focused review pass.

## Quick Edit

Quick Edit is for small changes.

Use it when you want to:

- fix a typo
- adjust one message
- make a small content correction
- quickly inspect an entry without opening the full workspace

Quick Edit is not meant for larger structural edits.

## Full Edit

Full Edit is the full workspace for an entry.

Use it when you need to:

- edit the system prompt
- change multiple exchanges
- add or remove exchanges
- use Group Chat mode
- adjust character assignments
- save a prompt as a template
- split a long entry
- make careful changes after Validation or Insights

Full Edit gives you more control and more context.

## Duplicate Entry

The Duplicate action creates a copy of an existing entry with a fresh entry UUID.

This is useful when:

- an entry is a good template for another example
- you want to create a variation without rewriting the setup
- you are building a set of similar scenes with different turns or tags

The duplicate is a separate entry. Editing it will not change the original.

## Editing Filtered or Searched Results

You can edit entries while filters or search are active.

This is helpful when you are working through:

- untagged entries
- entries with validation issues
- entries from an Insights recommendation
- entries matching a text search
- entries under a specific tag

Because entries use stable UUIDs, LoreForge can keep track of the entry even if its position in the list changes after edits.

## Save Behavior

When you save an edit, LoreForge updates the dataset and refreshes related metadata.

Protected operations create backups before writing. This makes editing recoverable if you later decide a change was wrong or something goes sideways.

Normal LoreForge edit forms guard against most structural invalid states before save. After imported-data cleanup, merge review, large edit batches, split/join work, or manual repair, it is still a good habit to run Validation again.

## Validation After Editing

Editing can fix validation issues. In normal LoreForge workflows, the app tries to prevent incomplete structure before save, but Validation is still useful for broader review and imported-data cleanup.

Run Validation after:

- a batch of edits
- split or join operations
- imported dataset cleanup
- changing Group Chat assignments
- repairing malformed entries

Validation is especially useful before export.

## Split and Join Relationship

Editing, splitting, and joining are related tools.

Use **split** when one entry has become too long or contains multiple distinct moments.

Use **join** when several small entries belong together as one coherent multi-turn conversation.

You do not need to decide perfectly up front. It is normal to create or import entries first, then restructure them once you can see the dataset shape.

## When to Use Each Tool

Use **Quick Edit** when the change is small.

Use **Full Edit** when the structure matters.

Use **Duplicate** when an entry is a good starting point for another one.

Use **Split** when an entry contains too much.

Use **Join** when related entries are too fragmented.

## Practical Tip

If you are cleaning a dataset, work in passes:

1. Filter or search for a problem area.
2. Quick Edit easy fixes.
3. Full Edit structural fixes.
4. Use Manage Dataset to retag, duplicate, join, or prepare a subset if needed.
5. Run Validation for a broader review pass.
6. Export only after the dataset feels stable.
