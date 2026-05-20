# RoleThread Lite Windows Installer Build Notes

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

This launcher source is wrapped by PyInstaller. The Inno installer creates
shortcuts to the wrapped launcher, not to raw terminal commands.

The launcher currently:

- resolves the RoleThread app root for development use
- loads the RoleThread LitLaunch profile from `litlaunch.toml`
- supplies a packaged backend command provider for the frozen executable
- passes product log and shutdown diagnostic environment to the backend
- delegates Streamlit command planning, health checks, browser app-mode launch,
  window monitoring, shutdown, and backend lifecycle to LitLaunch
- writes launcher logs under `%LOCALAPPDATA%\RoleThread\logs\launcher.log`
- reports clearly when `app.py`, `litlaunch.toml`, or bundled runtime resources
  are missing

The app does not receive a raw `webapp` argument. App-window launch semantics
belong to LitLaunch and the packaged launcher remains only a RoleThread product
adapter.

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

The packaged launcher is windowed/no-console. Double-clicking
`RoleThreadLauncher.exe` should not open a terminal window. Development helper
scripts may still show terminal output, but normal bundled startup should use
the browser or Edge webapp window as the visible app surface.

Bundled mode uses the PyInstaller executable as the runtime entry point. The
launcher starts a second internal copy of itself with a private Streamlit
bootstrap flag, then the child process runs the bundled `app.py` through
Streamlit. This keeps normal users independent of local Python, virtual
environment activation, and repository paths.

Bundled webapp mode starts Streamlit with `--server.headless true`, waits for
the health endpoint, then opens Microsoft Edge app mode from the launcher. The
child Streamlit app still receives the `webapp` flag, but it also receives a
launcher-managed environment marker so it does not relaunch Edge during
Streamlit reruns. Normal browser mode does not force headless mode.

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
4. Confirm no terminal window appears.
5. Confirm RoleThread starts on port `8501`.
6. In webapp mode, close the Edge app window and confirm the backend shutdown
   lifecycle and port-release result are logged.
7. If you inspect `netstat -ano | findstr :8501`, treat a `LISTENING` row as
   the failure condition. Temporary `TIME_WAIT`, `FIN_WAIT_2`, or `CLOSE_WAIT`
   rows can remain while Windows and Edge finish closing old TCP connections.
7. Confirm launcher logs are still written under:

```text
%LOCALAPPDATA%\RoleThread\logs\launcher.log
```

The launcher log is the primary diagnostic channel for the windowed bundle. It
records app-root detection, bundled-mode status, runtime path, selected launch
mode, full command, subprocess PID, health checks, exact app-window handle
monitoring, shutdown requests, fallback termination, port-release status, and
startup errors. If startup fails before the app opens, the launcher writes the
error to the log and may show a minimal Windows error dialog pointing to that
log.

Bundled webapp startup also writes app-side breadcrumbs to the same launcher
log. Those entries record whether the `webapp` flag was seen and whether the
session is launcher-managed. These diagnostics are intentionally file-based so
the packaged no-console launcher remains quiet for users.

To smoke-test bundled webapp mode, install with **Use Windows Edge webapp mode
by default (recommended)** selected, then run the bundled launcher. The launcher
should start Streamlit headless, open the initial Edge app window after health
succeeds, and pass the app's `webapp` flag with a launcher-managed marker so the
app does not relaunch Edge during reruns.

## Inno Setup Installer Prototype

The first installer prototype packages the PyInstaller one-folder bundle into a
standard Windows setup executable.

Source-controlled installer files:

```text
installer/windows/inno/rolethread_lite.iss
installer/windows/scripts/build_installer.ps1
```

Prerequisite:

```text
Inno Setup 6
```

Recommended Windows install:

```powershell
winget install --id JRSoftware.InnoSetup -e
```

