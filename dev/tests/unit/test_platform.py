from pathlib import Path

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


def test_platform_support_messages_describe_windows_planned_features():
    info = platform_helpers.detect_platform("Windows")
    messages = platform_helpers.get_platform_support_messages(info)
    text = " ".join(message.message for message in messages)

    assert "primary V1 support platform" in text
    assert "Installer support is planned" in text
    assert "Edge web app support is planned" in text


def test_platform_support_messages_describe_linux_manual_workflow():
    info = platform_helpers.detect_platform("Linux")
    messages = platform_helpers.get_platform_support_messages(info)
    text = " ".join(message.message for message in messages)

    assert "Linux is a primary V1 support platform" in text
    assert "Manual or git-clone setup" in text


def test_platform_support_messages_describe_macos_beta_status():
    info = platform_helpers.detect_platform("Darwin")
    messages = platform_helpers.get_platform_support_messages(info)
    text = " ".join(message.message for message in messages)

    assert "macOS is beta-supported" in text
    assert "community-tested" in text
    assert "installer is not planned" in text


def test_platform_support_messages_describe_unknown_graceful_degradation():
    info = platform_helpers.detect_platform("Plan9")
    messages = platform_helpers.get_platform_support_messages(info)
    text = " ".join(message.message for message in messages)

    assert "not officially supported" in text
    assert "disabled where support is unknown" in text


def test_browser_detection_finds_edge_with_path_lookup_on_windows():
    result = platform_helpers.detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    )

    assert result.capabilities.supports_edge_webapp is True
    assert result.browser.edge_detected is True
    assert result.browser.edge_path == Path(
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe"
    )
    assert result.browser.edge_detection_method == "path"
    assert result.capabilities.edge_webapp_available is True
    assert result.capabilities.fallback_to_default_browser is False
    assert "Edge is available" in result.message


def test_browser_detection_finds_edge_common_install_path_on_windows():
    edge_path = Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe")
    result = platform_helpers.detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={"PROGRAMFILES": "C:/Program Files"},
        which_fn=lambda name: None,
        path_exists_fn=lambda path: path == edge_path,
    )

    assert result.browser.edge_detected is True
    assert result.browser.edge_path == edge_path
    assert result.browser.edge_detection_method == "common_install_path"
    assert result.capabilities.edge_webapp_available is True


def test_browser_detection_falls_back_when_edge_missing_on_windows():
    result = platform_helpers.detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: None,
        path_exists_fn=lambda path: False,
    )

    assert result.browser.edge_detected is False
    assert result.browser.edge_path is None
    assert result.browser.edge_detection_method == "not_found"
    assert result.capabilities.supports_edge_webapp is True
    assert result.capabilities.edge_webapp_available is False
    assert result.capabilities.fallback_to_default_browser is True
    assert "fall back to the default browser" in result.message


def test_browser_detection_uses_default_browser_only_on_linux_and_macos():
    for system_name in ("Linux", "Darwin"):
        result = platform_helpers.detect_browser_capabilities(
            system_name,
            home="/home/scott",
            env={},
            which_fn=lambda name: "ignored",
            path_exists_fn=lambda path: True,
        )

        assert result.browser.edge_detected is False
        assert result.browser.edge_path is None
        assert result.browser.edge_detection_method == "not_applicable"
        assert result.capabilities.supports_edge_webapp is False
        assert result.capabilities.edge_webapp_available is False
        assert result.capabilities.supports_default_browser is True
        assert result.capabilities.fallback_to_default_browser is True
        assert "Default browser workflows are supported" in result.message


def test_browser_detection_gracefully_degrades_on_unknown_platform():
    result = platform_helpers.detect_browser_capabilities(
        "Plan9",
        home="/home/scott",
        env={},
        which_fn=lambda name: "ignored",
        path_exists_fn=lambda path: True,
    )

    assert result.browser.edge_detected is False
    assert result.capabilities.supports_default_browser is False
    assert result.capabilities.fallback_to_default_browser is False
    assert "Browser workflows are not supported" in result.message


def test_launch_plan_prefers_edge_webapp_when_edge_available_on_windows():
    detection = platform_helpers.detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    )

    plan = platform_helpers.get_platform_launch_plan(detection)

    assert plan.preferred_mode == platform_helpers.LAUNCH_MODE_EDGE_WEBAPP
    assert plan.preferred_label == "Microsoft Edge web app"
    assert plan.fallback_mode == platform_helpers.LAUNCH_MODE_DEFAULT_BROWSER
    assert plan.fallback_label == "Default browser"
    assert plan.is_preferred_available is True
    assert plan.edge_webapp_ready is True
    assert any("future Windows web-app launch flow" in note for note in plan.notes)


