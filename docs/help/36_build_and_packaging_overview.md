# Build and Packaging Overview

RoleThread Lite packaging supports two execution models:

- bundled Windows install for normal users
- source checkout for contributors and technical users

The bundled path removes Python, virtual environment, pip, and Streamlit command
knowledge from the installed-user workflow. The source path remains available
for contributors and technical users who want direct control over runtime
dependencies.

## Packaging Direction

The V1 Windows packaging direction is:

- PyInstaller one-folder bundle for the launcher, app, bundled Python runtime,
  Streamlit runtime, project code, docs, assets, and dependency metadata
- Inno Setup for the final Windows setup executable
- GitHub Releases for publishing generated installer artifacts

The installer packages a tested release snapshot. It does not clone from Git,
pull source code, or depend on system Python.

## Bundled Runtime Philosophy

The bundled Windows app includes the runtime and dependencies needed to start
RoleThread. The installed shortcut targets `RoleThreadLauncher.exe`, not
`streamlit`, `python`, or `app.py` directly.

The bundle includes the bundled Python runtime and bundled Streamlit runtime
needed by the installed app.

The bundle is intentionally one-folder rather than one-file. That keeps
dependency extraction simpler, makes missing-data issues easier to diagnose,
and matches the current Inno packaging model.

Manual source workflows remain available for power users, contributors, and Linux/macOS users.

## Development Environment

The current development environment expects a project-local virtual environment:

```text
.venv/
```

Runtime dependencies live in `requirements.txt`. Developer/build dependencies belong in `requirements-dev.txt` when they are not needed by normal app runtime.

Development launch workflows may use:

- `streamlit run app.py`
- `python -m litlaunch.cli run --profile rolethread-webapp`
- `python -m litlaunch.cli inspect --profile rolethread-webapp`
- `.venv\Scripts\python.exe installer\windows\launcher\rolethread_launcher.py`
- scripts under `installer/windows/scripts/`

Launcher and build scripts are source-controlled because they define the build. Generated bundles are not source-controlled.

## Build Scripts

Windows build helpers live under:

```text
installer/windows/scripts/
```

Scripts should print useful status, fail clearly, and avoid hiding packaging assumptions.

The current PyInstaller script produces a one-folder launcher bundle. Installer
passes consume that output without changing app runtime behavior.

For most contributor and release-test work, do not edit installer or launcher
source. Build with the scripts:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_installer.ps1
```

That command rebuilds the PyInstaller bundle first, validates the bundled
version against the source tree, then runs Inno Setup. Use the lower-level
bundle script only when you specifically need to smoke-test the one-folder
bundle before packaging:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\scripts\build_bundle.ps1
```

Treat `installer/windows/launcher/`, the PyInstaller spec, and the Inno script
as lifecycle-sensitive code. Touch them only when the change requires launcher
or installer behavior changes and you understand the packaged LitLaunch
boundary, backend-provider wiring, and stale-bundle safety implications.

## Generated Artifacts

Generated artifacts do not belong in Git.

That includes:

- PyInstaller `build/` output
- PyInstaller `dist/` output
- Inno Setup `Output/` folders
- generated setup executables
- temporary packaging folders

Final setup executables belong in GitHub Releases after a release build is
tested. Generated bundles and setup executables should not be committed to the
source tree.

## Release Workflow

The expected early release flow is manual:

1. bump and tag the release
2. build the Inno Setup installer prototype, which rebuilds the PyInstaller bundle by default
3. smoke-test the bundled app outside the repository when needed
4. verify the setup executable packages the same version as the source tree
5. test install, launch, uninstall, and data preservation behavior
6. upload the setup executable to GitHub Releases

The installer build script validates bundle freshness before Inno packaging. It
compares the source-tree `core/version.py` value with the bundled
`_internal/core/version.py` value and refuses to build the setup executable when
they differ. Reusing an existing bundle requires an explicit opt-out and still
runs the version check.

This guard exists because installer testing once packaged an older PyInstaller
bundle into a newer setup executable. The stale backend looked healthy on port
`8501`, but it was running old app code. Rebuilding the bundle by default and
checking source/bundle versions prevents updates from silently shipping stale
runtime behavior.

The Windows installer always launches through the packaged RoleThread launcher.
That wrapper loads the RoleThread LitLaunch profile and delegates runtime
behavior to LitLaunch. The installer does not offer a runtime selector.

On some Windows systems, the setup wizard may appear behind other windows after
the UAC prompt. If setup does not appear immediately, minimize other windows or
check the taskbar for the RoleThread Lite installer.

Normal uninstall preserves RoleThread user data by default. The uninstaller can
also remove local RoleThread app data and workspace folders when the user
explicitly confirms that destructive option. That same removal path is the
clean-state workflow for installer testing.

Cloud backup copies outside those local RoleThread folders are preserved.

The local data-removal prompts are part of the real Windows uninstall path,
such as Windows Installed apps, Control Panel, or the Start Menu **RoleThread
Uninstaller** shortcut. Rerunning the setup executable uses Inno Setup's
install/maintenance path and should not be treated as the data-removal flow.

CI/CD may automate pieces later; the source tree should stay free of generated artifacts either way.

## Current Status

Packaging is still evolving before V1. The architecture is fixed around a
bundled Windows app plus a source-based contributor workflow. Installer UX may
continue to improve across Windows and Edge machine differences, but the
runtime boundary is stable: installer builds package release snapshots, while
source users run either plain Streamlit or the LitLaunch app-window profile.

