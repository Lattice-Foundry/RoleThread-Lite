# Developer Launch Flags

RoleThread can be started with optional launch flags after Streamlit's `--` separator. These flags are intended for developers, testers, and launcher/installer integration. Normal users do not need them during everyday work.

Launch flags are deliberately centralized. They should not be checked with scattered `sys.argv` parsing throughout the app.

## Normal Launch

Use the standard Streamlit launch when you want the regular browser workflow:

```bat
streamlit run app.py
```

## Dev Diagnostics

Use `dev` to expose internal diagnostics in **Settings > About This Installation**:

```bat
streamlit run app.py -- dev
```

Dev mode is useful when checking platform detection, runtime details, browser availability, launch behavior, path resolution, or support diagnostics. Diagnostic details may change before release.

Diagnostics are gated behind `dev` so normal users do not see raw platform, path, browser, or window metadata during ordinary use. The default About view stays support-oriented; `dev` exposes the lower-level details a maintainer needs.

In dev mode, **Settings > About This Installation** adds a diagnostics stack:

- Launch Flags Detected
- Platform Capabilities
- Browser Support
- Platform Path Defaults with source/provenance
- Raw Platform Diagnostics
- Webapp Launch Diagnostics
- Duplicate Browser Cleanup Diagnostics
- Edge Window Debug
- Edge Process Debug

The normal About view keeps only the support-oriented summary, runtime compatibility, launch behavior, and storage locations.

## Webapp Mode

Use `webapp` to start RoleThread through the internal Edge webapp launch pathway:

```bat
streamlit run app.py -- webapp
```

This path is Windows/Microsoft Edge only. It is the official internal webapp launch mode used by the Windows launcher and future installer pipeline when webapp launch mode is enabled. It may require a fresh relaunch to take effect because the launch mode is evaluated during startup.

When Edge is available, RoleThread attempts to open the app in Microsoft Edge app mode. If Streamlit opens a normal browser window first, RoleThread may close only that duplicate browser window after the Edge app window is identified.

The launcher does not duplicate Edge cleanup logic. It chooses the startup mode and lets the app's internal `webapp` path own Edge detection, app-window launch, and duplicate-window cleanup.

On Linux, macOS, or unknown platforms, `webapp` does not attempt Edge launch, Windows window inspection, or duplicate-browser cleanup. RoleThread shows a controlled note and continues in normal browser mode. Use your browser's manual install-as-app or create-shortcut feature if you want an app-like shell on those platforms.

## Webapp Mode With Diagnostics

Use `webapp dev` when testing webapp launch behavior and you want Settings diagnostics visible:

```bat
streamlit run app.py -- webapp dev
```

## Edge Debug Diagnostics

Use `edge-debug` when investigating Microsoft Edge process/window behavior:

```bat
streamlit run app.py -- webapp dev edge-debug
```

`edge-debug` should generally be combined with `dev`; otherwise detailed diagnostic UI stays hidden. It records Edge process IDs, window handles, candidate classifications, and cleanup decisions where Windows exposes that metadata.

Edge Window Debug is currently the most useful diagnostic for duplicate browser cleanup because the normal browser window may already exist before `app.py` runs. Edge Process Debug remains available as secondary process-level evidence.

## Webapp Debug Alias

`webapp-debug` is also recognized as a debug flag for webapp launch investigation:

```bat
streamlit run app.py -- webapp dev webapp-debug
```

It should generally be used with `dev` for the same reason as `edge-debug`.

## Experimental Feature Preference

Settings includes **Experimental Features > Enable webapp launch mode**. That preference does not relaunch the current app session. It stores the user's choice so a future launcher or installer can decide whether to start RoleThread normally or with `webapp`.

