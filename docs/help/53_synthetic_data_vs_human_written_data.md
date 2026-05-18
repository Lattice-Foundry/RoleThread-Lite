# Synthetic Data vs Human-Written Data

Synthetic data is useful. It is not magic.

AI-generated examples can give you volume, variation, scaffolding, and structure quickly. Human-written or human-refined examples often carry sharper judgment, better emotional nuance, and more intentional conversational rhythm.

The best workflows often use both.

## What Synthetic Data Is Good At

Synthetic generation can help with:

- draft examples
- scenario variation
- structural templates
- format prototyping
- alternate tones
- broad coverage
- quick first-pass data

It is a force multiplier, not a replacement for curation.

## Where Synthetic Data Gets Weak

AI-generated data often has recognizable weaknesses:

- repetitive phrasing
- flattened emotional nuance
- generic assistant responses
- over-sterilized outputs
- predictable pacing
- shallow conflict handling
- weak emotional initiative
- excessive agreement
- repeated sentence shapes
- polished but empty responses

At small scale, these synthetic flaws are easy to miss. At large scale, they compound.

## Human Refinement Adds Signal

Human editing is often where conversational quality emerges.

A creator can notice:

- the response is technically correct but emotionally wrong
- the pacing is too fast or too slow
- the character is drifting
- the assistant is avoiding initiative
- the scene has no forward motion
- the dialogue sounds polished but lifeless
- the structure is valid but not useful

Those judgments are difficult to automate fully because they depend on what you are trying to teach.

## Do Not Demonize Synthetic Data

Synthetic data can be excellent when it is guided and reviewed.

The mistake is treating generated output as finished simply because it is cleanly formatted. A model can produce valid JSONL that still teaches weak behavior.

Use synthetic generation to create options. Use RoleThread to decide which options deserve to become training data.

## The Practical Mix

A healthy workflow may include:

- AI-generated drafts
- human-written anchor examples
- edited synthetic entries
- private or specialized local additions
- validation and repair
- targeted rebalancing after test results

The point is not whether an entry was generated or written by hand. The point is whether it teaches the behavior you want.
