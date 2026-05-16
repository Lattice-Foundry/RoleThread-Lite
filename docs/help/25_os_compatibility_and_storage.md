# OS Compatibility and Storage Policy

LoreForge Lite V1 is local-first and platform-aware.

The goal is simple: app-managed state should live in normal operating-system app data locations, while your visible datasets, exports, imports, and backups live in a clear user workspace.

## Support Levels

**Windows is a primary V1 support platform.**

Windows is the main maintainer-tested desktop target. Installer support is planned later. A Microsoft Edge web-app workflow is also planned when Edge is available, with default-browser fallback when Edge is not available.

**Linux is a primary V1 support platform.**

Linux is expected to use a manual or git-clone workflow for V1. Launching through the default browser or manually opening the local Streamlit URL is the expected model. OneDrive-specific integration is not supported on Linux.

**macOS is beta-supported for V1.**

macOS support is intended, but is community-tested because the maintainer cannot fully validate it directly yet. There is no V1 macOS installer planned. Default-browser use is the expected workflow. Safari-style web-app usage may work as a user-managed beta workflow, but LoreForge does not automate it in V1.

**Unknown platforms are unsupported.**

LoreForge should degrade gracefully where possible, but unsupported platforms should not be assumed to have platform-specific integrations.

## Official Python Runtime

LoreForge Lite V1 officially supports Python 3.14.4.

Older Python versions are blocked so the app fails clearly instead of producing confusing import or dependency errors later.

Newer Python versions may run, but they are untested for V1 unless documented later.

Manual Linux/macOS users should create their environment with `python3.14`. Windows development users should use `py -3.14`.

## Fresh-Install Storage Defaults

On a fresh install with no saved preferences, LoreForge uses platform-native defaults.

Windows:

```text
Internal app state:
%LOCALAPPDATA%\LoreForge

User workspace:
%USERPROFILE%\LoreForge

Workspace folders:
%USERPROFILE%\LoreForge\training_data
%USERPROFILE%\LoreForge\exports
%USERPROFILE%\LoreForge\imports
%USERPROFILE%\LoreForge\backups
```

Linux:

```text
Internal app state:
~/.local/share/loreforge

User workspace:
~/LoreForge

Workspace folders:
~/LoreForge/training_data
~/LoreForge/exports
~/LoreForge/imports
~/LoreForge/backups
```

macOS:

```text
Internal app state:
~/Library/Application Support/LoreForge

User workspace:
~/LoreForge

Workspace folders:
~/LoreForge/training_data
~/LoreForge/exports
~/LoreForge/imports
~/LoreForge/backups
```

Unknown platforms use a safe `~/LoreForge` fallback where possible.

## Existing Preferences Win

If you already configured a dataset folder or backup folder, LoreForge preserves that choice.

Platform defaults apply when preferences are missing or empty. They are not a migration system and do not move your existing datasets.

Settings shows whether important paths are using a platform default or a user override.

## Cloud Sync and Working Storage

Cloud sync folders are optional backup or sync targets, not the preferred active working location.

Using OneDrive, Dropbox, Google Drive, iCloud Drive, or another sync folder as live working storage can cause constant sync activity, file locking, conflicts, delayed writes, or unusual timestamps.

If OneDrive appears to be constantly syncing LoreForge files, review OneDrive backup and sync settings. In particular, check whether OneDrive is automatically syncing Documents, Desktop, or another folder that contains your LoreForge workspace.

The safest pattern is:

1. Work locally in the LoreForge workspace.
2. Let LoreForge create local backups.
3. Use Cloud Backup only to mirror backup material to a sync provider.

## Launch Behavior Policy

LoreForge V1 defines platform-aware launch policy and diagnostics. Production
installer, shortcut, and packaged browser behavior are still planned later.

For development testing on Windows, LoreForge supports an optional Microsoft
Edge web-app flag:

```bat
streamlit run app.py --server.headless true -- webapp
```

The `webapp` flag asks LoreForge to open the local Streamlit app in Microsoft
Edge app mode when Edge is detected. The `--server.headless true` option belongs
to Streamlit; it suppresses Streamlit's normal browser auto-open. If you run
`streamlit run app.py -- webapp` without headless mode, Streamlit may also open
a regular browser window before LoreForge app code can stop it.

Windows:

- preferred future workflow: Microsoft Edge web app when Edge is detected
- fallback: default browser when Edge is unavailable
- installer and shortcut integration are planned later
- development-only test workflow: Edge app mode through the `webapp` flag

Linux:

- preferred workflow: default browser
- fallback: manually open the local Streamlit URL
- manual/git-clone setup is expected for V1

macOS:

- preferred workflow: default browser
- fallback: manually open the local Streamlit URL
- Safari-style web-app use is user-managed and beta
- no V1 installer is planned

Unknown platforms:

- unsupported
- browser behavior should degrade gracefully

## Where To Check This In The App

Open **Settings** and review **About This Installation**.

That section shows:

- detected platform
- Python runtime compatibility
- platform capabilities
- browser support
- launch behavior
- raw diagnostics
- platform path defaults and path sources
