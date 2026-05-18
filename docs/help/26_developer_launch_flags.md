# Developer Launch Flags

RoleThread has two source launch paths:

- `python launch.py --webapp` for the managed app-window lifecycle
- `streamlit run app.py` for plain Streamlit browser development

Use the launcher path when testing the installed-runtime shape. Use plain
Streamlit when working on app UI behavior and you do not need app-window
closeout, browser adapter launch, or launcher diagnostics.

## Managed Webapp Launch

```bat
python launch.py --webapp
```

This is the canonical source/dev path for the managed webapp lifecycle. It
matches the installed runtime model:

1. build launcher configuration
2. start Streamlit headless
3. bind Streamlit to `127.0.0.1`
4. wait for `/_stcore/health`
5. launch the browser adapter
6. monitor the owned app window
7. request graceful shutdown when the window closes
8. verify port release

There is no place like `http://127.0.0.1`.

## Launcher Diagnostics

Use `--debug` for verbose lifecycle logging:

```bat
python launch.py --webapp --debug
```

Use `--diag` when you want the same diagnostic intent without changing the
primary launch mode:

```bat
python launch.py --webapp --diag
```

Diagnostics report the launcher sequence: command construction, backend start,
health wait, browser adapter launch, window monitoring, shutdown request,
backend exit, and port release status.

The old app-side Edge debug flags were removed. Launcher and browser diagnostics
belong behind `launch.py`.

## Plain Streamlit Browser Mode

```bat
streamlit run app.py
```

Use this when you want Streamlit's normal development loop. Streamlit owns the
browser in this mode, and RoleThread does not attempt app-window monitoring or
managed backend shutdown.

Do not use a custom `webapp` argument with `streamlit run`. Managed webapp
behavior is launcher-owned.

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

Installed Windows builds always use the managed launcher-owned webapp lifecycle.
The installer no longer exposes a runtime-mode selector.

`RoleThreadLauncher.exe` is the packaged adapter. Shared lifecycle code owns the
runtime sequence; the Windows adapter supplies bundled paths, subprocess flags,
Edge adapter wiring, HWND monitoring, and logging.
