# Windows Installer and Launcher Architecture

The Windows launcher is a startup orchestrator around the bundled Streamlit app.

It resolves runtime context, starts the app subprocess, and leaves app-specific behavior inside the application.

## Launcher Responsibilities

It is responsible for:

- finding the app root
- choosing the bundled runtime or development runtime
- reading RoleThread preferences
- deciding normal launch mode versus webapp launch mode
- starting the Streamlit app
- writing launcher logs
- reporting startup failures clearly

The launcher should stay focused on startup orchestration. It should not duplicate app business logic.

## Preferences and Launch Mode

The launcher reads the stored preference for webapp launch mode.

If webapp launch mode is disabled or preferences are missing, the launcher starts RoleThread in normal browser mode.

If webapp launch mode is enabled, the launcher passes the app's `webapp` flag into startup. The app-owned launch path then handles Microsoft Edge detection, Edge app-window launch, and duplicate-browser cleanup.

This keeps one source of truth for webapp behavior and avoids browser-control drift between launcher and app code.

## PyInstaller Windowed Bundle

The bundled launcher is built as a PyInstaller one-folder executable.

The packaged launcher is windowed/no-console. Because no terminal is visible, launcher logging is the primary diagnostic channel.

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

That boundary exists because cleanup depends on Windows process metadata and HWND/window classification. Unsupported platforms fall back to normal browser mode rather than attempting Windows-only inspection.

The launcher should not invent its own browser cleanup. It should call the app's supported startup path and let the app decide what is safe.

## Installer Responsibilities

The Inno Setup installer will install bundled app files and create shortcuts to the wrapped launcher.

The installer should keep app/runtime files separate from user data. Default uninstall should remove installed app files while preserving datasets, preferences, exports, backups, logs, and cache unless the user explicitly chooses full data removal.

## Graceful Shutdown Direction

Shutdown lifecycle remains future work. The long-term launcher direction is to own the Streamlit subprocess, detect normal exit conditions where practical, and leave room for graceful cleanup before forceful termination.
