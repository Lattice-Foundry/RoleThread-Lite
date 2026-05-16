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
    capabilities = detect_platform("Linux").capabilities

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
        path="C:/Users/digit/LoreForge/training_data",
        source="user_override",
        platform_default="C:/Users/digit/LoreForge/training_data",
    )

    assert ui_settings._format_platform_path_value(
        resolved,
        include_source=False,
    ) == "`C:/Users/digit/LoreForge/training_data`"


def test_platform_path_format_shows_source_in_dev_mode():
    resolved = _ResolvedPath(
        path="X:/custom/training_data",
        source="user_override",
        platform_default="C:/Users/digit/LoreForge/training_data",
    )

    value = ui_settings._format_platform_path_value(resolved, include_source=True)

    assert "User Override" in value
    assert "default `C:/Users/digit/LoreForge/training_data`" in value


def test_webapp_experimental_preference_uses_platform_capability():
    windows_capabilities = detect_platform("Windows").capabilities
    linux_capabilities = detect_platform("Linux").capabilities

    assert ui_settings._supports_webapp_launch_preference(windows_capabilities) is True
    assert ui_settings._supports_webapp_launch_preference(linux_capabilities) is False
