# Windows Installer and Launcher Architecture

The Windows launcher is separate from the Streamlit app on purpose.

RoleThread Lite is still a local Streamlit application internally, but normal installed users should start it like a desktop app. The launcher is the bridge between those worlds.

## Launcher Responsibilities

At a high level, the Windows launcher owns startup orchestration.

It is responsible for:

- finding the app root
- choosing the bundled runtime or development runtime
- reading RoleThread preferences
- deciding normal launch mode versus webapp launch mode
- starting the Streamlit app
- writing launcher logs
- reporting startup failures clearly

The launcher should stay focused on startup. It should not duplicate business logic from the app.

## Preferences and Launch Mode

The launcher reads the stored preference for webapp launch mode.

If webapp launch mode is disabled or preferences are missing, the launcher starts RoleThread in normal browser mode.

If webapp launch mode is enabled, the launcher passes the app's `webapp` flag into startup. The app's launch path then owns Microsoft Edge detection, Edge app-window launch, and duplicate-browser cleanup behavior.

This keeps one source of truth for webapp behavior.

## PyInstaller Windowed Bundle

The bundled launcher is built as a PyInstaller one-folder executable.

The packaged launcher is windowed/no-console so double-clicking it feels like launching a normal Windows app. Because no terminal is visible, launcher logging is the primary diagnostic channel.

Launcher logs should capture:

- app root detection
- bundled-mode status
- selected runtime
- preference path
- selected launch mode
- full startup command
- subprocess PID
- startup errors

## Webapp Mode Boundary

Managed webapp mode is Windows/Microsoft Edge only.

That boundary exists because the current cleanup behavior depends on Windows process and window metadata. On unsupported platforms, RoleThread should continue in normal browser mode and explain the fallback rather than attempting Windows-only inspection.

The launcher should not invent its own browser cleanup. It should call the app's supported startup path and let the app decide what is safe.

## Installer Responsibilities

The future Inno Setup installer will install the bundled app files and create shortcuts to the wrapped launcher.

The installer should keep app/runtime files separate from user data. Default uninstall should remove installed app files while preserving datasets, preferences, exports, backups, logs, and cache unless the user explicitly chooses a full data removal option in a future installer pass.

## Graceful Shutdown Direction

Shutdown lifecycle remains a future area.

The long-term launcher direction is to own the Streamlit subprocess, detect normal exit conditions where practical, and leave room for graceful cleanup before forceful termination is ever considered.

For now, the important rule is simple: launcher startup should be reliable, observable through logs, and conservative about behavior it does not yet own.

