# OS Compatibility and Storage Policy

RoleThread Lite V1 is platform-aware. App-managed state should live in normal
operating-system app data locations, while visible datasets, exports, imports,
and backups live in a clear user workspace.

For setup commands and uninstall instructions, see **Installing RoleThread
Lite**.

## Support Levels

**Windows is a primary V1 support platform.**

Windows is the main maintainer-tested desktop target. RoleThread Lite has a
beta setup installer for Windows and a local Microsoft Edge app-window
workflow through LitLaunch when Edge is available. Manual source installs
remain supported.

**Linux is a primary V1 support platform.**

Linux uses the manual/source workflow for V1. It remains a full supported
runtime path: source users can run plain Streamlit or use LitLaunch's
browser-mode profile for managed local runtime behavior, diagnostics, runtime
event logging, and support artifacts. OneDrive-specific integration is not
supported on Linux.

**macOS is beta-supported for V1.**

macOS support is intended, but is community-tested because the maintainer
cannot fully validate it directly yet. There is no V1 macOS installer planned.
Default-browser use is the expected workflow, and LitLaunch source workflows
are intended to provide the same profile, diagnostics, event-log, and support
artifact benefits where dependencies are available. Safari-style web-app usage
may work as a user-managed beta workflow, but RoleThread does not automate it
in V1.

**Unknown platforms are unsupported.**

RoleThread should degrade gracefully where possible, but unsupported platforms should not be assumed to have platform-specific integrations.

## Official Python Runtime

RoleThread Lite V1 officially supports Python 3.14.5.

Python 3.14.4 remains the minimum supported V1 runtime. Older Python versions
are blocked so the app fails clearly instead of producing confusing import or
dependency errors later.

Newer Python versions may run, but they are untested for V1 unless documented later.

Manual Linux/macOS users should create their environment with `python3.14`.
Windows development users should use `py -3.14`.

RoleThread Lite V1 is tested against Streamlit 1.57.x. Source installs should
use `requirements.txt` so the app stays on the tested Streamlit line.

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

RoleThread V1 defines platform-aware launch policy and diagnostics without
making the app itself own browser or process orchestration.

The Windows installer opens RoleThread as a local app-style window through the
packaged launcher. LitLaunch handles the local runtime profile, keeps the app
bound to `127.0.0.1`, and opens a Microsoft Edge app-style window when Edge is
available.

Source Windows users can launch the same app-window profile with:

```bat
python -m litlaunch.cli run --profile rolethread-webapp
```

Linux and macOS source users can use the browser-mode LitLaunch profile for
managed local runtime behavior without the Windows packaged app-window:

```bat
python -m litlaunch.cli run --profile rolethread-browser
```

Normal browser mode remains available through:

```bat
streamlit run app.py
```

When RoleThread is running, open **Support -> Diagnostics** for the integrated
runtime/support view. It shows LitLaunch posture, operational snapshot,
RoleThread product context, support artifact actions, and runtime event
history.

Source users can also generate a LitLaunch diagnostics report:

```bat
python -m litlaunch report --profile rolethread-webapp --force
```

Reports and bundles are written under `.litlaunch/reports/` and are support
artifacts, not telemetry. Review generated artifacts before sharing because
local paths and runtime metadata may appear.

Linux and macOS use source/manual workflows in V1, but LitLaunch is still useful
there for profile loading, browser-mode runtime ownership, diagnostics, support
artifacts, and runtime event logging. If you want an app-style window on those
platforms, use your browser's built-in install or shortcut option manually.

Windows:

- installed workflow: local Microsoft Edge app window
- source app-window workflow: `python -m litlaunch.cli run --profile rolethread-webapp`
- source browser workflow: `streamlit run app.py`

Linux:

- preferred workflow: source launch with `streamlit run app.py` or `python -m litlaunch.cli run --profile rolethread-browser`
- fallback: manually open the local Streamlit URL
- manual/git-clone setup is expected for V1

macOS:

- preferred workflow: source launch with `streamlit run app.py` or `python -m litlaunch.cli run --profile rolethread-browser`
- fallback: manually open the local Streamlit URL
- Safari-style web-app use is user-managed and beta
- no V1 installer is planned

Unknown platforms:

- unsupported
- browser behavior should degrade gracefully

## Where To Check This In The App

Open **Support -> Diagnostics** for product, platform, support, and Python
runtime details. That page shows:

- runtime posture
- operational snapshot
- storage paths
- cloud backup status
- product logs and support artifact locations
- LitLaunch diagnostics and runtime event history

Settings owns preferences. Diagnostics owns support detail.
