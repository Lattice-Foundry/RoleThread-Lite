# RoleThread Lite Windows Installer Build Notes

This folder contains the source-controlled Windows packaging and installer
workflow for RoleThread Lite.

The Windows installer is the normal path for non-technical Windows users. It
packages a tested release snapshot and does not depend on Git, system Python,
virtual environments, pip, or manual Streamlit commands on the user's machine.

## Packaging Stack

- **PyInstaller one-folder bundle** for the packaged launcher, app files,
  dependency metadata, docs, assets, and bundled runtime resources.
- **Inno Setup** for the final Windows setup executable.
- **GitHub Releases** for publishing tested setup executables.

The installed shortcut targets `RoleThreadLauncher.exe`.

## Runtime Boundary

RoleThread uses LitLaunch for runtime/platform behavior.

The packaged launcher owns RoleThread-specific packaging concerns:

- app-root and frozen resource resolution
- `litlaunch.toml` discovery
- packaged backend provider construction
- product log path selection
- branded startup failure messages
- installer/shortcut presentation

LitLaunch owns the generic runtime work:

- profile loading
- command planning
- backend startup and health checks
- browser/app-window launch
- window observation
- shutdown coordination
- runtime event logging
- diagnostics, support artifacts, and support bundles

The app does not receive a raw `webapp` argument. `app.py` remains the
Streamlit app entry point, not a launcher.

## Source vs Generated Files

Commit source-controlled packaging files:

- build scripts under `installer/windows/scripts/`
- Inno Setup source scripts under `installer/windows/inno/`
- PyInstaller spec files
- launcher source under `installer/windows/launcher/`
- packaging documentation

Do not commit generated artifacts:

- PyInstaller `build/` or `dist/` output
- Inno `output/` output
- temporary packaging work folders
- generated `.exe` or `.msi` installers

## Installed Layout

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

Keeping install files separate from user data lets upgrades replace app/runtime
files without touching datasets, backups, exports, preferences, logs, or cache.

## Build The PyInstaller Bundle

Build from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_bundle.ps1
```

Expected output folder:

```text
installer\windows\dist\RoleThreadLauncher\
```

Run the bundled app directly:

```powershell
installer\windows\dist\RoleThreadLauncher\RoleThreadLauncher.exe
```

The packaged launcher is windowed/no-console. Double-clicking it should not
open a terminal window.

## Bundle Smoke Test

1. Build the bundle with `build_bundle.ps1`.
2. Copy `installer\windows\dist\RoleThreadLauncher\` to a temporary folder
   outside the repository.
3. Run `RoleThreadLauncher.exe` from the copied folder.
4. Confirm no terminal window appears.
5. Confirm LitLaunch loads the `rolethread-webapp` profile.
6. Confirm RoleThread starts on `127.0.0.1:8501`.
7. Confirm the Edge app-style window opens.
8. Close the app window.
9. Confirm LitLaunch shutdown runs and cloud-sync closeout runs once.
10. Confirm the backend exits and port `8501` releases.
11. Confirm logs are written under:

```text
%LOCALAPPDATA%\RoleThread\logs\launcher.log
```

For port checks, a remaining `LISTENING` row on port `8501` is the important
failure condition. Temporary `TIME_WAIT`, `FIN_WAIT_2`, or `CLOSE_WAIT` rows can
remain while Windows and the browser finish closing old connections.

## Build The Installer

Prerequisite:

```text
Inno Setup 6
```

Recommended Windows install:

```powershell
winget install --id JRSoftware.InnoSetup -e
```

Build the installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_installer.ps1
```

`build_installer.ps1` rebuilds the PyInstaller bundle by default before running
Inno Setup. This is the recommended release/test path because it prevents the
setup executable from packaging stale bundled source.

If you need to smoke-test an existing bundle separately, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_bundle.ps1
```

An existing bundle can be reused only with an explicit opt-out:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_installer.ps1 -UseExistingBundle
```

Even in `-UseExistingBundle` mode, the script compares `core/version.py` from
the source tree with `_internal/core/version.py` inside the bundled app and
fails if the versions do not match.

Expected setup output:

```text
installer\windows\output\RoleThreadLiteSetup-v<version>.exe
```

On some Windows systems, the installer may appear behind other windows after
the UAC prompt. If setup does not appear immediately, minimize other windows or
check the taskbar for the **RoleThread Lite** installer.

