from core.launcher_lifecycle import (
    EdgeLaunchResult,
    HealthCheckResult,
    LauncherConfig,
    PortReleaseStatus,
    ShutdownRequestResult,
    TerminationResult,
    WindowCloseDetectionResult,
    format_port_release_lifecycle_status,
    report_lifecycle_status,
    run_launcher_lifecycle,
)


def test_report_lifecycle_status_is_noop_without_callback():
    assert report_lifecycle_status(None, "ignored") is None


def test_report_lifecycle_status_calls_callback():
    messages = []

    report_lifecycle_status(messages.append, "waiting for health")

    assert messages == ["waiting for health"]


def test_format_port_release_lifecycle_status():
    assert (
        format_port_release_lifecycle_status("Port 8501 is released.")
        == "Port release: Port 8501 is released."
    )


def test_shared_lifecycle_orchestrates_managed_webapp_steps_in_order(tmp_path):
    calls = []
    status_messages = []
    log_entries = []
    config = LauncherConfig(
        app_root=tmp_path,
        python_path=tmp_path / "python.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        launch_mode="webapp",
        command=("python.exe", "-m", "streamlit", "--server.headless", "true"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 1234

    def write_log(path, lines):
        log_entries.append((path, tuple(lines)))

    result = run_launcher_lifecycle(
        config,
        launch_backend_fn=lambda cfg: calls.append("launch_backend") or FakeProcess(),
        health_check_fn=lambda: calls.append("health")
        or HealthCheckResult(True, "health-url", 1, "healthy"),
        wait_for_close_fn=lambda mode, process: calls.append("wait_for_close")
        or WindowCloseDetectionResult(True, True, True, "closed"),
        shutdown_request_fn=lambda cfg: calls.append("shutdown")
        or ShutdownRequestResult(True, True, 200, "shutdown ok"),
        termination_fn=lambda process: (_ for _ in ()).throw(
            AssertionError("termination should not run")
        ),
        port_release_fn=lambda pid: calls.append("port_release")
        or PortReleaseStatus(True, None, "free", "released"),
        edge_launch_fn=lambda: calls.append("edge_launch")
        or EdgeLaunchResult(True, True, ("msedge", "--app=http://127.0.0.1:8501"), "launched"),
        write_log_fn=write_log,
        format_command_fn=lambda command: " ".join(command),
        wait_for_process_exit_fn=lambda process: calls.append("wait_for_exit") or True,
        status_callback=status_messages.append,
    )

    assert result.final_state == "graceful_shutdown"
    assert calls == [
        "launch_backend",
        "health",
        "edge_launch",
        "wait_for_close",
        "shutdown",
        "wait_for_exit",
        "port_release",
    ]
    assert any("lifecycle=health_check" in lines for _, lines in log_entries)
    assert any("lifecycle=edge_webapp_launch" in lines for _, lines in log_entries)
    assert any("lifecycle=shutdown_request" in lines for _, lines in log_entries)
    assert any("lifecycle=port_release" in lines for _, lines in log_entries)
    joined_status = "\n".join(status_messages)
    assert "Launching Edge app-mode window." in joined_status
    assert "App window closed; requesting graceful backend shutdown." in joined_status
    assert "Port release: released" in joined_status


def test_shared_lifecycle_terminates_owned_backend_when_health_fails(tmp_path):
    calls = []
    config = LauncherConfig(
        app_root=tmp_path,
        python_path=tmp_path / "python.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        launch_mode="webapp",
        command=("python.exe", "-m", "streamlit"),
    )

    class FakeProcess:
        pid = 5678

    result = run_launcher_lifecycle(
        config,
        launch_backend_fn=lambda cfg: calls.append("launch_backend") or FakeProcess(),
        health_check_fn=lambda: calls.append("health")
        or HealthCheckResult(False, "health-url", 3, "timeout"),
        wait_for_close_fn=lambda mode, process: (_ for _ in ()).throw(
            AssertionError("window monitoring should not run")
        ),
        shutdown_request_fn=lambda cfg: (_ for _ in ()).throw(
            AssertionError("shutdown should not run")
        ),
        termination_fn=lambda process: calls.append("terminate")
        or TerminationResult(True, "terminate", True, "terminated"),
        port_release_fn=lambda pid: calls.append("port_release")
        or PortReleaseStatus(True, None, "free", "released"),
        edge_launch_fn=lambda: (_ for _ in ()).throw(
            AssertionError("browser launch should not run")
        ),
        write_log_fn=lambda path, lines: None,
        format_command_fn=lambda command: " ".join(command),
        wait_for_process_exit_fn=lambda process: (_ for _ in ()).throw(
            AssertionError("graceful wait should not run")
        ),
    )

    assert result.final_state == "health_failed"
    assert result.shutdown_request.attempted is False
    assert result.termination.method == "terminate"
    assert calls == ["launch_backend", "health", "terminate", "port_release"]


def test_shared_lifecycle_reports_cloud_sync_warning_before_fallback_termination(tmp_path):
    calls = []
    status_messages = []
    log_entries = []
    config = LauncherConfig(
        app_root=tmp_path,
        python_path=tmp_path / "python.exe",
        preferences_path=tmp_path / "preferences.json",
        log_path=tmp_path / "launcher.log",
        launch_mode="webapp",
        command=("python.exe", "-m", "streamlit"),
        shutdown_port=54321,
        shutdown_token="secret",
    )

    class FakeProcess:
        pid = 2468

    result = run_launcher_lifecycle(
        config,
        launch_backend_fn=lambda cfg: calls.append("launch_backend") or FakeProcess(),
        health_check_fn=lambda: calls.append("health")
        or HealthCheckResult(True, "health-url", 1, "healthy"),
        wait_for_close_fn=lambda mode, process: calls.append("wait_for_close")
        or WindowCloseDetectionResult(True, True, True, "closed"),
        shutdown_request_fn=lambda cfg: calls.append("shutdown")
        or ShutdownRequestResult(True, True, 200, "shutdown ok"),
        termination_fn=lambda process: calls.append("terminate")
        or TerminationResult(True, "terminate", True, "terminated"),
        port_release_fn=lambda pid: calls.append("port_release")
        or PortReleaseStatus(True, None, "free", "released"),
        edge_launch_fn=lambda: calls.append("edge_launch")
        or EdgeLaunchResult(True, True, ("msedge", "--app=http://127.0.0.1:8501"), "launched"),
        write_log_fn=lambda path, lines: log_entries.append(tuple(lines)),
        format_command_fn=lambda command: " ".join(command),
        wait_for_process_exit_fn=lambda process: calls.append("wait_for_exit") or False,
        status_callback=status_messages.append,
    )

    assert result.final_state == "terminated"
    assert calls == [
        "launch_backend",
        "health",
        "edge_launch",
        "wait_for_close",
        "shutdown",
        "wait_for_exit",
        "terminate",
        "port_release",
    ]
    assert status_messages.index(
        "Cloud sync warning: Graceful closeout did not complete before shutdown timeout."
    ) < status_messages.index(
        "Graceful shutdown did not complete; terminating owned backend."
    )
    assert any("lifecycle=cloud_sync_shutdown_timeout" in lines for lines in log_entries)
