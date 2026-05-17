# Lite vs Studio Boundaries

RoleThread Lite and RoleThread Studio have different runtime and product boundaries.

Lite owns deterministic dataset tooling. Studio can eventually own heavier orchestration and runtime systems.

## What Belongs in Lite

Lite is the stable dataset tooling surface.

Good fits for Lite include:

- creating and loading datasets
- editing entries
- quick review and focused correction
- validation and repair
- tag and metadata organization
- character mapping review
- splitting, joining, duplicating, deleting, and merging entries
- exporting training data
- backups, sidecars, and recovery workflows
- clear settings and diagnostics

Lite features should remain testable inside the existing UI/service/core architecture.

## What Belongs in Studio

Studio is the planned surface for heavier RoleThread workflows.

Better fits for Studio may include:

- large-scale orchestration
- advanced automation
- runtime roleplay systems
- multi-agent workflows
- inference management
- power-user experimentation
- advanced AI-assisted systems
- native desktop workflows if they need heavier runtime ownership

This is a boundary statement, not a feature promise or release schedule.

## Why The Split Matters

Not every useful idea should go into Lite.

A feature can be valuable and still add too much state, orchestration, or runtime coupling for Lite.

## Decision Heuristics

When deciding whether a feature belongs in Lite, ask:

- Does it directly improve dataset creation, editing, validation, repair, organization, or export?
- Can it be tested without fragile UI automation?
- Does it preserve clear data ownership and recovery behavior?
- Does it make the common workflow simpler rather than heavier?
- Can it live within the existing UI/service/core architecture?

If the answer is mostly no, the idea may belong in Studio or a later architectural pass.

## Healthy Boundaries

Lite should remain complete on its own. Studio boundaries should not turn Lite into a waiting room for a larger product.
