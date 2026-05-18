import json
from pathlib import Path
import subprocess
import sqlite3
from types import SimpleNamespace

import pytest

from core.webapp_browser_state import (
    PendingWebappBrowserStateResetResult,
    WebappBrowserStateResetResult,
)
from core.shutdown_control import (
    SHUTDOWN_HEADER,
    SHUTDOWN_PORT_ENV,
    SHUTDOWN_TOKEN_ENV,
    LauncherShutdownControl,
    resolve_launcher_shutdown_control,
    start_launcher_shutdown_server,
)
from installer.windows.launcher import rolethread_launcher as launcher


def _make_app_root(tmp_path: Path, *, with_dev_python: bool = True) -> Path:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "app.py").write_text("print('RoleThread')", encoding="utf-8")
    if with_dev_python:
        python_path = app_root / ".venv" / "Scripts" / "python.exe"
        python_path.parent.mkdir(parents=True)
        python_path.write_text("", encoding="utf-8")
    return app_root


def test_missing_preferences_selects_normal_launch_mode(tmp_path):
    preferences_path = tmp_path / "missing.json"

    assert launcher.read_enable_webapp_launch_mode(preferences_path) is False
    assert launcher.select_launch_mode(enable_webapp_launch_mode=False) == "normal"


def test_false_preference_selects_normal_launch_mode(tmp_path):
    preferences_path = tmp_path / "preferences.json"
    preferences_path.write_text(
        json.dumps({"enable_webapp_launch_mode": False}),
        encoding="utf-8",
    )

    assert launcher.read_enable_webapp_launch_mode(preferences_path) is False
    assert launcher.select_launch_mode(enable_webapp_launch_mode=False) == "normal"


def test_true_preference_selects_webapp_launch_mode(tmp_path):
    preferences_path = tmp_path / "preferences.json"
    preferences_path.write_text(
        json.dumps({"enable_webapp_launch_mode": True}),
        encoding="utf-8",
    )

    assert launcher.read_enable_webapp_launch_mode(preferences_path) is True
    assert launcher.select_launch_mode(enable_webapp_launch_mode=True) == "webapp"


def test_db_webapp_preference_overrides_legacy_json_preference(tmp_path):
    preferences_path = tmp_path / "preferences.json"
    database_path = tmp_path / "rolethread.db"
    preferences_path.write_text(
        json.dumps({"enable_webapp_launch_mode": False}),
        encoding="utf-8",
    )

    launcher.write_webapp_launch_preference_to_db(database_path, True)

    assert launcher.read_enable_webapp_launch_mode_from_db(database_path) is True
    assert launcher.resolve_enable_webapp_launch_mode(
        preferences_path=preferences_path,
        database_path=database_path,
    ) is True


def test_installer_seed_applies_only_webapp_preference_and_removes_seed(tmp_path):
    seed_path = tmp_path / "installer_seed.json"
    database_path = tmp_path / "rolethread.db"
    log_path = tmp_path / "logs" / "launcher.log"
    seed_path.write_text(
        json.dumps({"enable_webapp_launch_mode": True, "unrelated": "ignored"}),
        encoding="utf-8",
    )

    result = launcher.apply_installer_seed(
        seed_path=seed_path,
        database_path=database_path,
        log_path=log_path,
    )

    assert result is True
    assert not seed_path.exists()
    assert launcher.read_enable_webapp_launch_mode_from_db(database_path) is True
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute("SELECT key FROM app_settings").fetchall()
    assert rows == [(launcher.WEBAPP_PREFERENCE_KEY,)]
    assert "installer_seed_applied" in log_path.read_text(encoding="utf-8")


def test_build_launcher_config_applies_installer_seed_before_launch_selection(tmp_path):
    app_root = _make_app_root(tmp_path)
    local_app_data = tmp_path / "local"
    seed_path = local_app_data / "RoleThread" / "installer_seed.json"
    seed_path.parent.mkdir(parents=True)
    seed_path.write_text(
        json.dumps({"enable_webapp_launch_mode": True}),
        encoding="utf-8",
    )

    config = launcher.build_launcher_config(
        app_root=app_root,
        env={"LOCALAPPDATA": str(local_app_data)},
        current_executable=str(tmp_path / "unused.exe"),
        shutdown_port=54321,
        shutdown_token="token",
    )

    assert config.launch_mode == launcher.LAUNCH_MODE_WEBAPP
    assert config.command[-2:] == ("--", "webapp")
    assert not seed_path.exists()


