# Lite vs Studio Boundaries

RoleThread Lite and RoleThread Studio are meant to have different jobs.

Lite should stay focused. Studio is where heavier orchestration and experimental systems can eventually live.

## What Belongs in Lite

Lite is the stable dataset workshop.

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

Lite features should be understandable, testable, and useful without turning the app into a larger orchestration platform.

## What Belongs in Studio

Studio is the future advanced environment for heavier RoleThread workflows.

Better fits for Studio may include:

- large-scale orchestration
- advanced automation
- runtime roleplay systems
- multi-agent workflows
- inference management
- power-user experimentation
- advanced AI-assisted systems
- native desktop workflows if they need heavier runtime ownership

This is direction, not a feature promise or release schedule.

## Why The Split Matters

Not every useful idea should go into Lite.

A feature can be valuable and still add too much weight to the focused dataset workflow. Lite should preserve simplicity, maintainability, workflow clarity, and recoverable data operations.

Studio gives RoleThread room to explore ambitious systems without destabilizing the everyday dataset tool.

## Decision Heuristics

When deciding whether a feature belongs in Lite, ask:

- Does it directly improve dataset creation, editing, validation, repair, organization, or export?
- Can it be tested without fragile UI automation?
- Does it preserve clear data ownership and recovery behavior?
- Does it make the common workflow simpler rather than heavier?
- Can it live within the existing UI/service/core architecture?

If the answer is mostly no, the idea may belong in Studio or a later architectural pass.

## Healthy Boundaries

Lite should remain complete on its own.

The point is not to make Lite feel limited. The point is to keep it dependable. A focused tool that does its job well is more useful than a broad tool that makes every workflow harder to understand.

