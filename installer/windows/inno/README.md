# Inno Setup Sources

This folder contains source-controlled Inno Setup scripts for the RoleThread
Lite Windows installer.

The current prototype script is:

```text
rolethread_lite.iss
```

It packages the PyInstaller one-folder bundle from:

```text
installer/windows/dist/RoleThreadLauncher/
```

Generated Inno output, including final setup executables, should not be
committed. Those artifacts belong in local build folders and GitHub Releases.


