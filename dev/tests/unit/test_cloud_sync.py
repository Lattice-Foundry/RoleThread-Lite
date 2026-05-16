import json
import sqlite3

import pytest
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


def _patch_backup_config_paths(tmp_path, monkeypatch):
    config_file = tmp_path / "app_data" / "backup_config.json"
    legacy_config_file = tmp_path / "backup_config.json"
    monkeypatch.setattr(cloud_sync, "BACKUP_CONFIG_FILE", config_file)
    monkeypatch.setattr(cloud_sync, "LEGACY_BACKUP_CONFIG_FILE", legacy_config_file)
    return config_file, legacy_config_file


def test_backup_config_roundtrip(tmp_path, monkeypatch):
    config_file, _legacy_config_file = _patch_backup_config_paths(tmp_path, monkeypatch)

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
    assert config_file.exists()


def test_load_backup_config_creates_default_in_app_data(tmp_path, monkeypatch):
    config_file, legacy_config_file = _patch_backup_config_paths(tmp_path, monkeypatch)

    assert cloud_sync.load_backup_config() == {}

    assert config_file.read_text(encoding="utf-8") == "{}\n"
    assert not legacy_config_file.exists()


def test_load_backup_config_migrates_legacy_root_config(tmp_path, monkeypatch):
    config_file, legacy_config_file = _patch_backup_config_paths(tmp_path, monkeypatch)
    legacy_config_file.write_text(
        json.dumps({
            "backup_destination_type": "custom",
            "backup_destination_custom_path": str(tmp_path / "legacy-cloud"),
        }) + "\n",
        encoding="utf-8",
    )

    assert cloud_sync.load_backup_config() == {
        "backup_destination_type": "custom",
        "backup_destination_custom_path": str(tmp_path / "legacy-cloud"),
    }
    assert config_file.read_text(encoding="utf-8") == legacy_config_file.read_text(
        encoding="utf-8"
    )
    assert legacy_config_file.exists()


def test_load_backup_config_prefers_existing_app_data_config(tmp_path, monkeypatch):
    config_file, legacy_config_file = _patch_backup_config_paths(tmp_path, monkeypatch)
    config_file.parent.mkdir(parents=True)
    config_file.write_text(
        json.dumps({"backup_destination_type": "dropbox"}) + "\n",
        encoding="utf-8",
    )
    legacy_config_file.write_text(
        json.dumps({"backup_destination_type": "custom"}) + "\n",
        encoding="utf-8",
    )

    assert cloud_sync.load_backup_config() == {"backup_destination_type": "dropbox"}
    assert json.loads(config_file.read_text(encoding="utf-8")) == {
        "backup_destination_type": "dropbox",
    }


def test_resolve_cloud_backup_destination_uses_custom_path(tmp_path):
    destination = tmp_path / "Dropbox"

    assert cloud_sync.resolve_cloud_backup_destination({
        "backup_destination_type": "dropbox",
        "backup_destination_custom_path": str(destination),
    }) == destination / "LoreForge Lite" / "backups"


def test_resolve_cloud_backup_destination_uses_onedrive_setting_before_detection(
    tmp_path,
    monkeypatch,
):
    destination = tmp_path / "OneDrive"
    monkeypatch.setattr(
        cloud_sync,
        "detect_platform",
        lambda: type(
            "Platform",
            (),
            {"capabilities": type("Capabilities", (), {"supports_onedrive": True})()},
        )(),
    )

    assert cloud_sync.resolve_cloud_backup_destination({
        "backup_destination_type": "onedrive",
        "backup_destination_custom_path": str(destination),
    }) == destination / "LoreForge Lite" / "backups"


