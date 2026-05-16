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
