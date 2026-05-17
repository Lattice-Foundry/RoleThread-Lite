from pathlib import Path
import subprocess

from core.launch import (
    EdgeProcessInfo,
    EdgeProcessSnapshot,
    EdgeWindowInfo,
    EdgeWindowSnapshot,
    EDGE_CLASSIFICATION_APP,
    EDGE_CLASSIFICATION_BROWSER,
    EDGE_CLASSIFICATION_UNCERTAIN,
    EDGE_CLEANUP_STATUS_ATTEMPTED,
    EDGE_CLEANUP_STATUS_SKIPPED,
    EDGE_CLEANUP_METHOD_CLOSE_WINDOW_HANDLE,
    EDGE_CONFIDENCE_LIKELY,
    EDGE_CONFIDENCE_PARTIAL,
    EDGE_CONFIDENCE_UNRELIABLE,
    DEV_FLAG,
    DEFAULT_STREAMLIT_LOCAL_URL,
    EDGE_DEBUG_FLAG,
    EXTERNAL_WEBAPP_LAUNCH_ENV,
    LaunchFlags,
    RECOMMENDED_V1_LAUNCH_COMMAND,
    RECOMMENDED_WEBAPP_STREAMLIT_COMMAND,
    WEBAPP_AUTOMATION_DEFERRED_MESSAGE,
    WEBAPP_DEBUG_FLAG,
    WEBAPP_LAUNCH_STATUS_FALLBACK,
    WEBAPP_UNSUPPORTED_PLATFORM_MESSAGE,
    attempt_webapp_launch,
    build_external_webapp_launch_status,
    build_edge_webapp_command,
    capture_edge_process_snapshot,
    capture_edge_process_snapshot_poll,
    capture_edge_window_snapshot,
    classify_edge_process,
    close_duplicate_edge_browser_window,
    diff_edge_process_snapshots,
    diff_edge_window_snapshots,
    get_streamlit_local_url,
    get_webapp_launch_guidance,
    get_webapp_launch_status,
    is_external_webapp_launcher,
    parse_launch_flags,
    reset_webapp_launch_guard_for_tests,
    should_attempt_webapp_launch,
    should_show_dev_diagnostics,
    supports_managed_webapp_launch,
)
from core.platform import detect_browser_capabilities


def setup_function():
    reset_webapp_launch_guard_for_tests()


def test_parse_launch_flags_detects_webapp_flag():
    assert parse_launch_flags(["webapp"]).webapp is True
    assert parse_launch_flags(["--server.port=8502", "webapp"]).webapp is True


def test_parse_launch_flags_detects_dev_flag():
    flags = parse_launch_flags([DEV_FLAG])
    combined = parse_launch_flags(["webapp", DEV_FLAG, EDGE_DEBUG_FLAG])

    assert flags.dev is True
    assert flags.webapp is False
    assert should_show_dev_diagnostics(flags) is True
    assert combined.dev is True
    assert combined.webapp is True
    assert combined.edge_debug is True


def test_parse_launch_flags_detects_edge_debug_flag_and_alias():
    flags = parse_launch_flags(["webapp", EDGE_DEBUG_FLAG])
    alias_flags = parse_launch_flags(["webapp", WEBAPP_DEBUG_FLAG])

    assert flags.webapp is True
    assert flags.edge_debug is True
    assert alias_flags.edge_debug is True


def test_parse_launch_flags_without_webapp_flag():
    assert parse_launch_flags([]).webapp is False
    assert parse_launch_flags([]).dev is False
    assert parse_launch_flags(["--server.port=8502"]).webapp is False
    assert parse_launch_flags(["--server.port=8502"]).edge_debug is False
    assert should_show_dev_diagnostics(parse_launch_flags(["edge-debug"])) is False


