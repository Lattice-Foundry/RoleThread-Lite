# Common Dataset Mistakes

Most dataset problems are not dramatic. They are small patterns that repeat until the model learns them.

That is why review matters. More data does not automatically mean better data, and poor synthetic data can compound problems quickly.

## Malformed Structure

Common structural problems include:

- missing system, user, or assistant messages
- malformed role order
- broken JSONL
- empty turns
- assistant replies stored under the wrong role
- conversations that stop before the behavior is demonstrated

These issues weaken the training signal before style or creativity even matters.

## Duplicated Conversations

Duplicates can overweight one pattern.

If the same conversation appears many times, the model may treat that phrasing, structure, or behavior as more important than it really is. Near-duplicates can do the same thing more quietly.

Use deduplication and review tools before assuming volume is helping.

## Repetitive Phrasing

Synthetic data often repeats itself.

Watch for:

- repeated openings
- repeated emotional beats
- repeated sentence structures
- repeated catchphrases
- repeated scene transitions
- repeated assistant reassurance

Repetition can become a learned habit, especially when it appears across many entries.

## Contradictory Behavior

Contradictions teach instability.

If one entry reinforces a calm grounded character and another teaches the same character to become erratic without cause, the model gets mixed signals.

Some contradiction is natural when contexts differ. The problem is unexplained contradiction: behavior that changes because the dataset is inconsistent, not because the scene calls for it.

## Shallow Emotional Loops

Roleplay data can fall into loops where characters keep restating emotion without moving the interaction forward.

Examples:

- endless reassurance
- repeated apologies
- repeated "I understand" responses
- emotional intensity that never changes
- conflict that never develops or resolves

These entries may look emotionally rich at a glance, but they can teach stagnant conversation.

## Excessive Greeting Data

Too many greetings can distort a dataset.

If a large share of entries are openings, introductions, or first-turn setup, the model may learn startup behavior better than sustained interaction.

Roleplay models need middle turns too: escalation, correction, quiet moments, continuity, repair, and resolution.

## Formatting Drift

Inconsistent formatting can become output drift.

Watch for accidental mixing of:

- quote styles
- markdown habits
- action markers
- name labels
- tense
- point of view
- paragraph length

There is no single correct format. The issue is unintentional inconsistency.

## Low-Quality Filler

Filler responses are contagious.

Avoid padding the dataset with assistant turns that are technically valid but behaviorally weak:

- generic agreement
- empty enthusiasm
- vague summaries
- noncommittal emotional responses
- replies that ignore the user's specific action

If the response does not teach a useful pattern, it may not deserve to stay.

## Synthetic Data Needs Human Judgment

AI-generated examples can be useful scaffolding.

They can also amplify flaws fast. If the prompt produces repetitive, shallow, overlong, or contradictory data, generating more of it usually makes the problem worse.

Use AI for draft volume. Use RoleThread to decide what is worth keeping.

## Related Articles

- **Why Dataset Quality Matters**
- **What Makes a Good Roleplay Dataset**
- **Dataset Scaling and Maintenance**
