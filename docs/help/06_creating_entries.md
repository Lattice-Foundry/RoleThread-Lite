# Creating Entries

Create Entry is where you write new training examples for the loaded dataset. It is designed for a steady writing flow: set the system prompt, write one or more user/assistant exchanges, add tags, preview the result, then save.

You do not need to make every entry perfect on the first pass. LoreForge Lite gives you editing, validation, search, duplicate, split, and join tools so you can refine entries over time.

## Before You Start

Create Entry works after a dataset is loaded.

If no dataset is loaded, go to **Manage Dataset** first and either:

- create a new dataset
- load an existing JSONL file
- load a working copy created by LoreForge

New entries are saved into the currently loaded dataset.

## The Basic Entry Shape

Most entries contain:

1. A `system` message that sets the context.
2. One or more `user` messages.
3. One or more `assistant` messages.

The user and assistant messages are written as exchange pairs. A single-turn entry has one user message and one assistant response. A multi-turn entry has multiple pairs under the same system prompt.

Example shape:

```json
{
  "messages": [
    {"role": "system", "content": "You are writing a grounded character scene."},
    {"role": "user", "content": "Ask about the locked door."},
    {"role": "assistant", "content": "Nicole studies the frame, then lowers her voice..."}
  ]
}
```

LoreForge handles the JSON structure for you. You write the content.

## System Prompt

The system prompt tells the training example what kind of response belongs in the entry.

Good system prompts are usually:

- specific enough to set the scene or style
- short enough to stay focused
- consistent with the entry content
- reusable when several entries share the same setup

You can write a custom prompt directly, or use **Load from library** to fill the field from a saved system prompt template. Loading from the library does not lock the field. You can still edit the prompt before saving.

If you write a prompt you expect to reuse, use **Save as template** to add it to the System Prompts library.

## Exchanges

Each exchange has a user side and an assistant side.

Use the planned exchange count to decide how many pairs you want in the entry. The save button stays disabled until the planned exchanges are complete and valid.

Use multiple exchanges when:

- the scene needs a short back-and-forth
- the assistant response depends on earlier user turns
- you want to train continuity within a focused moment

Avoid making one entry carry too many unrelated beats. If an entry grows into multiple scenes, the Split tool in Full Edit may be a better fit later.

## Tags

Tags are optional for saving, but they are strongly useful.

Tags help you:

- find entries later
- filter Manage Dataset and Edit Entries
- export selected slices of a dataset
- understand coverage in Insights
- keep related scenes or behaviors organized

Start simple. A few useful tags are better than a complicated registry you do not actually use.

## Validation While Writing

Create Entry shows a preview of the entry before saving. If the entry is valid, LoreForge tells you it looks valid.

The save button may be disabled when:

- planned exchanges are incomplete
- required message content is blank
- the entry has validation problems
- no dataset is loaded

When a button is disabled, read the small caption near it. It usually tells you what still needs to be finished.

## Entry Quality Mindset

Good training entries are not only valid JSON. They should also be useful examples.

Aim for:

- clear setup
- focused scene intent
- assistant responses with enough detail to teach style and behavior
- consistent tone within the entry
- no accidental refusal or meta-language unless that is truly part of the dataset
- no unrelated conversations stitched together

For many narrative datasets, assistant responses that are too short are less useful than responses that show the behavior you want the model to learn.

## Practical Workflow

A simple creation workflow:

1. Choose **Default** or **Group Chat** mode.
2. Write or load a system prompt.
3. Set the planned exchange count.
4. Fill each user/assistant exchange.
5. Add relevant tags.
6. Review the JSON preview.
7. Save the entry.
8. Run Validation after a batch of new entries.

## Common Mistake

**Mistake:** Trying to make one entry cover an entire long scene.

**Better approach:** Keep entries focused. If a conversation naturally has several distinct moments, consider multiple entries or use Full Edit to split it later.

## What Happens After Save

When an entry is saved, LoreForge assigns stable identity metadata such as an entry UUID, updates the dataset, refreshes sidecar metadata, and keeps the entry available for search, editing, validation, and export.

You can always return to the entry later through Manage Dataset or Edit Entries.