def test_get_streamlit_local_url_uses_default_and_env_override():
    assert get_streamlit_local_url({}) == DEFAULT_STREAMLIT_LOCAL_URL
    assert get_streamlit_local_url({"ROLETHREAD_STREAMLIT_URL": "http://localhost:8502"}) == (
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
        ".venv\\Scripts\\python.exe -m streamlit run app.py "
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


def test_attempt_webapp_launch_does_not_attempt_edge_on_unsupported_platforms():
    for system_name in ("Linux", "Darwin", "FreeBSD"):
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
        assert status.message == WEBAPP_UNSUPPORTED_PLATFORM_MESSAGE
        assert status.status_code == WEBAPP_LAUNCH_STATUS_FALLBACK


def test_supports_managed_webapp_launch_is_windows_edge_only():
    windows = detect_browser_capabilities(
        "Windows",
        home="C:/Users/User",
        env={},
        which_fn=lambda name: "C:/Edge/msedge.exe",
    )
    linux = detect_browser_capabilities(
        "Linux",
        home="/home/user",
        env={},
        which_fn=lambda name: None,
    )
    macos = detect_browser_capabilities(
        "Darwin",
        home="/Users/user",
        env={},
        which_fn=lambda name: None,
    )
    unknown = detect_browser_capabilities(
        "FreeBSD",
        home="/home/user",
        env={},
        which_fn=lambda name: None,
    )

    assert supports_managed_webapp_launch(windows) is True
    assert supports_managed_webapp_launch(linux) is False
    assert supports_managed_webapp_launch(macos) is False
    assert supports_managed_webapp_launch(unknown) is False


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
    assert "already handled" in second.message
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
    assert not should_attempt_webapp_launch(
        LaunchFlags(dev=True, edge_debug=True),
        already_attempted=False,
    )


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
                '"executable_path":"C:\\\\Edge\\\\msedge.exe","window_title":"RoleThread Lite",'
                '"creation_time":"20260516010101.000000-300"},'
                '{"pid":102,"parent_pid":50,"command_line":"msedge http://localhost:8501",'
                '"executable_path":"C:\\\\Edge\\\\msedge.exe","window_title":"RoleThread Lite - Streamlit",'
                '"creation_time":"20260516010102.000000-300"}]'
            ),
            stderr="",
        )

    snapshot = capture_edge_process_snapshot(system_name="Windows", run_fn=run_fn)

    assert len(snapshot.processes) == 2
    assert snapshot.processes[0].pid == 101
    assert snapshot.processes[0].parent_pid == 50
    assert snapshot.processes[0].window_title == "RoleThread Lite"
    assert snapshot.processes[0].creation_time == "20260516010101.000000-300"
    assert "Stop-Process" not in captured_script
    assert "taskkill" not in captured_script.lower()


def test_capture_edge_process_snapshot_handles_empty_output():
    def run_fn(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    snapshot = capture_edge_process_snapshot(system_name="Windows", run_fn=run_fn)

    assert snapshot.processes == ()
    assert snapshot.error == ""


def test_capture_edge_window_snapshot_parses_visible_top_level_windows():
    captured_script = ""

    def run_fn(command, **kwargs):
        nonlocal captured_script
        captured_script = command[-1]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                '[{"handle":"0x1001","pid":101,"title":"RoleThread Lite",'
                '"process_name":"msedge.exe","class_name":"Chrome_WidgetWin_1",'
                '"command_line":"msedge --app=http://localhost:8501"},'
                '{"handle":"0x1002","pid":102,"title":"RoleThread Lite",'
                '"process_name":"ApplicationFrameHost.exe","class_name":"Chrome_WidgetWin_1",'
                '"command_line":"msedge http://localhost:8501"}]'
            ),
            stderr="",
        )

    snapshot = capture_edge_window_snapshot(system_name="Windows", run_fn=run_fn)

    assert len(snapshot.windows) == 2
    assert snapshot.windows[0].handle == "0x1001"
    assert snapshot.windows[0].pid == 101
    assert snapshot.windows[0].process_name == "msedge.exe"
    assert snapshot.windows[0].class_name == "Chrome_WidgetWin_1"
    assert "--app=http://localhost:8501" in snapshot.windows[0].command_line
    assert "Stop-Process" not in captured_script
    assert "taskkill" not in captured_script.lower()


