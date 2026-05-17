# Developer Launch Flags

RoleThread accepts runtime flags after Streamlit's `--` separator. These flags are for development diagnostics, launcher integration, and webapp-mode testing.

Launch flags are deliberately centralized. They should not be checked with scattered `sys.argv` parsing throughout the app.

## Normal Launch

Use the standard Streamlit launch for the regular browser workflow:

```bat
streamlit run app.py
```

## Dev Diagnostics

Use `dev` to expose internal diagnostics in **Settings > About This Installation**:

```bat
streamlit run app.py -- dev
```

Dev mode exposes platform detection, runtime details, browser availability, launch behavior, path resolution, and support diagnostics.

Diagnostics are gated behind `dev` so raw platform, path, browser, and window metadata stay out of the default About view.

In dev mode, **Settings > About This Installation** adds a diagnostics stack:

- Launch Flags Detected
- Platform Capabilities
- Browser Support
- Platform Path Defaults with source/provenance
- Raw Platform Diagnostics
- Webapp Launch Diagnostics

The normal About view keeps only the support-oriented summary, runtime compatibility, launch behavior, and storage locations.

## Webapp Mode

Use `webapp` to start RoleThread through the Edge webapp launch path:

```bat
streamlit run app.py -- webapp
```

This path is Windows/Microsoft Edge only. It is the official internal webapp launch mode used by the Windows launcher/installer pipeline when webapp mode is selected during setup. Launch mode is evaluated during startup.

When Edge is available, RoleThread attempts to open the app in Microsoft Edge app mode. If Streamlit opens a normal browser window first, RoleThread may close only that duplicate browser window after the Edge app window is identified.

The launcher does not duplicate Edge cleanup logic. It selects the startup mode and lets the app-owned `webapp` path handle Edge detection, app-window launch, and duplicate-window cleanup.

On Linux, macOS, or unknown platforms, `webapp` does not attempt Edge launch, Windows window inspection, or duplicate-browser cleanup. RoleThread shows a controlled note and continues in normal browser mode. Use your browser's manual install-as-app or create-shortcut feature if you want an app-like shell on those platforms.

## Webapp Mode With Diagnostics

Use `webapp dev` when testing webapp launch behavior and you want Settings diagnostics visible:

```bat
streamlit run app.py -- webapp dev
```

## Edge Debug Diagnostics

Use `edge-debug` when investigating Microsoft Edge process/window behavior:

```bat
streamlit run app.py -- webapp edge-debug
```

`edge-debug` exposes a single **Edge Launch Debug Diagnostics** section in
**Settings > About This Installation**. It records Edge process IDs,
HWND/window handles, candidate classifications, and cleanup decisions where
Windows exposes that metadata.

The window-handle section is usually the most useful diagnostic for duplicate
browser cleanup because the normal browser window may already exist before
`app.py` runs. Process-level evidence remains in the same expander as secondary
context.

## Webapp Debug Alias

`webapp-debug` is also recognized as a debug flag for webapp launch investigation:

```bat
streamlit run app.py -- webapp webapp-debug
```

It enables the same Edge launch debug diagnostics as `edge-debug`.

## Installer Launch Preference

The Windows installer can seed the internal `enable_webapp_launch_mode` preference during setup. The launcher reads that preference on startup to choose normal browser mode or webapp mode. This is installer/launcher plumbing, not a normal Settings control.

