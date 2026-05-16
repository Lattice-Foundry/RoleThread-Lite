import core.platform as platform_helpers


def test_detect_platform_normalizes_windows():
    info = platform_helpers.detect_platform("Windows")

    assert info.os_name == platform_helpers.OS_WINDOWS
    assert info.platform_slug == platform_helpers.OS_WINDOWS
    assert info.display_name == "Windows"
    assert info.support_level == platform_helpers.SUPPORT_PRIMARY
    assert info.diagnostics.raw_system == "Windows"
    assert info.capabilities.supports_installer is True
    assert info.capabilities.supports_edge_webapp is True
    assert info.capabilities.supports_default_browser is True
    assert info.capabilities.supports_onedrive is True
    assert info.capabilities.supports_safe_cloud_sync is True
    assert info.capabilities.supports_linux_manual_run is False
    assert info.capabilities.supports_macos_beta is False


def test_detect_platform_normalizes_linux():
    info = platform_helpers.detect_platform("Linux")

    assert info.os_name == platform_helpers.OS_LINUX
    assert info.platform_slug == platform_helpers.OS_LINUX
    assert info.display_name == "Linux"
    assert info.support_level == platform_helpers.SUPPORT_PRIMARY
    assert info.diagnostics.raw_system == "Linux"
    assert info.capabilities.supports_installer is False
    assert info.capabilities.supports_edge_webapp is False
    assert info.capabilities.supports_default_browser is True
    assert info.capabilities.supports_onedrive is False
    assert info.capabilities.supports_safe_cloud_sync is True
    assert info.capabilities.supports_linux_manual_run is True
    assert info.capabilities.supports_macos_beta is False


def test_detect_platform_normalizes_macos_beta():
    info = platform_helpers.detect_platform("Darwin")

    assert info.os_name == platform_helpers.OS_MACOS
    assert info.platform_slug == platform_helpers.OS_MACOS
    assert info.display_name == "macOS"
    assert info.support_level == platform_helpers.SUPPORT_BETA
    assert info.diagnostics.raw_system == "Darwin"
    assert info.capabilities.supports_installer is False
    assert info.capabilities.supports_edge_webapp is False
    assert info.capabilities.supports_default_browser is True
    assert info.capabilities.supports_onedrive is False
    assert info.capabilities.supports_safe_cloud_sync is True
    assert info.capabilities.supports_linux_manual_run is False
    assert info.capabilities.supports_macos_beta is True


def test_detect_platform_unknown_is_unsupported():
    info = platform_helpers.detect_platform("Plan9")

    assert info.os_name == platform_helpers.OS_UNKNOWN
    assert info.platform_slug == platform_helpers.OS_UNKNOWN
    assert info.display_name == "Unknown"
    assert info.support_level == platform_helpers.SUPPORT_UNSUPPORTED
    assert info.diagnostics.raw_system == "Plan9"
    assert info.capabilities.supports_installer is False
    assert info.capabilities.supports_edge_webapp is False
    assert info.capabilities.supports_default_browser is False
    assert info.capabilities.supports_onedrive is False
    assert info.capabilities.supports_safe_cloud_sync is False
    assert info.capabilities.supports_linux_manual_run is False
    assert info.capabilities.supports_macos_beta is False


def test_detect_platform_uses_platform_system_when_not_supplied(monkeypatch):
    monkeypatch.setattr(platform_helpers._platform, "system", lambda: "Linux")

    assert platform_helpers.detect_platform().os_name == platform_helpers.OS_LINUX


def test_collect_platform_diagnostics_reads_runtime_metadata(monkeypatch):
    monkeypatch.setattr(platform_helpers._platform, "release", lambda: "release-x")
    monkeypatch.setattr(platform_helpers._platform, "version", lambda: "version-y")
    monkeypatch.setattr(platform_helpers._platform, "platform", lambda: "platform-z")
    monkeypatch.setattr(platform_helpers._platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(platform_helpers._platform, "processor", lambda: "CPU")
    monkeypatch.setattr(platform_helpers._platform, "python_version", lambda: "3.14.4")
    monkeypatch.setattr(platform_helpers._platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(platform_helpers._platform, "architecture", lambda: ("64bit", ""))

    diagnostics = platform_helpers.collect_platform_diagnostics("Windows")

    assert diagnostics.raw_system == "Windows"
    assert diagnostics.release == "release-x"
    assert diagnostics.version == "version-y"
    assert diagnostics.platform_string == "platform-z"
    assert diagnostics.machine == "AMD64"
    assert diagnostics.processor == "CPU"
    assert diagnostics.python_version == "3.14.4"
    assert diagnostics.python_implementation == "CPython"
    assert diagnostics.python_architecture == "64bit"


def test_detect_onedrive_path_uses_env_on_windows(tmp_path, monkeypatch):
    one_drive = tmp_path / "OneDrive"
    one_drive.mkdir()
    monkeypatch.setattr(platform_helpers, "IS_WINDOWS", True)
    monkeypatch.setenv("ONEDRIVE", str(one_drive))

    assert platform_helpers.detect_onedrive_path() == one_drive.resolve()


def test_detect_onedrive_path_falls_back_to_userprofile(tmp_path, monkeypatch):
    one_drive = tmp_path / "Profile" / "OneDrive"
    one_drive.mkdir(parents=True)
    monkeypatch.setattr(platform_helpers, "IS_WINDOWS", True)
    monkeypatch.delenv("ONEDRIVE", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "Profile"))

    assert platform_helpers.detect_onedrive_path() == one_drive.resolve()


def test_detect_onedrive_path_returns_none_off_windows(tmp_path, monkeypatch):
    one_drive = tmp_path / "OneDrive"
    one_drive.mkdir()
    monkeypatch.setattr(platform_helpers, "IS_WINDOWS", False)
    monkeypatch.setenv("ONEDRIVE", str(one_drive))

    assert platform_helpers.detect_onedrive_path() is None


def test_default_onedrive_backup_path_appends_loreforge_folder(tmp_path, monkeypatch):
    one_drive = tmp_path / "OneDrive"
    one_drive.mkdir()
    monkeypatch.setattr(platform_helpers, "IS_WINDOWS", True)
    monkeypatch.setenv("ONEDRIVE", str(one_drive))

    assert platform_helpers.default_onedrive_backup_path() == (
        one_drive.resolve() / "LoreForge Lite" / "backups"
    )
