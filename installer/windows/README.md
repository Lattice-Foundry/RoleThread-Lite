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

The final Windows launcher is not implemented in this skeleton pass.

The launcher should eventually:

- use the bundled runtime and bundled app files
- start LoreForge/Streamlit locally
- read `enable_webapp_launch_mode` from preferences
- launch either normal browser mode or Windows Edge webapp mode
- use the existing internal `webapp` flag for managed Edge webapp startup
- write launcher/app logs under `%LOCALAPPDATA%\LoreForge\logs`
- keep local server startup, readiness detection, browser/webapp launch, and shutdown lifecycle under launcher control

The current in-app `webapp` flag remains the internal launch path future launcher/installer procedures should call when webapp mode is enabled.

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

This is a planning and scaffolding pass only. It does not build the final launcher, PyInstaller bundle, Inno installer, bundled Python runtime, shortcuts, or release executable.