def test_launch_plan_falls_back_to_default_browser_when_edge_missing_on_windows():
    detection = platform_helpers.detect_browser_capabilities(
        "Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: None,
        path_exists_fn=lambda path: False,
    )

    plan = platform_helpers.get_platform_launch_plan(detection)

    assert plan.preferred_mode == platform_helpers.LAUNCH_MODE_DEFAULT_BROWSER
    assert plan.preferred_label == "Default browser"
    assert plan.fallback_mode is None
    assert plan.fallback_label == "None"
    assert plan.is_preferred_available is True
    assert plan.edge_webapp_ready is False
    assert any("Edge was not detected" in note for note in plan.notes)


def test_launch_plan_prefers_default_browser_for_linux():
    detection = platform_helpers.detect_browser_capabilities(
        "Linux",
        home="/home/scott",
        env={},
        which_fn=lambda name: None,
        path_exists_fn=lambda path: False,
    )

    plan = platform_helpers.get_platform_launch_plan(detection)

    assert plan.preferred_mode == platform_helpers.LAUNCH_MODE_DEFAULT_BROWSER
    assert plan.fallback_mode == platform_helpers.LAUNCH_MODE_MANUAL
    assert plan.is_preferred_available is True
    assert plan.edge_webapp_ready is False
    assert any("Linux workflow" in note for note in plan.notes)


def test_launch_plan_prefers_default_browser_for_macos_beta():
    detection = platform_helpers.detect_browser_capabilities(
        "Darwin",
        home="/Users/scott",
        env={},
        which_fn=lambda name: None,
        path_exists_fn=lambda path: False,
    )

    plan = platform_helpers.get_platform_launch_plan(detection)

    assert plan.preferred_mode == platform_helpers.LAUNCH_MODE_DEFAULT_BROWSER
    assert plan.fallback_mode == platform_helpers.LAUNCH_MODE_MANUAL
    assert plan.is_preferred_available is True
    assert plan.edge_webapp_ready is False
    assert any("Safari web-app style workflows" in note for note in plan.notes)


def test_launch_plan_gracefully_degrades_on_unknown_platform():
    detection = platform_helpers.detect_browser_capabilities(
        "Plan9",
        home="/home/scott",
        env={},
        which_fn=lambda name: None,
        path_exists_fn=lambda path: False,
    )

    plan = platform_helpers.get_platform_launch_plan(detection)

    assert plan.preferred_mode == platform_helpers.LAUNCH_MODE_UNSUPPORTED
    assert plan.fallback_mode == platform_helpers.LAUNCH_MODE_MANUAL
    assert plan.is_preferred_available is False
    assert plan.edge_webapp_ready is False
    assert any("not officially supported" in note for note in plan.notes)


def test_launch_plan_helper_accepts_browser_detection_kwargs():
    plan = platform_helpers.get_platform_launch_plan(
        system_name="Windows",
        home="C:/Users/Scott",
        env={},
        which_fn=lambda name: None,
        path_exists_fn=lambda path: False,
    )

    assert plan.preferred_mode == platform_helpers.LAUNCH_MODE_DEFAULT_BROWSER
    assert plan.edge_webapp_ready is False


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


def test_windows_platform_paths_use_localappdata_and_userprofile():
    paths = platform_helpers.get_platform_paths(
        "Windows",
        home="C:/Users/Fallback",
        env={
            "LOCALAPPDATA": "C:/Users/Scott/AppData/Local",
            "USERPROFILE": "C:/Users/Scott",
        },
    )

    assert paths.app_data_root == Path("C:/Users/Scott/AppData/Local/LoreForge")
    assert paths.workspace_root == Path("C:/Users/Scott/LoreForge")
    assert paths.training_data_dir == Path("C:/Users/Scott/LoreForge/training_data")
    assert paths.exports_dir == Path("C:/Users/Scott/LoreForge/exports")
    assert paths.imports_dir == Path("C:/Users/Scott/LoreForge/imports")
    assert paths.backups_dir == Path("C:/Users/Scott/LoreForge/backups")
    assert paths.logs_dir == paths.app_data_root / "logs"
    assert paths.cache_dir == paths.app_data_root / "cache"
    assert paths.database_path == paths.app_data_root / "loreforge.db"
    assert paths.preferences_path == paths.app_data_root / "preferences.json"


def test_windows_platform_paths_fall_back_to_userprofile_local_appdata():
    paths = platform_helpers.get_platform_paths(
        "Windows",
        home="C:/Users/Fallback",
        env={"USERPROFILE": "C:/Users/Scott"},
    )

    assert paths.app_data_root == Path("C:/Users/Scott/AppData/Local/LoreForge")
    assert paths.workspace_root == Path("C:/Users/Scott/LoreForge")