def test_capture_edge_window_snapshot_is_windows_only():
    calls = []

    def run_fn(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("should not inspect windows on non-Windows")

    snapshot = capture_edge_window_snapshot(system_name="Linux", run_fn=run_fn)

    assert snapshot.windows == ()
    assert "Windows-only" in snapshot.error
    assert calls == []


def test_diff_edge_window_snapshots_reports_new_handles():
    before = EdgeWindowSnapshot(
        windows=(
            EdgeWindowInfo(
                handle="0x1001",
                pid=101,
                process_name="msedge.exe",
                title="Existing Edge",
                class_name="Chrome_WidgetWin_1",
            ),
        )
    )
    after = EdgeWindowSnapshot(
        windows=(
            before.windows[0],
            EdgeWindowInfo(
                handle="0x1002",
                pid=102,
                process_name="msedge.exe",
                title="RoleThread Lite",
                class_name="Chrome_WidgetWin_1",
                command_line="msedge http://localhost:8501",
            ),
        )
    )

    diff = diff_edge_window_snapshots(before, after)

    assert diff.before_handles == ("0x1001",)
    assert diff.after_handles == ("0x1001", "0x1002")
    assert diff.new_handles == ("0x1002",)
    assert diff.new_windows[0].pid == 102
    assert "1 new Edge top-level window" in diff.note


def test_capture_edge_process_snapshot_poll_merges_late_metadata():
    snapshots = [
        EdgeProcessSnapshot(
            processes=(
                EdgeProcessInfo(
                    pid=101,
                    parent_pid=10,
                    command_line="",
                    executable_path="C:\\Edge\\msedge.exe",
                    window_title="",
                ),
            )
        ),
        EdgeProcessSnapshot(
            processes=(
                EdgeProcessInfo(
                    pid=101,
                    parent_pid=10,
                    command_line="msedge http://localhost:8501",
                    executable_path="",
                    window_title="RoleThread Lite - Streamlit",
                    creation_time="20260516010101.000000-300",
                ),
            )
        ),
    ]
    calls = []

    def snapshot_fn():
        calls.append("snapshot")
        return snapshots[min(len(calls) - 1, len(snapshots) - 1)]

    delays = []
    result = capture_edge_process_snapshot_poll(
        attempts=2,
        delay_seconds=0.01,
        sleep_fn=lambda delay: delays.append(delay),
        snapshot_fn=snapshot_fn,
    )

    assert result.attempts == 2
    assert delays == [0.01]
    assert len(result.snapshot.processes) == 1
    merged = result.snapshot.processes[0]
    assert merged.command_line == "msedge http://localhost:8501"
    assert merged.executable_path == "C:\\Edge\\msedge.exe"
    assert merged.window_title == "RoleThread Lite - Streamlit"


def test_capture_edge_process_snapshot_uses_detected_platform_diagnostics(monkeypatch):
    calls = []

    def fake_detection():
        return detect_browser_capabilities(
            "Windows",
            home="C:/Users/Scott",
            env={},
            which_fn=lambda name: "C:/Edge/msedge.exe",
        )

    def run_fn(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("core.launch.detect_browser_capabilities", fake_detection)

    snapshot = capture_edge_process_snapshot(run_fn=run_fn)

    assert snapshot.processes == ()
    assert snapshot.error == ""
    assert calls


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
                window_title="RoleThread Lite",
                creation_time="20260516010101.000000-300",
            ),
            EdgeProcessInfo(
                pid=102,
                parent_pid=10,
                command_line="msedge http://localhost:8501",
                executable_path="C:\\Edge\\msedge.exe",
                window_title="RoleThread Lite - Streamlit",
                creation_time="20260516010102.000000-300",
            ),
        )
    )

    diff = diff_edge_process_snapshots(before, after)

    assert diff.before_pids == (100,)
    assert diff.after_pids == (100, 101, 102)
    assert diff.new_pids == (101, 102)
    assert diff.confidence_level == EDGE_CONFIDENCE_LIKELY
    assert [item.classification for item in diff.classifications] == [
        EDGE_CLASSIFICATION_APP,
        EDGE_CLASSIFICATION_BROWSER,
    ]
    assert "app-window candidate" in diff.distinguishability_note
    assert "normal-browser candidate" in diff.distinguishability_note
    assert "101:app_window_candidate" in diff.process_order_note
    assert "102:browser_window_candidate" in diff.process_order_note


