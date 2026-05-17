# OS Compatibility and Storage Policy

RoleThread Lite V1 is local-first and platform-aware.

The goal is simple: app-managed state should live in normal operating-system app data locations, while your visible datasets, exports, imports, and backups live in a clear user workspace.

## Support Levels

**Windows is a primary V1 support platform.**

Windows is the main maintainer-tested desktop target. Installer support is planned later. A Microsoft Edge web-app workflow is also planned when Edge is available, with default-browser fallback when Edge is not available.

**Linux is a primary V1 support platform.**

Linux is expected to use a manual or git-clone workflow for V1. Launching through the default browser or manually opening the local Streamlit URL is the expected model. OneDrive-specific integration is not supported on Linux.

**macOS is beta-supported for V1.**

macOS support is intended, but is community-tested because the maintainer cannot fully validate it directly yet. There is no V1 macOS installer planned. Default-browser use is the expected workflow. Safari-style web-app usage may work as a user-managed beta workflow, but RoleThread does not automate it in V1.

**Unknown platforms are unsupported.**

RoleThread should degrade gracefully where possible, but unsupported platforms should not be assumed to have platform-specific integrations.

## Official Python Runtime

RoleThread Lite V1 officially supports Python 3.14.4.

Older Python versions are blocked so the app fails clearly instead of producing confusing import or dependency errors later.

Newer Python versions may run, but they are untested for V1 unless documented later.

Manual Linux/macOS users should create their environment with `python3.14`. Windows development users should use `py -3.14`.

## Fresh-Install Storage Defaults

On a fresh install with no saved preferences, RoleThread uses platform-native defaults.

Windows:

```text
Internal app state:
%LOCALAPPDATA%\RoleThread

User workspace:
%USERPROFILE%\RoleThread

Workspace folders:
%USERPROFILE%\RoleThread\training_data
%USERPROFILE%\RoleThread\exports
%USERPROFILE%\RoleThread\imports
%USERPROFILE%\RoleThread\backups
```

Linux:

```text
Internal app state:
~/.local/share/rolethread

User workspace:
~/RoleThread

Workspace folders:
~/RoleThread/training_data
~/RoleThread/exports
~/RoleThread/imports
~/RoleThread/backups
```

macOS:

```text
Internal app state:
~/Library/Application Support/RoleThread

User workspace:
~/RoleThread

Workspace folders:
~/RoleThread/training_data
~/RoleThread/exports
~/RoleThread/imports
~/RoleThread/backups
```

Unknown platforms use a safe `~/RoleThread` fallback where possible.

## Existing Preferences Win

If you already configured a dataset folder or backup folder, RoleThread preserves that choice.

Platform defaults apply when preferences are missing or empty. They are not a migration system and do not move your existing datasets.

Settings shows whether important paths are using a platform default or a user override.

## Cloud Sync and Working Storage

Cloud sync folders are optional backup or sync targets, not the preferred active working location.

Using OneDrive, Dropbox, Google Drive, iCloud Drive, or another sync folder as live working storage can cause constant sync activity, file locking, conflicts, delayed writes, or unusual timestamps.

If OneDrive appears to be constantly syncing RoleThread files, review OneDrive backup and sync settings. In particular, check whether OneDrive is automatically syncing Documents, Desktop, or another folder that contains your RoleThread workspace.

The safest pattern is:

1. Work locally in the RoleThread workspace.
2. Let RoleThread create local backups.
3. Use Cloud Backup only to mirror backup material to a sync provider.

## Launch Behavior Policy

RoleThread V1 defines platform-aware launch policy and diagnostics. Production
installer, shortcut, and packaged browser behavior are still planned later.

For V1, run RoleThread normally and use the browser workflow that is most
reliable on your machine. If you want an app-style window, use your browser's
built-in install or shortcut option manually. In Microsoft Edge, open the local
RoleThread URL and use **Apps > Install this site as an app** or the equivalent
shortcut option.

The `webapp` flag is RoleThread's internal Windows web-app launch method for
future launcher and installer workflows. It opens Microsoft Edge app mode when
Edge is available. If Streamlit opens a normal browser window first, RoleThread
attempts to close only that duplicate browser window after the Edge app window
is observed. On Linux, macOS, or unknown platforms, the flag does not attempt
Windows-specific launch or cleanup work; RoleThread continues in normal browser
mode.

Developer diagnostics are hidden unless RoleThread is started with the `dev`
flag. `edge-debug` and `webapp-debug` are developer-only investigation flags and
should be combined with `dev` when detailed process/window metadata is needed.
Cleanup uses a polite window-close request against an exact Windows window
handle or a tightly classified candidate; it does not use `taskkill` or close
app-window candidates.

Windows:

- preferred future workflow: Microsoft Edge web app when Edge is detected
- fallback: default browser when Edge is unavailable
- installer and shortcut integration are planned later
- V1 workflow: normal browser launch, with manual browser install-as-app if desired

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

