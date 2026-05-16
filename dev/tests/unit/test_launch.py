from pathlib import Path
import subprocess

from core.launch import (
    EdgeProcessInfo,
    EdgeProcessSnapshot,
    DEFAULT_STREAMLIT_LOCAL_URL,
    EDGE_DEBUG_FLAG,
    EXTERNAL_WEBAPP_LAUNCH_ENV,
    LaunchFlags,
    RECOMMENDED_V1_LAUNCH_COMMAND,
    RECOMMENDED_WEBAPP_STREAMLIT_COMMAND,
    WEBAPP_AUTOMATION_DEFERRED_MESSAGE,
    WEBAPP_DEBUG_FLAG,
    attempt_webapp_launch,
    build_external_webapp_launch_status,
    build_edge_webapp_command,
    capture_edge_process_snapshot,
    diff_edge_process_snapshots,
    get_streamlit_local_url,
    get_webapp_launch_guidance,
    get_webapp_launch_status,
    is_external_webapp_launcher,
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


def test_parse_launch_flags_detects_edge_debug_flag_and_alias():
    flags = parse_launch_flags(["webapp", EDGE_DEBUG_FLAG])
    alias_flags = parse_launch_flags(["webapp", WEBAPP_DEBUG_FLAG])

    assert flags.webapp is True
    assert flags.edge_debug is True
    assert alias_flags.edge_debug is True


def test_parse_launch_flags_without_webapp_flag():
    assert parse_launch_flags([]).webapp is False
    assert parse_launch_flags(["--server.port=8502"]).webapp is False
    assert parse_launch_flags(["--server.port=8502"]).edge_debug is False


def test_get_streamlit_local_url_uses_default_and_env_override():
    assert get_streamlit_local_url({}) == DEFAULT_STREAMLIT_LOCAL_URL
    assert get_streamlit_local_url({"LOREFORGE_STREAMLIT_URL": "http://localhost:8502"}) == (
        "http://localhost:8502"
    )


def test_external_webapp_launcher_env_detection():
    assert is_external_webapp_launcher({EXTERNAL_WEBAPP_LAUNCH_ENV: "1"}) is True
    assert is_external_webapp_launcher({EXTERNAL_WEBAPP_LAUNCH_ENV: "true"}) is True
    assert is_external_webapp_launcher({EXTERNAL_WEBAPP_LAUNCH_ENV: "yes"}) is True
    assert is_external_webapp_launcher({EXTERNAL_WEBAPP_LAUNCH_ENV: "0"}) is False
    assert is_external_webapp_launcher({}) is False


def test_recommended_webapp_commands():
    assert RECOMMENDED_V1_LAUNCH_COMMAND == "streamlit run app.py"
    assert RECOMMENDED_WEBAPP_STREAMLIT_COMMAND == (
        "trainer\\Scripts\\python.exe -m streamlit run app.py "
        "--server.headless true --server.port 8501 -- webapp"
    )


def test_webapp_guidance_warns_when_streamlit_headless_is_inactive():
    guidance = get_webapp_launch_guidance(
        LaunchFlags(webapp=True),
        streamlit_headless=False,
    )

    assert guidance.webapp_requested is True
    assert guidance.streamlit_headless is False
    assert guidance.normal_browser_suppressed is False
    assert guidance.warning is True
    assert guidance.can_suppress_from_app is False
    assert guidance.recommended_command == "streamlit run app.py"
    assert WEBAPP_AUTOMATION_DEFERRED_MESSAGE in guidance.message


def test_webapp_guidance_confirms_headless_suppression():
    guidance = get_webapp_launch_guidance(
        LaunchFlags(webapp=True),
        streamlit_headless=True,
    )

    assert guidance.webapp_requested is True
    assert guidance.external_launcher is False
    assert guidance.streamlit_headless is True
    assert guidance.normal_browser_suppressed is True
    assert guidance.warning is True
    assert guidance.can_suppress_from_app is False


def test_webapp_guidance_prefers_external_launcher_when_active():
    guidance = get_webapp_launch_guidance(
        LaunchFlags(webapp=True),
        streamlit_headless=True,
        external_launcher=True,
    )

    assert guidance.webapp_requested is True
    assert guidance.external_launcher is True
    assert guidance.streamlit_headless is True
    assert guidance.normal_browser_suppressed is True
    assert guidance.warning is True
    assert WEBAPP_AUTOMATION_DEFERRED_MESSAGE in guidance.message


def test_webapp_guidance_handles_unknown_streamlit_headless_state():
    guidance = get_webapp_launch_guidance(
        LaunchFlags(webapp=True),
        streamlit_headless=None,
    )

    assert guidance.webapp_requested is True
    assert guidance.streamlit_headless is None
    assert guidance.normal_browser_suppressed is False
    assert guidance.warning is True
    assert WEBAPP_AUTOMATION_DEFERRED_MESSAGE in guidance.message


def test_webapp_guidance_is_quiet_when_flag_is_missing():
    guidance = get_webapp_launch_guidance(
        LaunchFlags(webapp=False),
        streamlit_headless=False,
    )

    assert guidance.webapp_requested is False
    assert guidance.external_launcher is False
    assert guidance.warning is False
    assert guidance.message == "Web-app launch mode is not active."


def test_external_launch_status_records_app_skip():
    status = build_external_webapp_launch_status(
        LaunchFlags(webapp=True),
        url="http://localhost:8501",
    )

    assert status is not None
    assert status.webapp_requested is True
    assert status.attempted is False
    assert status.launched is False
    assert status.status_code == "external_orchestrated"
    assert "experimental and deferred" in status.message


def test_external_launch_status_ignores_missing_flag():
    assert build_external_webapp_launch_status(LaunchFlags(webapp=False)) is None


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
    assert not should_attempt_webapp_launch(
        LaunchFlags(webapp=True),
        already_attempted=False,
        external_launcher=True,
    )
    assert not should_attempt_webapp_launch(LaunchFlags(webapp=False), already_attempted=False)


def test_capture_edge_process_snapshot_is_windows_only():
    calls = []

    def run_fn(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("should not inspect processes on non-Windows")

    snapshot = capture_edge_process_snapshot(system_name="Linux", run_fn=run_fn)

    assert snapshot.processes == ()
    assert "Windows-only" in snapshot.error
    assert calls == []


def test_capture_edge_process_snapshot_parses_powershell_json_without_kill_commands():
    captured_script = ""

    def run_fn(command, **kwargs):
        nonlocal captured_script
        captured_script = command[-1]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                '[{"pid":101,"parent_pid":50,"command_line":"msedge --app=http://localhost:8501",'
                '"executable_path":"C:\\\\Edge\\\\msedge.exe","window_title":"LoreForge Lite"},'
                '{"pid":102,"parent_pid":50,"command_line":"msedge http://localhost:8501",'
                '"executable_path":"C:\\\\Edge\\\\msedge.exe","window_title":"LoreForge Lite - Streamlit"}]'
            ),
            stderr="",
        )

    snapshot = capture_edge_process_snapshot(system_name="Windows", run_fn=run_fn)

    assert len(snapshot.processes) == 2
    assert snapshot.processes[0].pid == 101
    assert snapshot.processes[0].parent_pid == 50
    assert snapshot.processes[0].window_title == "LoreForge Lite"
    assert "Stop-Process" not in captured_script
    assert "taskkill" not in captured_script.lower()


