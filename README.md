# RoleThread Lite

### Local-First Dataset Crafting for Narrative AI

RoleThread Lite is a local-first tool for creating, validating, repairing,
organizing, merging, and exporting narrative AI training datasets.

Built for writers, conversational dataset builders, and fine-tuning creators,
RoleThread Lite keeps your JSONL files, registry database, backups, and sidecar
metadata on your machine while giving you practical tools for structured
dataset engineering.

---

## Project Links

* Website and documentation: [LatticeFoundry](https://latticefoundry.dev)
* Windows downloads: [GitHub Releases](https://github.com/Lattice-Foundry/RoleThread-Lite/releases)
* Support development: open **Support -> Support RoleThread** in the app or visit
  the [LatticeFoundry donation page](https://latticefoundry.dev/donate?source=rolethread-lite&interest=rolethread)
* Sierra Cognitive Group: [sierracognitive.com](https://www.sierracognitive.com)

---

## Current Features

* ChatML dataset creation and management
* ShareGPT import/export with ChatML conversion support
* Quick edit and full edit workflows for multi-turn entries
* Entry search across Manage Dataset and Deep Edit with role scopes and match modes
* Validation page with auto-fixable repairs and character role mapping
* Custom tag categories, active/archived tag lifecycle handling, and alias repair
* Character registry and per-entry character-to-turn metadata
* Portable registry sidecars for tags, aliases, characters, and mappings
* Protected working copies for untrusted files so originals stay untouched
* Dataset merge tools with dataset UUID, entry UUID, sidecar, and tag hardening
* Bulk tag edits, system prompt tools, dataset insights, and diagnostics
* Prompt Generation (Beta) for provider-agnostic external AI prompt compilation
* Local preferences, dataset backups, and database backups

---

## Design Philosophy

RoleThread Lite is designed around:

* privacy-first, file-owned workflows
* maintainable JSONL training data
* deterministic validation and repair before subjective scoring
* portable sidecar metadata for registry and character reconstruction
* a clear core/service/UI architecture that can support future RoleThread Studio work

Lite stays focused on dataset craftsmanship. Larger orchestration, cloud, and
AI-assisted workflow systems belong in future RoleThread Studio work rather
than the Lite release surface.

---

## Data Safety and Recovery

RoleThread Lite keeps working data local and creates recovery points before
important dataset and registry changes.

* JSONL dataset writes use local backups and atomic file replacement where
  practical.
* SQLite database backups protect tag, character, prompt-template, settings,
  and lifecycle metadata.
* Registry sidecars are refreshed alongside dataset saves so portable metadata
  stays close to the JSONL file.
* Optional cloud backup mirrors the latest local backup material to a configured
  sync folder after staging the output locally.

There is one known partial-failure recovery window in some durable operations:
the JSONL dataset save may succeed before a later SQLite commit fails. For
example, a tag lifecycle edit can update the dataset file and then fail while
committing registry metadata. In that case, the JSONL and database may briefly
reflect different states.

This is rare in normal local single-user use, and both recovery materials are
created before the operation:

* Dataset backups live under `backups/datasets/<dataset_name>/`
* SQLite database backups live under `backups/database/`

To recover, close RoleThread Lite and restore the most recent consistent dataset
and database backup pair. Dataset backups restore the JSONL data. Database
backups restore the tag registry, lifecycle metadata, character registry,
system prompt templates, local settings, and other app metadata.

RoleThread Lite does not claim one global transaction across JSONL files,
sidecars, SQLite, and cloud-sync folders. The recovery design is instead:
backup first, write carefully, refresh sidecars, and keep enough local material
available for a clear restore if the machine or process fails mid-operation.

---

## Version 1 Stable Status

RoleThread Lite 1.0.0 is the stable release surface for dataset craftsmanship.

## Install Options

**Source installs require Python 3.14.** RoleThread Lite V1 is validated on
Python `3.14.5`.

Python `3.14.4` remains the minimum supported V1 runtime. Newer Python versions
may run, but they are not guaranteed for V1 unless they are tested later.

RoleThread Lite V1 is tested against the Streamlit `1.57.x` runtime line.
The source install requirements keep Streamlit on that release line for the
V1 stabilization window.

Windows users have two practical paths:

* **Windows setup executable**: the packaged Windows installer published
  through [GitHub Releases](https://github.com/Lattice-Foundry/RoleThread-Lite/releases).
  It bundles the runtime and starts RoleThread Lite like a desktop app.
* **Manual source install**: the most transparent technical workflow for
  contributors, power users, and anyone who wants direct control over the
  Python environment.

The in-app Help system includes an **Installing RoleThread Lite** guide with
current setup and uninstall details.

Linux/macOS manual setup:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Linux and macOS source users can also use LitLaunch profiles for managed local
runtime behavior, diagnostics, runtime event logging, and support artifacts:

```bash
litlaunch --profile rolethread-browser
litlaunch report --profile rolethread-webapp --force
```

Windows/dev setup:

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Windows setup installer:

Download the latest `RoleThreadLiteSetup-v<version>.exe` from
[GitHub Releases](https://github.com/Lattice-Foundry/RoleThread-Lite/releases).
The installer is the packaged Windows path, not the only supported way to run
RoleThread Lite.

Because the Windows installer is not yet code-signed, Windows SmartScreen may
show an unknown publisher warning. If you downloaded it from the official
GitHub Releases page, choose **More info -> Run anyway**.

Installed Windows builds open like a local desktop-style app. The packaged
launcher starts RoleThread on your machine and opens a Microsoft Edge app
window backed by LitLaunch.

Source users can launch the same Windows app-window profile with:

```bat
litlaunch --profile rolethread-webapp
```

The installed app includes **Support -> Diagnostics**, a LitLaunch-powered
support page for runtime posture, operational snapshots, RoleThread product
context, support artifacts, and the runtime event trail. Generated reports and
bundles are written under `.litlaunch/reports/`.

Source users and support workflows can also generate a report without opening
the app:

```bat
litlaunch report --profile rolethread-webapp --force
```

Diagnostics are support artifacts, not telemetry. LitLaunch uses pattern-based
redaction and may include a generic privacy warning; review generated artifacts
before sharing because local paths and runtime metadata can still appear.
LitLaunch reports runtime posture and configuration. It does not make a
Streamlit app secure by itself.

Normal source/browser development can still use `streamlit run app.py`.

## Why RoleThread Uses LitLaunch

RoleThread Lite is local-first, but it still benefits from a dependable app
runtime: clean startup, loopback-only local access, browser/app-window launch,
shutdown coordination, runtime event logging, and diagnostics when something
goes wrong.

[LitLaunch 1.0.0](https://pypi.org/project/litlaunch/1.0.0/) provides that
runtime layer so RoleThread can stay focused on dataset work instead of
maintaining custom browser, process, and shutdown machinery. It also gives
source users and packaged users the same runtime profile model, plus an
integrated diagnostics/support surface that makes troubleshooting clearer.

## Windows Installer Status

RoleThread Lite has a Windows setup installer for normal users. The
installer packages a tested release snapshot; it does not clone or pull from Git
on the user's machine.

Target packaging stack:

* PyInstaller one-folder bundle for the app/runtime.
* Inno Setup for the Windows setup executable.
* GitHub Releases for publishing generated setup executables.

Installer source scaffolding lives under `installer/windows/`. Generated build
output and final setup executables are ignored and should not be committed.

The intended installed app/runtime location is:

```text
C:\Program Files\RoleThread Lite\
```

User data remains separate:

```text
%LOCALAPPDATA%\RoleThread\
%USERPROFILE%\RoleThread\
```

Default uninstall removes installed app/runtime files while preserving user
data. The uninstaller can optionally remove local RoleThread data after a clear
warning. Cloud/external backup destinations outside RoleThread-owned local
folders are preserved.

See `installer/windows/README.md` for packaging architecture and manual release
workflow details.

## OS Compatibility and Storage

RoleThread Lite V1 supports Windows and Linux as primary platforms. macOS is
beta-supported because direct maintainer testing is limited for V1, not because
the LitLaunch runtime model is Windows-only. Unknown platforms are unsupported
and should expect graceful degradation rather than platform-specific
integrations.

Fresh installs use platform-native storage defaults:

* Windows app state: `%LOCALAPPDATA%\RoleThread`
* Windows workspace: `%USERPROFILE%\RoleThread`
* Linux app state: `~/.local/share/rolethread`
* Linux workspace: `~/RoleThread`
* macOS app state: `~/Library/Application Support/RoleThread`
* macOS workspace: `~/RoleThread`

Workspace folders include `training_data`, `exports`, `imports`, and `backups`.
Existing user-configured paths remain preserved.

Cloud sync folders are optional backup/sync targets, not the preferred active
working directory. Using OneDrive or another sync folder as live working
storage can cause constant sync activity, file locking, conflicts, or odd
timestamps. If OneDrive keeps syncing RoleThread files, review OneDrive backup
and sync settings for folders such as Documents or Desktop.

Launch policy is platform-aware. The Windows installer opens a local Edge app
window when available. Linux and macOS do not have a V1 packaged installer, but
source checkouts can still benefit from LitLaunch profile loading, local
browser-mode runtime ownership, diagnostics, support artifacts, and runtime
event logging.

The V1 stability gate is:

* Full unit and service suite passes with `python -m pytest`
* Help and FAQ content are present in-app
* Lite and future RoleThread Studio boundaries are documented
* Local backups, sidecars, validation, merge, tag lifecycle, character mapping,
  export, and settings flows remain covered by regression tests
* Known limitations are documented rather than implied as missing V1 work

---

## Support Development

RoleThread Lite is developed by LatticeFoundry, a software division of Sierra
Cognitive Group, LLC.

If RoleThread Lite is useful to your workflow, open **Support -> Support
RoleThread** in the app to contribute through the LatticeFoundry donation
platform. Donations are processed by LatticeFoundry infrastructure through
Stripe; RoleThread Lite does not process, store, or retain payment information.

---

## Vision

High-quality narrative AI experiences begin with high-quality narrative data.
RoleThread Lite focuses on the local, inspectable, repairable dataset workflow
needed to build that data with confidence.

Creator-controlled. File-owned. Built for narrative AI datasets.

## License

RoleThread Lite is licensed under the Apache License, Version 2.0.

Copyright (c) 2026 Sierra Cognitive Group, LLC

RoleThread Lite is developed and maintained by LatticeFoundry,
a software division of Sierra Cognitive Group, LLC.