def test_linux_platform_paths_use_xdg_style_app_data_and_home_workspace():
    paths = platform_helpers.get_platform_paths(
        "Linux",
        home="/home/scott",
        env={},
    )

    assert paths.app_data_root == Path("/home/scott/.local/share/loreforge")
    assert paths.workspace_root == Path("/home/scott/LoreForge")
    assert paths.training_data_dir == Path("/home/scott/LoreForge/training_data")
    assert paths.exports_dir == Path("/home/scott/LoreForge/exports")
    assert paths.imports_dir == Path("/home/scott/LoreForge/imports")
    assert paths.backups_dir == Path("/home/scott/LoreForge/backups")
    assert paths.database_path == Path("/home/scott/.local/share/loreforge/loreforge.db")


def test_macos_platform_paths_use_application_support_and_home_workspace():
    paths = platform_helpers.get_platform_paths(
        "Darwin",
        home="/Users/scott",
        env={},
    )

    assert paths.app_data_root == Path(
        "/Users/scott/Library/Application Support/LoreForge"
    )
    assert paths.workspace_root == Path("/Users/scott/LoreForge")
    assert paths.training_data_dir == Path("/Users/scott/LoreForge/training_data")
    assert paths.exports_dir == Path("/Users/scott/LoreForge/exports")
    assert paths.imports_dir == Path("/Users/scott/LoreForge/imports")
    assert paths.backups_dir == Path("/Users/scott/LoreForge/backups")


def test_unknown_platform_paths_use_safe_home_folder_fallback():
    paths = platform_helpers.get_platform_paths(
        "Plan9",
        home="/home/scott",
        env={},
    )

    assert paths.app_data_root == Path("/home/scott/LoreForge")
    assert paths.workspace_root == Path("/home/scott/LoreForge")
    assert paths.training_data_dir == Path("/home/scott/LoreForge/training_data")
    assert paths.backups_dir == Path("/home/scott/LoreForge/backups")


def test_platform_paths_preserve_existing_user_configured_preferences():
    paths = platform_helpers.get_platform_paths(
        "Linux",
        home="/home/scott",
        env={},
        preferences={
            "default_dataset_directory": "/custom/datasets",
            "backup_directory": "/custom/backups",
        },
    )

    assert paths.training_data_dir == Path("/custom/datasets")
    assert paths.backups_dir == Path("/custom/backups")
    assert paths.exports_dir == Path("/home/scott/LoreForge/exports")


def test_platform_path_resolutions_mark_default_sources():
    resolutions = platform_helpers.get_platform_path_resolutions(
        "Linux",
        home="/home/scott",
        env={},
    )

    assert resolutions.training_data_dir.path == Path(
        "/home/scott/LoreForge/training_data"
    )
    assert (
        resolutions.training_data_dir.source
        == platform_helpers.PATH_SOURCE_PLATFORM_DEFAULT
    )
    assert resolutions.training_data_dir.platform_default == Path(
        "/home/scott/LoreForge/training_data"
    )
    assert resolutions.training_data_dir.is_user_override is False
    assert resolutions.backups_dir.source == platform_helpers.PATH_SOURCE_PLATFORM_DEFAULT
    assert resolutions.exports_dir.source == platform_helpers.PATH_SOURCE_PLATFORM_DEFAULT


def test_platform_path_resolutions_mark_user_overrides():
    resolutions = platform_helpers.get_platform_path_resolutions(
        "Linux",
        home="/home/scott",
        env={},
        preferences={
            "default_dataset_directory": "/custom/datasets",
            "backup_directory": "/custom/backups",
        },
    )

    assert resolutions.training_data_dir.path == Path("/custom/datasets")
    assert resolutions.training_data_dir.platform_default == Path(
        "/home/scott/LoreForge/training_data"
    )
    assert resolutions.training_data_dir.source == platform_helpers.PATH_SOURCE_USER_OVERRIDE
    assert resolutions.training_data_dir.is_user_override is True
    assert resolutions.backups_dir.path == Path("/custom/backups")
    assert resolutions.backups_dir.platform_default == Path(
        "/home/scott/LoreForge/backups"
    )
    assert resolutions.backups_dir.source == platform_helpers.PATH_SOURCE_USER_OVERRIDE
    assert resolutions.exports_dir.source == platform_helpers.PATH_SOURCE_PLATFORM_DEFAULT


def test_platform_path_sources_reports_mixed_configuration_sources():
    sources = platform_helpers.get_platform_path_sources(
        "Linux",
        home="/home/scott",
        env={},
        preferences={
            "default_dataset_directory": "/custom/datasets",
            "backup_directory": "",
        },
    )

    assert sources.training_data_dir == platform_helpers.PATH_SOURCE_USER_OVERRIDE
    assert sources.backups_dir == platform_helpers.PATH_SOURCE_PLATFORM_DEFAULT
    assert sources.app_data_root == platform_helpers.PATH_SOURCE_PLATFORM_DEFAULT


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
