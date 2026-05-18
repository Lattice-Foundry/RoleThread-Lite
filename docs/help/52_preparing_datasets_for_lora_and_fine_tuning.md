# Preparing Datasets for LoRA and Fine-Tuning

Training readiness is a workflow, not a button.

Before a dataset leaves RoleThread for an external LoRA or fine-tuning tool, it should be cleaned, reviewed, balanced, and exported with intention. The goal is not to make the dataset perfect. The goal is to avoid training on avoidable noise.

## Clean Before Export

Before exporting, review for:

- malformed entries
- duplicated or near-duplicated conversations
- weak synthetic generations
- inconsistent formatting
- role-order problems
- shallow emotional loops
- system prompt drift
- overrepresented greetings or openings
- repeated catchphrases
- assistant turns that do not teach useful behavior

This is not busywork. It is how you protect the training signal.

## Balance Examples

Balance does not mean every category must have the same count.

It means the dataset should not accidentally overtrain one pattern while underrepresenting another.

Watch for:

- too many openings and not enough middle turns
- too much narration and not enough dialogue
- too many dramatic scenes and not enough quiet continuity
- too many long assistant turns
- too few correction or recovery examples
- too many examples from one character, tone, or scenario type

If one pattern dominates the dataset, the model may treat it as the expected behavior.

## Formatting Discipline

Formatting is training data.

If you want consistent quotes, action markers, paragraph breaks, or message style, the dataset needs to show that. If formatting changes randomly, the model may learn random formatting.

Use RoleThread to inspect entries before export instead of trusting that raw JSONL looks fine because it technically parses.

## Iterative Refinement Is Normal

Most training workflows do not succeed perfectly on the first pass.

A practical cycle looks like:

1. Prepare and export a dataset.
2. Train or adapt externally.
3. Test the resulting behavior.
4. Identify drift, repetition, weakness, or missing patterns.
5. Return to the dataset.
6. Add, remove, edit, rebalance, and export again.

That loop is normal. It is iterative dataset engineering.

## Avoid Garbage Amplification

Training can amplify flaws.

Repeated filler becomes a habit. Repeated verbosity becomes a habit. Repeated emotional flatness becomes a habit. Repeated formatting mistakes become a habit.

RoleThread's value is in slowing the process down enough to inspect what you are about to reinforce.
