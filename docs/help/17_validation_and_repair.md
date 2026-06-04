# Validation and Repair

Validation helps you find dataset problems before they become training problems.

It is not there to judge your writing. It is there to make structure, metadata, and common cleanup issues visible so you can decide what to fix.

Entries created and edited through normal RoleThread workflows are guarded against most structural invalid states before save. Validation is most valuable as an audit, cleanup, and final-review tool, especially for imported datasets, external edits, merge outputs, and large review passes.

## What Validation Checks

Validation looks for issues such as:

- malformed entry structure
- missing `messages`
- missing or empty message content
- role problems
- duplicate system messages
- incomplete user/assistant exchange structure
- formatting or code leakage
- AI refusal or meta-language in assistant responses
- inactive character references in system prompts
- entries that may be good split candidates

Some checks are format-focused. Others are quality or cleanup signals.

## Diagnostics

A diagnostic is a specific issue Validation found.

Diagnostics usually include:

- what was found
- how serious it is
- which entries are affected
- whether an automatic repair is available

Warnings and info messages do not always mean the entry is broken. They often mean "review this before export."

## Automatic vs Manual Fixes

Some issues can be repaired automatically.

Automatic fixes are best for safe structural cleanup, such as normalizing fields or repairing predictable format problems.

Other issues need human judgment.

Manual review is better for:

- rewriting unclear content
- removing AI refusal language
- deciding whether markdown is intentional
- resolving character references
- splitting or joining entries
- changing system prompts

RoleThread will not rewrite creative content without you choosing that action.

## Malformed Structure

Malformed structure means the entry does not look like a usable ChatML-style record.

Examples:

- messages are missing
- a message is not an object
- a message has no role
- a message has no content
- roles are not in an expected shape

These problems matter because training tools expect consistent structure.

## Duplicate System Messages

A normal entry should have one system prompt at the beginning.

Validation can flag entries with multiple system messages. This often happens when conversations were concatenated or manually edited.

If an entry has extra system messages, review them. You may want to merge the useful instruction text into the first system prompt, then remove the extras.

## Role Issues

Training data should use standard roles:

- `system`
- `user`
- `assistant`

Imported datasets may contain custom speaker names as roles. RoleThread can help preserve the speaker meaning as character metadata while keeping the saved training roles standard.

## Formatting and Meta-Language

Validation can flag assistant responses that contain patterns often found in unwanted generated data.

Examples:

- "as an AI language model"
- "I cannot assist"
- markdown/code artifacts
- HTML fragments
- JSON-looking leakage

These are not always wrong, but they are worth reviewing. In roleplay or narrative datasets, a single refusal-style response can teach behavior you did not intend.

## Character-Related Validation

Validation can warn when inactive characters are referenced in system prompts.

This does not block you. It simply tells you that an entry may still mention a character you removed or deactivated.

Use the focused entry link to review those entries in Manage Dataset.

## Imported Dataset Cleanup

Imported datasets often need a validation pass.

They may have:

- inconsistent roles
- missing system prompts
- unknown tags
- custom speaker labels
- long conversations saved as one entry
- formatting artifacts

This is normal. Validation gives you a map for cleanup.

If you want to learn Validation safely, create a small scratch dataset or load
a copy of outside JSONL data. RoleThread may create a protected working copy for
untrusted imports, which lets you review warnings, diagnostics, and repair
workflows without changing the original source file.

## Normal RoleThread Workflows

If you create entries inside RoleThread, you usually do not need to treat Validation as an emergency repair loop.

RoleThread forms check required structure before saving. That means normal entry creation and editing should usually produce structurally safe records.

Validation still matters because it sees the whole dataset at once. It can find patterns that are easy to miss while writing:

- repeated short responses
- inactive character references
- split candidates
- duplicate system messages from imported material
- formatting artifacts
- metadata gaps

Use it as a review pass, not as proof that every normal save is risky.

## Repair Workflow

A practical repair workflow:

1. Load the dataset, especially if it came from outside RoleThread.
2. Open Validation.
3. Review issue groups.
4. Apply safe automatic fixes first.
5. Use focused links to inspect manual issues.
6. Use Manage Dataset for quick cleanup and Full Edit for deeper repairs.
7. Run Validation again.
8. Export only when the remaining issues are understood.

## When to Run Validation

Run Validation after:

- loading an imported dataset
- externally or manually editing dataset files
- large cleanup passes
- using split or join
- merging datasets
- reviewing imported ShareGPT data
- applying automatic repair
- preparing for export

## Common Mistake

**Mistake:** Treating every warning as a failure.

**Better mental model:** Validation is guidance. Some warnings are cleanup suggestions. You decide what matters for your dataset.

## Practical Tip

Fix structural issues before content-quality issues. A clean structure makes every later review pass easier.
