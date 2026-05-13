import core.platform as platform_helpers


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