def test_resolve_cloud_backup_destination_ignores_stale_onedrive_off_windows(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        cloud_sync,
        "detect_platform",
        lambda: type(
            "Platform",
            (),
            {"capabilities": type("Capabilities", (), {"supports_onedrive": False})()},
        )(),
    )

    assert cloud_sync.resolve_cloud_backup_destination({
        "backup_destination_type": "onedrive",
        "backup_destination_custom_path": str(tmp_path / "OneDrive"),
    }) is None
    assert cloud_sync.resolve_cloud_backup_destination_from_config({
        "backup_destination_type": "onedrive",
        "backup_destination_custom_path": str(tmp_path / "OneDrive"),
    }) is None


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
    _patch_backup_config_paths(tmp_path, monkeypatch)
    publish_observations = []

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

    original_publish = cloud_sync._publish_staged_cloud_sync

    def observe_publish(staging, destination):
        publish_observations.append({
            "destination_exists": destination.exists(),
            "staged_db_exists": (staging / "database" / latest_db.name).exists(),
            "staged_sidecar_exists": (
                staging / "sidecars" / "scene" / "scene.registry.json"
            ).exists(),
            "staged_settings_exists": (staging / "settings.json").exists(),
        })
        return original_publish(staging, destination)

    monkeypatch.setattr(cloud_sync, "_publish_staged_cloud_sync", observe_publish)

    result = cloud_sync.sync_backups_to_cloud(tmp_path / "cloud")

    assert result.ok is True
    assert publish_observations == [
        {
            "destination_exists": False,
            "staged_db_exists": True,
            "staged_sidecar_exists": True,
            "staged_settings_exists": True,
        }
    ]
    assert (tmp_path / "cloud" / "database" / latest_db.name).read_text(
        encoding="utf-8"
    ) == "latest"
    assert not (tmp_path / "cloud" / "database" / older_db.name).exists()
    assert (tmp_path / "cloud" / "sidecars" / "scene" / "scene.registry.json").exists()
    settings = json.loads((tmp_path / "cloud" / "settings.json").read_text(encoding="utf-8"))
    assert settings["preview_user_name"] == "Scott"
    assert preferences.get_setting("cloud_backup_last_sync_at")
    assert cloud_sync.load_backup_config()["backup_destination_type"] == "custom"


def test_atomic_file_copy_preserves_existing_target_on_failure(tmp_path, monkeypatch):
    source = tmp_path / "source.db"
    target = tmp_path / "cloud" / "database" / "backup.db"
    source.write_text("new backup", encoding="utf-8")
    target.parent.mkdir(parents=True)
    target.write_text("existing backup", encoding="utf-8")

    def fail_copy(_source, temp_target):
        temp_target.write_text("partial backup", encoding="utf-8")
        raise OSError("copy interrupted")

    monkeypatch.setattr(cloud_sync.shutil, "copy2", fail_copy)

    with pytest.raises(OSError, match="copy interrupted"):
        cloud_sync._copy_file_atomically(source, target)

    assert target.read_text(encoding="utf-8") == "existing backup"
    assert list(target.parent.glob(f".{target.name}.tmp-*")) == []


def test_atomic_text_write_preserves_existing_target_on_replace_failure(
    tmp_path,
    monkeypatch,
):
    target = tmp_path / "cloud" / "settings.json"
    target.parent.mkdir(parents=True)
    target.write_text('{"existing": true}\n', encoding="utf-8")

    def fail_replace(_source, _target):
        raise OSError("replace interrupted")

    monkeypatch.setattr(cloud_sync.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace interrupted"):
        cloud_sync._write_text_atomically(target, '{"new": true}\n')

    assert target.read_text(encoding="utf-8") == '{"existing": true}\n'
    assert list(target.parent.glob(f".{target.name}.tmp-*")) == []


def test_sync_backups_to_cloud_keeps_previous_publish_on_staging_failure(
    tmp_path,
    monkeypatch,
):
    _settings_db(tmp_path, monkeypatch)
    _patch_backup_config_paths(tmp_path, monkeypatch)

    db_backup_dir = tmp_path / "local_backups" / "database"
    db_backup_dir.mkdir(parents=True)
    latest_db = db_backup_dir / f"{DB_BACKUP_PREFIX}20260513_130000{DB_BACKUP_SUFFIX}"
    latest_db.write_text("latest", encoding="utf-8")
    monkeypatch.setattr(cloud_sync, "get_db_backup_dir", lambda: db_backup_dir)

    destination = tmp_path / "cloud"
    destination.mkdir()
    previous_settings = destination / "settings.json"
    previous_settings.write_text('{"previous": true}\n', encoding="utf-8")

    def fail_sidecar_copy(_target):
        raise RuntimeError("sidecar copy failed")

    monkeypatch.setattr(cloud_sync, "_copy_training_sidecars", fail_sidecar_copy)

    result = cloud_sync.sync_backups_to_cloud(destination)

    assert result.ok is False
    assert "sidecar copy failed" in result.message
    assert previous_settings.read_text(encoding="utf-8") == '{"previous": true}\n'
    assert not (destination / "database" / latest_db.name).exists()
    assert not list(tmp_path.glob(".cloud.staging-*"))


def test_table_row_count_rejects_unapproved_table_name():
    conn = sqlite3.connect(":memory:")
    try:
        with pytest.raises(ValueError):
            cloud_sync._table_row_count(conn, "tags; DROP TABLE tags")
    finally:
        conn.close()


def test_cloud_backup_restore_imports_settings_and_latest_db(tmp_path, monkeypatch):
    _settings_db(tmp_path, monkeypatch)
    _patch_backup_config_paths(tmp_path, monkeypatch)
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
