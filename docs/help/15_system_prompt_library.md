# System Prompt Library

The System Prompt Library stores reusable system prompts so you do not have to rewrite the same setup over and over.

It is a practical writing tool, not a rule system. Loading a template fills the system prompt field, and then you can edit it for the specific entry.

## What a System Prompt Template Is

A **system prompt template** is a saved prompt you can reuse.

It can include:

- scene setup
- character instructions
- style guidance
- response expectations
- roleplay boundaries
- dataset-specific formatting guidance

Templates are useful when several entries share the same kind of setup.

## Creating Templates

You can create templates from the System Prompts page under Metadata.

A template usually has:

- a name
- prompt content
- an optional description

The name should help you recognize when to use it. The description can explain the intended situation or dataset style.

## Loading Templates Into Entries

Create Entry and Full Edit can load prompts from the library.

When you select a template:

- its content fills the system prompt field
- the entry still stores only the final prompt text
- you can edit the prompt before saving
- no permanent link is stored on the entry

This means templates are starting points, not locked references.

## Editing After Load

After loading a template, treat the prompt like normal entry content.

You can:

- adjust character names
- tighten the instruction
- add scene-specific context
- remove details that do not apply
- rewrite it completely

The saved entry keeps whatever text is in the system prompt field at save time.

## Saving Prompts From Entries

If you write a prompt in Create Entry or Full Edit and realize you will reuse it, save it as a template.

This is useful when:

- you find a strong scene setup
- a prompt works well for a recurring character dynamic
- you are building many entries with the same style
- you want consistent openings across a dataset section

## Templates Do Not Update Existing Entries

Changing a template does not automatically rewrite entries that were created from it.

This is intentional.

An entry should remain stable after you save it. If you want an older entry to use the updated wording, open the entry and update the system prompt directly.

## Relationship to Entry Structure

The system prompt is part of the entry. It sits before the user and assistant turns and describes how the example should be interpreted.

A good template can make entry creation faster, but the final entry still needs coherent user/assistant content.

Templates do not replace review, validation, or good writing judgment.

## Workflow Examples

### Reuse a Group Scene Setup

1. Create a template for a recurring group scene.
2. Load it in Create Entry.
3. Adjust any scene-specific details.
4. Use Group Chat mode to assign characters per turn.
5. Save the entry.

### Build a Dataset Section

1. Create a template for a training style.
2. Use it across several entries.
3. Vary the conversations while keeping the setup consistent.
4. Review Insights later for prompt concentration if too many entries use the same setup.

## Common Mistake

**Mistake:** Treating a template like a live link.

**Better mental model:** A template fills the field. Once saved, the entry owns its own prompt text.

## Practical Tip

Keep templates focused. If a prompt contains too many unrelated instructions, create a few smaller templates instead of one giant one.