def test_command_construction_for_normal_launch(tmp_path):
    python_path = tmp_path / "python.exe"

    command = launcher.build_streamlit_command(
        python_path,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
    )

    assert command == (
        str(python_path),
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        "8501",
    )


def test_command_construction_for_webapp_launch(tmp_path):
    python_path = tmp_path / "python.exe"

    command = launcher.build_streamlit_command(
        python_path,
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
    )

    assert command[-2:] == ("--", "webapp")
    assert command[:4] == (str(python_path), "-m", "streamlit", "run")


def test_bundled_command_uses_internal_streamlit_mode(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    command = launcher.build_streamlit_command(
        launcher_exe,
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        app_root=app_root,
        frozen=True,
    )

    assert command == (
        str(launcher_exe),
        launcher.INTERNAL_STREAMLIT_FLAG,
        str(app_root / "app.py"),
        "--global.developmentMode=false",
        "--server.port",
        "8501",
        "--server.headless",
        "true",
        "--",
        "webapp",
    )


def test_bundled_normal_command_does_not_force_headless(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    command = launcher.build_streamlit_command(
        launcher_exe,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        app_root=app_root,
        frozen=True,
    )

    assert "--server.headless" not in command


def test_dev_python_path_selection_prefers_venv_runtime(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=True)
    fallback = tmp_path / "fallback.exe"
    fallback.write_text("", encoding="utf-8")

    python_path = launcher.resolve_python_runtime(
        app_root,
        current_executable=str(fallback),
    )

    assert python_path == app_root / ".venv" / "Scripts" / "python.exe"


def test_python_path_selection_falls_back_to_current_executable(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    fallback = tmp_path / "fallback.exe"
    fallback.write_text("", encoding="utf-8")

    python_path = launcher.resolve_python_runtime(
        app_root,
        current_executable=str(fallback),
    )

    assert python_path == fallback


def test_bundled_runtime_selection_uses_launcher_executable(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    python_path = launcher.resolve_python_runtime(
        app_root,
        current_executable=str(launcher_exe),
        frozen=True,
    )

    assert python_path == launcher_exe


def test_python_path_selection_errors_without_runtime(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)

    with pytest.raises(launcher.LauncherConfigurationError):
        launcher.resolve_python_runtime(
            app_root,
            current_executable=str(tmp_path / "missing.exe"),
        )


def test_build_launcher_config_errors_when_app_root_has_no_app_py(tmp_path):
    app_root = tmp_path / "not_rolethread"
    app_root.mkdir()

    with pytest.raises(launcher.LauncherConfigurationError) as exc_info:
        launcher.build_launcher_config(
            app_root=app_root,
            current_executable=str(tmp_path / "missing.exe"),
        )

    assert "app.py" in str(exc_info.value)


def test_resolve_app_root_uses_pyinstaller_meipass_in_frozen_mode(tmp_path, monkeypatch):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    monkeypatch.setattr(launcher.sys, "_MEIPASS", str(app_root), raising=False)

    assert launcher.resolve_app_root(frozen=True) == app_root.resolve()


def test_build_launcher_config_uses_bundled_command_in_frozen_mode(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=False)
    launcher_exe = tmp_path / "RoleThreadLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    config = launcher.build_launcher_config(
        app_root=app_root,
        env={"LOCALAPPDATA": str(tmp_path / "local")},
        current_executable=str(launcher_exe),
        frozen=True,
        shutdown_port=54321,
        shutdown_token="token",
    )

    assert config.python_path == launcher_exe
    assert config.bundled_mode is True
    assert config.command[:3] == (
        str(launcher_exe),
        launcher.INTERNAL_STREAMLIT_FLAG,
        str(app_root / "app.py"),
    )
    assert "-m" not in config.command
    assert config.shutdown_port == 54321
    assert config.shutdown_token == "token"


def test_launcher_log_path_resolution_uses_localappdata():
    log_path = launcher.resolve_launcher_log_path(
        {"LOCALAPPDATA": "C:/Users/Public/AppData/Local"}
    )

    assert log_path == Path("C:/Users/Public/AppData/Local/RoleThread/logs/launcher.log")


def test_build_launcher_config_reads_preference_and_builds_webapp_command(tmp_path):
    app_root = _make_app_root(tmp_path)
    local_app_data = tmp_path / "local"
    preferences_path = local_app_data / "RoleThread" / "preferences.json"
    preferences_path.parent.mkdir(parents=True)
    preferences_path.write_text(
        json.dumps({"enable_webapp_launch_mode": True}),
        encoding="utf-8",
    )

    config = launcher.build_launcher_config(
        app_root=app_root,
        env={"LOCALAPPDATA": str(local_app_data)},
        current_executable=str(tmp_path / "unused.exe"),
        shutdown_port=54321,
        shutdown_token="token",
    )

    assert config.launch_mode == launcher.LAUNCH_MODE_WEBAPP
    assert config.preferences_path == preferences_path
    assert config.log_path == local_app_data / "RoleThread" / "logs" / "launcher.log"
    assert config.command[-2:] == ("--", "webapp")


def test_launch_rolethread_logs_and_invokes_subprocess(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    command = ("python.exe", "-m", "streamlit", "run", "app.py")
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=command,
    )
    calls = []

    class FakeProcess:
        pid = 1234

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeProcess()

    result = launcher.launch_rolethread(
        config,
        popen=fake_popen,
        port_available_fn=lambda: True,
    )

    assert isinstance(result, FakeProcess)
    assert len(calls) == 1
    assert calls[0][0] == (command,)
    assert calls[0][1]["cwd"] == app_root
    assert SHUTDOWN_PORT_ENV not in calls[0][1]["env"]
    log_text = log_path.read_text(encoding="utf-8")
    assert "launch_mode=normal" in log_text
    assert f"app_version={launcher.get_app_version()}" in log_text
    assert "bundled_mode=False" in log_text
    assert "command=python.exe -m streamlit run app.py" in log_text
    assert "started_pid=1234" in log_text


def test_launch_rolethread_reports_port_in_use_without_starting_subprocess(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=("python.exe", "-m", "streamlit", "run", "app.py"),
    )

    with pytest.raises(launcher.LauncherConfigurationError) as exc_info:
        launcher.launch_rolethread(
            config,
            popen=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("subprocess should not start")
            ),
            port_available_fn=lambda: False,
        )

    assert "Port 8501 is already in use" in str(exc_info.value)
    assert "Port 8501 is already in use" in log_path.read_text(encoding="utf-8")


def test_launch_rolethread_logs_subprocess_failure(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=("python.exe", "-m", "streamlit", "run", "app.py"),
    )

    def fail_popen(*args, **kwargs):
        raise OSError("streamlit exploded")

    with pytest.raises(OSError):
        launcher.launch_rolethread(
            config,
            popen=fail_popen,
            port_available_fn=lambda: True,
        )

    log_text = log_path.read_text(encoding="utf-8")
    assert "subprocess_error=streamlit exploded" in log_text


def test_port_available_false_when_connection_succeeds(monkeypatch):
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(launcher.socket, "create_connection", lambda *args, **kwargs: FakeSocket())

    assert launcher.is_port_available() is False


def test_port_available_true_when_connection_fails(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("closed")

    monkeypatch.setattr(launcher.socket, "create_connection", fail)

    assert launcher.is_port_available() is True


def test_capture_rolethread_webapp_windows_parses_exact_hwnd_metadata(monkeypatch):
    monkeypatch.setattr(launcher.os, "name", "nt")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "handle": "0x7D09AA",
                        "pid": 25740,
                        "title": "RoleThread Lite",
                        "class_name": "Chrome_WidgetWin_1",
                        "process_name": "msedge",
                    }
                ]
            ),
            stderr="",
        )

    windows = launcher.capture_rolethread_webapp_windows(run_fn=fake_run)

    assert windows == (
        launcher.WebappWindowInfo(
            handle="0x7D09AA",
            pid=25740,
            title="RoleThread Lite",
            class_name="Chrome_WidgetWin_1",
            process_name="msedge",
        ),
    )
    assert launcher.count_rolethread_webapp_windows(run_fn=fake_run) == 1


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("RoleThread Lite", True),
        ("RoleThread Lite - Personal - Microsoft Edge", False),
        ("RoleThread Lite - Microsoft Edge", False),
        ("RoleThread", False),
        ("Codex", False),
    ],
)
def test_webapp_window_title_rejects_normal_edge_browser_chrome(title, expected):
    assert launcher._is_rolethread_webapp_window_title(title) is expected


