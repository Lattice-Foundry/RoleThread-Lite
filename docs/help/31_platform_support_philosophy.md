# Platform Support Philosophy

RoleThread Lite uses centralized platform metadata for support levels, capability gates, path defaults, diagnostics, and launch planning.

The app should not scatter raw operating-system checks across UI code.

## Windows

Windows is a primary supported platform for V1 and the first installer target.

Windows support includes:

- platform-native app data paths under `%LOCALAPPDATA%\RoleThread`
- user workspace defaults under `%USERPROFILE%\RoleThread`
- Windows launcher and PyInstaller bundle work
- managed Microsoft Edge app-window lifecycle
- future Inno Setup installer work

The Windows launcher/installer path exists to remove Python, virtual environment, Streamlit command, and dependency setup from the installed-user workflow.

## Linux

Linux is a primary supported platform for technical and manual workflows.

The expected V1 path is:

- clone the project
- create a Python 3.14 virtual environment
- install dependencies
- run Streamlit manually

Linux uses standard browser workflows. OneDrive integration and managed Edge webapp mode are not part of Linux V1 support.

## macOS

macOS is beta/manual support for V1.

RoleThread Lite should degrade gracefully on macOS, but direct maintainer testing is limited. The expected workflow is similar to Linux: manual setup, local files, and default browser usage.

macOS installer behavior is not planned for V1.

## Managed Webapp Mode

Managed webapp mode is Windows/Microsoft Edge only.

The implementation depends on Windows process metadata and HWND/window
inspection so RoleThread can open the Edge app window, monitor the exact window
handle, and shut down the launcher-owned Streamlit backend cleanly.

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
