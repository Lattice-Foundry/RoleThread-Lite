# Build and Packaging Overview

RoleThread Lite supports two practical audiences:

- normal Windows users who should be able to install and run the app without knowing Python, virtual environments, pip, or Streamlit commands
- technical users and contributors who are comfortable running from Git and managing a development environment

The packaging work exists to serve the first group without removing the second path.

## Packaging Direction

The V1 Windows packaging direction is:

- PyInstaller one-folder bundle for the runnable app and bundled runtime
- Inno Setup for the final Windows setup executable
- GitHub Releases for publishing generated installer artifacts

The installer packages a tested release snapshot. It does not clone from Git, pull source code, or depend on a user's local Python installation.

## Bundled Runtime Philosophy

Normal installed users should not need to think about the Python runtime.

The bundled Windows app should include the runtime and dependencies needed to start RoleThread. That keeps the installed experience closer to a normal desktop app and avoids asking users to troubleshoot virtual environments before they can work with their datasets.

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

The launcher and build scripts are source-controlled because they describe how the app is packaged. Generated bundles are not source-controlled.

## Build Scripts

Windows build helpers live under:

```text
installer/windows/scripts/
```

These scripts should be boring and explicit. They should print useful status, fail clearly, and avoid hiding important packaging assumptions.

The current PyInstaller bundle script produces a one-folder launcher bundle. Future installer passes can build on that output without changing the app's core runtime behavior.

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
2. run the Windows bundle build
3. smoke-test the bundled app outside the repository
4. build the installer when that pass exists
5. test install, launch, uninstall, and data preservation behavior
6. upload the setup executable to GitHub Releases

CI/CD may automate pieces later, but the source tree should stay clean either way.

## Current Status

Packaging is still evolving before V1.

The important architectural direction is already set: normal Windows users get a bundled installed app, while technical users can continue running from source with a managed development environment.

