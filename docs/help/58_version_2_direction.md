# Version 2 Direction

RoleThread Lite V2 is the direction for evolving the current local dataset
workflow without changing product identity.

This page describes intended direction. It is not a release commitment, feature
guarantee, or date promise.

## Direction

Lite V2 is expected to continue focusing on deterministic, local, creator-owned
dataset work:

- structured dataset editing
- validation and repair
- Prompt Generation (Beta) prompt compilation
- metadata organization
- import, merge, backup, and export workflows
- reliable local runtime behavior

The goal is to make the existing workflow stronger, broader, and easier to
trust.

## Runtime and Packaging Improvements

Installed Windows builds now use LitLaunch for local app startup, app-window
launch, diagnostics, and shutdown coordination.

V2 direction includes:

- broader packaged runtime polish
- clearer LitLaunch diagnostics guidance
- lifecycle hardening
- runtime reliability improvements
- packaged app refinement

The intended boundary remains the same: RoleThread owns dataset workflows,
product policy, and user data behavior. LitLaunch owns generic runtime
platform behavior.

## macOS and Linux Expansion

V2 direction for non-Windows workflows includes:

- additional Linux packaging or desktop integration polish
- macOS validation refinement once direct or community testing improves
- Chrome and Chromium app-mode testing
- community-driven macOS validation
- clearer platform-specific setup and diagnostics

Linux is already a primary source/manual platform, and LitLaunch can provide
runtime diagnostics, event logging, support artifacts, and managed browser-mode
launch there today. The current Windows installed-app work creates a stronger
model for broader packaged platform support, but it does not imply all
platforms receive identical installer or desktop integration.

## Prompt Generation Improvements

Prompt Generation keeps moving from prompt compilation plumbing toward deeper
workflow usefulness.

Direction includes:

- additional generation templates
- improved template modifiers
- model-tailored generation guidance
- conversational style presets
- better generation workflow ergonomics
- tighter preview and export preparation flows

Lite should remain provider-agnostic. It compiles structured prompts and
workflows; it does not become a hosted inference service.

## Validation and Heuristics

V2 validation direction includes stronger dataset-quality assistance:

- improved validation coverage
- conversational consistency checks
- pacing and repetition heuristics
- duplicate detection
- structure analysis
- better repair workflows
- clearer quality feedback

Validation should remain guidance-oriented. Lite should help creators see
problems and apply safe deterministic fixes, not enforce a single creative
style.

## Workflow and UX Improvements

Expected V2 work includes quality-of-life improvements across daily workflows:

- smoother editing flows
- faster review and correction paths
- community-requested workflow refinements
- local runtime polish
- clearer diagnostics and logs
- more predictable recovery paths

Small workflow improvements matter when users spend long sessions curating
conversation data.

## Backup and Recovery

Backup and recovery workflows should become more visible and easier to trust.

Direction includes:

- in-app backup browsing
- dataset restore workflows
- lightweight dataset history visibility
- backup metadata visibility
- safer restore paths
- optional cloud-backup recovery
- restoring local datasets from cloud backups when local copies are lost

This direction is intended to support creator-controlled recovery, not full
Git-like version control, collaborative cloud editing, or mandatory hosted
storage. Cloud backup and recovery should remain optional; Lite should continue
to treat local datasets as the primary source of control.

## Reliability, Security, and Hardening

V2 should continue hardening the local runtime:

- shutdown reliability
- crash recovery
- deterministic runtime behavior
- loopback-only local runtime posture
- local security improvements
- packaged startup and update safety
- clearer failure reporting

The app should stay understandable when something goes wrong.

## Optional Future Update System

A future packaged update workflow is possible, but not guaranteed.

If it happens, it should be:

- optional or clearly user-controlled
- visible rather than silent
- compatible with graceful shutdown
- careful around local data
- easy to diagnose

Lite should not become an account-gated or cloud-controlled update surface.

## Long-Term Runtime Architecture

Runtime platform work should stay reusable through LitLaunch rather than become
RoleThread-specific infrastructure. Lite should benefit from that platform
without turning its own docs or codebase into a runtime framework.

## What Lite V2 Is Not Intended To Become

Lite V2 is not intended to become:

- hosted inference
- mandatory cloud workflow
- enterprise SaaS platform
- account-gated ecosystem
- telemetry-heavy product
- collaborative cloud editor
- Electron rewrite
- plugin marketplace
- cloud-dependent AI operating system

Lite should remain a focused local tool for dataset engineering and creator
workflow control.
