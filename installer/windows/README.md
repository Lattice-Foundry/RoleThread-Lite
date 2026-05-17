# LoreForge Lite Windows Installer Plan

This folder is the source-controlled home for the Windows packaging and installer work.

LoreForge Lite V1 will use a fully bundled Windows installer for normal users. Users who install this way should not need to know about Python, virtual environments, pip, Streamlit, or dependency installation. Manual source-based workflows remain available for developers and power users.

## Target Stack

- **PyInstaller one-folder bundle** for the runnable LoreForge app and bundled Python runtime.
- **Inno Setup** for the final Windows setup executable.
- **GitHub Releases** for publishing final generated setup executables.

The installer does not clone from Git, pull updates, or depend on a user's local Python installation. It packages a tested release snapshot.

## Source vs Generated Files

Commit source-controlled packaging files:

- build scripts under `installer/windows/scripts/`
- Inno Setup source scripts under `installer/windows/inno/`
- future customized PyInstaller `.spec` files
- packaging documentation

Do not commit generated artifacts:

- PyInstaller `build/` or `dist/` output
- Inno `Output/` output
- temporary packaging work folders
- generated `.exe` or `.msi` installers

## Intended Installed Layout

The installed application/runtime files should live separately from user data.

Recommended install directory:

```text
C:\Program Files\LoreForge Lite\
```

Platform-managed app state:

```text
%LOCALAPPDATA%\LoreForge\
```

User workspace:

```text
%USERPROFILE%\LoreForge\
```

Workspace subfolders are expected to include:

- `training_data`
- `exports`
- `imports`
- `backups`

Keeping the install directory separate from user data lets upgrades replace app/runtime files without touching datasets, backups, exports, preferences, logs, or cache.

## Launcher Responsibilities

A first source prototype lives at:

```text
installer/windows/launcher/loreforge_launcher.py
```

This launcher source is intended to be wrapped by PyInstaller in a later pass.
The Inno installer will eventually create shortcuts to the wrapped launcher,
not to raw terminal commands.

The prototype currently:

- resolves the LoreForge app root for development use
- prefers `trainer\Scripts\python.exe` when running from the repository
- reads `%LOCALAPPDATA%\LoreForge\preferences.json`
- uses `enable_webapp_launch_mode` to choose normal or `webapp` launch mode
- starts Streamlit with `python -m streamlit run app.py`
- adds `-- webapp` when webapp launch mode is enabled
- writes launcher logs under `%LOCALAPPDATA%\LoreForge\logs\launcher.log`
- reports clearly when `app.py` is missing, the runtime cannot be found, or port `8501` is already in use

The launcher does not own Microsoft Edge launch or duplicate-browser cleanup.
It delegates that behavior to the app's existing internal `webapp` startup
path.

## Dev Launcher Smoke Test

Run the launcher prototype from the repository root:

```powershell
trainer\Scripts\python.exe installer\windows\launcher\loreforge_launcher.py
```

Or use the helper script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\run_launcher_dev.ps1
```

Expected behavior:

- the launcher uses `trainer\Scripts\python.exe`
- the launcher reads `%LOCALAPPDATA%\LoreForge\preferences.json`
- `enable_webapp_launch_mode: false` or missing preferences starts normal browser mode
- `enable_webapp_launch_mode: true` adds the app's `webapp` launch flag
- logs are appended to `%LOCALAPPDATA%\LoreForge\logs\launcher.log`

Before smoke testing, make sure no other LoreForge/Streamlit process is already
using port `8501`. If the port is busy, the launcher exits with a clear message
instead of starting a second server.

To test webapp mode, enable **Settings > Experimental Features > Enable webapp
launch mode**, close LoreForge, then run the launcher again. The launcher only
chooses the startup flag; Edge app mode and duplicate-browser cleanup still
belong to the app's `webapp` startup path.

The launcher should eventually:

- use the bundled runtime and bundled app files
- start LoreForge/Streamlit locally
- read `enable_webapp_launch_mode` from preferences
- launch either normal browser mode or Windows Edge webapp mode
- use the existing internal `webapp` flag for managed Edge webapp startup
- write launcher/app logs under `%LOCALAPPDATA%\LoreForge\logs`
- keep local server startup, readiness detection, browser/webapp launch, and shutdown lifecycle under launcher control

The current in-app `webapp` flag remains the internal launch path future launcher/installer procedures should call when webapp mode is enabled.

Future graceful shutdown work should make the launcher own the Streamlit
subprocess, detect app-window/browser shutdown where practical, request a
normal app shutdown so `atexit` and cloud sync cleanup can run, and use forceful
termination only as a fallback.

## Uninstall Requirements

Default uninstall should remove installed app/runtime files only.

Default uninstall should preserve:

- `%LOCALAPPDATA%\LoreForge\`
- `%USERPROFILE%\LoreForge\`

The installer may later offer an explicit full uninstall option. That option must warn clearly that it deletes LoreForge user data, including:

- datasets
- exports
- imports
- backups
- preferences
- logs
- cache
- local database/app state

Full uninstall targets:

```text
%LOCALAPPDATA%\LoreForge\
%USERPROFILE%\LoreForge\
```

## Expected Manual Release Flow

Until CI/CD packaging is added, the likely release flow is manual:

1. Update version and changelog.
2. Create a release branch/tag.
3. Build the PyInstaller one-folder bundle locally on Windows.
4. Build the Inno Setup installer locally.
5. Test fresh install, upgrade, normal uninstall, and full uninstall behavior.
6. Upload the generated setup executable to GitHub Releases.

Pushing to `main` does not automatically create installer artifacts unless CI/CD is added later.

## Current Status

This is still pre-packaging work. It does not build the final launcher executable, PyInstaller bundle, Inno installer, bundled Python runtime, shortcuts, or release executable.
