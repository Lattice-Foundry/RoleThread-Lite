# Why RoleThread Uses LitLaunch

RoleThread Lite is a local-first app. Your datasets, sidecars, backups,
settings, and local database stay on your machine unless you configure an
optional backup destination.

That local-first model still needs a dependable app runtime. RoleThread needs
to start cleanly, open in a familiar local app window on Windows, keep the
backend bound to your own computer, shut down without leaving stray processes,
and produce useful diagnostics when support is needed.

LitLaunch provides that runtime layer.

## What LitLaunch Does For RoleThread

LitLaunch handles the app startup and closeout path around RoleThread:

- source launch profiles
- local app-window launch on Windows
- loopback-only local runtime configuration
- startup checks and diagnostics reports
- clean shutdown coordination

RoleThread stays focused on the product work: dataset editing, validation,
repair, backups, cloud backup policy, preferences, and export workflows.

## Source And Installed Launch

Installed Windows users normally launch RoleThread from the Start Menu or
Desktop shortcut. The packaged app uses LitLaunch behind the scenes and opens a
local app-style window.

Source users can run the same profile from a checkout:

```bat
python -m litlaunch.cli run --profile rolethread-webapp
```

Normal Streamlit browser mode is still useful for development:

```bat
streamlit run app.py
```

## Diagnostics

When runtime troubleshooting is needed, source users can generate a LitLaunch
diagnostics report:

```bat
python -m litlaunch report --profile rolethread-webapp --force
```

Reports are written under `.litlaunch/reports/`. Diagnostics are meant to help
explain startup, profile, browser, and local runtime behavior. They are support
artifacts, not telemetry. A generic redaction/privacy warning may appear; review
reports before sharing, especially if your local paths are sensitive. LitLaunch
reports posture and runtime configuration, but it does not secure Streamlit apps
by itself.

## Why This Matters

Earlier RoleThread prototypes proved the need for a stronger local runtime
model. LitLaunch is the reusable version of that work, separated from
RoleThread's dataset logic.

That split keeps RoleThread easier to maintain and makes the app a better
example for other serious Streamlit projects that want a desktop-style local
experience without rebuilding runtime infrastructure from scratch.
