# RoleThread Lite Windows Installer Plan

This folder is the source-controlled home for the Windows packaging and installer work.

RoleThread Lite V1 will use a fully bundled Windows installer for normal users. Users who install this way should not need to know about Python, virtual environments, pip, Streamlit, or dependency installation. Manual source-based workflows remain available for developers and power users.

## Target Stack

- **PyInstaller one-folder bundle** for the runnable RoleThread app and bundled Python runtime.
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
C:\Program Files\RoleThread Lite\
```

Platform-managed app state:

```text
%LOCALAPPDATA%\RoleThread\
```

User workspace:

```text
%USERPROFILE%\RoleThread\
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
installer/windows/launcher/rolethread_launcher.py
```

This launcher source is intended to be wrapped by PyInstaller in a later pass.
The Inno installer will eventually create shortcuts to the wrapped launcher,
not to raw terminal commands.

The prototype currently:

- resolves the RoleThread app root for development use
- prefers `.venv\Scripts\python.exe` when running from the repository
- reads `%LOCALAPPDATA%\RoleThread\preferences.json`
- uses `enable_webapp_launch_mode` to choose normal or `webapp` launch mode
- starts Streamlit with `python -m streamlit run app.py`
- adds `-- webapp` when webapp launch mode is enabled
- writes launcher logs under `%LOCALAPPDATA%\RoleThread\logs\launcher.log`
- reports clearly when `app.py` is missing, the runtime cannot be found, or port `8501` is already in use

The launcher does not own Microsoft Edge launch or duplicate-browser cleanup.
It delegates that behavior to the app's existing internal `webapp` startup
path.

## PyInstaller Bundle Prototype

The first bundled prototype builds the launcher in PyInstaller one-folder mode.
The bundle target is the launcher, not `app.py` directly.

Source-controlled packaging files:

```text
installer/windows/rolethread_launcher.spec
installer/windows/scripts/build_bundle.ps1
```

Build from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_bundle.ps1
```

Expected output folder:

```text
installer\windows\dist\RoleThreadLauncher\
```

Run the bundled prototype:

```powershell
installer\windows\dist\RoleThreadLauncher\RoleThreadLauncher.exe
```

Bundled mode uses the PyInstaller executable as the runtime entry point. The
launcher starts a second internal copy of itself with a private Streamlit
bootstrap flag, then the child process runs the bundled `app.py` through
Streamlit. This keeps normal users independent of local Python, virtual
environment activation, and repository paths.

The one-folder bundle includes:

- launcher source
- `app.py`
- `core/`
- `services/`
- `ui/`
- `docs/`
- Streamlit configuration
- runtime dependencies collected by PyInstaller

Generated `build/` and `dist/` folders remain ignored and should not be
committed.

### Bundle Smoke Test

1. Build the bundle with `build_bundle.ps1`.
2. Copy `installer\windows\dist\RoleThreadLauncher\` to a temporary folder
   outside the repository.
3. Run `RoleThreadLauncher.exe` from the copied folder.
4. Confirm RoleThread starts on port `8501`.
5. Confirm launcher logs are still written under:

```text
%LOCALAPPDATA%\RoleThread\logs\launcher.log
```

To smoke-test bundled webapp mode, enable **Settings > Experimental Features >
Enable webapp launch mode**, close RoleThread, then run the bundled launcher
again. The launcher should pass the app's `webapp` flag through the same
internal startup path used by source/dev mode.

## Dev Launcher Smoke Test

Run the launcher prototype from the repository root:

```powershell
.venv\Scripts\python.exe installer\windows\launcher\rolethread_launcher.py
```

Or use the helper script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\run_launcher_dev.ps1
```

Expected behavior:

- the launcher uses `.venv\Scripts\python.exe`
- the launcher reads `%LOCALAPPDATA%\RoleThread\preferences.json`
- `enable_webapp_launch_mode: false` or missing preferences starts normal browser mode
- `enable_webapp_launch_mode: true` adds the app's `webapp` launch flag
- logs are appended to `%LOCALAPPDATA%\RoleThread\logs\launcher.log`

Before smoke testing, make sure no other RoleThread/Streamlit process is already
using port `8501`. If the port is busy, the launcher exits with a clear message
instead of starting a second server.

To test webapp mode, enable **Settings > Experimental Features > Enable webapp
launch mode**, close RoleThread, then run the launcher again. The launcher only
chooses the startup flag; Edge app mode and duplicate-browser cleanup still
belong to the app's `webapp` startup path.

The launcher should eventually:

- use the bundled runtime and bundled app files
- start RoleThread/Streamlit locally
- read `enable_webapp_launch_mode` from preferences
- launch either normal browser mode or Windows Edge webapp mode
- use the existing internal `webapp` flag for managed Edge webapp startup
- write launcher/app logs under `%LOCALAPPDATA%\RoleThread\logs`
- keep local server startup, readiness detection, browser/webapp launch, and shutdown lifecycle under launcher control

The current in-app `webapp` flag remains the internal launch path future launcher/installer procedures should call when webapp mode is enabled.

Future graceful shutdown work should make the launcher own the Streamlit
subprocess, detect app-window/browser shutdown where practical, request a
normal app shutdown so `atexit` and cloud sync cleanup can run, and use forceful
termination only as a fallback.

## Uninstall Requirements

Default uninstall should remove installed app/runtime files only.

Default uninstall should preserve:

- `%LOCALAPPDATA%\RoleThread\`
- `%USERPROFILE%\RoleThread\`

The installer may later offer an explicit full uninstall option. That option must warn clearly that it deletes RoleThread user data, including:

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
%LOCALAPPDATA%\RoleThread\
%USERPROFILE%\RoleThread\
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
