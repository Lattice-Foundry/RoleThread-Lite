from pathlib import Path

from core.platform import detect_platform
from core.cloud_sync import (
    BACKUP_DESTINATION_BOX,
    BACKUP_DESTINATION_DROPBOX,
    BACKUP_DESTINATION_GOOGLE_DRIVE,
    BACKUP_DESTINATION_ICLOUD_DRIVE,
    BACKUP_DESTINATION_LOCAL,
    BACKUP_DESTINATION_ONEDRIVE,
)
from ui import ui_settings


def _option_values(options):
    return [value for _label, value in options]


def test_cloud_destination_options_include_onedrive_when_capability_supported():
    capabilities = detect_platform("Windows").capabilities

    values = _option_values(ui_settings._cloud_destination_options(capabilities))

    assert values == [
        BACKUP_DESTINATION_LOCAL,
        BACKUP_DESTINATION_ONEDRIVE,
        BACKUP_DESTINATION_GOOGLE_DRIVE,
        BACKUP_DESTINATION_DROPBOX,
        BACKUP_DESTINATION_ICLOUD_DRIVE,
        BACKUP_DESTINATION_BOX,
    ]


def test_cloud_destination_options_hide_onedrive_when_capability_unsupported():
    for system_name in ("Linux", "Darwin", "FreeBSD"):
        capabilities = detect_platform(system_name).capabilities

        values = _option_values(ui_settings._cloud_destination_options(capabilities))

        assert BACKUP_DESTINATION_ONEDRIVE not in values
        assert values == [
            BACKUP_DESTINATION_LOCAL,
            BACKUP_DESTINATION_GOOGLE_DRIVE,
            BACKUP_DESTINATION_DROPBOX,
            BACKUP_DESTINATION_ICLOUD_DRIVE,
            BACKUP_DESTINATION_BOX,
        ]


def test_settings_no_longer_exposes_webapp_preference_toggle():
    source = Path(ui_settings.__file__).read_text(encoding="utf-8")

    assert "Experimental Features" not in source
    assert "Enable webapp launch mode" not in source
    assert "_enable_webapp_launch_mode_checkbox" not in source


def test_obsolete_edge_debug_diagnostics_are_removed_from_settings_ui():
    source = Path(ui_settings.__file__).read_text(encoding="utf-8")

    assert "detect_browser_capabilities" not in source
    assert "get_platform_launch_plan" not in source
    assert "Browser Support" not in source
    assert "Fallback behavior" not in source
    assert "Webapp support" not in source
    assert "Edge Launch Debug Diagnostics" not in source
    assert "edge-debug" not in source
    assert "webapp-debug" not in source
    assert "get_edge_version_history" not in source
    assert "edge_debug_mode" not in source
    assert "Duplicate Browser Cleanup Diagnostics" not in source
    assert "Edge Window Debug" not in source
    assert "Edge Process Debug" not in source
    assert "litlaunch.cli inspect --profile rolethread-webapp" not in source
    assert "litlaunch-report.html" not in source
    assert "litlaunch report --profile rolethread-webapp --force" not in source


def test_settings_about_is_concise_and_points_to_diagnostics():
    source = Path(ui_settings.__file__).read_text(encoding="utf-8")

    assert "About This Installation" in source
    assert "Support -> Diagnostics" in source
    assert "Python status:" in source
    assert "Launch Behavior" not in source
    assert "Source app-window profile" not in source
    assert "Python Runtime Compatibility" not in source
    assert "Storage Locations" not in source
    assert "Advanced storage paths" not in source
    assert "Platform Path Defaults" not in source
    assert "Raw Platform Diagnostics" not in source
    assert "_render_platform_paths" not in source


def test_settings_no_longer_exposes_webapp_browser_state_reset():
    source = Path(ui_settings.__file__).read_text(encoding="utf-8")

    assert "Reset Webapp Browser State" not in source
    assert "Clear Session State" not in source
    assert "schedule_webapp_browser_state_reset" not in source
    assert "is_webapp_browser_state_reset_pending" not in source


def test_project_info_markup_preserves_official_attribution_and_colors():
    markup = ui_settings._format_project_info_markup()

    assert "Developed by:" in markup
    assert "LatticeFoundry" in markup
    assert "A Sierra Cognitive Group company" in markup
    assert "latticefoundry.dev" in markup
    assert "github.com/Lattice-Foundry/RoleThread-Lite" in markup
    assert "Scott Jackson | " in markup
    assert "d1g1talshad0w" in markup
    assert markup.count("color: #3D9F64") == 2

