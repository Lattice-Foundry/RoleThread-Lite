# Developer Launch and Diagnostics

RoleThread has two source launch paths:

- `python -m litlaunch.cli run --profile rolethread-webapp` for the LitLaunch app-window profile
- `streamlit run app.py` for plain Streamlit browser development

Use the LitLaunch profile path when testing the same runtime shape used by the
installed Windows app. Use plain Streamlit when working on app UI behavior and
you do not need app-window closeout or runtime diagnostics.

## LitLaunch Profile Launch

```bat
python -m litlaunch.cli run --profile rolethread-webapp
```

This command loads `litlaunch.toml` and lets LitLaunch own runtime behavior:
command planning, backend startup, health checks, browser/app-window launch,
window observation, shutdown coordination, and diagnostics.

RoleThread's job is narrower: provide product settings, app title, local paths,
cloud-sync shutdown hooks, and packaged-mode configuration where needed.
`app.py` should remain launch-semantics-blind. Do not pass a custom `webapp`
argument through `streamlit run`.

## LitLaunch Diagnostics

Use LitLaunch report when you need a runtime support artifact without launching
the app:

```bat
python -m litlaunch report --profile rolethread-webapp --force
```

Reports are written under `.litlaunch/reports/`. They are support artifacts,
not telemetry. LitLaunch may show a generic redaction/privacy warning so you
review local paths before sharing. It reports runtime posture and configuration;
it does not secure a Streamlit app by itself.

Advanced support workflows can still inspect structured profile data:

```bat
python -m litlaunch inspect --profile rolethread-webapp --json
python -m litlaunch inspect --profile rolethread-webapp --bundle
```

Diagnostics are useful for profile loading, command planning, browser policy,
health URLs, and local runtime configuration.

## Plain Streamlit Browser Mode

```bat
streamlit run app.py
```

Use this for Streamlit's normal development loop. Streamlit owns the browser in
this mode. LitLaunch app-window monitoring and shutdown coordination are not
part of this path.

## App Developer Diagnostics

Use the app-level `dev` flag to expose internal diagnostics inside
**Settings > About This Installation**:

```bat
streamlit run app.py -- dev
```

Dev mode keeps raw platform, path, browser, and runtime metadata out of the
default About view while keeping those details available to contributors.

The dev view adds diagnostic sections such as:

- Launch Flags Detected
- Platform Capabilities
- Browser Support
- Platform Path Defaults
- Raw Platform Diagnostics

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
