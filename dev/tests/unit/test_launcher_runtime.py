from pathlib import Path

import pytest

from core.launcher_runtime import (
    LAUNCH_MODE_NORMAL,
    LAUNCH_MODE_WEBAPP,
    build_launcher_shutdown_url,
    build_streamlit_app_url,
    build_streamlit_command,
    build_streamlit_health_url,
    format_command,
)


def test_shared_dev_webapp_command_is_headless_loopback_and_keeps_separator(tmp_path):
    python_path = tmp_path / "python.exe"

    command = build_streamlit_command(python_path, launch_mode=LAUNCH_MODE_WEBAPP)

    assert command == (
        str(python_path),
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        "8501",
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--",
        "webapp",
    )


def test_shared_normal_command_preserves_streamlit_browser_flow(tmp_path):
    python_path = tmp_path / "python.exe"

    command = build_streamlit_command(python_path, launch_mode=LAUNCH_MODE_NORMAL)

    assert command == (
        str(python_path),
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.port",
        "8501",
    )
    assert "--server.address" not in command
    assert "--server.headless" not in command


def test_shared_bundled_webapp_command_uses_internal_streamlit_adapter(tmp_path):
    launcher_path = tmp_path / "RoleThreadLauncher.exe"
    app_script = tmp_path / "app.py"

    command = build_streamlit_command(
        launcher_path,
        launch_mode=LAUNCH_MODE_WEBAPP,
        app_script=app_script,
        internal_streamlit_flag="--rolethread-run-streamlit",
    )

    assert command[:5] == (
        str(launcher_path),
        "--rolethread-run-streamlit",
        str(app_script),
        "--global.developmentMode=false",
        "--server.port",
    )
    assert command[-2:] == ("--", "webapp")
    assert "--server.address" in command
    assert "--server.headless" in command


def test_shared_command_rejects_unknown_launch_mode(tmp_path):
    with pytest.raises(ValueError, match="Unknown launch mode"):
        build_streamlit_command(tmp_path / "python.exe", launch_mode="other")


def test_shared_command_rejects_bundled_command_without_internal_flag(tmp_path):
    with pytest.raises(ValueError, match="internal flag"):
        build_streamlit_command(
            tmp_path / "python.exe",
            launch_mode=LAUNCH_MODE_WEBAPP,
            app_script=tmp_path / "app.py",
        )


def test_shared_launcher_urls_use_loopback_defaults():
    assert build_streamlit_health_url() == "http://127.0.0.1:8501/_stcore/health"
    assert build_streamlit_app_url() == "http://127.0.0.1:8501"
    assert build_launcher_shutdown_url(port=54321) == "http://127.0.0.1:54321/shutdown"


def test_format_command_quotes_arguments_with_spaces():
    assert format_command(("python.exe", "path with spaces/app.py")) == (
        'python.exe "path with spaces/app.py"'
    )