def _edge_diff_with_new_processes(*processes: EdgeProcessInfo) -> object:
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
    after = EdgeProcessSnapshot(processes=(before.processes[0], *processes))
    return diff_edge_process_snapshots(before, after)


def _app_process(pid: int = 101) -> EdgeProcessInfo:
    return EdgeProcessInfo(
        pid=pid,
        parent_pid=10,
        command_line="msedge --app=http://localhost:8501",
        executable_path="C:\\Edge\\msedge.exe",
        window_title="RoleThread Lite",
        creation_time="20260516010101.000000-300",
    )


def _browser_process(
    pid: int = 102,
    *,
    command_line: str | None = None,
    window_title: str = "RoleThread Lite - Personal - Microsoft Edge",
) -> EdgeProcessInfo:
    return EdgeProcessInfo(
        pid=pid,
        parent_pid=10,
        command_line=command_line or "msedge http://localhost:8501",
        executable_path="C:\\Edge\\msedge.exe",
        window_title=window_title,
        creation_time="20260516010102.000000-300",
    )


def _uncertain_process(pid: int = 103) -> EdgeProcessInfo:
    return EdgeProcessInfo(
        pid=pid,
        parent_pid=10,
        command_line="msedge --type=utility",
        executable_path="C:\\Edge\\msedge.exe",
        window_title="",
    )


def _window_diff_with_preexisting_browser_and_new_app() -> object:
    before = EdgeWindowSnapshot(
        windows=(
            EdgeWindowInfo(
                handle="0xBEEF",
                pid=23456,
                process_name="msedge.exe",
                title="RoleThread Lite - Personal - Microsoft Edge",
                class_name="Chrome_WidgetWin_1",
                command_line=(
                    '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" '
                    "--single-argument http://localhost:8501/"
                ),
            ),
        )
    )
    after = EdgeWindowSnapshot(
        windows=(
            before.windows[0],
            EdgeWindowInfo(
                handle="0xCAFE",
                pid=23457,
                process_name="msedge.exe",
                title="RoleThread Lite",
                class_name="Chrome_WidgetWin_1",
                command_line=(
                    '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" '
                    "--app=http://localhost:8501"
                ),
            ),
        )
    )
    return diff_edge_window_snapshots(before, after)


def _window_diff_with_new_browser_and_new_app(
    *,
    browser_title: str = "RoleThread Lite - Personal - Microsoft Edge",
    app_title: str = "RoleThread Lite",
    app_command: str = "--app=http://localhost:8501",
) -> object:
    before = EdgeWindowSnapshot(windows=())
    after = EdgeWindowSnapshot(
        windows=(
            EdgeWindowInfo(
                handle="0xBEEF",
                pid=23456,
                process_name="msedge.exe",
                title=browser_title,
                class_name="Chrome_WidgetWin_1",
                command_line=(
                    '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" '
                    "--single-argument http://localhost:8501/"
                ),
            ),
            EdgeWindowInfo(
                handle="0xCAFE",
                pid=23457,
                process_name="msedge.exe",
                title=app_title,
                class_name="Chrome_WidgetWin_1",
                command_line=(
                    '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" '
                    f"{app_command}"
                ),
            ),
        )
    )
    return diff_edge_window_snapshots(before, after)


def test_edge_cleanup_closes_single_likely_browser_candidate_gracefully():
    diff = _edge_diff_with_new_processes(_app_process(), _browser_process())
    commands = []

    def run_fn(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="close_main_window_sent",
            stderr="",
        )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=run_fn,
    )

    assert status.attempted is True
    assert status.skipped is False
    assert status.target_pid == 102
    assert status.status_code == EDGE_CLEANUP_STATUS_ATTEMPTED
    assert status.result == "close_main_window_sent"
    assert commands
    script = commands[0][-1]
    assert "CloseMainWindow" in script
    assert "taskkill" not in script.lower()


