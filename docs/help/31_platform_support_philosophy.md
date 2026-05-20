# Platform Support Philosophy

RoleThread Lite uses centralized platform metadata for support levels, capability gates, path defaults, diagnostics, and launch planning.

The app should not scatter raw operating-system checks across UI code.

## Windows

Windows is a primary supported platform for V1 and the first installer target.

Windows support includes:

- platform-native app data paths under `%LOCALAPPDATA%\RoleThread`
- user workspace defaults under `%USERPROFILE%\RoleThread`
- Windows packaged launcher and PyInstaller bundle work
- local Microsoft Edge app-window support through LitLaunch
- Inno Setup installer work

The Windows installer path exists to remove Python, virtual environment,
Streamlit command, and dependency setup from the installed-user workflow.

## Linux

Linux is a primary supported platform for technical and manual workflows.

The expected V1 path is:

- clone the project
- create a Python 3.14 virtual environment
- install dependencies
- run Streamlit manually

Linux uses standard browser workflows. OneDrive integration and Windows Edge
app-window launch are not part of Linux V1 support.

## macOS

macOS is beta/manual support for V1.

RoleThread Lite should degrade gracefully on macOS, but direct maintainer testing is limited. The expected workflow is similar to Linux: manual setup, local files, and default browser usage.

macOS installer behavior is not planned for V1.

## Local App-Window Runtime

RoleThread's installed Windows app opens in a local Microsoft Edge app-style
window when Edge is available.

LitLaunch owns the runtime behavior around that app window: profile-based
startup, browser/app-window launch, local health checks, and shutdown
coordination. RoleThread supplies the product configuration and cleanup hooks.

On unsupported platforms, source users should use plain Streamlit browser mode:
`streamlit run app.py`.

## Storage Policy

RoleThread keeps install/runtime files separate from user data.

Internal app state uses platform-native locations. User-facing datasets, exports, imports, and backups live in workspace folders that users can understand.

Cloud sync folders are treated as optional backup or sync targets, not preferred live working directories. This avoids file locking, constant sync churn, partial upload states, and conflict behavior controlled by third-party sync clients.

## Why Support Is Explicit

RoleThread Lite does not hide platform differences behind vague abstraction.

Different systems have different expectations around installers, browsers, filesystem locations, cloud folders, and desktop integration. The app uses centralized platform capability metadata so UI and launch behavior can adapt without scattered OS checks.

The priority is explicit support behavior over pretending every platform should receive every integration at once.
