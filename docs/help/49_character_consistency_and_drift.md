# Character Consistency and Drift

Character consistency is dataset behavior shaping.

Models reinforce repeated behavioral patterns. If the examples show a stable personality, tone, and interaction rhythm, the model has a clearer pattern to learn. If examples contradict each other without context, the character can drift.

## Personality Consistency

A consistent character does not behave identically in every scene.

Consistency means the behavior makes sense for the character and context:

- confidence stays recognizable
- shyness has a stable shape
- humor fits the voice
- anger appears for believable reasons
- affection develops in a coherent way
- boundaries stay consistent unless the story explains a change

Variation should come from the situation, not random dataset noise.

## Tone Stability

Tone drift is common in generated data.

A character may start reserved, become melodramatic, then turn overly casual for no reason. That inconsistency teaches unstable tone.

Review for:

- sudden personality shifts
- unexplained emotional reversals
- inconsistent formality
- mismatched vocabulary
- changing response length
- unstable narration style

## Exaggerated Quirks

Quirks are easy to overtrain.

If a character repeatedly uses the same catchphrase, speech tic, nickname, or emotional reaction, the model may overuse it later.

A trait should support the character. It should not become the entire character.

## Contradictory Examples

Contradictory examples are not always bad.

A character can act differently under pressure, with different people, or at different points in a relationship. The dataset should make those differences legible.

The problem is contradiction without cause:

- affectionate in one entry, hostile in another with no context
- careful in one entry, reckless in another without setup
- concise in one entry, wildly verbose in another without purpose

Models do not know which version you meant unless the examples make it clear.

## Emotional Consistency

Emotional consistency does not mean emotional flatness.

It means emotional reactions have continuity:

- fear changes how the character speaks
- trust changes how much they reveal
- conflict changes pacing and word choice
- relief changes tension
- embarrassment changes behavior

Emotion should respond to the scene instead of resetting every turn.

## Dataset Behavior Shaping

Every repeated pattern is a training vote.

Repeated careful boundaries teach careful boundaries. Repeated rambling teaches rambling. Repeated emotional whiplash teaches emotional whiplash. Repeated continuity teaches continuity.

That is dataset behavior shaping: using examples to reinforce the behavior you want while removing patterns you do not want amplified.

RoleThread helps by making entries inspectable, editable, taggable, searchable, and easier to validate before export.
