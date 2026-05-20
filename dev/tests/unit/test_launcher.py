from pathlib import Path

from core.app_flags import (
    DEV_FLAG,
    LaunchFlags,
    parse_launch_flags,
    should_show_dev_diagnostics,
)


def test_parse_launch_flags_detects_dev_flag():
    flags = parse_launch_flags([DEV_FLAG])

    assert flags == LaunchFlags(dev=True)
    assert should_show_dev_diagnostics(flags) is True


def test_parse_launch_flags_ignores_unknown_app_side_flags():
    flags = parse_launch_flags(["unknown-flag", "--unused-diagnostic"])

    assert flags == LaunchFlags()
    assert should_show_dev_diagnostics(flags) is False


def test_app_no_longer_owns_webapp_browser_orchestration():
    source = Path("app.py").read_text(encoding="utf-8")

    assert "run_legacy_app_owned_webapp_launch" not in source
    assert "_handle_webapp_launch" not in source
    assert "_legacy_webapp_launch_warning" not in source
    assert "_dev_edge_debug_report" not in source


def test_root_source_launcher_removed_in_litlaunch_first_architecture():
    assert not Path("launch.py").exists()
