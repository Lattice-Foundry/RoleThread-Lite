# Default Mode vs Group Chat

LoreForge Lite supports two ways to write entries:

- **Default** mode for standard two-role conversation examples.
- **Group Chat** mode for scenes where you want to track which character speaks on each turn.

Both modes save training data with standard roles: `system`, `user`, and `assistant`.

That part is important.

## Default Mode

Default mode is the simplest writing flow.

You write:

- one system prompt
- one or more user messages
- one or more assistant messages

The display names shown in previews come from Settings. They are cosmetic. They help the entry read naturally while you write, but they do not change the JSONL roles.

Use Default mode when:

- the entry is a normal user/assistant example
- the speaker identity is obvious from context
- you do not need per-turn character tracking
- you want the fastest writing flow

## Group Chat Mode

Group Chat mode adds character selection to each turn.

Each user and assistant turn can be assigned to a character from the Character registry. You can also create a new character inline while writing.

Use Group Chat mode when:

- a scene has multiple named characters
- the assistant side may speak as different characters across examples
- you want previews to show actual character names
- you want character metadata to travel with the dataset sidecar
- you are building group chat or roleplay training examples from scratch

## Character Mapping

A **character mapping** connects a message turn to a character.

In plain English, it means:

> "This turn belongs to this character."

LoreForge stores that relationship as metadata tied to the entry UUID and turn position. The entry content stays clean and compatible with normal training formats.

## Roles Stay Standard

Group Chat mode does not turn JSONL roles into character names.

Even if a preview shows:

```text
Scott:
Nicole:
Kai:
```

the exported training roles remain:

```text
system
user
assistant
```

Character names are preserved as metadata through LoreForge and its sidecar system.

This design keeps the dataset compatible with normal ChatML-style training while still letting you organize group scenes clearly inside LoreForge.

## Why LoreForge Keeps Standard Roles

Training tools generally expect standard message roles. If a dataset uses custom role names directly in the JSONL, many tools either reject the file or interpret it incorrectly.

LoreForge separates two concerns:

- **Training roles**: the standard roles required by the dataset format.
- **Character identity**: metadata that helps you write, preview, organize, and round-trip group scenes.

That separation gives you better compatibility without losing creative structure.

## Switching From Default to Group Chat

When you switch from Default to Group Chat:

- existing message content is preserved
- character dropdowns appear for each turn
- the first exchange may use your Settings display names if matching characters exist
- new exchanges inherit character choices from the previous exchange

You can then adjust characters per turn.

## Switching From Group Chat to Default

When you switch back to Default:

- message content is preserved
- character dropdowns are hidden
- character assignment state for that editor is cleared

If you save in Default mode after opening an entry that had mappings, LoreForge clears those mappings for that entry. That keeps the saved metadata consistent with the mode you chose.

## Full Edit Behavior

If you open an existing entry in Full Edit and it already has character mappings, LoreForge opens it in Group Chat mode so the assignments are visible.

If an entry has no mappings, it opens in Default mode.

## Validation and Group Chat

Validation still checks the actual JSONL structure. Group Chat metadata does not make custom role names valid in the exported messages.

If imported data contains custom speaker names as roles, LoreForge may help detect and map them into character metadata while returning the saved entry structure to standard roles.

## Common Mistake

**Mistake:** Expecting Group Chat mode to export roles like `Nicole` or `Kai`.

**Better mental model:** Group Chat mode preserves character identity as metadata. Clean training records still use `system`, `user`, and `assistant`.

## Practical Tip

Use Group Chat mode when character identity matters to how you review or maintain the dataset. Use Default mode when the example is already clear as a normal user/assistant exchange.