def test_edge_cleanup_uses_window_handle_when_browser_preexists_but_app_window_is_new():
    diff = _edge_diff_with_new_processes(_uncertain_process(pid=9340))
    window_diff = _window_diff_with_preexisting_browser_and_new_app()
    commands = []

    def run_fn(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="wm_close_sent",
            stderr="",
        )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        window_diff=window_diff,
        system_name="Windows",
        run_fn=run_fn,
    )

    assert status.attempted is True
    assert status.skipped is False
    assert status.target_pid == 23456
    assert status.target_title == "RoleThread Lite - Personal - Microsoft Edge"
    assert status.method == EDGE_CLEANUP_METHOD_CLOSE_WINDOW_HANDLE
    assert status.result == "wm_close_sent"
    assert commands
    script = commands[0][-1]
    assert "PostMessage" in script
    assert "0xBEEF" in script
    assert "Stop-Process" not in script
    assert "taskkill" not in script.lower()


def test_edge_cleanup_uses_window_handle_when_browser_and_app_are_new():
    diff = _edge_diff_with_new_processes(_uncertain_process(pid=9340))
    window_diff = _window_diff_with_new_browser_and_new_app()
    commands = []

    def run_fn(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="wm_close_sent",
            stderr="",
        )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        window_diff=window_diff,
        system_name="Windows",
        run_fn=run_fn,
    )

    assert status.attempted is True
    assert status.target_pid == 23456
    assert status.method == EDGE_CLEANUP_METHOD_CLOSE_WINDOW_HANDLE
    assert status.result == "wm_close_sent"
    assert status.decision_details
    assert any("browser_window_candidate" in detail for detail in status.decision_details)
    assert any("app_window_candidate" in detail for detail in status.decision_details)
    script = commands[0][-1]
    assert "0xBEEF" in script
    assert "0xCAFE" not in script
    assert "PostMessage" in script
    assert "Stop-Process" not in script
    assert "taskkill" not in script.lower()


def test_edge_cleanup_uses_command_line_when_browser_and_app_titles_match():
    diff = _edge_diff_with_new_processes(_uncertain_process(pid=9340))
    window_diff = _window_diff_with_new_browser_and_new_app(
        browser_title="RoleThread Lite",
        app_title="RoleThread Lite",
    )
    commands = []

    def run_fn(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="wm_close_sent",
            stderr="",
        )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        window_diff=window_diff,
        system_name="Windows",
        run_fn=run_fn,
    )

    assert status.attempted is True
    assert status.method == EDGE_CLEANUP_METHOD_CLOSE_WINDOW_HANDLE
    assert status.target_pid == 23456
    assert any("0xBEEF: browser_window_candidate" in detail for detail in status.decision_details)
    assert any("0xCAFE: app_window_candidate" in detail for detail in status.decision_details)
    script = commands[0][-1]
    assert "0xBEEF" in script
    assert "0xCAFE" not in script
    assert "Stop-Process" not in script


def test_edge_cleanup_treats_embedded_edgeview_window_as_app_candidate():
    diff = _edge_diff_with_new_processes(_uncertain_process(pid=9340))
    window_diff = _window_diff_with_new_browser_and_new_app(
        browser_title="RoleThread Lite",
        app_title="RoleThread Lite",
        app_command="--embedded-browser-edgeview=1 --edge-webview-host-pid=2872",
    )
    commands = []

    def run_fn(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="wm_close_sent",
            stderr="",
        )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        window_diff=window_diff,
        system_name="Windows",
        run_fn=run_fn,
    )

    assert status.attempted is True
    assert status.target_pid == 23456
    assert status.method == EDGE_CLEANUP_METHOD_CLOSE_WINDOW_HANDLE
    assert any("0xCAFE: app_window_candidate" in detail for detail in status.decision_details)
    script = commands[0][-1]
    assert "0xBEEF" in script
    assert "0xCAFE" not in script


