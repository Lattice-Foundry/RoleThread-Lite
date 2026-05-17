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
- waiting for the Streamlit health endpoint
- monitoring app-window closure where practical
- requesting local token-protected shutdown
- using terminate/kill fallback only after graceful shutdown fails
- writing launcher logs
- reporting startup failures clearly

The launcher should stay focused on startup orchestration. It should not duplicate app business logic.

## Shutdown Lifecycle

Launcher-started sessions receive a generated localhost shutdown port and token.

The app enables a local-only shutdown endpoint only when those launcher-provided environment variables are present. Manual `streamlit run app.py` sessions do not expose the control endpoint.

For supported webapp runs, the launcher lifecycle is:

1. start the Streamlit subprocess
2. wait for `/_stcore/health`
3. monitor the Edge app window through Windows HWND metadata
4. request graceful shutdown after the app window closes
5. wait for app exit hooks to run
6. fall back to `terminate()`
7. use `kill()` only as a last resort

Normal browser mode has limited automatic browser-close detection because default-browser tabs are not consistently attributable to the launcher. In that mode, lifecycle logging records the limitation instead of guessing.

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
- health check result
- app-window close detection result
- shutdown request result
- fallback termination result
- startup errors

## Webapp Mode Boundary

Managed webapp mode is Windows/Microsoft Edge only.

That boundary exists because cleanup depends on Windows process metadata and HWND/window classification. Unsupported platforms fall back to normal browser mode rather than attempting Windows-only inspection.

The launcher should not invent its own browser cleanup. It should call the app's supported startup path and let the app decide what is safe.

## Installer Responsibilities

The Inno Setup installer prototype installs bundled app files and creates shortcuts to the wrapped launcher.

The installer offers **Launch RoleThread Lite as a Windows Edge webapp** as a
checked-by-default option. That option writes an installer seed file containing
only `enable_webapp_launch_mode`. The launcher consumes the seed on first run,
updates the DB-backed setting, removes the seed file, and leaves unrelated
preferences untouched. Users can later change the same preference in **Settings
> Experimental Features**.

The installer keeps app/runtime files separate from user data. Default uninstall removes installed app files and shortcuts while preserving datasets, preferences, exports, backups, logs, and cache. Interactive uninstall can optionally remove local RoleThread data under `%LOCALAPPDATA%\RoleThread` and `%USERPROFILE%\RoleThread` after a clear warning.

The Developer clean uninstall prompt is currently visible during installer testing. It maps to the same RoleThread-owned local data roots as full local data removal, with stricter testing intent. It does not remove repositories, `.venv`, `.dev`, Git data, generated source-tree build artifacts, arbitrary custom paths, or external/cloud backup destinations.

Cloud backup copies outside the local RoleThread folders are preserved and must be removed manually from the cloud provider or sync folder if desired.

If `RoleThreadLauncher.exe` is still running, the uninstaller asks the user to close RoleThread Lite before continuing. It does not broadly terminate Python, Streamlit, Edge, or unrelated browser processes.

## Graceful Shutdown Direction

Shutdown lifecycle remains future work. The long-term launcher direction is to own the Streamlit subprocess, detect normal exit conditions where practical, and leave room for graceful cleanup before forceful termination.
