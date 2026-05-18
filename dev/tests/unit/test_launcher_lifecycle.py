from core.launcher_lifecycle import (
    format_port_release_lifecycle_status,
    report_lifecycle_status,
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
