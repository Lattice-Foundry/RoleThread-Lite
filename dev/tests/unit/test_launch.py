from pathlib import Path

from core.launch import (
    DEFAULT_STREAMLIT_LOCAL_URL,
    LaunchFlags,
    attempt_webapp_launch,
    build_edge_webapp_command,
    get_streamlit_local_url,
    get_webapp_launch_status,
    parse_launch_flags,
    reset_webapp_launch_guard_for_tests,
    should_attempt_webapp_launch,
)
from core.platform import detect_browser_capabilities


def setup_function():
    reset_webapp_launch_guard_for_tests()


def test_parse_launch_flags_detects_webapp_flag():
    assert parse_launch_flags(["webapp"]).webapp is True
    assert parse_launch_flags(["--server.port=8502", "webapp"]).webapp is True


def test_parse_launch_flags_without_webapp_flag():
    assert parse_launch_flags([]).webapp is False
    assert parse_launch_flags(["--server.port=8502"]).webapp is False


def test_get_streamlit_local_url_uses_default_and_env_override():
    assert get_streamlit_local_url({}) == DEFAULT_STREAMLIT_LOCAL_URL
    assert get_streamlit_local_url({"LOREFORGE_STREAMLIT_URL": "http://localhost:8502"}) == (
        "http://localhost:8502"
    )


def test_build_edge_webapp_command():
    edge_path = Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe")
    command = build_edge_webapp_command(
        edge_path,
        "http://localhost:8501",
    )

    assert command == (
        str(edge_path),
        "--app=http://localhost:8501",
    )


def test_attempt_webapp_launch_ignores_missing_flag():
    status = attempt_webapp_launch(LaunchFlags(webapp=False), url="http://localhost:8501")

    assert status.webapp_requested is False
    assert status.attempted is False
    assert status.launched is False
    assert status.fallback_used is False
    assert get_webapp_launch_status() is None


def test_attempt_webapp_launch_uses_edge_when_available_on_windows():
    edge_path = "C:/Program Files/Microsoft/Edge/Application/msedge.exe"
    detection = detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: edge_path,
    )
    commands: list[tuple[str, ...]] = []

    status = attempt_webapp_launch(
        LaunchFlags(webapp=True),
        url="http://localhost:8501",
        browser_detection=detection,
        popen_fn=lambda command: commands.append(tuple(command)),
    )

    assert status.webapp_requested is True
    assert status.edge_available is True
    assert status.attempted is True
    assert status.launched is True
    assert status.fallback_used is False
    assert status.command == (str(Path(edge_path)), "--app=http://localhost:8501")
    assert commands == [status.command]
    assert get_webapp_launch_status() == status


def test_attempt_webapp_launch_falls_back_when_edge_missing_on_windows():
    detection = detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: None,
        path_exists_fn=lambda path: False,
    )

    status = attempt_webapp_launch(
        LaunchFlags(webapp=True),
        url="http://localhost:8501",
        browser_detection=detection,
        popen_fn=lambda command: (_ for _ in ()).throw(AssertionError("should not launch")),
    )

    assert status.webapp_requested is True
    assert status.edge_available is False
    assert status.attempted is False
    assert status.launched is False
    assert status.fallback_used is True
    assert "Edge was not detected" in status.message


def test_attempt_webapp_launch_does_not_attempt_edge_on_non_windows():
    for system_name in ("Linux", "Darwin"):
        reset_webapp_launch_guard_for_tests()
        detection = detect_browser_capabilities(
            system_name,
            home="/home/scott",
            env={},
            which_fn=lambda name: "ignored",
            path_exists_fn=lambda path: True,
        )

        status = attempt_webapp_launch(
            LaunchFlags(webapp=True),
            url="http://localhost:8501",
            browser_detection=detection,
            popen_fn=lambda command: (_ for _ in ()).throw(AssertionError("should not launch")),
        )

        assert status.webapp_requested is True
        assert status.edge_available is False
        assert status.attempted is False
        assert status.launched is False
        assert status.fallback_used is True
        assert "Windows/Microsoft Edge only" in status.message


def test_attempt_webapp_launch_reports_nonfatal_launch_failure():
    edge_path = "C:/Program Files/Microsoft/Edge/Application/msedge.exe"
    detection = detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: edge_path,
    )

    def fail_launch(command):
        raise OSError("boom")

    status = attempt_webapp_launch(
        LaunchFlags(webapp=True),
        url="http://localhost:8501",
        browser_detection=detection,
        popen_fn=fail_launch,
    )

    assert status.edge_available is True
    assert status.attempted is True
    assert status.launched is False
    assert status.fallback_used is True
    assert "Edge launch failed" in status.message


def test_attempt_webapp_launch_is_process_idempotent():
    edge_path = "C:/Program Files/Microsoft/Edge/Application/msedge.exe"
    detection = detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: edge_path,
    )
    commands: list[tuple[str, ...]] = []

    first = attempt_webapp_launch(
        LaunchFlags(webapp=True),
        url="http://localhost:8501",
        browser_detection=detection,
        popen_fn=lambda command: commands.append(tuple(command)),
    )
    second = attempt_webapp_launch(
        LaunchFlags(webapp=True),
        url="http://localhost:8501",
        browser_detection=detection,
        popen_fn=lambda command: commands.append(tuple(command)),
    )

    assert first.launched is True
    assert first.attempted is True
    assert second.launched is False
    assert second.attempted is False
    assert second.status_code == "already_attempted"
    assert "already attempted" in second.message
    assert commands == [first.command]


def test_should_attempt_webapp_launch_guards_reruns():
    assert should_attempt_webapp_launch(LaunchFlags(webapp=True), already_attempted=False)
    assert not should_attempt_webapp_launch(LaunchFlags(webapp=True), already_attempted=True)
    assert not should_attempt_webapp_launch(LaunchFlags(webapp=False), already_attempted=False)
