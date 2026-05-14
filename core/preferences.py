"""DB-backed local application preferences.

The SQLite app_settings table is the runtime source of truth. The legacy
preferences.json file is read only once when the settings table is empty, then
left in place as a backup. JSON export/import remains available for portability.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.db import SessionLocal, init_db
from core.models import AppSetting
from core.storage import (
    APP_DATA_DIR,
    ensure_app_directories,
    get_backups_dir,
    get_default_training_data_dir,
)

ensure_app_directories()

PREFS_FILE = APP_DATA_DIR / "preferences.json"

DEFAULTS: dict = {
    "last_loaded_dataset_path": "",
    "recent_dataset_paths": [],
    "last_open_directory": "",
    "last_system_prompt": "",
    "preview_user_name": "User",
    "preview_assistant_name": "Assistant",
    "confirm_delete_entries": True,
    "default_dataset_directory": str(get_default_training_data_dir()),
    "auto_backups_enabled": True,
    "backup_directory": str(get_backups_dir()),
    "backups_per_dataset": 25,
    "backup_destination_type": "local",
    "backup_destination_custom_path": "",
    "cloud_backup_last_sync_at": "",
    "auto_correct_validation_errors": True,
}


def get_setting(key: str, default: Any = None) -> Any:
    """Return one setting value from the DB, or default when it is missing."""

    _ensure_settings_ready()
    session = SessionLocal()
    try:
        row = session.query(AppSetting).filter_by(key=str(key)).first()
        if row is None:
            return default
        return _deserialize_setting(row.value, default)
    finally:
        session.close()


def set_setting(key: str, value: Any) -> None:
    """Serialize and upsert one setting value."""

    set_all_settings({str(key): value})


def get_all_settings() -> dict:
    """Return all stored settings without applying defaults."""

    _ensure_settings_ready()
    session = SessionLocal()
    try:
        rows = session.query(AppSetting).order_by(AppSetting.key).all()
        return {
            row.key: _deserialize_setting(row.value, None)
            for row in rows
        }
    finally:
        session.close()


def set_all_settings(settings: dict) -> None:
    """Bulk upsert settings into the DB."""

    _ensure_settings_table()
    session = SessionLocal()
    try:
        for key, value in dict(settings or {}).items():
            key = str(key)
            row = session.query(AppSetting).filter_by(key=key).first()
            serialized = json.dumps(value, ensure_ascii=False)
            if row is None:
                session.add(AppSetting(key=key, value=serialized))
            else:
                row.value = serialized
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def export_settings(path: str | Path) -> None:
    """Write current settings, including defaults, to a UTF-8 JSON file."""

    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(load_preferences(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def import_settings(path: str | Path) -> dict:
    """Read settings from a JSON file, upsert them, and return merged settings."""

    input_path = Path(path).expanduser()
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Settings import file must contain a JSON object.")
    _apply_legacy_preference_keys(data)
    set_all_settings(data)
    return load_preferences()


def migrate_preferences_json_if_needed() -> bool:
    """Import preferences.json into the DB if the settings table is empty."""

    _ensure_settings_table()
    if not PREFS_FILE.exists() or _settings_table_has_rows():
        return False

    data = _read_preferences_json()
    if data is None:
        return False

    _apply_legacy_preference_keys(data)
    set_all_settings(data)
    print("Migrated settings from preferences.json to database")
    return True


def load_preferences() -> dict:
    """Load DB-backed preferences merged with defaults."""

    migrate_preferences_json_if_needed()
    stored = get_all_settings()
    if (
        "auto_correct_validation_errors" not in stored
        and "auto_normalize_on_load" in stored
    ):
        stored["auto_correct_validation_errors"] = stored["auto_normalize_on_load"]
        set_setting("auto_correct_validation_errors", stored["auto_normalize_on_load"])
    return {**DEFAULTS, **stored}


def save_preferences(prefs: dict) -> None:
    """Persist preferences to the DB.

    Kept for compatibility with existing UI/session code; it no longer writes
    preferences.json.
    """

    set_all_settings(dict(prefs or {}))


def get_initial_dir(
    prefs: dict,
    path_key: str = "",
    dir_key: str = "last_open_directory",
) -> str | None:
    """Return the best initialdir for a file dialog, or None to let the OS decide."""
    if path_key:
        p = prefs.get(path_key, "")
        if p:
            parent = Path(p).parent
            if parent.exists():
                return str(parent)
    d = prefs.get(dir_key, "")
    if d and Path(d).exists():
        return d
    default_dir = prefs.get("default_dataset_directory", "")
    if default_dir and Path(default_dir).exists():
        return default_dir
    return None


def _ensure_settings_ready() -> None:
    _ensure_settings_table()
    migrate_preferences_json_if_needed()


def _ensure_settings_table() -> None:
    init_db()


def _settings_table_has_rows() -> bool:
    session = SessionLocal()
    try:
        return session.query(AppSetting.key).first() is not None
    finally:
        session.close()


def _read_preferences_json() -> dict | None:
    try:
        data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _apply_legacy_preference_keys(data: dict) -> None:
    if (
        "auto_correct_validation_errors" not in data
        and "auto_normalize_on_load" in data
    ):
        data["auto_correct_validation_errors"] = data["auto_normalize_on_load"]


def _deserialize_setting(value: str | None, default: Any) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default
