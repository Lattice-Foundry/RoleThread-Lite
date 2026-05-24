import ast
from pathlib import Path

import ui.litlaunch_diagnostics as diagnostics_page
from core.product_log import (
    PRODUCT_LOG_PATH_ENV,
    SOURCE_RUNTIME_EVENT_LOG_PATH,
    resolve_diagnostics_event_log_path,
)


def test_diagnostics_event_log_path_defaults_to_source_runtime_log(monkeypatch):
    monkeypatch.delenv(PRODUCT_LOG_PATH_ENV, raising=False)

    assert resolve_diagnostics_event_log_path() == SOURCE_RUNTIME_EVENT_LOG_PATH


def test_generated_litlaunch_diagnostics_page_imports_and_parses():
    source_path = Path(diagnostics_page.__file__)
    source = source_path.read_text(encoding="utf-8")

    ast.parse(source)

    assert callable(diagnostics_page.render_litlaunch_diagnostics)
    assert diagnostics_page.APP_NAME == "RoleThread Lite"
    assert diagnostics_page.PROFILE_NAME == "rolethread-webapp"
    assert diagnostics_page.THEME == "auto"
    assert diagnostics_page.EVENT_LOG_PATH == str(SOURCE_RUNTIME_EVENT_LOG_PATH)
    assert "litlaunch-support-bundle.txt" in source


def test_generated_litlaunch_diagnostics_page_uses_product_log_env(monkeypatch):
    monkeypatch.setenv(
        PRODUCT_LOG_PATH_ENV,
        r"C:\Users\tester\AppData\Local\RoleThread\logs\launcher.log",
    )

    import importlib

    reloaded = importlib.reload(diagnostics_page)

    assert reloaded.EVENT_LOG_PATH == (
        r"C:\Users\tester\AppData\Local\RoleThread\logs\launcher.log"
    )

    monkeypatch.delenv(PRODUCT_LOG_PATH_ENV, raising=False)
    importlib.reload(diagnostics_page)