Build the installer from a fresh PyInstaller bundle:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_installer.ps1
```

`build_installer.ps1` rebuilds the PyInstaller bundle by default before running
Inno Setup. This is the recommended release/test path because it prevents the
setup executable from packaging stale bundled source.

If you need to smoke-test the bundle separately, run:

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

The prototype installer:

- installs bundled app/runtime files under `{autopf}\RoleThread Lite`
- creates a Start Menu shortcut named **RoleThread Lite**
- creates a Start Menu shortcut named **RoleThread Uninstaller**
- offers an optional Desktop shortcut
- registers a normal Windows uninstaller
- offers **Launch RoleThread Lite** after setup completes
- removes installed app/runtime files and shortcuts during normal uninstall
- preserves `%LOCALAPPDATA%\RoleThread` and `%USERPROFILE%\RoleThread`

Installed Windows builds use the managed LitLaunch Edge app-window lifecycle.
Normal source browser mode remains available to developers through
`streamlit run app.py`.

The prototype installer does not yet implement firewall rules, code signing,
auto-update, GitHub Release automation, or final branding polish.

### Uninstall behavior

Normal uninstall removes only the installed app/runtime files, shortcuts, and
Windows uninstall entry. It preserves:

```text
%LOCALAPPDATA%\RoleThread
%USERPROFILE%\RoleThread
```

Use one of the real Windows uninstall paths to access the data-removal prompts:

- Start Menu > RoleThread Lite > **RoleThread Uninstaller**
- Windows Settings > Apps > Installed apps > RoleThread Lite > Uninstall
- Control Panel > Programs and Features > RoleThread Lite > Uninstall

Rerunning `RoleThreadLiteSetup-v<version>.exe` enters the Inno Setup install /
maintenance path. That path may show install tasks such as the webapp launch
option, but it is not the expected place to access uninstall data-removal
prompts.

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

- the launcher loads `litlaunch.toml`
- the launcher supplies the packaged backend command provider
- LitLaunch starts Streamlit headless on `127.0.0.1:8501`
- LitLaunch opens the Edge app-mode window
- logs are appended to `%LOCALAPPDATA%\RoleThread\logs\launcher.log`
- LitLaunch monitors the Edge app window and requests graceful shutdown
- backend exit and shutdown status are logged

Before smoke testing, make sure no other RoleThread/Streamlit process is already
using port `8501`. If the port is busy, the launcher exits with a clear message
instead of starting a second server.

To test source webapp mode, use:

```powershell
python -m litlaunch.cli run --profile rolethread-webapp
```

## Installer Test Reset

Installer testing can create state in the same platform-default locations used
by normal RoleThread runs:

```text
%LOCALAPPDATA%\RoleThread\
%USERPROFILE%\RoleThread\
```

For clean installer testing, use the normal Windows uninstaller and answer
**Yes** when prompted to remove local RoleThread user data. That covers the
two RoleThread-owned user-data roots while keeping cleanup behavior in the real
uninstall path.

The uninstall cleanup does not touch the source repository, `.venv`, `.dev`,
Git data, generated source-tree build artifacts, arbitrary custom paths, or
external/cloud backup destinations.

The launcher is responsible for:

- using the bundled runtime and bundled app files
- loading the RoleThread LitLaunch profile
- supplying the packaged backend command provider
- passing product log and shutdown diagnostic environment
- writing launcher/app logs under `%LOCALAPPDATA%\RoleThread\logs`

LitLaunch owns the shutdown lifecycle for supported webapp runs: it starts the
Streamlit subprocess, waits for health, observes the app window, requests
graceful shutdown when that window closes so cloud sync cleanup can run, then
escalates only for the backend subprocess it started.

For port checks, a remaining `TIME_WAIT`, `FIN_WAIT_2`, or `CLOSE_WAIT` row is
not the same as a stuck backend. The important failure condition is a
`LISTENING` row on port `8501`, especially one owned by `RoleThreadLauncher.exe`.

If a webapp launch never produces a stable app-window handle, LitLaunch does
not leave the backend running indefinitely. It reports the timeout and stops the
backend subprocess it started.

## Uninstall Requirements

Default uninstall should remove installed app/runtime files only.

Default uninstall should preserve:

- `%LOCALAPPDATA%\RoleThread\`
- `%USERPROFILE%\RoleThread\`

The installer offers an explicit full local data removal prompt during
interactive uninstall. That option warns clearly that it deletes RoleThread
user data, including:

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

External/cloud backup copies outside those local RoleThread folders are
preserved.

The data-removal prompts are exposed by the real uninstaller, not by rerunning
the setup executable. The installer also creates a Start Menu shortcut named
**RoleThread Uninstaller** so testers do not have to hunt through Windows
Settings during repeated installer validation.

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

This is installer prototype work. The source-controlled scripts can build a
PyInstaller one-folder launcher bundle and package that bundle into a first
Inno Setup installer executable. The prototype does not yet implement firewall
rules, code signing, auto-update, or release publishing automation.

