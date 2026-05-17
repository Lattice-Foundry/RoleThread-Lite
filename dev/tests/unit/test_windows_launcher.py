import json
from pathlib import Path

import pytest

from installer.windows.launcher import loreforge_launcher as launcher


def _make_app_root(tmp_path: Path, *, with_dev_python: bool = True) -> Path:
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "app.py").write_text("print('LoreForge')", encoding="utf-8")
    if with_dev_python:
        python_path = app_root / "trainer" / "Scripts" / "python.exe"
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
    launcher_exe = tmp_path / "LoreForgeLauncher.exe"
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
        "--",
        "webapp",
    )


def test_dev_python_path_selection_prefers_trainer_runtime(tmp_path):
    app_root = _make_app_root(tmp_path, with_dev_python=True)
    fallback = tmp_path / "fallback.exe"
    fallback.write_text("", encoding="utf-8")

    python_path = launcher.resolve_python_runtime(
        app_root,
        current_executable=str(fallback),
    )

    assert python_path == app_root / "trainer" / "Scripts" / "python.exe"


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
    launcher_exe = tmp_path / "LoreForgeLauncher.exe"
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
    app_root = tmp_path / "not_loreforge"
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
    launcher_exe = tmp_path / "LoreForgeLauncher.exe"
    launcher_exe.write_text("", encoding="utf-8")

    config = launcher.build_launcher_config(
        app_root=app_root,
        env={"LOCALAPPDATA": str(tmp_path / "local")},
        current_executable=str(launcher_exe),
        frozen=True,
    )

    assert config.python_path == launcher_exe
    assert config.command[:3] == (
        str(launcher_exe),
        launcher.INTERNAL_STREAMLIT_FLAG,
        str(app_root / "app.py"),
    )
    assert "-m" not in config.command


def test_launcher_log_path_resolution_uses_localappdata():
    log_path = launcher.resolve_launcher_log_path(
        {"LOCALAPPDATA": "C:/Users/Public/AppData/Local"}
    )

    assert log_path == Path("C:/Users/Public/AppData/Local/LoreForge/logs/launcher.log")


def test_build_launcher_config_reads_preference_and_builds_webapp_command(tmp_path):
    app_root = _make_app_root(tmp_path)
    local_app_data = tmp_path / "local"
    preferences_path = local_app_data / "LoreForge" / "preferences.json"
    preferences_path.parent.mkdir(parents=True)
    preferences_path.write_text(
        json.dumps({"enable_webapp_launch_mode": True}),
        encoding="utf-8",
    )

    config = launcher.build_launcher_config(
        app_root=app_root,
        env={"LOCALAPPDATA": str(local_app_data)},
        current_executable=str(tmp_path / "unused.exe"),
    )

    assert config.launch_mode == launcher.LAUNCH_MODE_WEBAPP
    assert config.preferences_path == preferences_path
    assert config.log_path == local_app_data / "LoreForge" / "logs" / "launcher.log"
    assert config.command[-2:] == ("--", "webapp")


def test_launch_loreforge_logs_and_invokes_subprocess(tmp_path):
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
        pass

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeProcess()

    result = launcher.launch_loreforge(config, popen=fake_popen)

    assert isinstance(result, FakeProcess)
    assert calls == [((command,), {"cwd": app_root})]
    log_text = log_path.read_text(encoding="utf-8")
    assert "launch_mode=normal" in log_text
    assert "command=python.exe -m streamlit run app.py" in log_text
    assert "started_pid=unknown" in log_text


def test_launch_loreforge_reports_port_in_use_without_starting_subprocess(tmp_path):
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
        launcher.launch_loreforge(
            config,
            popen=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("subprocess should not start")
            ),
            port_available_fn=lambda: False,
        )

    assert "Port 8501 is already in use" in str(exc_info.value)
    assert "Port 8501 is already in use" in log_path.read_text(encoding="utf-8")


def test_launch_loreforge_logs_subprocess_failure(tmp_path):
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
        launcher.launch_loreforge(
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
