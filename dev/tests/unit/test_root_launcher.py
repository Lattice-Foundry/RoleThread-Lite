from pathlib import Path

import launch as root_launcher
from core.launcher_console import (
    ANSI_MINT,
    ANSI_STREAMLIT_BLUE,
    format_launcher_status,
    strip_ansi,
    terminal_supports_ansi,
)
from installer.windows.launcher import rolethread_launcher as launcher


def _make_app_root(tmp_path: Path) -> Path:
    app_root = tmp_path / "rolethread"
    app_root.mkdir()
    (app_root / "app.py").write_text("print('RoleThread')\n", encoding="utf-8")
    return app_root


def test_parse_launch_args_defaults_to_browser_mode():
    options = root_launcher.parse_launch_args([])

    assert options.launch_mode == launcher.LAUNCH_MODE_NORMAL
    assert options.debug is False


def test_parse_launch_args_supports_webapp_and_debug():
    options = root_launcher.parse_launch_args(["--webapp", "--debug"])

    assert options.launch_mode == launcher.LAUNCH_MODE_WEBAPP
    assert options.debug is True


def test_parse_launch_args_supports_diag_alias_for_launcher_debug():
    options = root_launcher.parse_launch_args(["--webapp", "--diag"])

    assert options.launch_mode == launcher.LAUNCH_MODE_WEBAPP
    assert options.debug is True


def test_manual_webapp_config_starts_streamlit_headless(tmp_path):
    app_root = _make_app_root(tmp_path)
    python_path = tmp_path / "python.exe"
    python_path.write_text("", encoding="utf-8")

    config = root_launcher.build_manual_launcher_config(
        root_launcher.LaunchOptions(launch_mode=launcher.LAUNCH_MODE_WEBAPP),
        app_root=app_root,
        env={"LOCALAPPDATA": str(tmp_path / "local")},
        current_executable=str(python_path),
        shutdown_port=54321,
        shutdown_token="token",
    )

    assert config.app_root == app_root.resolve()
    assert config.launch_mode == launcher.LAUNCH_MODE_WEBAPP
    assert config.bundled_mode is False
    assert config.shutdown_port == 54321
    assert config.shutdown_token == "token"
    assert config.command[:4] == (str(python_path), "-m", "streamlit", "run")
    assert "--server.port" in config.command
    assert config.command[config.command.index("--server.port") + 1] == "8501"
    assert "--server.address" in config.command
    assert config.command[config.command.index("--server.address") + 1] == "127.0.0.1"
    assert "--server.headless" in config.command
    assert config.command[config.command.index("--server.headless") + 1] == "true"
    assert "--" not in config.command


def test_manual_browser_config_keeps_normal_streamlit_browser_flow(tmp_path):
    app_root = _make_app_root(tmp_path)
    python_path = tmp_path / "python.exe"
    python_path.write_text("", encoding="utf-8")

    config = root_launcher.build_manual_launcher_config(
        root_launcher.LaunchOptions(launch_mode=launcher.LAUNCH_MODE_NORMAL),
        app_root=app_root,
        env={"LOCALAPPDATA": str(tmp_path / "local")},
        current_executable=str(python_path),
        shutdown_port=54321,
        shutdown_token="token",
    )

    assert config.launch_mode == launcher.LAUNCH_MODE_NORMAL
    assert "--server.headless" not in config.command
    assert "--server.address" not in config.command
    assert config.command == (
        str(python_path),
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        "8501",
    )


def test_webapp_run_delegates_to_lifecycle_with_status_callback():
    calls = []

    config = launcher.LauncherConfig(
        app_root=Path("X:/rolethread"),
        python_path=Path("python.exe"),
        preferences_path=Path("preferences.json"),
        log_path=Path("launcher.log"),
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit", "run", "app.py"),
    )

    def build_config(options):
        calls.append(("config", options.launch_mode))
        return config

    def run_lifecycle(config_arg, *, status_callback=None):
        calls.append(("lifecycle", config_arg.launch_mode))
        calls.append(("status_callback", callable(status_callback)))

    exit_code = root_launcher.run(
        ["--webapp"],
        config_builder=build_config,
        lifecycle_fn=run_lifecycle,
    )

    assert exit_code == 0
    assert calls == [
        ("config", launcher.LAUNCH_MODE_WEBAPP),
        ("lifecycle", launcher.LAUNCH_MODE_WEBAPP),
        ("status_callback", True),
    ]