def test_wait_for_app_window_close_tracks_exact_webapp_handle():
    target = launcher.WebappWindowInfo(
        handle="0x7D09AA",
        pid=25740,
        title="RoleThread Lite",
        class_name="Chrome_WidgetWin_1",
        process_name="msedge",
    )
    calls = iter([(), (target,), (target,), (target,), ()])

    result = launcher.wait_for_app_window_close(
        launcher.LAUNCH_MODE_WEBAPP,
        capture_windows_fn=lambda: next(calls),
        sleep_fn=lambda _: None,
        appear_timeout_seconds=5,
        poll_seconds=0,
    )

    assert result.supported is True
    assert result.observed is True
    assert result.closed is True
    assert result.target_handle == "0x7D09AA"
    assert result.target_pid == 25740
    assert result.target_title == "RoleThread Lite"


def test_wait_for_app_window_close_rejects_transient_webapp_handle():
    transient = launcher.WebappWindowInfo(
        handle="0x111",
        pid=100,
        title="RoleThread Lite",
        class_name="Chrome_WidgetWin_1",
        process_name="msedge",
    )
    stable = launcher.WebappWindowInfo(
        handle="0x222",
        pid=101,
        title="RoleThread Lite",
        class_name="Chrome_WidgetWin_1",
        process_name="msedge",
    )
    calls = iter([(transient,), (), (stable,), (stable,), ()])

    result = launcher.wait_for_app_window_close(
        launcher.LAUNCH_MODE_WEBAPP,
        capture_windows_fn=lambda: next(calls),
        sleep_fn=lambda _: None,
        appear_timeout_seconds=5,
        poll_seconds=0,
    )

    assert result.supported is True
    assert result.closed is True
    assert result.target_handle == "0x222"


