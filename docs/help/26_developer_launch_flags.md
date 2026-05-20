# Developer Launch Flags

RoleThread has two source launch paths:

- `python -m litlaunch.cli run --profile rolethread-webapp` for the managed app-window lifecycle
- `streamlit run app.py` for plain Streamlit browser development

Use the LitLaunch profile path when testing the installed-runtime shape. Use
plain Streamlit when working on app UI behavior and you do not need app-window
closeout, browser launch, or runtime diagnostics.

## Managed Webapp Launch

```bat
python -m litlaunch.cli run --profile rolethread-webapp
```

This is the canonical source/dev path for the managed webapp lifecycle. It
matches the installed runtime model:

1. load `litlaunch.toml`
2. start Streamlit headless
3. bind Streamlit to `127.0.0.1`
4. wait for `/_stcore/health`
5. launch Microsoft Edge app-mode
6. monitor the app window
7. request graceful shutdown when the window closes
8. verify backend exit

## LitLaunch Diagnostics

Use LitLaunch inspect when you need a runtime plan without launching the app:

```bat
python -m litlaunch.cli inspect --profile rolethread-webapp
```

Diagnostics cover profile loading, command planning, backend health URLs,
browser policy, and runtime configuration. Detailed LitLaunch runtime behavior
belongs in the LitLaunch docs.

## Plain Streamlit Browser Mode

```bat
streamlit run app.py
```

Use this when you want Streamlit's normal development loop. Streamlit owns the
browser in this mode, and RoleThread does not attempt app-window monitoring or
managed backend shutdown.

Do not use a custom `webapp` argument with `streamlit run`. Managed webapp
behavior is LitLaunch-owned.

## App Developer Diagnostics

Use the app-level `dev` flag to expose internal diagnostics inside
**Settings > About This Installation**:

```bat
streamlit run app.py -- dev
```

Dev mode keeps raw platform, path, browser, and runtime metadata out of the
default About view while keeping those details available to contributors.

The normal About view stays support-oriented. The dev view adds diagnostic
sections such as:

- Launch Flags Detected
- Platform Capabilities
- Browser Support
- Platform Path Defaults
- Raw Platform Diagnostics

## Installed Runtime

Installed Windows builds always use the managed LitLaunch webapp lifecycle.
The installer no longer exposes a runtime-mode selector.

`RoleThreadLauncher.exe` is the packaged product adapter. LitLaunch owns the
runtime sequence; the Windows adapter supplies bundled paths, the packaged
backend provider, product log paths, and branded failure messaging.
