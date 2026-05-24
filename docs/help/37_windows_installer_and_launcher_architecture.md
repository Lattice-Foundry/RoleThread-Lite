# Windows Installer and Launcher Architecture

The Windows packaged launcher is RoleThread's product wrapper around
LitLaunch. It exists so installed users can start RoleThread from a normal
shortcut without knowing about Python, virtual environments, Streamlit, or
source checkout paths.

LitLaunch owns runtime/platform behavior. RoleThread owns product packaging and
presentation.

## Architecture Boundary

The installed path is:

```text
RoleThreadLauncher.exe
-> RoleThread packaged wrapper
-> LitLaunch monitored runtime
-> Streamlit app
```

The source/dev app-window path uses the `rolethread-webapp` profile in
`litlaunch.toml`:

```bat
python -m litlaunch.cli run --profile rolethread-webapp
```

Both paths should express the same product choices: app title, host, port,
headless Streamlit behavior, browser policy, logging expectations, and shutdown
hooks.

## What RoleThread Owns

The packaged launcher owns only RoleThread-specific packaging concerns:

- frozen app-root and resource resolution
- packaged backend provider construction
- product log path selection
- environment values needed by app-side product cleanup
- branded startup failure messages
- installer-facing behavior such as shortcuts and uninstall expectations

It should not build a second runtime platform. No custom browser stack, no
parallel monitor loop, no private shutdown protocol. LitLaunch already owns
that machinery, and the maintenance bill has been paid once.

## What LitLaunch Owns

LitLaunch owns the generic Streamlit runtime platform:

- profile loading
- command planning
- backend startup
- health checks
- browser/app-window launch
- window observation
- graceful shutdown
- backend stop escalation
- diagnostics and inspect reports

RoleThread docs should explain how RoleThread uses those capabilities, not
repeat their internals.

## Packaged Backend Provider

Source launch can use the normal Python/Streamlit command shape. A frozen app
cannot assume the same command.

The packaged launcher supplies a LitLaunch backend provider that starts the
bundled executable in its internal Streamlit mode. That keeps installed users
independent of system Python and repository paths while still allowing
LitLaunch to own runtime planning and session behavior.

## Logging and Diagnostics

The packaged launcher is windowed/no-console. The product log is therefore the
main support path for startup failures:

```text
%LOCALAPPDATA%\RoleThread\logs\launcher.log
```

Source/runtime diagnostics use LitLaunch reports:

```bat
python -m litlaunch report --profile rolethread-webapp --force
```

Reports are written under `.litlaunch/reports/` and are useful for profile,
command, browser, health, and local runtime questions. They are support
artifacts, not telemetry. Generated reports should stay out of Git and should
be reviewed before sharing; LitLaunch reports runtime posture and configuration,
not application security.

Advanced support workflows can still use:

```bat
python -m litlaunch inspect --profile rolethread-webapp --json
python -m litlaunch inspect --profile rolethread-webapp --bundle
```

Use those when structured output is more useful than a report.

## Shutdown and Cloud Sync

RoleThread product cleanup, such as cloud-sync closeout, is registered through
the runtime shutdown bridge. Cleanup must be idempotent because shutdown can be
requested by normal closeout, failed startup cleanup, or process exit.

LitLaunch owns the shutdown protocol and backend stop behavior. RoleThread
owns what product cleanup should run.

## Installer Responsibilities

The Inno Setup installer installs bundled app files and creates shortcuts to
`RoleThreadLauncher.exe`.

Installer builds rebuild the PyInstaller bundle by default before Inno Setup
packages it. The build script also compares the source-tree app version with
the bundled `_internal/core/version.py` value and stops if they differ. This
prevents a setup executable from accidentally shipping stale app/runtime code.

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

## Smoke Validation

A useful packaged smoke checks:

- bundle includes `app.py`, `litlaunch.toml`, docs, assets, and dependency metadata
- `RoleThreadLauncher.exe` starts without a console requirement
- LitLaunch loads the `rolethread-webapp` profile
- backend health passes at `127.0.0.1:8501`
- the Edge app-style window opens
- closing the window triggers LitLaunch shutdown
- cloud-sync closeout runs once
- backend exits and port `8501` releases
- logs are written under `%LOCALAPPDATA%\RoleThread\logs`

For port checks, a remaining `LISTENING` row on port `8501` is the failure
condition. Short-lived TCP states such as `TIME_WAIT`, `FIN_WAIT_2`, or
`CLOSE_WAIT` can appear briefly after normal closeout.
