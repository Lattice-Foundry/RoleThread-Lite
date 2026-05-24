import ast
import importlib
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
