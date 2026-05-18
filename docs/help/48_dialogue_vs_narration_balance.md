# Dialogue vs Narration Balance

Dialogue and narration balance shapes how a model responds.

There is no single correct style. The right balance depends on the kind of interaction you want the dataset to teach.

## Dialogue-Heavy Datasets

Dialogue-heavy datasets prioritize fast conversational exchange.

They are useful when you want:

- quick back-and-forth roleplay
- chat-style interaction
- compact emotional cues
- fast response pacing
- less descriptive prose

The risk is thinness. If there is too little context, the model may respond quickly but fail to preserve scene state, emotional continuity, or physical awareness.

## Prose-Heavy Datasets

Prose-heavy datasets include more narration, action, setting, and internal context.

They are useful when you want:

- immersive descriptive roleplay
- scene continuity
- atmospheric detail
- slower pacing
- richer emotional context
- novel-style narration

The risk is drag. If every assistant response becomes long prose, the model may become verbose even when the user wants a direct exchange.

## Action Formatting

Action formatting teaches the model how to represent movement, behavior, and scene state.

Examples include:

- quoted dialogue with prose narration
- asterisks for actions
- third-person narration
- first-person narration
- compact chat-style action beats

Pick patterns intentionally. Mixed action formats can be useful when they reflect real variation, but accidental inconsistency can confuse the output style.

## Internal Thoughts

Internal thoughts are powerful training signals.

They can teach emotional depth, hesitation, attraction, fear, uncertainty, restraint, or conflict. They can also make the model overexplain hidden feelings if used constantly.

Use internal thought patterns only when they support the kind of roleplay you want.

## Four Common Style Targets

Short chat-style roleplay:

- fast turns
- minimal narration
- clear emotional cues
- direct interaction

Immersive descriptive roleplay:

- scene detail
- physical continuity
- emotional pacing
- action and dialogue together

Novel-style narration:

- richer prose
- more atmosphere
- slower movement
- stronger descriptive voice

Emotionally dense conversational roleplay:

- focused emotional state
- realistic reactions
- restrained narration
- continuity across turns

Each style can be valid. The mistake is mixing them without knowing what pattern the dataset is teaching.

## Intentional Shaping

Models learn from the balance they see.

If 90% of assistant turns are long narration, the model may become long-winded. If almost everything is short dialogue, the model may struggle with immersion. If action formatting changes randomly, output formatting may drift.

Use RoleThread to inspect, split, edit, and organize entries so the balance is intentional.