def test_capture_edge_process_snapshot_handles_empty_output():
    def run_fn(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    snapshot = capture_edge_process_snapshot(system_name="Windows", run_fn=run_fn)

    assert snapshot.processes == ()
    assert snapshot.error == ""


def test_diff_edge_process_snapshots_reports_new_candidates():
    before = EdgeProcessSnapshot(
        processes=(
            EdgeProcessInfo(
                pid=100,
                parent_pid=10,
                command_line="msedge existing",
                executable_path="C:\\Edge\\msedge.exe",
                window_title="Existing",
            ),
        )
    )
    after = EdgeProcessSnapshot(
        processes=(
            before.processes[0],
            EdgeProcessInfo(
                pid=101,
                parent_pid=10,
                command_line="msedge --app=http://localhost:8501",
                executable_path="C:\\Edge\\msedge.exe",
                window_title="LoreForge Lite",
            ),
            EdgeProcessInfo(
                pid=102,
                parent_pid=10,
                command_line="msedge http://localhost:8501",
                executable_path="C:\\Edge\\msedge.exe",
                window_title="LoreForge Lite - Streamlit",
            ),
        )
    )

    diff = diff_edge_process_snapshots(before, after)

    assert diff.before_pids == (100,)
    assert diff.after_pids == (100, 101, 102)
    assert diff.new_pids == (101, 102)
    assert "app-mode candidate" in diff.distinguishability_note
    assert "normal-browser candidate" in diff.distinguishability_note
