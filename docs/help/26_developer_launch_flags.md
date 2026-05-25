# Developer Launch and Diagnostics

RoleThread has three source launch paths:

- `python -m litlaunch.cli run --profile rolethread-webapp` for the LitLaunch app-window profile
- `python -m litlaunch.cli run --profile rolethread-browser` for a secondary LitLaunch browser smoke profile
- `streamlit run app.py` for plain Streamlit browser development

Use `rolethread-webapp` when testing the same runtime shape used by the
installed Windows app. Use `rolethread-browser` when you want LitLaunch runtime
ownership in a regular browser window. Use plain Streamlit when working on app
UI behavior and you do not need LitLaunch runtime ownership.

## Official LitLaunch App-Window Profile

```bat
python -m litlaunch.cli run --profile rolethread-webapp
```

This command loads `litlaunch.toml` and lets LitLaunch own runtime behavior:
command planning, backend startup, health checks, browser/app-window launch,
window observation, runtime event logging, shutdown coordination, and
diagnostics.

RoleThread's job is narrower: provide product settings, app title, local paths,
cloud-sync shutdown hooks, and packaged-mode configuration where needed.
`app.py` should remain launch-semantics-blind. Do not pass a custom `webapp`
argument through `streamlit run`.

## Secondary Browser Smoke Profile

```bat
python -m litlaunch.cli run --profile rolethread-browser
```

This profile is developer-oriented. It opens RoleThread through LitLaunch in a
regular browser window, still bound to `127.0.0.1`, and is useful for browser
mode smoke testing. It is not the normal installed-user path and should not be
presented as the primary source launch command.

## LitLaunch Diagnostics

Use **Support -> Diagnostics** in the running app for the full RoleThread
support surface: LitLaunch runtime posture, operational snapshot, support
artifacts, RoleThread storage/cloud/data context, and the runtime event trail.

Use LitLaunch report when you need a support artifact without launching the
app:

```bat
python -m litlaunch report --profile rolethread-webapp --force
```

Reports and bundles are written under `.litlaunch/reports/`. They are support
artifacts, not telemetry. LitLaunch may show a generic redaction/privacy warning
so you review local paths before sharing. Redaction is pattern-based; local
paths and runtime metadata may still appear. LitLaunch reports runtime posture
and configuration; it does not secure a Streamlit app by itself.

Advanced support workflows can still inspect structured profile data:

```bat
python -m litlaunch inspect --profile rolethread-webapp --json
python -m litlaunch inspect --profile rolethread-webapp --bundle
```

Diagnostics are useful for profile loading, command planning, browser policy,
health URLs, and local runtime configuration.

## Generated Diagnostics Page

RoleThread commits the generated LitLaunch diagnostics page as app-owned UI and
adds a small RoleThread product diagnostics layer around it. That layer supplies
storage paths, cloud backup status, product log locations, data-health signals,
and other support facts that are specific to RoleThread.

The generated page should stay close to LitLaunch's output. RoleThread may add
product panels and navigation wiring, but it should not fork LitLaunch runtime
internals into the app.

## Plain Streamlit Browser Mode

```bat
streamlit run app.py
```

Use this for Streamlit's normal development loop. Streamlit owns the browser in
this mode. LitLaunch app-window monitoring and shutdown coordination are not
part of this path.

## App Developer Diagnostics

Use **Support -> Diagnostics** for RoleThread product diagnostics, LitLaunch
runtime diagnostics, support artifacts, and the runtime event trail. Runtime
event logs are written as local support data and surfaced in the page as
session replay rather than raw console text.

The older app-side `dev` flag is intentionally not the primary diagnostics
surface. Runtime and storage support details now live in the Diagnostics page so
Settings can stay focused on user preferences.

## Installed Runtime

Installed Windows builds start through `RoleThreadLauncher.exe`. That executable
is a thin product wrapper around LitLaunch:

- it resolves frozen app paths
- it loads the RoleThread LitLaunch profile
- it supplies the packaged backend provider
- it points logs and support output at RoleThread locations
- it shows branded startup failures

LitLaunch owns the runtime lifecycle. RoleThread should not rebuild browser,
monitor, backend, or shutdown orchestration around it. That way lies the tiny
maintenance dungeon, and we have already escaped it.
