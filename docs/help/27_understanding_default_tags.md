# Understanding Default Tags

RoleThread Lite includes a small default tag taxonomy so a new dataset starts with useful, shared vocabulary.

The defaults are designed for conversational dataset engineering. They focus on interaction structure, assistant behavior, writing style, provenance, and review state. They are intentionally broad so they can work across roleplay, assistant, task, explanation, and mixed narrative datasets.

Default tags are metadata. They do not change the conversation text, train a model by themselves, or magically fix weak examples. They help you organize, filter, review, export, and analyze entries more consistently.

You do not need to use every tag. A few well-chosen tags are usually better than tagging every possible detail. Overtagging can become noisy and make filtering harder.

## Default Tags vs Custom Tags

Built-in tags cover general workflow and training dimensions.

Custom tags are expected for project-specific vocabulary, such as:

- genre: `fantasy`, `cyberpunk`, `romance`, `horror`
- fandom or setting
- domain or topic: `medical`, `coding`, `legal_review`
- organization-specific workflows
- niche metadata that only matters to your dataset

You can add custom tags to built-in categories when they belong there, or create your own categories when your workflow needs a separate structure.

## Behavior

Behavior tags describe what the assistant is doing or what kind of behavioral pattern the entry demonstrates.

- `pacing`: Useful when the response controls rhythm well, such as slowing down, moving forward, or leaving space instead of rushing.
- `boundaries`: Marks examples where the assistant respects limits, constraints, safety lines, user preferences, or role boundaries.
- `no_user_control`: The assistant avoids narrating or deciding the user's actions, thoughts, feelings, or choices.
- `followup_question`: The assistant asks a relevant follow-up instead of assuming too much or ending the exchange abruptly.
- `emotional_awareness`: The assistant recognizes emotional context and responds with appropriate sensitivity.
- `instruction_following`: The assistant clearly follows the user's instructions, format, constraints, or requested task.
- `consistency`: The assistant maintains continuity, facts, character behavior, style, or previous context.
- `initiative`: The assistant moves the interaction forward helpfully without taking over the user's role.

Use Behavior tags when you want to study or filter for how the assistant behaves.

## Interaction

Interaction tags describe the shape of the exchange.

- `greeting`: Opening exchanges, introductions, welcomes, or first-contact examples.
- `roleplay`: Character, scenario, persona, or immersive interaction examples.
- `question_answer`: The user asks a question and the assistant answers directly.
- `task_completion`: The assistant performs or completes a requested task.
- `explanation`: The assistant explains a concept, decision, process, or reasoning path.
- `feedback`: The assistant gives critique, evaluation, suggestions, or review notes.
- `correction`: The assistant fixes an error, revises a previous answer, or responds to correction.

Use Interaction tags when you want to group entries by conversation structure.

## Style

Style tags describe how the answer is written.

- `dialogue`: Conversation-forward writing with spoken turns or character voice.
- `narration`: Prose that describes actions, events, or unfolding context.
- `descriptive`: Rich sensory, visual, emotional, or environmental detail.
- `concise`: Short, direct, low-fluff responses.
- `detailed`: Expanded responses with more context, explanation, or development.
- `grounded`: Realistic, believable, restrained prose or behavior that avoids overstatement.

Use Style tags when tone, density, or writing shape matters to the dataset.

## Source

Source tags describe where the entry came from or how it was created.

- `manual`: Written or curated directly by a person.
- `ai_generated`: Produced partly or fully by an AI system before review.
- `imported`: Originated outside RoleThread Lite, such as another dataset, tool, or manual file.
- `converted`: Changed from another supported format, such as ShareGPT converted into ChatML-style entries.

Use Source tags when provenance matters for review, trust, cleanup, or export decisions.

## Status

Status tags describe review state and operational workflow.

- `draft`: Early material that is not ready for final use.
- `needs_review`: Requires human review before approval.
- `needs_edit`: Needs correction, cleanup, rewriting, or structural work.
- `approved`: Reviewed and considered ready for the intended workflow.
- `invalid`: Known-bad or structurally unsuitable content that should not be used as-is.
- `duplicate`: Likely repeated or redundant dataset content.

Use Status tags to manage review passes without losing track of what still needs attention.

## Practical Tagging Habits

Start light. Add the tags that help you answer real workflow questions:

- Which entries need review?
- Which examples show the behavior I want?
- Which entries came from outside the app?
- Which examples are ready for export?
- Which style or interaction patterns are overrepresented?

If a tag will not help you find, review, export, or understand entries later, it may not need to exist.
