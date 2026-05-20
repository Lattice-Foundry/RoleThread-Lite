# Windows Installer and Launcher Architecture

The Windows launcher is the packaged adapter for RoleThread's managed webapp
lifecycle.

LitLaunch owns the desktop/webapp lifecycle: backend startup, health readiness,
browser app-mode launch, window monitoring, graceful shutdown, fallback
termination, and runtime diagnostics. RoleThread owns packaged path resolution,
the packaged backend provider, product log paths, and branded failure messages.

## Architecture Boundary

The current installed path is:

```text
RoleThreadLauncher.exe
-> RoleThread packaged adapter
-> LitLaunch monitored webapp runtime
-> managed app window
-> Streamlit runtime
```

The source/dev path uses the `rolethread-webapp` profile in `litlaunch.toml`.
The packaged launcher stays Windows-specific where it must: frozen path
resolution, PyInstaller resource layout, packaged backend command construction,
log paths, and installer assumptions.

## Launcher Responsibilities

The launcher is responsible for:

- resolving app root and bundled runtime paths
- loading the RoleThread LitLaunch profile
- supplying the packaged backend command provider
- passing product log and shutdown diagnostic environment
- reporting startup failures clearly

The launcher should not duplicate dataset logic, UI behavior, import/export
rules, LitLaunch command planning, browser launch, window monitoring, or
shutdown protocol behavior.

## Managed Runtime Sequence

Installed and source-managed webapp runs follow the same LitLaunch-owned order:

1. load runtime configuration
2. start Streamlit headless
3. wait for `/_stcore/health`
4. launch Edge app-mode
5. monitor the app window
6. request graceful backend shutdown when the app window closes
7. wait for backend exit hooks
8. fall back to `terminate()` if needed
9. use `kill()` only as a last resort
10. verify and log whether port `8501` was released

Health means the backend is ready to accept traffic. It does not mean a durable
browser/frontend session exists, so browser launch and HWND monitoring remain
separate lifecycle steps.

## Shutdown Control

Launcher-started sessions receive a generated localhost shutdown port and token.

The app enables the shutdown endpoint only when those launcher-provided
environment variables are present. Manual `streamlit run app.py` sessions do
not expose the control endpoint.

Fallback termination targets only the Streamlit subprocess created by the
launcher. The launcher does not broadly kill Edge, Python, Streamlit, unknown
port owners, or arbitrary browser processes.

## Browser Adapter Boundary

Edge is the current supported browser adapter for installed Windows webapp
runs.

Browser adapter code owns Edge discovery, Edge app-mode command construction,
launch execution, and Edge version recording. The launcher lifecycle consumes
that adapter through a browser-launch step instead of hardcoding browser command
details into the orchestration layer.

Future Chrome or Chromium support should extend the browser adapter boundary,
not add parallel launcher flows.

## HWND Monitoring

Edge process IDs are not a reliable app-window abstraction. Chromium-based
browsers can share browser, renderer, utility, and app-mode work across related
processes, and an app window and normal tab can share the same Edge PID.

The stable user-visible object is the top-level Windows window handle. The
launcher therefore tracks the exact app HWND for closeout and backend shutdown
when that metadata is available.

There is no PID/process-kill fallback for browser windows. If classification is
uncertain, RoleThread leaves browser windows alone and only manages the backend
it owns.

## PyInstaller Windowed Bundle

The bundled launcher is built as a PyInstaller one-folder executable.

The packaged launcher is windowed/no-console. Because no terminal is visible,
launcher logging is the primary diagnostic channel.

Launcher logs should capture:

- app root detection
- bundled-mode status
- selected runtime
- full startup command
- subprocess PID
- health check result
- browser adapter launch result
- app-window close detection result
- shutdown request result
- fallback termination result
- final port-release state
- startup errors

## Installer Responsibilities

The Inno Setup installer installs bundled app files and creates shortcuts to
`RoleThreadLauncher.exe`.

Installer builds rebuild the PyInstaller bundle by default before Inno Setup
packages it. The build script also compares the source-tree app version with
the bundled `_internal/core/version.py` value and stops if they differ. This
prevents a setup executable from accidentally shipping stale app/runtime code.

The installer no longer offers a runtime-mode selector. Installed RoleThread
Lite always launches through the managed launcher-owned webapp lifecycle.

The installer keeps app/runtime files separate from user data. Default uninstall
removes installed app files and shortcuts while preserving datasets,
preferences, exports, backups, logs, and cache. Interactive uninstall can
optionally remove local RoleThread data under `%LOCALAPPDATA%\RoleThread` and
`%USERPROFILE%\RoleThread` after a clear warning.

The data-removal prompts appear through the real Windows uninstall path:
Windows Installed apps, Control Panel, or the Start Menu **RoleThread
Uninstaller** shortcut. Rerunning the setup executable is an
install/maintenance flow and is not expected to show the uninstall data-removal
prompts.

Cloud backup copies outside the local RoleThread folders are preserved and must
be removed manually from the cloud provider or sync folder if desired.

If `RoleThreadLauncher.exe` is still running, the uninstaller asks the user to
close RoleThread Lite before continuing. It does not broadly terminate Python,
Streamlit, Edge, or unrelated browser processes.

## Port Release Policy

The launcher should release port `8501` by shutting down the backend it started,
not by attaching to or killing unrelated listeners. Reusing an existing healthy
backend can mask stale installed builds after an update, so the default
lifecycle is shutdown, process exit, and a fresh start on the next launch.

If graceful shutdown does not complete, fallback termination targets only the
launcher-owned Streamlit subprocess. Unknown processes on port `8501` are logged
for diagnosis and left alone.

If a launcher-started webapp session never produces a stable app HWND, the
launcher treats that as a failed startup and terminates only the backend
subprocess it owns. That prevents a failed app-window launch from leaving port
`8501` occupied indefinitely.

When validating shutdown, the key failure condition is a remaining `LISTENING`
row on port `8501`. Residual TCP rows such as `TIME_WAIT`, `FIN_WAIT_2`, or
`CLOSE_WAIT` can appear briefly after Edge and Streamlit close old connections;
those states do not indicate that the backend is still accepting new
connections.

Successful relaunch is also a practical validation signal. If no `LISTENING`
row remains, the launcher process exits, and the app starts cleanly again, the
lifecycle is functioning even if residual TCP rows are still visible.
