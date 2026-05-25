from dataclasses import asdict
import json
import sqlite3

from core.product_diagnostics import (
    BACKUP_CONFIG_FILE_NAME,
    collect_product_diagnostics,
)
from core.product_log import PRODUCT_LOG_PATH_ENV
from core.runtime import get_python_runtime_status
from core.version import ROLETHREAD_VERSION


def test_collect_product_diagnostics_returns_overview(tmp_path):
    diagnostics = collect_product_diagnostics(
        app_root=tmp_path,
        app_data_dir=tmp_path / "app_data",
        runtime_status=get_python_runtime_status((3, 14, 5)),
        frozen=False,
    )

    assert diagnostics.overview.rolethread_version == ROLETHREAD_VERSION
    assert diagnostics.overview.python_version == "3.14.5"
    assert diagnostics.overview.python_status == "Supported"
    assert diagnostics.overview.runtime_context == "source"
    assert diagnostics.overview.streamlit_version
    assert diagnostics.overview.litlaunch_version


def test_collect_product_diagnostics_does_not_create_missing_dirs(tmp_path):
    app_root = tmp_path / "source"
    app_data = tmp_path / "missing_app_data"

    diagnostics = collect_product_diagnostics(
        app_root=app_root,
        app_data_dir=app_data,
        frozen=False,
    )

    assert not app_root.exists()
    assert not app_data.exists()
    assert diagnostics.support_artifacts.reports_dir.endswith(".litlaunch\\reports")
    assert diagnostics.support_artifacts.reports_dir_exists is False


def test_collect_product_diagnostics_handles_cloud_backup_not_configured(tmp_path):
    diagnostics = collect_product_diagnostics(
        app_root=tmp_path,
        app_data_dir=tmp_path / "app_data",
    )

    assert diagnostics.cloud_backup.status == "local_only"
    assert diagnostics.cloud_backup.provider == "Local only"
    assert diagnostics.cloud_backup.destination_path is None
    assert diagnostics.cloud_backup.destination_exists is None
    assert diagnostics.cloud_backup.config_exists is False


def test_collect_product_diagnostics_reads_cloud_backup_config_safely(tmp_path):
    app_data = tmp_path / "app_data"
    destination = tmp_path / "OneDrive" / "RoleThread Lite" / "backups"
    app_data.mkdir()
    destination.mkdir(parents=True)
    (app_data / BACKUP_CONFIG_FILE_NAME).write_text(
        json.dumps(
            {
                "backup_destination_type": "onedrive",
                "backup_destination_custom_path": str(destination),
                "cloud_backup_last_sync_at": "2026-05-24T12:00:00",
                "secret_token": "do-not-leak",
            }
        ),
        encoding="utf-8",
    )

    diagnostics = collect_product_diagnostics(
        app_root=tmp_path,
        app_data_dir=app_data,
    )

    assert diagnostics.cloud_backup.status == "configured"
    assert diagnostics.cloud_backup.provider == "OneDrive"
    assert diagnostics.cloud_backup.destination_path == str(destination)
    assert diagnostics.cloud_backup.destination_exists is True
    assert diagnostics.cloud_backup.last_sync_at == "2026-05-24T12:00:00"
    assert "do-not-leak" not in str(asdict(diagnostics))


def test_collect_product_diagnostics_uses_existing_preference_overrides(tmp_path):
    app_data = tmp_path / "app_data"
    app_data.mkdir()
    database = app_data / "rolethread.db"
    training_dir = tmp_path / "custom_training"
    backups_dir = tmp_path / "custom_backups"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE app_settings (key TEXT, value TEXT)")
        connection.execute(
            "INSERT INTO app_settings VALUES (?, ?)",
            ("default_dataset_directory", json.dumps(str(training_dir))),
        )
        connection.execute(
            "INSERT INTO app_settings VALUES (?, ?)",
            ("backup_directory", json.dumps(str(backups_dir))),
        )
        connection.execute(
            "INSERT INTO app_settings VALUES (?, ?)",
            ("api_token", json.dumps("do-not-leak")),
        )

    diagnostics = collect_product_diagnostics(
        app_root=tmp_path,
        app_data_dir=app_data,
    )

    paths_by_label = {path.label: path for path in diagnostics.paths}
    assert paths_by_label["Training data"].path == str(training_dir)
    assert paths_by_label["Training data"].source == "user_override"
    assert paths_by_label["Backups"].path == str(backups_dir)
    assert paths_by_label["Backups"].source == "user_override"
    assert "do-not-leak" not in str(asdict(diagnostics))


def test_collect_product_diagnostics_reports_support_artifact_paths(tmp_path):
    log_path = tmp_path / "logs" / "launcher.log"

    diagnostics = collect_product_diagnostics(
        app_root=tmp_path,
        app_data_dir=tmp_path / "app_data",
        env={PRODUCT_LOG_PATH_ENV: str(log_path), "SECRET_TOKEN": "do-not-leak"},
    )

    assert diagnostics.support_artifacts.product_log_path == str(log_path)
    assert diagnostics.support_artifacts.product_log_env_var == PRODUCT_LOG_PATH_ENV
    assert diagnostics.support_artifacts.runtime_event_log_path == str(
        tmp_path / ".litlaunch/runtime-events.log"
    )
    assert diagnostics.support_artifacts.reports_dir == str(
        tmp_path / ".litlaunch/reports"
    )
    assert "do-not-leak" not in str(asdict(diagnostics))


def test_collect_product_diagnostics_reports_data_health(tmp_path):
    app_data = tmp_path / "app_data"
    app_data.mkdir()
    database = app_data / "rolethread.db"
    preferences = app_data / "preferences.json"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE app_settings (key TEXT, value TEXT)")
    preferences.write_text('{"preview_user_name": "User"}', encoding="utf-8")

    diagnostics = collect_product_diagnostics(
        app_root=tmp_path,
        app_data_dir=app_data,
    )

    assert diagnostics.data_health.database_exists is True
    assert diagnostics.data_health.database_readable is True
    assert diagnostics.data_health.preferences_exists is True
    assert diagnostics.data_health.preferences_readable is True
    assert diagnostics.data_health.warnings == ()


def test_collect_product_diagnostics_packaged_detection_is_mockable(tmp_path):
    diagnostics = collect_product_diagnostics(
        app_root=tmp_path,
        app_data_dir=tmp_path / "app_data",
        frozen=True,
    )

    assert diagnostics.overview.runtime_context == "packaged"