def test_check_port_release_status_reports_free_port():
    status = launcher.check_port_release_status(
        owned_pid=123,
        port_available_fn=lambda: True,
        port_owner_fn=lambda: (_ for _ in ()).throw(
            AssertionError("owner should not be queried for free port")
        ),
    )

    assert status.released is True
    assert status.owner_kind == "free"


def test_check_port_release_status_reports_owned_process():
    status = launcher.check_port_release_status(
        owned_pid=123,
        port_available_fn=lambda: False,
        port_owner_fn=lambda: 123,
    )

    assert status.released is False
    assert status.owner_pid == 123
    assert status.owner_kind == "owned_process"


def test_check_port_release_status_reports_unknown_process():
    status = launcher.check_port_release_status(
        owned_pid=123,
        port_available_fn=lambda: False,
        port_owner_fn=lambda: 999,
    )

    assert status.released is False
    assert status.owner_pid == 999
    assert status.owner_kind == "unknown_process"


def test_pyinstaller_spec_uses_windowed_no_console_mode():
    spec_path = Path(__file__).parents[3] / "installer" / "windows" / "rolethread_launcher.spec"
    spec_text = spec_path.read_text(encoding="utf-8")

    assert "console=False" in spec_text
    assert "console=True" not in spec_text


def test_inno_installer_script_packages_launcher_bundle():
    inno_path = (
        Path(__file__).parents[3]
        / "installer"
        / "windows"
        / "inno"
        / "rolethread_lite.iss"
    )
    inno_text = inno_path.read_text(encoding="utf-8")

    assert "AppName={#AppName}" in inno_text
    assert '#define AppName "RoleThread Lite"' in inno_text
    assert "DefaultDirName={autopf}\\RoleThread Lite" in inno_text
    assert "#define BundleDir \"..\\dist\\RoleThreadLauncher\"" in inno_text
    assert "Source: \"{#BundleDir}\\*\"" in inno_text
    assert "Name: \"{group}\\RoleThread Lite\"" in inno_text
    assert "Name: \"{group}\\RoleThread Uninstaller\"" in inno_text
    assert 'Filename: "{uninstallexe}"' in inno_text
    assert "Name: \"{autodesktop}\\RoleThread Lite\"" in inno_text
    assert "Tasks: desktopicon" in inno_text
    assert "postinstall" in inno_text
    assert "OutputBaseFilename=RoleThreadLiteSetup-v{#AppVersion}" in inno_text
    assert 'Name: "webappmode"' in inno_text
    assert "Use Windows Edge webapp mode by default (recommended)" in inno_text
    assert "can be changed later in Settings" not in inno_text
    assert "installer_seed.json" in inno_text
    assert '"enable_webapp_launch_mode": true' in inno_text
    assert '"enable_webapp_launch_mode": false' in inno_text
    assert "WizardIsTaskSelected('webappmode')" in inno_text
    assert "Remove local RoleThread user data" in inno_text
    assert "database/app state, preferences, logs, cache" in inno_text
    assert "Developer clean uninstall / remove installer test state" not in inno_text
    assert "RoleThreadLauncher.exe" in inno_text
    assert "tasklist" in inno_text
    assert "RoleThreadAppDataRoot()" in inno_text
    assert "RoleThreadWorkspaceRoot()" in inno_text
    assert "DelTree(Path, True, True, True)" in inno_text
    assert "External/cloud backup destinations" in inno_text
    assert "BringWizardToFront" in inno_text
    assert "ShowWindow(WizardForm.Handle, SW_RESTORE)" in inno_text
    assert "WizardForm.BringToFront" in inno_text
    assert "SetActiveWindow(WizardForm.Handle)" in inno_text
    assert "SetForegroundWindow(WizardForm.Handle)" in inno_text