def test_edge_cleanup_closes_browser_hwnd_when_edge_reuses_app_process_command():
    diff = _edge_diff_with_new_processes(_uncertain_process(pid=9340))
    before = EdgeWindowSnapshot(
        windows=(
            EdgeWindowInfo(
                handle="0xBEEF",
                pid=25740,
                process_name="msedge.exe",
                title="RoleThread Lite - Personal - Microsoft Edge",
                class_name="Chrome_WidgetWin_1",
                command_line=(
                    '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" '
                    "--embedded-browser-edgeview=1 --edge-webview-host-pid=2872"
                ),
            ),
        )
    )
    after = EdgeWindowSnapshot(
        windows=(
            before.windows[0],
            EdgeWindowInfo(
                handle="0xCAFE",
                pid=25740,
                process_name="msedge.exe",
                title="RoleThread Lite",
                class_name="Chrome_WidgetWin_1",
                command_line=(
                    '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" '
                    "--embedded-browser-edgeview=1 --edge-webview-host-pid=2872"
                ),
            ),
        )
    )
    window_diff = diff_edge_window_snapshots(before, after)
    commands = []

    def run_fn(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="wm_close_sent",
            stderr="",
        )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        window_diff=window_diff,
        system_name="Windows",
        run_fn=run_fn,
    )

    assert status.attempted is True
    assert status.target_pid == 25740
    assert status.target_title == "RoleThread Lite - Personal - Microsoft Edge"
    assert any("0xBEEF: browser_window_candidate" in detail for detail in status.decision_details)
    assert any("0xCAFE: app_window_candidate" in detail for detail in status.decision_details)
    script = commands[0][-1]
    assert "0xBEEF" in script
    assert "0xCAFE" not in script
    assert "Stop-Process" not in script


def test_edge_cleanup_reports_window_candidate_skip_reason():
    diff = _edge_diff_with_new_processes(_uncertain_process(pid=9340))
    window_diff = _window_diff_with_new_browser_and_new_app(browser_title="Unrelated")

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        window_diff=window_diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close ambiguous window")
        ),
    )

    assert status.skipped is True
    assert "browser candidate" in status.message
    assert status.decision_details
    assert any("rejected" in detail for detail in status.decision_details)


def test_edge_cleanup_reports_when_no_app_window_candidate_is_found():
    diff = _edge_diff_with_new_processes(_uncertain_process(pid=9340))
    before = EdgeWindowSnapshot(windows=())
    after = EdgeWindowSnapshot(
        windows=(
            EdgeWindowInfo(
                handle="0xBEEF",
                pid=23456,
                process_name="msedge.exe",
                title="RoleThread Lite",
                class_name="Chrome_WidgetWin_1",
                command_line=(
                    '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" '
                    "--single-argument http://localhost:8501/"
                ),
            ),
        )
    )
    window_diff = diff_edge_window_snapshots(before, after)

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        window_diff=window_diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close without app window evidence")
        ),
    )

    assert status.skipped is True
    assert "no confirmed app-window candidate" in status.message
    assert status.decision_details


def test_edge_cleanup_never_targets_app_candidate():
    diff = _edge_diff_with_new_processes(_app_process())

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close app candidate")
        ),
    )

    assert status.skipped is True
    assert status.status_code == EDGE_CLEANUP_STATUS_SKIPPED


def test_edge_cleanup_skips_uncertain_candidate():
    diff = _edge_diff_with_new_processes(_app_process(), _uncertain_process())

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close uncertain candidate")
        ),
    )

    assert status.skipped is True
    assert "confidence" in status.message


def test_edge_cleanup_skips_preexisting_browser_pid():
    existing_browser = _browser_process(pid=100)
    before = EdgeProcessSnapshot(processes=(existing_browser,))
    after = EdgeProcessSnapshot(processes=(existing_browser, _app_process()))
    diff = diff_edge_process_snapshots(before, after)

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close preexisting browser")
        ),
    )

    assert status.skipped is True
    assert status.target_pid is None


def test_edge_cleanup_skips_multiple_browser_candidates():
    diff = _edge_diff_with_new_processes(
        _app_process(),
        _browser_process(pid=102),
        _browser_process(pid=103, command_line="msedge http://localhost:8501 --new-window"),
    )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close ambiguous browser candidates")
        ),
    )

    assert status.skipped is True
    assert "Expected exactly one" in status.message


def test_edge_cleanup_failure_is_nonfatal():
    diff = _edge_diff_with_new_processes(_app_process(), _browser_process())

    def fail(command, **kwargs):
        raise OSError("nope")

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=fail,
    )

    assert status.attempted is True
    assert status.result == "exception"
    assert "nonfatally" in status.message


