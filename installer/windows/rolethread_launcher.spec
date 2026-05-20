# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-folder prototype for the RoleThread Lite Windows launcher."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


repo_root = Path(SPECPATH).parents[1]


def collect_project_data(source: str, destination: str) -> list[tuple[str, str]]:
    source_root = repo_root / source
    if not source_root.exists():
        return []

    data: list[tuple[str, str]] = []
    if source_root.is_file():
        data.append((str(source_root), destination))
        return data

    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        relative_parent = path.relative_to(source_root).parent
        data.append((str(path), str(Path(destination) / relative_parent)))
    return data


datas = []
for package_name in ("streamlit", "litlaunch", "pandas", "plotly", "sqlalchemy"):
    datas += copy_metadata(package_name)

datas += collect_data_files("streamlit")
datas += collect_project_data("app.py", ".")
datas += collect_project_data("litlaunch.toml", ".")
datas += collect_project_data("core", "core")
datas += collect_project_data("services", "services")
datas += collect_project_data("ui", "ui")
datas += collect_project_data("docs", "docs")
datas += collect_project_data(".streamlit/config.toml", ".streamlit")
datas += collect_project_data("README.md", ".")
datas += collect_project_data("requirements.txt", ".")

hiddenimports = [
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "pandas",
    "plotly",
    "sqlalchemy",
]
for package_name in ("core", "services", "ui", "litlaunch"):
    hiddenimports += collect_submodules(package_name)


a = Analysis(
    [str(repo_root / "installer" / "windows" / "launcher" / "rolethread_launcher.py")],
    pathex=[str(repo_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RoleThreadLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RoleThreadLauncher",
)

