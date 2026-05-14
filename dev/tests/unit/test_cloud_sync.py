import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.cloud_sync as cloud_sync
import core.preferences as preferences
from core.models import Base
from core.db_backups import DB_BACKUP_PREFIX, DB_BACKUP_SUFFIX


def _settings_db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'settings.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(preferences, "SessionLocal", session_factory)
    monkeypatch.setattr(
        preferences,
        "init_db",
        lambda: Base.metadata.create_all(bind=engine),
    )
    monkeypatch.setattr(preferences, "PREFS_FILE", tmp_path / "preferences.json")
    Base.metadata.create_all(bind=engine)


def test_backup_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud_sync, "BACKUP_CONFIG_FILE", tmp_path / "backup_config.json")

    cloud_sync.save_backup_config_from_settings({
        "backup_destination_type": "custom",
        "backup_destination_custom_path": str(tmp_path / "cloud"),
        "cloud_backup_last_sync_at": "2026-05-13T00:00:00+00:00",
        "unrelated": "ignored",
    })

    assert cloud_sync.load_backup_config() == {
        "backup_destination_type": "custom",
        "backup_destination_custom_path": str(tmp_path / "cloud"),
        "cloud_backup_last_sync_at": "2026-05-13T00:00:00+00:00",
    }


def test_resolve_cloud_backup_destination_uses_custom_path(tmp_path):
    destination = tmp_path / "Dropbox"

    assert cloud_sync.resolve_cloud_backup_destination({
        "backup_destination_type": "dropbox",
        "backup_destination_custom_path": str(destination),
    }) == destination / "LoreForge Lite" / "backups"


def test_resolve_cloud_backup_destination_uses_onedrive_setting_before_detection(
    tmp_path,
):
    destination = tmp_path / "OneDrive"

    assert cloud_sync.resolve_cloud_backup_destination({
        "backup_destination_type": "onedrive",
        "backup_destination_custom_path": str(destination),
    }) == destination / "LoreForge Lite" / "backups"


def test_cloud_backup_destination_path_does_not_double_append(tmp_path):
    destination = tmp_path / "Dropbox" / "LoreForge Lite" / "backups"

    assert cloud_sync.cloud_backup_destination_path(destination) == destination


def test_detect_cloud_sync_provider_for_path_uses_onedrive_env(tmp_path, monkeypatch):
    onedrive = tmp_path / "OneDrive"
    local_backup = onedrive / "LoreForge" / "backups"
    local_backup.mkdir(parents=True)
    monkeypatch.setenv("ONEDRIVE", str(onedrive))

    assert cloud_sync.detect_cloud_sync_provider_for_path(local_backup) == "OneDrive"


def test_detect_cloud_sync_provider_for_path_uses_common_folder_names(tmp_path):
    assert cloud_sync.detect_cloud_sync_provider_for_path(
        tmp_path / "Google Drive" / "LoreForge"
    ) == "Google Drive"
    assert cloud_sync.detect_cloud_sync_provider_for_path(
        tmp_path / "Dropbox" / "LoreForge"
    ) == "Dropbox"
    assert cloud_sync.detect_cloud_sync_provider_for_path(
        tmp_path / "iCloud Drive" / "LoreForge"
    ) == "iCloud Drive"
    assert cloud_sync.detect_cloud_sync_provider_for_path(
        tmp_path / "Box Sync" / "LoreForge"
    ) == "Box"


def test_sync_backups_to_cloud_copies_db_sidecars_and_settings(tmp_path, monkeypatch):
    _settings_db(tmp_path, monkeypatch)
    monkeypatch.setattr(cloud_sync, "BACKUP_CONFIG_FILE", tmp_path / "backup_config.json")

    db_backup_dir = tmp_path / "local_backups" / "database"
    db_backup_dir.mkdir(parents=True)
    older_db = db_backup_dir / f"{DB_BACKUP_PREFIX}20260513_120000{DB_BACKUP_SUFFIX}"
    latest_db = db_backup_dir / f"{DB_BACKUP_PREFIX}20260513_130000{DB_BACKUP_SUFFIX}"
    older_db.write_text("older", encoding="utf-8")
    latest_db.write_text("latest", encoding="utf-8")
    monkeypatch.setattr(cloud_sync, "get_db_backup_dir", lambda: db_backup_dir)

    training_data = tmp_path / "training_data"
    sidecar = training_data / "scene" / "scene.registry.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text('{"metadata": {}}', encoding="utf-8")
    monkeypatch.setattr(cloud_sync, "TRAINING_DATA_DIR", training_data)

    preferences.set_all_settings({
        "backup_destination_type": "custom",
        "backup_destination_custom_path": str(tmp_path / "cloud"),
        "preview_user_name": "Scott",
    })

    result = cloud_sync.sync_backups_to_cloud(tmp_path / "cloud")

    assert result.ok is True
    assert (tmp_path / "cloud" / "database" / latest_db.name).read_text(
        encoding="utf-8"
    ) == "latest"
    assert not (tmp_path / "cloud" / "database" / older_db.name).exists()
    assert (tmp_path / "cloud" / "sidecars" / "scene" / "scene.registry.json").exists()
    settings = json.loads((tmp_path / "cloud" / "settings.json").read_text(encoding="utf-8"))
    assert settings["preview_user_name"] == "Scott"
    assert preferences.get_setting("cloud_backup_last_sync_at")
    assert cloud_sync.load_backup_config()["backup_destination_type"] == "custom"


def test_cloud_backup_restore_imports_settings_and_latest_db(tmp_path, monkeypatch):
    _settings_db(tmp_path, monkeypatch)
    monkeypatch.setattr(cloud_sync, "BACKUP_CONFIG_FILE", tmp_path / "backup_config.json")
    local_db = tmp_path / "local" / "loreforge.db"
    monkeypatch.setattr(cloud_sync, "get_db_path", lambda: local_db)

    destination = tmp_path / "cloud"
    destination.mkdir()
    (destination / "settings.json").write_text(
        json.dumps({"preview_user_name": "Restored"}),
        encoding="utf-8",
    )
    db_backup_dir = destination / "database"
    db_backup_dir.mkdir()
    older_db = db_backup_dir / f"{DB_BACKUP_PREFIX}20260513_120000{DB_BACKUP_SUFFIX}"
    latest_db = db_backup_dir / f"{DB_BACKUP_PREFIX}20260513_130000{DB_BACKUP_SUFFIX}"
    older_db.write_text("older", encoding="utf-8")
    latest_db.write_text("latest", encoding="utf-8")

    result = cloud_sync.restore_cloud_backup(destination)

    assert result.ok is True
    assert result.settings_imported is True
    assert result.db_restored is True
    assert preferences.get_setting("preview_user_name") == "Restored"
    assert local_db.read_text(encoding="utf-8") == "latest"
