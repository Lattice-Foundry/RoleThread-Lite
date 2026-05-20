from pathlib import Path

from core.platform import detect_platform
from core.launcher import LaunchFlags
from core.cloud_sync import (
    BACKUP_DESTINATION_BOX,
    BACKUP_DESTINATION_DROPBOX,
    BACKUP_DESTINATION_GOOGLE_DRIVE,
    BACKUP_DESTINATION_ICLOUD_DRIVE,
    BACKUP_DESTINATION_LOCAL,
    BACKUP_DESTINATION_ONEDRIVE,
)
from ui import ui_settings


class _ResolvedPath:
    def __init__(self, path, source, platform_default):
        self.path = path
        self.source = source
        self.platform_default = platform_default


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


def test_platform_path_format_hides_source_outside_dev_mode():
    resolved = _ResolvedPath(
        path="C:/Users/digit/RoleThread/training_data",
        source="user_override",
        platform_default="C:/Users/digit/RoleThread/training_data",
    )

    assert ui_settings._format_platform_path_value(
        resolved,
        include_source=False,
    ) == "`C:/Users/digit/RoleThread/training_data`"


def test_platform_path_format_shows_source_in_dev_mode():
    resolved = _ResolvedPath(
        path="X:/custom/training_data",
        source="user_override",
        platform_default="C:/Users/digit/RoleThread/training_data",
    )

    value = ui_settings._format_platform_path_value(resolved, include_source=True)

    assert "User Override" in value
    assert "default `C:/Users/digit/RoleThread/training_data`" in value


def test_settings_no_longer_exposes_webapp_preference_toggle():
    source = Path(ui_settings.__file__).read_text(encoding="utf-8")

    assert "Experimental Features" not in source
    assert "Enable webapp launch mode" not in source
    assert "_enable_webapp_launch_mode_checkbox" not in source


def test_public_launch_mode_summarizes_active_or_preferred_mode():
    assert ui_settings._format_public_launch_mode(
        LaunchFlags(),
        {},
    ) == "`Normal Streamlit mode`"
    assert ui_settings._format_public_launch_mode(
        LaunchFlags(dev=True),
        {},
    ) == "`Dev diagnostics`"


def test_launch_flags_detected_summary_is_compact():
    assert ui_settings._format_launch_flags_detected(LaunchFlags()) == "`None`"
    assert ui_settings._format_launch_flags_detected(LaunchFlags(dev=True)) == "`dev`"


def test_obsolete_edge_debug_diagnostics_are_removed_from_settings_ui():
    source = Path(ui_settings.__file__).read_text(encoding="utf-8")

    assert "Edge Launch Debug Diagnostics" not in source
    assert "edge-debug" not in source
    assert "webapp-debug" not in source
    assert "get_edge_version_history" not in source
    assert "edge_debug_mode" not in source
    assert "Duplicate Browser Cleanup Diagnostics" not in source
    assert "Edge Window Debug" not in source
    assert "Edge Process Debug" not in source


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

