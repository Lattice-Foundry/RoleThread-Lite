# Tags, Categories, and Tag Lifecycle

Tags are how LoreForge Lite helps you organize a dataset without changing the conversation text.

A tag is metadata. It helps you find, filter, export, and understand entries. It does not become part of the `system`, `user`, or `assistant` messages unless you write it into the messages yourself.

## What Tags Are For

Use tags to mark how an entry functions in your dataset.

Examples:

- behavior pattern
- interaction structure
- writing style
- source or provenance
- review status
- operational cleanup state

Tags become useful everywhere:

- **Manage Dataset** filtering
- **Deep Edit** filtering
- selected or filtered export
- Insights metadata coverage
- bulk organization workflows
- reviewing untagged entries

## Categories

Categories group related tags.

For example, you might have categories such as:

- Behavior
- Interaction
- Style
- Source
- Status

Categories keep a growing registry readable. They also make it easier to decide where a new tag belongs.

## Built-In Tags

LoreForge Lite includes a small built-in taxonomy for common conversational dataset workflows.

The V1 built-in categories are:

- **Behavior**: conversational behavior and instruction-following patterns.
- **Interaction**: the shape of the exchange, such as greetings, Q&A, correction, or task completion.
- **Style**: response style, density, and presentation.
- **Source**: where the entry came from or how it was produced.
- **Status**: operational review state.

Built-in tags are locked to keep them consistent across datasets. This matters because built-in tags may be used by validation, organization, or future workflows.

You can use built-in tags, but you should not need to rename or delete them.

## Custom Tags

Custom tags are tags you create for your own dataset workflow.

You can use them for anything that helps you work:

- `slow-burn`
- `needs-review`
- `medical-scene`
- `combat-training`
- `high-emotion`

Custom tags are the right place for domain, topic, genre, character, project, or niche workflow vocabulary. The bundled defaults stay broad on purpose.

Custom tags can be edited, renamed, or deleted.

## Active Tags

An **active tag** is available for normal use.

Active tags appear in:

- tag selectors
- filters
- entry metadata
- export selection workflows
- Insights summaries

If you are actively using a tag, it should usually live in a category and remain active.

## Renaming Tags

Renaming a tag changes how it appears going forward, but LoreForge also preserves alias information so older tag references can still be understood.

This matters when:

- a tag name was misspelled
- your terminology changed
- an imported dataset used a different name
- several older tags should point to one cleaner tag

LoreForge tracks this kind of history intentionally. It avoids silently losing meaning when names change.

## Deleting Tags

Deleting a custom active tag removes it from normal active use.

Before deleting, think about whether the tag is:

- truly no longer needed
- attached to entries you still care about
- better renamed or merged into another tag
- useful as a review marker

Deleting built-in tags is not allowed because those tags are part of the shared LoreForge vocabulary.

## Aliases and Tag Lifecycle

An **alias** is a remembered relationship between an older tag name and its current meaning.

You do not need to manage aliases directly for normal work. They are part of how LoreForge keeps tag history stable.

At a high level, tag lifecycle means:

- tags can be created
- tags can be renamed
- imported tags can be adopted
- old names can resolve to current names
- unknown tags are preserved instead of thrown away

That is why LoreForge can be conservative with metadata while still letting you clean it up over time.

## Why Stable Tag Organization Matters

Stable tags make the rest of the app more useful.

They improve:

- search and filtering
- export slices
- metadata completeness
- Insights quality scoring
- cleanup passes
- collaboration with future versions of LoreForge

You do not need a perfect taxonomy. You only need tags that mean something to you and stay reasonably consistent.

## Practical Workflow

A simple tag workflow:

1. Create a few categories.
2. Add custom tags only when you know you will use them.
3. Tag entries during creation or cleanup.
4. Use Manage Dataset filters to review tag groups.
5. Rename tags when terminology improves.
6. Adopt archived/imported tags when they are useful.

## Common Mistake

**Mistake:** Treating tags as conversation content.

**Better mental model:** Tags are organizational metadata. They help LoreForge manage the dataset, but clean training exports can remove LoreForge metadata from the records.

## Practical Tip

Start with fewer tags than you think you need. Add more when a real workflow asks for them.

