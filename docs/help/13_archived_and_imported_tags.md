# Archived and Imported Tags

Archived/imported tags are one of LoreForge Lite's safety systems.

They exist because external datasets often contain tags that do not match your current active tag registry. Instead of dropping those tags, LoreForge preserves them so you can decide what to do.

Archived/imported tags are not errors.

## What Archived/Imported Tags Are

An **archived/imported tag** is a tag LoreForge found on an entry but could not treat as a normal active tag.

This can happen when:

- you load a dataset from another tool
- a sidecar contains tags not present in your local registry
- a tag existed in an older project but is not active now
- a dataset was manually edited
- a tag was renamed or replaced over time

LoreForge keeps that tag visible instead of discarding it.

## Why LoreForge Creates Them

Unknown tags may still be meaningful.

If an imported entry has a tag like `slow-burn-confession`, LoreForge should not throw it away just because your current registry does not know it yet.

Preserving the tag lets you choose:

- adopt it into an active category
- rename it into your preferred vocabulary
- leave it archived for reference
- remove or replace it later

That choice stays with you.

## Unknown Tag Preservation

When LoreForge encounters unknown tags, it handles them conservatively.

It avoids:

- silently deleting tags
- pretending unknown tags are already active
- overwriting your registry
- forcing imported vocabulary into the wrong category

Instead, it keeps the unknown tag as archived/imported metadata until you make a decision.

## Adopting Imported Tags

If an archived/imported tag is useful, assign it to an active category.

Once adopted, it becomes part of your normal tag workflow and can appear in selectors, filters, and organization tools.

A practical adoption workflow:

1. Open Tag Management.
2. Review archived/imported tags.
3. Choose tags that are meaningful.
4. Assign each useful tag to a category.
5. Leave noisy or unclear tags archived until you know what they mean.

## Safe Handling of External Datasets

External datasets can be messy.

They may contain:

- tags from another app
- inconsistent spelling
- old category names
- one-off cleanup labels
- tags that were useful to someone else but not to you

Archived/imported tags let you inspect that material safely.

LoreForge does not require you to clean everything immediately. You can load the dataset, preserve its meaning, then organize it when you are ready.

## How Archived Tags Affect Workflows

Archived/imported tags are preserved, but they are not the same as active tags.

They may not behave like active tags in every selector or workflow until you adopt them.

Use them as a review queue:

- "Do I want this tag?"
- "Should this be merged into an existing tag?"
- "Does this tag reveal something useful about the source dataset?"
- "Can I ignore this safely?"

## Why This Exists

The goal is not to make tags complicated.

The goal is to avoid data loss.

When a dataset arrives with metadata you did not create, LoreForge treats it carefully. It keeps the information visible and lets you decide how much of it belongs in your active registry.

## Common Mistake

**Mistake:** Seeing archived/imported tags and thinking the dataset failed to load.

**Better mental model:** LoreForge loaded the tags and protected them from being lost. Archived/imported means "review this when convenient," not "something broke."

## Practical Tip

Do not adopt every imported tag automatically. Keep the ones that support your workflow and leave the rest archived until they prove useful.

