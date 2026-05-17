# RoleThread Lite

### Local-First Dataset Crafting for Narrative AI

RoleThread Lite is a local-first tool for creating, validating, repairing,
organizing, merging, and exporting narrative AI training datasets.

Built for writers, conversational dataset builders, and fine-tuning creators,
RoleThread Lite keeps your JSONL files, registry database, backups, and sidecar
metadata on your machine while giving you practical tools for structured
dataset engineering.

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

RoleThread Lite 1.0 is the stable release surface for dataset craftsmanship.

## Supported Runtime

RoleThread Lite V1 officially supports Python `3.14.4`.

Other Python versions may run, but they are not guaranteed for V1 unless they
are tested later. Python versions below `3.14.4` are unsupported. Windows
installer work will bundle or target the supported runtime later; manual
Linux/macOS setup should use `python3.14`.

Linux/macOS manual setup:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Windows/dev setup:

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Windows app-style browser workflow:

Run RoleThread normally, then use your browser's built-in app shortcut feature
if you want a standalone window. In Microsoft Edge, open the local RoleThread
URL and use **Apps > Install this site as an app** or the equivalent shortcut
option. This remains the reliable V1 fallback.

`streamlit run app.py -- webapp` is the internal Windows web-app launch method
that future launcher and installer workflows will call. It opens the local app
in Microsoft Edge app mode when Edge is available. If Streamlit opens a normal
browser window first, RoleThread attempts to close only that duplicate browser
window by targeting the exact Windows window handle after the Edge app window is
observed. On Linux, macOS, or unknown platforms, the flag is a safe no-op:
RoleThread continues in normal browser mode.

Developer diagnostics are hidden by default. Add `dev` to expose launch and
platform internals in Settings. Add `edge-debug` or `webapp-debug` only when
investigating Edge launch behavior:

```bat
streamlit run app.py -- webapp dev edge-debug
```

The debug mode records Edge process IDs and visible window metadata where
Windows exposes it. Cleanup uses a polite window-close request against an exact
window handle or a tightly classified candidate; it does not use `taskkill` or
close app-window candidates.

## Windows Installer Plan

RoleThread Lite V1 will ship a fully bundled Windows installer for normal users.
The installer will package a tested release snapshot; it will not clone or pull
from Git on the user's machine.

Target packaging stack:

* PyInstaller one-folder bundle for the app/runtime.
* Inno Setup for the final Windows setup executable.
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

Default uninstall should remove installed app/runtime files while preserving
user data. A future full uninstall option may remove all RoleThread data only
after a clear warning.

See `installer/windows/README.md` for the current packaging architecture and
manual release plan.

## OS Compatibility and Storage

RoleThread Lite V1 supports Windows and Linux as primary platforms. macOS is
beta-supported because direct maintainer testing is limited for V1. Unknown
platforms are unsupported and should expect graceful degradation rather than
platform-specific integrations.

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

Launch policy is defined for future launcher/installer work. Windows will
prefer an Edge web-app workflow when Edge is available and fall back to the
default browser when it is not. Linux and macOS use default-browser or manual
local-URL workflows.

The V1 stability gate is:

* Full unit and service suite passes with `python -m pytest`
* Help and FAQ content are present in-app
* Lite and future RoleThread Studio boundaries are documented
* Local backups, sidecars, validation, merge, tag lifecycle, character mapping,
  export, and settings flows remain covered by regression tests
* Known limitations are documented rather than implied as missing V1 work

---

## Vision

High-quality narrative AI experiences begin with high-quality narrative data.
RoleThread Lite focuses on the local, inspectable, repairable dataset workflow
needed to build that data with confidence.

Creator-controlled. File-owned. Built for narrative AI datasets.