def test_build_installer_script_validates_bundle_and_inno_compiler():
    script_path = (
        Path(__file__).parents[3]
        / "installer"
        / "windows"
        / "scripts"
        / "build_installer.ps1"
    )
    script_text = script_path.read_text(encoding="utf-8")

    assert "rolethread_lite.iss" in script_text
    assert "RoleThreadLauncher.exe" in script_text
    assert "Resolve-InnoCompiler" in script_text
    assert "ISCC.exe" in script_text
    assert "Inno Setup compiler was not found" in script_text
    assert "/DAppVersion=$version" in script_text
    assert "RoleThreadLiteSetup-v$version.exe" in script_text
    assert "BuildBundle" in script_text
    assert "UseExistingBundle" in script_text
    assert "Building fresh PyInstaller bundle before installer packaging" in script_text
    assert "Bundle version: $bundleVersion" in script_text
    assert "Bundle rebuilt this run: $bundleWasRebuilt" in script_text
    assert "Refusing to build installer from a stale PyInstaller bundle" in script_text
    assert "$bundleVersion -ne $version" in script_text
    assert "LOCALAPPDATA" in script_text
    assert "Programs\\Inno Setup 6\\ISCC.exe" in script_text


def test_obsolete_developer_cleanup_script_is_removed_from_installer_docs():
    repo_root = Path(__file__).parents[3]
    cleanup_script = (
        repo_root / "installer" / "windows" / "scripts" / "clean_rolethread_user_data.ps1"
    )
    readme_text = (
        repo_root / "installer" / "windows" / "README.md"
    ).read_text(encoding="utf-8")

    assert not cleanup_script.exists()
    assert "clean_rolethread_user_data.ps1" not in readme_text
    assert "Developer clean uninstall" not in readme_text
    assert "normal Windows uninstaller" in readme_text


def test_shutdown_control_resolves_only_when_launcher_env_is_complete():
    assert resolve_launcher_shutdown_control({}) is None
    assert resolve_launcher_shutdown_control(
        {SHUTDOWN_PORT_ENV: "not-a-port", SHUTDOWN_TOKEN_ENV: "token"}
    ) is None

    control = resolve_launcher_shutdown_control(
        {SHUTDOWN_PORT_ENV: "54321", SHUTDOWN_TOKEN_ENV: "token"}
    )

    assert control == LauncherShutdownControl(port=54321, token="token")


def test_start_launcher_shutdown_server_ignores_missing_control():
    assert start_launcher_shutdown_server(None, shutdown_fn=lambda: None) is False