## Installed Smoke Test

1. Run the generated setup executable.
2. Install or upgrade to:

```text
C:\Program Files\RoleThread Lite\
```

3. Launch from the Start Menu, Desktop shortcut, or installed
   `RoleThreadLauncher.exe`.
4. Confirm the app opens in the local Edge app-style window.
5. Close the app window.
6. Confirm LitLaunch shutdown runs and cloud-sync closeout runs once.
7. Confirm port `8501` releases.
8. Confirm no orphan RoleThread/Streamlit backend process remains.
9. Confirm logs are written to:

```text
%LOCALAPPDATA%\RoleThread\logs\launcher.log
```

## Source/Dev Launcher Smoke

Run the packaged launcher source from the repository root:

```powershell
.venv\Scripts\python.exe installer\windows\launcher\rolethread_launcher.py
```

Or use the helper script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\run_launcher_dev.ps1
```

Expected behavior:

- launcher loads `litlaunch.toml`
- launcher supplies the packaged backend provider
- LitLaunch starts the backend on `127.0.0.1:8501`
- LitLaunch opens the Edge app-style window
- logs are appended under `%LOCALAPPDATA%\RoleThread\logs`
- closing the window triggers graceful shutdown

To test source profile launch without the packaged wrapper, use:

```powershell
litlaunch --profile rolethread-webapp
```

For diagnostics:

Installed users should normally open **Support -> Diagnostics** in the app.
That page shows runtime summary, operational snapshot, RoleThread product
support context, support artifact actions, and the runtime event trail.

Source/operator workflows can also generate a report directly:

```powershell
litlaunch report --profile rolethread-webapp --force
```

Generated diagnostics reports and bundles are written under
`.litlaunch/reports/` and should stay out of Git. They are support artifacts,
not telemetry. A generic redaction/privacy warning may appear; review artifacts
before sharing because local paths and runtime metadata can still appear.
LitLaunch reports runtime posture and configuration, but it does not secure
Streamlit apps by itself. For advanced support output, use:

```powershell
litlaunch inspect --profile rolethread-webapp --json
litlaunch inspect --profile rolethread-webapp --bundle
```

## Uninstall Behavior

Normal uninstall removes installed app/runtime files, shortcuts, and the
Windows uninstall entry. It preserves:

```text
%LOCALAPPDATA%\RoleThread
%USERPROFILE%\RoleThread
```

Use one of the real Windows uninstall paths to access the data-removal prompts:

- Start Menu > RoleThread Lite > **RoleThread Uninstaller**
- Windows Settings > Apps > Installed apps > RoleThread Lite > Uninstall
- Control Panel > Programs and Features > RoleThread Lite > Uninstall

Rerunning `RoleThreadLiteSetup-v<version>.exe` enters the Inno Setup
install/maintenance path. That path is not the expected place to access
uninstall data-removal prompts.

During interactive uninstall, the uninstaller asks whether to remove local
RoleThread user data. Choosing this option deletes local database/app state,
preferences, logs, cache, training data, imports, exports, backups, and
workspace data under the two RoleThread-owned roots above.

Cloud backup copies stored outside the local RoleThread folders are not
removed. Delete those manually from the cloud provider or sync folder if
desired.

Close RoleThread Lite before uninstalling. If `RoleThreadLauncher.exe` is still
running, the uninstaller asks the user to close RoleThread and stops before
removing files. It does not broadly kill Python, Streamlit, Edge, or unrelated
browser processes.

## Manual Release Flow

Until CI/CD packaging is added, the likely release flow is manual:

1. Update version and changelog.
2. Create a release branch/tag.
3. Build the PyInstaller one-folder bundle locally on Windows.
4. Build the Inno Setup installer locally.
5. Test fresh install, upgrade, normal uninstall, and full uninstall behavior.
6. Open **Support -> Diagnostics** or generate a LitLaunch diagnostics report if
   runtime support data is needed.
7. Upload the generated setup executable to GitHub Releases.

Pushing to `main` does not automatically create installer artifacts unless
CI/CD is added later.

## Current Status

The source-controlled scripts can build a PyInstaller one-folder launcher
bundle and package that bundle into an Inno Setup installer executable. The
installer flow does not implement firewall rules, code signing, auto-update, or
release publishing automation.
