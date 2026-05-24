import ast
from pathlib import Path

import ui.litlaunch_diagnostics as diagnostics_page


def test_generated_litlaunch_diagnostics_page_imports_and_parses():
    source_path = Path(diagnostics_page.__file__)
    source = source_path.read_text(encoding="utf-8")

    ast.parse(source)

    assert callable(diagnostics_page.render_litlaunch_diagnostics)
    assert diagnostics_page.APP_NAME == "RoleThread Lite"
    assert diagnostics_page.PROFILE_NAME == "rolethread-webapp"
    assert diagnostics_page.THEME == "auto"
    assert "litlaunch-support-bundle.txt" in source


def test_generated_litlaunch_diagnostics_page_uses_product_log_env(monkeypatch):
    monkeypatch.setenv(
        "ROLETHREAD_LAUNCHER_LOG_PATH",
        r"C:\Users\tester\AppData\Local\RoleThread\logs\launcher.log",
    )

    import importlib

    reloaded = importlib.reload(diagnostics_page)

    assert reloaded.EVENT_LOG_PATH == (
        r"C:\Users\tester\AppData\Local\RoleThread\logs\launcher.log"
    )

    monkeypatch.delenv("ROLETHREAD_LAUNCHER_LOG_PATH", raising=False)
    importlib.reload(diagnostics_page)