def test_build_subprocess_env_includes_shutdown_control(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    env = launcher.build_subprocess_env(config, {"BASE": "1"})

    assert env["BASE"] == "1"
    assert env[SHUTDOWN_PORT_ENV] == "54321"
    assert env[SHUTDOWN_TOKEN_ENV] == "secret"
    assert env[launcher.LAUNCHER_LOG_PATH_ENV] == str(config.log_path)
    assert env[launcher.EXTERNAL_WEBAPP_LAUNCH_ENV] == "1"


def test_build_subprocess_env_does_not_mark_normal_launch_as_external_webapp(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    env = launcher.build_subprocess_env(config, {})

    assert launcher.EXTERNAL_WEBAPP_LAUNCH_ENV not in env


def test_launch_edge_webapp_window_uses_detected_edge_path(monkeypatch):
    edge_path = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    monkeypatch.setattr(
        launcher,
        "detect_browser_capabilities",
        lambda: SimpleNamespace(
            platform=SimpleNamespace(os_name="windows"),
            browser=SimpleNamespace(edge_path=edge_path),
        ),
    )
    commands = []

    result = launcher.launch_edge_webapp_window(
        url="http://127.0.0.1:8501",
        popen=lambda command: commands.append(tuple(command)),
    )

    assert result.attempted is True
    assert result.launched is True
    assert result.command == (str(edge_path), "--app=http://127.0.0.1:8501")
    assert commands == [result.command]


def test_launch_edge_webapp_window_skips_without_edge(monkeypatch):
    monkeypatch.setattr(
        launcher,
        "detect_browser_capabilities",
        lambda: SimpleNamespace(
            platform=SimpleNamespace(os_name="windows"),
            browser=SimpleNamespace(edge_path=None),
        ),
    )

    result = launcher.launch_edge_webapp_window(
        popen=lambda command: (_ for _ in ()).throw(
            AssertionError("should not launch without Edge")
        ),
    )

    assert result.attempted is False
    assert result.launched is False


def test_request_graceful_shutdown_builds_tokenized_local_request(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )
    calls = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request_obj, timeout):
        calls.append((request_obj, timeout))
        return FakeResponse()

    result = launcher.request_graceful_shutdown(config, urlopen=fake_urlopen)

    assert result.ok is True
    assert result.status_code == 200
    assert calls[0][0].full_url == "http://127.0.0.1:54321/shutdown"
    headers = dict(calls[0][0].header_items())
    assert headers["X-rolethread-launcher-token"] == "secret"


def test_wait_for_app_window_close_detects_webapp_close_sequence():
    counts = iter([0, 1, 1, 0])

    result = launcher.wait_for_app_window_close(
        launcher.LAUNCH_MODE_WEBAPP,
        count_windows_fn=lambda: next(counts),
        sleep_fn=lambda _: None,
        appear_timeout_seconds=5,
        poll_seconds=0,
    )

    assert result.supported is True
    assert result.observed is True
    assert result.closed is True


def test_wait_for_app_window_close_reports_normal_mode_limitation():
    result = launcher.wait_for_app_window_close(launcher.LAUNCH_MODE_NORMAL)

    assert result.supported is False
    assert result.closed is False
    assert "normal browser" in result.message


def test_terminate_process_fallback_uses_terminate_before_kill():
    class FakeProcess:
        def __init__(self):
            self.calls = []
            self.exited = False

        def poll(self):
            return 0 if self.exited else None

        def terminate(self):
            self.calls.append("terminate")
            self.exited = True

        def kill(self):
            self.calls.append("kill")

        def wait(self, timeout):
            if self.exited:
                return 0
            raise subprocess.TimeoutExpired("fake", timeout)

    process = FakeProcess()

    result = launcher.terminate_process_fallback(process)

    assert result.method == "terminate"
    assert result.completed is True
    assert process.calls == ["terminate"]


def test_terminate_process_fallback_kills_as_last_resort(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.calls = []

        def poll(self):
            return None

        def terminate(self):
            self.calls.append("terminate")

        def kill(self):
            self.calls.append("kill")

    process = FakeProcess()
    waits = iter([False, True])
    monkeypatch.setattr(launcher, "wait_for_process_exit", lambda *args, **kwargs: next(waits))

    result = launcher.terminate_process_fallback(process)

    assert result.method == "kill"
    assert result.completed is True
    assert process.calls == ["terminate", "kill"]


def test_run_launcher_lifecycle_graceful_shutdown_path(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 777

        def __init__(self):
            self.exited = False

        def poll(self):
            return 0 if self.exited else None

        def wait(self, timeout):
            self.exited = True
            return 0

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(
            ok=True,
            url="http://127.0.0.1:8501/_stcore/health",
            attempts=1,
            message="ok",
        ),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            supported=True,
            closed=True,
            observed=True,
            message="closed",
        ),
        shutdown_request_fn=lambda cfg: launcher.ShutdownRequestResult(
            attempted=True,
            ok=True,
            status_code=200,
            message="ok",
        ),
        termination_fn=lambda process: (_ for _ in ()).throw(
            AssertionError("termination should not run")
        ),
        port_release_fn=lambda pid: launcher.PortReleaseStatus(
            True,
            None,
            "free",
            "released",
        ),
        edge_launch_fn=lambda: launcher.EdgeLaunchResult(
            True,
            True,
            ("msedge", "--app=http://127.0.0.1:8501"),
            "launched",
        ),
    )

    assert result.final_state == "graceful_shutdown"
    assert result.shutdown_request.ok is True
    log_text = log_path.read_text(encoding="utf-8")
    assert "lifecycle=health_check" in log_text
    assert "lifecycle=window_monitor" in log_text
    assert "lifecycle=shutdown_request" in log_text
    assert "lifecycle=port_release" in log_text


def test_run_launcher_lifecycle_consumes_pending_webapp_reset_before_startup(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )
    calls = []

    class FakeProcess:
        pid = 778

        def wait(self, timeout):
            return 0

    def pending_reset():
        calls.append("pending_reset")
        return PendingWebappBrowserStateResetResult(
            pending=False,
            attempted=True,
            completed=True,
            marker_path=tmp_path / "webapp_browser_state_reset.json",
            reset_result=WebappBrowserStateResetResult(success=True),
            message="completed",
        )

    def popen(*args, **kwargs):
        calls.append("popen")
        return FakeProcess()

    def edge_launch():
        calls.append("edge_launch")
        return launcher.EdgeLaunchResult(True, True, ("msedge",), "launched")

    result = launcher.run_launcher_lifecycle(
        config,
        popen=popen,
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(True, "url", 1, "ok"),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            True,
            True,
            True,
            "closed",
        ),
        shutdown_request_fn=lambda cfg: launcher.ShutdownRequestResult(
            True,
            True,
            200,
            "ok",
        ),
        port_release_fn=lambda pid: launcher.PortReleaseStatus(
            True,
            None,
            "free",
            "released",
        ),
        edge_launch_fn=edge_launch,
        pending_browser_reset_fn=pending_reset,
    )

    assert result.final_state == "graceful_shutdown"
    assert calls[:3] == ["pending_reset", "popen", "edge_launch"]
    log_text = log_path.read_text(encoding="utf-8")
    assert "lifecycle=webapp_browser_state_reset" in log_text
    assert "completed=True" in log_text


