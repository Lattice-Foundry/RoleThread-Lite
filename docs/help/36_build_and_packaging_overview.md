# Build and Packaging Overview

RoleThread Lite packaging supports two execution models:

- bundled Windows install for normal users
- source checkout for contributors and technical users

The bundled path removes Python, virtual environment, pip, and Streamlit command knowledge from the installed-user workflow.

## Packaging Direction

The V1 Windows packaging direction is:

- PyInstaller one-folder bundle for the runnable app and bundled runtime
- Inno Setup for the final Windows setup executable
- GitHub Releases for publishing generated installer artifacts

The installer packages a tested release snapshot. It does not clone from Git, pull source code, or depend on system Python.

## Bundled Runtime Philosophy

The bundled Windows app includes the runtime and dependencies needed to start RoleThread.

Manual source workflows remain available for power users, contributors, and Linux/macOS users.

## Development Environment

The current development environment expects a project-local virtual environment:

```text
.venv/
```

Runtime dependencies live in `requirements.txt`. Developer/build dependencies belong in `requirements-dev.txt` when they are not needed by normal app runtime.

Development launch workflows may use:

- `streamlit run app.py`
- `.venv\Scripts\python.exe installer\windows\launcher\rolethread_launcher.py`
- scripts under `installer/windows/scripts/`

Launcher and build scripts are source-controlled because they define the build. Generated bundles are not source-controlled.

## Build Scripts

Windows build helpers live under:

```text
installer/windows/scripts/
```

Scripts should print useful status, fail clearly, and avoid hiding packaging assumptions.

The current PyInstaller script produces a one-folder launcher bundle. Installer passes can consume that output without changing app runtime behavior.

## Generated Artifacts

Generated artifacts do not belong in Git.

That includes:

- PyInstaller `build/` output
- PyInstaller `dist/` output
- Inno Setup `Output/` folders
- generated setup executables
- temporary packaging folders

Final setup executables belong in GitHub Releases after a release build is tested.

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

The Windows installer defaults to the managed Edge webapp launch mode because
that path has the strongest launcher-owned lifecycle behavior. Normal browser
mode remains available by clearing the installer option during setup.

On some Windows systems, the setup wizard may appear behind other windows after
the UAC prompt. If setup does not appear immediately, minimize other windows or
check the taskbar for the RoleThread Lite installer.

Normal uninstall preserves RoleThread user data by default. The uninstaller can
also remove local RoleThread app data and workspace folders when the user
explicitly confirms that destructive option.

Cloud backup copies outside those local RoleThread folders are preserved.

The local data-removal prompts are part of the real Windows uninstall path,
such as Windows Installed apps, Control Panel, or the Start Menu **RoleThread
Uninstaller** shortcut. Rerunning the setup executable uses Inno Setup's
install/maintenance path and should not be treated as the data-removal flow.

CI/CD may automate pieces later; the source tree should stay free of generated artifacts either way.

## Current Status

Packaging is still evolving before V1. The architecture is fixed around a bundled Windows app plus a source-based contributor workflow.