def test_edge_cleanup_does_not_fall_back_to_exact_pid_stop_after_graceful_failure():
    diff = _edge_diff_with_new_processes(_app_process(), _browser_process())
    commands = []

    def run_fn(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            3,
            stdout="no_main_window",
            stderr="",
        )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=run_fn,
    )

    assert status.attempted is True
    assert status.target_pid == 102
    assert status.method != "stop_process_exact_pid"
    assert status.result == "no_main_window"
    assert len(commands) == 1
    assert "CloseMainWindow" in commands[0][-1]
    assert "Stop-Process" not in commands[0][-1]
    assert "taskkill" not in commands[0][-1].lower()


def test_edge_cleanup_requires_confirmed_app_window_candidate():
    diff = _edge_diff_with_new_processes(_browser_process())

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close without app candidate")
        ),
    )

    assert status.skipped is True
    assert status.attempted is False


def test_edge_cleanup_skips_process_candidate_without_visible_browser_title():
    diff = _edge_diff_with_new_processes(
        _app_process(),
        _browser_process(window_title=""),
    )

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close renderer-like process")
        ),
    )

    assert status.skipped is True
    assert "visible normal Edge browser title" in status.message


def test_edge_cleanup_skips_without_webapp_flag():
    diff = _edge_diff_with_new_processes(_app_process(), _browser_process())

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=False),
        diff,
        system_name="Windows",
        run_fn=lambda command, **kwargs: (_ for _ in ()).throw(
            AssertionError("should not close without webapp flag")
        ),
    )

    assert status.skipped is True
    assert "not active" in status.message


def test_edge_cleanup_uses_detected_platform_diagnostics(monkeypatch):
    diff = _edge_diff_with_new_processes(_app_process(), _browser_process())
    calls = []

    def fake_detection():
        return detect_browser_capabilities(
            "Windows",
            home="C:/Users/Scott",
            env={},
            which_fn=lambda name: "C:/Edge/msedge.exe",
        )

    def run_fn(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="close_main_window_sent",
            stderr="",
        )

    monkeypatch.setattr("core.launch.detect_browser_capabilities", fake_detection)

    status = close_duplicate_edge_browser_window(
        LaunchFlags(webapp=True),
        diff,
        run_fn=run_fn,
    )

    assert status.attempted is True
    assert calls


def test_classify_edge_process_detects_app_mode_arguments():
    classification = classify_edge_process(
        EdgeProcessInfo(
            pid=1,
            parent_pid=0,
            command_line="msedge --app=http://localhost:8501",
            executable_path="C:\\Edge\\msedge.exe",
            window_title="RoleThread Lite",
        )
    )

    assert classification.classification == EDGE_CLASSIFICATION_APP
    assert classification.confidence == EDGE_CONFIDENCE_LIKELY
    assert any("app-mode" in reason for reason in classification.reasons)


def test_classify_edge_process_detects_normal_browser_by_local_url():
    classification = classify_edge_process(
        EdgeProcessInfo(
            pid=2,
            parent_pid=0,
            command_line="msedge http://localhost:8501",
            executable_path="C:\\Edge\\msedge.exe",
            window_title="RoleThread Lite - Streamlit",
        )
    )

    assert classification.classification == EDGE_CLASSIFICATION_BROWSER
    assert classification.confidence == EDGE_CONFIDENCE_LIKELY
    assert any("local Streamlit URL" in reason for reason in classification.reasons)


def test_classify_edge_process_uses_window_title_as_partial_browser_signal():
    classification = classify_edge_process(
        EdgeProcessInfo(
            pid=3,
            parent_pid=0,
            command_line="msedge --type=renderer",
            executable_path="C:\\Edge\\msedge.exe",
            window_title="RoleThread Lite - Streamlit",
        )
    )

    assert classification.classification == EDGE_CLASSIFICATION_BROWSER
    assert classification.confidence == EDGE_CONFIDENCE_PARTIAL


def test_classify_edge_process_marks_opaque_metadata_uncertain():
    classification = classify_edge_process(
        EdgeProcessInfo(
            pid=4,
            parent_pid=0,
            command_line="msedge --type=utility",
            executable_path="C:\\Edge\\msedge.exe",
            window_title="",
        )
    )

    assert classification.classification == EDGE_CLASSIFICATION_UNCERTAIN
    assert classification.confidence == EDGE_CONFIDENCE_UNRELIABLE
