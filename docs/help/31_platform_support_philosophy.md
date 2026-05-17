# Platform Support Philosophy

RoleThread Lite is local-first software. Platform support is designed around that fact.

The app should run predictably, store data in understandable locations, and avoid pretending every operating system supports the same integrations.

## Windows

Windows is a primary supported platform for V1.

It is also the first installer target.

Windows support includes:

- platform-native app data paths under `%LOCALAPPDATA%\RoleThread`
- user workspace defaults under `%USERPROFILE%\RoleThread`
- Windows launcher and PyInstaller bundle work
- managed Microsoft Edge webapp mode
- future Inno Setup installer work

The Windows launcher/installer path is prioritized because normal Windows users should not need to understand Python, virtual environments, Streamlit commands, or dependency setup.

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

RoleThread Lite is designed to degrade gracefully on macOS, but direct maintainer testing is limited. The expected workflow is similar to Linux: manual setup, local files, and default browser usage.

macOS installer behavior is not planned for V1.

## Webapp Mode

Managed webapp mode is Windows/Microsoft Edge only.

The reason is practical: the current implementation depends on Windows process and window metadata so RoleThread can open the Edge app window and, when safe, close the duplicate normal browser window Streamlit may create.

On unsupported platforms, the `webapp` flag should not crash. It should continue in normal browser mode and explain that managed webapp mode is Windows Edge only.

## Storage Policy

RoleThread keeps install/runtime files separate from user data.

Internal app state uses platform-native locations. User-facing datasets, exports, imports, and backups live in workspace folders that users can understand.

Cloud sync folders are treated as optional backup or sync targets, not preferred live working directories. This avoids file locking, constant sync churn, partial upload states, and conflict behavior controlled by third-party sync clients.

## Why Support Is Explicit

RoleThread Lite does not try to hide platform differences behind vague abstraction.

Different systems have different expectations around installers, browsers, filesystem locations, cloud folders, and desktop integration. The app uses centralized platform capability metadata so UI and launch behavior can adapt without scattered operating-system checks.

The priority is maintainability over pretending every platform should receive every integration at once.

Advanced or experimental platform workflows may eventually fit more naturally in RoleThread Studio, where heavier runtime and orchestration systems can be explored without making Lite harder to maintain.

