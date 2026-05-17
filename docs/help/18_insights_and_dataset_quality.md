# Insights and Dataset Quality

Insights helps you understand the shape of a loaded dataset.

It is not a universal judgment system. It is a set of deterministic measurements and practical heuristics that point out patterns worth reviewing.

Use Insights to ask:

- Are assistant responses long enough?
- Is the dataset structurally healthy?
- Are tags and metadata being used consistently?
- Is the dataset too repetitive?
- Are entries too short or too long?
- Is the style more narrative-heavy or dialogue-heavy?

The included example datasets are useful for learning Insights. They let you see how different organization styles, prompt patterns, tags, and character mappings change the report.

## The Dataset Health Score

Insights shows a composite score from 0 to 100.

That score is built from four categories:

- **Response Quality**
- **Diversity**
- **Structure**
- **Metadata Integrity**

The score is a guide. It helps you prioritize review, but it does not replace your judgment.

## Response Quality

Response Quality looks at assistant responses.

It considers signals such as:

- average response length
- median response length
- short responses
- empty responses
- placeholder content
- user/assistant length balance

For many narrative datasets, assistant responses should be detailed enough to teach style, voice, and behavior. Very short responses may be valid, but a dataset dominated by them may not train the behavior you want.

## Diversity

Diversity looks for variety across the dataset.

It considers signals such as:

- unique system prompts
- prompt concentration
- tag coverage
- tag entropy
- category coverage
- near-duplicate entries

Low diversity does not always mean bad. A specialized dataset may intentionally repeat a style. Insights simply shows when repetition is strong enough to review.

## Structure

Structure looks at entry shape.

It considers signals such as:

- validation pass rate
- invalid entry count
- average exchange count
- exchange depth distribution
- entries in the 3-7 exchange range
- missing or short system prompts

Structure helps you find entries that may need editing, repair, split, or join.

## Metadata Integrity

Metadata Integrity looks at organization and portability.

It considers signals such as:

- RoleThread-native stamp coverage
- tagged entry percentage
- character mapping coverage
- sidecar presence
- sidecar currency

This category rewards datasets that are easier to manage, search, export, and move safely.

## Narrative and Dialogue Balance

Insights includes a narrative spectrum based on assistant response content.

It estimates whether the dataset leans toward:

- heavy narrative
- narrative-leaning
- balanced
- dialogue-leaning
- heavy dialogue

This is a style signal, not a score gate. Different datasets should land in different places.

Narrative-heavy datasets may produce more descriptive, atmospheric behavior. Dialogue-heavy datasets may produce more conversational or chat-like behavior. A balanced dataset can support both, but only if the examples are consistent enough to teach the intended style.

Watch for repeated formatting patterns too. Quoted dialogue, paragraph style, name labels, tense, and point of view can all become learned habits.

For example:

```text
"I don't think this is a good idea," she says quietly.
```

Consistent quoted dialogue helps teach clear conversational structure. Inconsistent formatting can teach inconsistency.

Name usage also matters. Repeating specific character names can be useful in character-bound scenes, but heavy name repetition can make behavior feel tied to those names. Pronoun-based narration often generalizes better when the behavior matters more than the specific character.

## Exchange Depth

Exchange depth shows how many user/assistant pairs entries contain.

This helps you spot:

- many single-turn entries
- long multi-turn entries
- entries that may benefit from splitting
- tiny related entries that might be better joined

The right depth depends on your training goal.

## Prompt Concentration

Prompt concentration shows whether a few system prompts dominate the dataset.

High concentration can be useful for a focused dataset. It can also mean the dataset lacks scenario variety.

Use this insight to decide whether repeated prompts are intentional.

## Near-Duplicate Detection

Insights can flag entries that look very similar.

Near-duplicates are not always wrong. Variations can be useful. But accidental duplicates can overweight one behavior in training.

Review near-duplicate groups before export if the dataset came from merges, imports, or repeated templates.

## Recommendations and Focused Views

Insights may show recommendations based on the lowest-scoring areas.

Some counts can link to focused Manage Dataset views. For example:

- untagged entries
- short-response entries
- invalid entries
- split candidates
- near-duplicate entries

These links let you move from "something looks off" to "show me the entries."

Manage Dataset is the right place to act on most focused views. Use it to tag, search, quick edit, duplicate, join, or open entries in Full Edit.

## Common Mistake

**Mistake:** Trying to force every dataset to an excellent score.

**Better mental model:** Insights helps you understand tradeoffs. A deliberately narrow dataset may score lower on diversity and still be useful.

## Practical Tip

Use Insights after a cleanup pass, not after every tiny edit. It is best for seeing patterns across the whole dataset.

