# Installing RoleThread Lite

RoleThread Lite can run from a normal source checkout or from the Windows setup
installer. The setup installer is the easier Windows beta path. The manual path
is still the most transparent workflow for developers, technical users, Linux,
and macOS.

## Choose An Install Method

Use the Windows setup installer if you want RoleThread Lite to behave like a
normal desktop app with a Start Menu shortcut, bundled runtime, and managed
Windows Edge app window.

Use the manual source workflow if you want full visibility into the Python
environment, dependency installation, launch command, and repository files.

## Windows Setup Installer

The Windows setup executable is a beta convenience path. It packages a tested
release snapshot and does not clone from Git or require a local Python install.
It is expected to keep improving as installer testing continues.

1. Download the latest RoleThread Lite setup executable from GitHub Releases.
2. Run the setup executable and accept the Windows UAC prompt.
3. Choose whether to create a Desktop shortcut.
4. Finish setup and launch RoleThread Lite from the installer, Start Menu, or
   Desktop shortcut.

Installed RoleThread Lite uses the managed launcher automatically. It starts the
local Streamlit backend headless, binds it to `127.0.0.1`, and opens the app in
a local Edge app-style window. Users do not choose a runtime mode during setup.

On some Windows systems, the installer may appear behind other windows after
the UAC prompt. If setup does not appear immediately, minimize other windows or
check the taskbar for the RoleThread Lite installer.

The installed app stores user data separately from installed program files:

```text
Program files:
C:\Program Files\RoleThread Lite\

App data:
%LOCALAPPDATA%\RoleThread\

Workspace:
%USERPROFILE%\RoleThread\
```

## Windows Manual Install

Manual Windows setup is useful when working from source.

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

For the managed Windows Edge app-window launch path:

```bat
python -m litlaunch.cli run --profile rolethread-webapp
```

This uses the same LitLaunch-owned webapp lifecycle as the installed app.
Streamlit runs headless, binds to `127.0.0.1`, and LitLaunch opens the managed
Edge app window.

## Linux Manual Install

Linux uses the source/manual workflow for V1.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Managed Windows Edge app-window mode is not available on Linux. Use normal browser
mode, or create a browser app shortcut manually if your browser supports it.

## macOS Manual Install

macOS is beta/manual for V1.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Managed Windows Edge app-window mode is not available on macOS. Use normal browser
mode, or create a browser app shortcut manually if your browser supports it.

## Uninstalling On Windows

The normal Windows uninstall path removes installed app/runtime files,
shortcuts, and the uninstall entry. It preserves local RoleThread user data.

Use one of these uninstall paths:

- Start Menu > RoleThread Lite > **RoleThread Uninstaller**
- Windows Settings > Apps > Installed apps > RoleThread Lite > Uninstall
- Control Panel > Programs and Features > RoleThread Lite > Uninstall

Default uninstall preserves:

```text
%LOCALAPPDATA%\RoleThread\
%USERPROFILE%\RoleThread\
```

The uninstaller can optionally remove local RoleThread user data. That
destructive option deletes local database/app state, preferences, logs, cache,
training data, imports, exports, backups, and workspace data under the two
RoleThread-owned roots above.

Cloud backup copies and external sync folders outside the local RoleThread
folders are preserved. Delete those manually from the cloud provider or sync
folder if desired.

Close RoleThread Lite before uninstalling. The uninstaller checks for
`RoleThreadLauncher.exe` and asks you to close the app instead of broadly
terminating Python, Edge, Streamlit, or browser processes.
