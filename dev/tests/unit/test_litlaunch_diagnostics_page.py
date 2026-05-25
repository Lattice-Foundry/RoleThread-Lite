import ast
import importlib
import json
from pathlib import Path

import ui.litlaunch_diagnostics as diagnostics_page
from core.product_log import PRODUCT_LOG_PATH_ENV


def test_generated_litlaunch_diagnostics_page_imports_and_parses():
    source_path = Path(diagnostics_page.__file__)
    source = source_path.read_text(encoding="utf-8")

    ast.parse(source)

    assert callable(diagnostics_page.render_litlaunch_diagnostics)
    assert diagnostics_page.APP_NAME == "RoleThread Lite"
    assert diagnostics_page.PROFILE_NAME == "rolethread-webapp"
    assert diagnostics_page.THEME == "auto"
    assert diagnostics_page.EVENT_LOG_PATH == r".litlaunch\runtime-events.log"
    assert diagnostics_page.EVENT_LOG_ENV_VAR == PRODUCT_LOG_PATH_ENV
    assert "litlaunch-support-bundle.txt" in source
    assert "use_container_width" not in source
    assert 'width="stretch"' in source
    assert 'st.subheader("Runtime Event Trail")' in source
    assert "Runtime Sessions" not in source
    assert "Raw Runtime Event Trail" in source
    assert "litlaunch-console" in source


def test_generated_litlaunch_diagnostics_page_resolves_event_log(monkeypatch):
    monkeypatch.delenv(PRODUCT_LOG_PATH_ENV, raising=False)
    reloaded = importlib.reload(diagnostics_page)

    assert reloaded._runtime_event_log_path() == Path(
        r".litlaunch\runtime-events.log"
    ).resolve()

    monkeypatch.setenv(
        PRODUCT_LOG_PATH_ENV,
        r"C:\Users\tester\AppData\Local\RoleThread\logs\launcher.log",
    )

    reloaded = importlib.reload(diagnostics_page)

    assert reloaded._runtime_event_log_path() == Path(
        r"C:\Users\tester\AppData\Local\RoleThread\logs\launcher.log"
    )

    monkeypatch.delenv(PRODUCT_LOG_PATH_ENV, raising=False)
    importlib.reload(diagnostics_page)


def test_generated_litlaunch_diagnostics_page_counts_jsonl_events(
    monkeypatch,
    tmp_path,
):
    event_log = tmp_path / "runtime-events.log"
    records = [
        {"category": "launch", "details": {"token": "secret"}},
        {"category": "backend"},
        {"category": "launch"},
        {"category": ""},
        {"category": 123},
    ]
    event_log.write_text(
        "\n".join(json.dumps(record) for record in records)
        + "\nnot-json\nlitlaunch_event level=info category=hook name=done",
        encoding="utf-8",
    )
    monkeypatch.setenv(PRODUCT_LOG_PATH_ENV, str(event_log))
    reloaded = importlib.reload(diagnostics_page)

    assert reloaded._event_category_counts() == {
        "backend": 1,
        "hook": 1,
        "launch": 2,
    }

    monkeypatch.delenv(PRODUCT_LOG_PATH_ENV, raising=False)
    importlib.reload(diagnostics_page)


def test_generated_litlaunch_diagnostics_page_groups_sessions_newest_first():
    records = [
        {
            "name": "launch_planned",
            "category": "launch",
            "level": "info",
            "timestamp": "2026-05-24T21:00:00+00:00",
            "details": {"mode": "webapp", "browser": "Microsoft Edge"},
        },
        {
            "name": "port_released",
            "category": "port",
            "level": "info",
            "timestamp": "2026-05-24T21:00:03+00:00",
            "details": {"host": "127.0.0.1", "port": "8501"},
        },
        {
            "name": "launch_planned",
            "category": "launch",
            "level": "info",
            "timestamp": "2026-05-24T22:00:00+00:00",
            "details": {
                "mode": "webapp",
                "browser": "Microsoft Edge",
                "host": "127.0.0.1",
                "port": "8501",
            },
        },
        {
            "name": "monitor_started",
            "category": "monitor",
            "level": "info",
            "timestamp": "2026-05-24T22:00:01+00:00",
            "details": {"target": "RoleThread Lite"},
        },
        {
            "name": "hook_succeeded",
            "category": "hook",
            "level": "info",
            "timestamp": "2026-05-24T22:00:02+00:00",
            "details": {"label": "Cloud backup sync"},
        },
        {
            "name": "port_released",
            "category": "port",
            "level": "info",
            "timestamp": "2026-05-24T22:00:04+00:00",
            "details": {"host": "127.0.0.1", "port": "8501"},
        },
    ]

    sessions = diagnostics_page._group_runtime_sessions(records)

    assert [session[0]["timestamp"] for session in sessions] == [
        "2026-05-24T22:00:00+00:00",
        "2026-05-24T21:00:00+00:00",
    ]
    summary = diagnostics_page._summarize_runtime_session(sessions[0])
    assert summary["title"] == "Webapp launched in Microsoft Edge"
    assert summary["fields"]["Duration"] == "4.0s"
    assert summary["fields"]["Status"] == "Clean shutdown"
    assert summary["fields"]["Host"] == "127.0.0.1"
    assert summary["fields"]["Port"] == "8501"
    assert summary["fields"]["Hooks"] == "1 completed, 0 failed"


def test_generated_litlaunch_diagnostics_page_formats_console_replay_line():
    record = {
        "name": "backend_started",
        "category": "backend",
        "level": "info",
        "timestamp": "2026-05-24T22:00:01+00:00",
        "message": "Started Streamlit backend.",
        "details": {"pid": 1234},
    }

    line = diagnostics_page._console_event_line(record)

    assert "[   ok   ]" in line
    assert "Backend:" in line
    assert "Started Streamlit with PID 1234." in line
    assert "{'pid': 1234}" not in line
