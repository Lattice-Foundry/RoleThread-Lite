# Character Registry and Character Mappings

The Character registry helps LoreForge Lite preserve who is speaking in creator workflows without changing the training roles in the JSONL.

Characters are metadata. They help you write, preview, organize, edit, and round-trip group scenes.

They do not replace the standard `system`, `user`, and `assistant` roles.

## Character Registry

The Character registry is the list of characters LoreForge knows about.

A character can have:

- a display name
- an optional description
- active or inactive status

The display name is what you see in previews and character dropdowns.

Use the registry when you want consistent character names across entries instead of typing names manually into every scene.

## Active and Inactive Characters

An **active character** appears in normal Group Chat dropdowns.

An **inactive character** is kept for history and compatibility, but is no longer offered as a normal new selection.

Inactive characters are useful when:

- a character is no longer part of the dataset
- an imported dataset references an older character
- you want to preserve existing mappings without encouraging new use

Deactivating a character does not rewrite your entry text.

## Character Display Names

Display names are for humans.

They make previews and editors easier to read:

```text
User:
Assistant:
Kai:
```

The saved training messages still use standard roles:

```text
user
assistant
```

This keeps your dataset compatible while letting LoreForge show character-aware previews.

## Character Mappings

A **character mapping** connects a character to a specific message turn.

For example:

- exchange 1 user turn belongs to User
- exchange 1 assistant turn belongs to Assistant
- exchange 2 assistant turn belongs to Kai

LoreForge stores those assignments as metadata tied to the entry UUID and turn position.

## How Mappings Survive Edits

Character mappings are designed to survive normal editing.

When you open an entry in Full Edit:

- entries with mappings open in Group Chat mode
- dropdowns show the existing character assignments
- content edits preserve assignments unless you change them
- saving refreshes the mappings

If you switch an entry from Group Chat mode back to Default and save, LoreForge clears the mappings for that entry. That keeps the metadata honest.

## Split, Join, and Merge

LoreForge tries to preserve character mappings through structural changes.

When you split an entry:

- character mappings move with the turns they belong to
- turn positions are reindexed for the new entries
- each resulting entry gets its own stable identity

When you join entries:

- mappings from the selected entries are combined
- turn positions are reindexed in the joined conversation
- the joined entry receives a fresh entry UUID

When datasets are merged, mappings are preserved only for entries that survive the merge. LoreForge avoids creating orphan mappings for discarded duplicate entries.

## Sidecars and Characters

Character definitions and character mappings can travel through sidecars.

That means a dataset can carry:

- character names
- character descriptions
- per-turn assignments
- related registry metadata

without putting that metadata directly into the clean training messages.

Keep the sidecar near the dataset when moving or sharing files if you want character metadata to travel with it.

## Imported or Unknown Characters

Imported datasets can contain character-like information in different forms.

LoreForge may help identify custom speaker names or imported character metadata and preserve them as character definitions or mappings where possible.

If a mapping references a character that is missing or inactive, LoreForge should handle it safely. You may see an unassigned state or a warning rather than a crash.

## Workflow Examples

### Create a Group Scene

1. Add characters in Character Management.
2. Open Create Entry.
3. Choose Group Chat mode.
4. Assign characters to each turn.
5. Save the entry.
6. Review the character-aware preview.

### Clean Up an Imported Dataset

1. Load the dataset.
2. Review Validation messages about roles or characters.
3. Create or adopt character definitions as needed.
4. Open entries in Full Edit to review mappings.
5. Save corrected mappings.

## Common Mistake

**Mistake:** Thinking character mappings are the same as role names.

**Better mental model:** Roles are the training format. Character mappings are LoreForge metadata that tells you who the role represents in a specific turn.

## Practical Tip

Use character mappings when they help you maintain the dataset. If an entry is already clear as a simple user/assistant example, Default mode is still perfectly valid.

