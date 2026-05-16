# Developer Launch Flags

LoreForge can be started with optional launch flags after Streamlit's `--` separator. These flags are intended for developers, testers, and future launcher/installer integration. Normal users do not need them during everyday work.

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

Use `webapp` to start LoreForge through the internal Edge webapp launch pathway:

```bat
streamlit run app.py -- webapp
```

This path is Windows/Microsoft Edge only. It is the method future launchers or installers should call when webapp launch mode is enabled. It may require a fresh relaunch to take effect because the launch mode is evaluated during startup.

When Edge is available, LoreForge attempts to open the app in Microsoft Edge app mode. If Streamlit opens a normal browser window first, LoreForge may close only that duplicate browser window after the Edge app window is identified.

On Linux, macOS, or unknown platforms, `webapp` does not attempt Edge launch, Windows window inspection, or duplicate-browser cleanup. LoreForge shows a controlled note and continues in normal browser mode. Use your browser's manual install-as-app or create-shortcut feature if you want an app-like shell on those platforms.

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

Settings includes **Experimental Features > Enable webapp launch mode**. That preference does not relaunch the current app session. It stores the user's choice so a future launcher or installer can decide whether to start LoreForge normally or with `webapp`.