def test_browser_run_without_debug_keeps_quiet_lifecycle_callback():
    calls = []
    config = launcher.LauncherConfig(
        app_root=Path("X:/rolethread"),
        python_path=Path("python.exe"),
        preferences_path=Path("preferences.json"),
        log_path=Path("launcher.log"),
        launch_mode=launcher.LAUNCH_MODE_NORMAL,
        command=("python.exe", "-m", "streamlit", "run", "app.py"),
    )

    def build_config(options):
        calls.append(("config", options.launch_mode))
        return config

    def run_lifecycle(config_arg):
        calls.append(("lifecycle", config_arg.launch_mode))

    exit_code = root_launcher.run(
        ["--browser"],
        config_builder=build_config,
        lifecycle_fn=run_lifecycle,
    )

    assert exit_code == 0
    assert calls == [
        ("config", launcher.LAUNCH_MODE_NORMAL),
        ("lifecycle", launcher.LAUNCH_MODE_NORMAL),
    ]


def test_webapp_run_prints_lifecycle_status_without_debug(capsys):
    config = launcher.LauncherConfig(
        app_root=Path("X:/rolethread"),
        python_path=Path("python.exe"),
        preferences_path=Path("preferences.json"),
        log_path=Path("launcher.log"),
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=("python.exe", "-m", "streamlit", "run", "app.py"),
    )

    def build_config(options):
        return config

    def run_lifecycle(config_arg, *, status_callback=None):
        status_callback("Waiting for Streamlit health endpoint.")
        status_callback("Launching Edge app-mode window.")

    exit_code = root_launcher.run(
        ["--webapp"],
        config_builder=build_config,
        lifecycle_fn=run_lifecycle,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[RoleThread Launcher] Building launcher configuration." not in output
    assert "[RoleThread Launcher] Command:" not in output
    assert "[RoleThread Launcher] Waiting for Streamlit health endpoint." in output
    assert "[RoleThread Launcher] Launching Edge app-mode window." in output


def test_debug_run_prints_lifecycle_status_and_configuration(capsys):
    config = launcher.LauncherConfig(
        app_root=Path("X:/rolethread"),
        python_path=Path("python.exe"),
        preferences_path=Path("preferences.json"),
        log_path=Path("launcher.log"),
        launch_mode=launcher.LAUNCH_MODE_WEBAPP,
        command=(
            "python.exe",
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless",
            "true",
        ),
    )

    def build_config(options):
        return config

    def run_lifecycle(config_arg, *, status_callback=None):
        status_callback("Waiting for Streamlit health endpoint.")
        status_callback("Launching Edge app-mode window.")
        status_callback("Backend exited after graceful shutdown.")

    exit_code = root_launcher.run(
        ["--webapp", "--debug"],
        config_builder=build_config,
        lifecycle_fn=run_lifecycle,
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[RoleThread Launcher] Building launcher configuration." in output
    assert "[RoleThread Launcher] Managed webapp mode: Streamlit will start headless." in output
    assert "--server.headless true" in output
    assert "[RoleThread Launcher] Waiting for Streamlit health endpoint." in output
    assert "[RoleThread Launcher] Launching Edge app-mode window." in output
    assert "[RoleThread Launcher] Backend exited after graceful shutdown." in output


def test_launcher_status_formatting_keeps_plain_text_without_color():
    formatted = format_launcher_status("Streamlit health: endpoint responded.", color=False)

    assert formatted == "[RoleThread Launcher] Streamlit health: endpoint responded."


def test_launcher_status_formatting_colors_prefix_and_lifecycle_label():
    formatted = format_launcher_status("Streamlit health: endpoint responded.", color=True)

    assert ANSI_MINT in formatted
    assert ANSI_STREAMLIT_BLUE in formatted
    assert strip_ansi(formatted) == "[RoleThread Launcher] Streamlit health: endpoint responded."


def test_launcher_status_formatting_does_not_color_non_label_message_body():
    formatted = format_launcher_status("Monitoring app window for close.", color=True)

    assert ANSI_MINT in formatted
    assert ANSI_STREAMLIT_BLUE not in formatted
    assert strip_ansi(formatted) == "[RoleThread Launcher] Monitoring app window for close."


def test_terminal_supports_ansi_honors_no_color_and_force_color():
    class NonTty:
        def isatty(self):
            return False

    assert terminal_supports_ansi(stream=NonTty(), env={"FORCE_COLOR": "1"}) is True
    assert terminal_supports_ansi(stream=NonTty(), env={"NO_COLOR": "1"}) is False
    assert terminal_supports_ansi(stream=NonTty(), env={}) is False
