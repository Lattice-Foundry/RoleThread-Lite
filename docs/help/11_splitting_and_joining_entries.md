# Splitting and Joining Entries

Split and join tools help you reshape a dataset after you can see how the entries actually read.

They are useful because good training examples need structure. Entries that are too long can become unfocused. Entries that are too tiny can lose context.

## Why Structure Matters

A useful entry usually teaches one coherent pattern.

That pattern might be:

- a complete exchange
- a short scene beat
- a specific response style
- a focused multi-turn interaction
- a character behavior under a clear setup

When an entry contains several unrelated moments, the model gets a muddy example. When related turns are split across disconnected entries, the model may lose continuity.

Splitting and joining help you find the middle ground.

## When to Split

Consider splitting an entry when:

- it has 8 or more exchanges
- it contains multiple scene beats
- the topic changes halfway through
- assistant responses become very long across the entry
- Insights or Validation marks it as a split candidate
- one part is good training data and another part needs separate review

Splitting is especially useful for imported datasets where long conversations were saved as one record.

## How Split Works

Split happens in **Full Edit**.

When an entry has enough exchanges to split, RoleThread shows centered split buttons between exchange groups, such as:

```text
Split @ Exchange 3
```

Clicking a split button immediately separates the earlier portion into a new entry and keeps you working on the remaining lower portion.

The split keeps:

- the system prompt on both entries
- the original tags
- character mappings, reindexed for each resulting entry
- clean standard message roles

The new entry receives a fresh entry UUID.

RoleThread creates a backup before applying the split.

## Split Examples

### Split a Long Entry

If exchanges 1-4 are an introduction and exchanges 5-9 are a conflict, split at the point where the second beat begins. You now have two focused training examples instead of one oversized entry.

### Split Off a Good Opening

If the first part of an imported entry is clean but the later part needs heavy editing, split off the clean section first. Then edit the remaining section without risking the good portion.

## When to Join

Consider joining entries when:

- several tiny entries belong to the same conversation
- a scene was split too aggressively
- entries share the same system prompt and should train continuity
- you want one multi-turn example instead of isolated turns

Joining is best when the entries naturally belong together.

## How Join Works

Join happens in **Manage Dataset**.

Select two or more entries, then use **Join Selected**.

RoleThread joins entries in the current display order. The joined entry uses:

- the system prompt from the first selected entry
- all non-system turns from the selected entries
- a union of the selected entries' tags
- character mappings reindexed into the new message order
- a fresh entry UUID

If system prompts differ, RoleThread warns you but can still proceed using the first prompt.

RoleThread creates a backup before applying the join.

## Join Examples

### Join Related Single-Turn Entries

If three entries are really one short conversation split into separate examples, join them into one multi-turn entry so the response pattern has context.

### Join Before Editing

If you know several entries belong together but need cleanup, join them first, then open the result in Full Edit.

## Preserving Training Quality

Use split and join intentionally.

A good split should create entries that still make sense by themselves.

A good join should create one conversation that reads naturally from top to bottom.

After either operation, review:

- system prompt fit
- turn order
- tags
- character assignments
- validation results

## Practical Tip

Run Validation after restructuring. Split and join are safe operations with backups, but they can change the shape of the training examples enough that a second review is worth it.

## Common Mistake

**Mistake:** Splitting only because an entry looks long.

**Better approach:** Split where the conversation naturally changes focus. Length is a signal, but coherence is the real goal.

## Related Articles

- **Creating Entries**
- **Deep Edit**
- **Validation and Repair**