def test_run_launcher_lifecycle_logs_preserved_pending_webapp_reset(tmp_path):
    app_root = _make_app_root(tmp_path)
    log_path = tmp_path / "logs" / "launcher.log"
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=log_path,
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 779

        def wait(self, timeout):
            return 0

    def pending_reset():
        return PendingWebappBrowserStateResetResult(
            pending=True,
            attempted=True,
            completed=False,
            marker_path=tmp_path / "webapp_browser_state_reset.json",
            reset_result=WebappBrowserStateResetResult(
                success=False,
                items_skipped=[
                    "Edge appears to be running, so browser profile files were left untouched."
                ],
            ),
            message="still pending",
        )

    launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(True, "url", 1, "ok"),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            True,
            True,
            True,
            "closed",
        ),
        shutdown_request_fn=lambda cfg: launcher.ShutdownRequestResult(
            True,
            True,
            200,
            "ok",
        ),
        port_release_fn=lambda pid: launcher.PortReleaseStatus(
            True,
            None,
            "free",
            "released",
        ),
        edge_launch_fn=lambda: launcher.EdgeLaunchResult(True, True, ("msedge",), "launched"),
        pending_browser_reset_fn=pending_reset,
    )

    log_text = log_path.read_text(encoding="utf-8")
    assert "lifecycle=webapp_browser_state_reset" in log_text
    assert "pending=True" in log_text
    assert "completed=False" in log_text


