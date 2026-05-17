# UI and Theme Style Guide

RoleThread Lite's interface should feel calm, readable, and creator-oriented.

The app is used for careful dataset work: reading entries, editing text, validating structure, repairing metadata, tagging content, and exporting training data. The UI should support concentration instead of competing for attention.

## Design Philosophy

RoleThread Lite is dark-theme-first, workflow-focused, and intentionally restrained.

The interface should prioritize:

- readable text
- predictable navigation
- clear workflow grouping
- low visual noise
- compact but comfortable controls
- strong data visibility
- clear feedback after actions

It should avoid "AI startup dashboard chaos": noisy gradients, excessive cards, ornamental motion, overloaded metrics, and decoration that makes dataset work harder to scan.

## Theme Colors

The current Streamlit theme uses:

- primary accent: `#3EB489`
- app background: `#101214`
- secondary surface: `#383A3C`
- main text: `#E8E8E8`

RoleThread also uses the inline slug/path green `#3D9F64` for compact technical values such as slugs, paths, and developer-style metadata.

Use these colors consistently. New UI should not introduce a competing palette unless there is a clear product reason.

## Accent Use

Mint green is the primary accent.

Use it for selected navigation, primary action emphasis, section identity, and important highlights. It should not be sprayed across every label. If everything is highlighted, nothing is highlighted.

The slug/path green should stay connected to technical inline values. It is useful because it makes paths, slugs, and machine-readable identifiers recognizable without making them look like primary buttons.

## Layout and Spacing

RoleThread pages should feel organized rather than dense for density's sake.

Prefer:

- clear page titles
- concise section headings
- grouped controls near the workflow they affect
- left-aligned lists and paths
- predictable button rows
- enough vertical spacing to scan

Avoid deeply nested cards, centered operational lists, and layouts that make ordinary actions feel like marketing sections.

## Sidebar and Navigation

The sidebar is part of the application shell.

It should preserve brand identity, quick navigation, and contextual navigation for Help and FAQ. When a page owns the sidebar, that ownership should be obvious and useful rather than decorative.

Navigation labels should stay stable and workflow-oriented:

- Manage Dataset
- Create Entry
- Deep Edit
- Validation
- Insights
- Export
- Settings
- Help

Labels should teach the user where work belongs without requiring long explanations.

## Status and Notifications

Notifications should be readable, left-aligned, and proportional to the content.

They should not collapse into narrow columns, center themselves awkwardly, or become a wall that hides the active workflow. Use status messages to explain what happened and what the user can do next, not to narrate every internal detail.

Developer diagnostics belong behind developer mode. Normal users should see clear support information, not raw internals.

## Controls

Controls should look and behave like the thing they are.

Use buttons for commands, expanders for optional detail, checkboxes for toggles, select boxes for choices, and search forms for repeatable search actions. Avoid making links look like primary buttons unless they are meant to behave like primary actions.

Long paths and dataset names should have enough horizontal room to be readable.

## Documentation Tone in the UI

The UI should be helpful without becoming wordy.

Short, specific guidance is better than large instructional blocks. Help articles and FAQ pages can carry deeper explanations; operational pages should keep the user close to the task.

## What to Avoid

RoleThread Lite should avoid:

- flashy dashboard patterns
- excessive animation
- decorative gradients
- noisy metric walls
- oversized hero sections inside the app
- centered operational lists
- vague "AI magic" language
- burying primary workflows below explanation text

The best UI for RoleThread is one that quietly helps users protect, inspect, and improve their datasets.