def test_run_launcher_lifecycle_terminates_after_shutdown_timeout(tmp_path, monkeypatch):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "logs" / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 888

        def poll(self):
            return None

    monkeypatch.setattr(launcher, "wait_for_process_exit", lambda *args, **kwargs: False)

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(True, "url", 1, "ok"),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            True,
            True,
            True,
            "closed",
        ),
        shutdown_request_fn=lambda cfg: launcher.ShutdownRequestResult(
            True,
            False,
            None,
            "failed",
        ),
        termination_fn=lambda process: launcher.TerminationResult(
            True,
            "terminate",
            True,
            "terminated",
        ),
        port_release_fn=lambda pid: launcher.PortReleaseStatus(
            True,
            None,
            "free",
            "released",
        ),
        edge_launch_fn=lambda: launcher.EdgeLaunchResult(False, False, (), "skipped"),
    )

    assert result.final_state == "terminated"
    assert result.termination.method == "terminate"


def test_run_launcher_lifecycle_terminates_when_health_check_fails(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "logs" / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 889

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(False, "url", 3, "timeout"),
        wait_for_close_fn=lambda mode, process: (_ for _ in ()).throw(
            AssertionError("window monitoring should not run")
        ),
        shutdown_request_fn=lambda cfg: (_ for _ in ()).throw(
            AssertionError("shutdown should not run")
        ),
        termination_fn=lambda process: launcher.TerminationResult(
            True,
            "terminate",
            True,
            "terminated",
        ),
        port_release_fn=lambda pid: launcher.PortReleaseStatus(
            True,
            None,
            "free",
            "released",
        ),
    )

    assert result.final_state == "health_failed"
    assert result.termination.method == "terminate"
    assert result.shutdown_request.attempted is False


def test_run_launcher_lifecycle_does_not_shutdown_when_monitoring_unsupported(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "logs" / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 999

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(True, "url", 1, "ok"),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            False,
            False,
            False,
            "unsupported",
        ),
        shutdown_request_fn=lambda cfg: (_ for _ in ()).throw(
            AssertionError("shutdown should not run")
        ),
        termination_fn=lambda process: (_ for _ in ()).throw(
            AssertionError("termination should not run")
        ),
        port_release_fn=lambda pid: launcher.PortReleaseStatus(
            False,
            999,
            "unknown_process",
            "still occupied",
        ),
        edge_launch_fn=lambda: (_ for _ in ()).throw(
            AssertionError("normal mode should not launch Edge")
        ),
    )

    assert result.final_state == "monitoring_unavailable"
    assert result.shutdown_request.attempted is False


def test_run_launcher_lifecycle_terminates_owned_webapp_backend_when_window_never_appears(tmp_path):
    app_root = _make_app_root(tmp_path)
    config = launcher.LauncherConfig(
        app_root=app_root,
        python_path=Path("python.exe"),
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "logs" / "launcher.log",
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 1001

    result = launcher.run_launcher_lifecycle(
        config,
        popen=lambda *args, **kwargs: FakeProcess(),
        port_available_fn=lambda: True,
        health_check_fn=lambda: launcher.HealthCheckResult(True, "url", 1, "ok"),
        wait_for_close_fn=lambda mode, process: launcher.WindowCloseDetectionResult(
            False,
            False,
            False,
            "Timed out waiting for the Edge app window to appear.",
        ),
        shutdown_request_fn=lambda cfg: (_ for _ in ()).throw(
            AssertionError("shutdown should not run without app-window close")
        ),
        termination_fn=lambda process: launcher.TerminationResult(
            True,
            "terminate",
            True,
            "terminated owned backend",
        ),
        port_release_fn=lambda pid: launcher.PortReleaseStatus(
            True,
            None,
            "free",
            "released",
        ),
        edge_launch_fn=lambda: launcher.EdgeLaunchResult(
            True,
            True,
            ("msedge", "--app=http://127.0.0.1:8501"),
            "launched",
        ),
    )

    assert result.final_state == "window_monitor_failed_terminated"
    assert result.termination.attempted is True
    assert result.termination.method == "terminate"
    log_text = config.log_path.read_text(encoding="utf-8")
    assert "lifecycle=window_monitor_failed" in log_text
    assert "terminated owned backend" in log_text

