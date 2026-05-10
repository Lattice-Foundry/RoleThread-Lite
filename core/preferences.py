"""Persisted local application preferences.

Preferences are stored as JSON under app_data and merged with defaults on
load. This module is filesystem-only and must stay Streamlit-free.
"""
import json
from pathlib import Path

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
    "last_open_directory": "",
    "last_system_prompt": "",
    "preview_user_name": "User",
    "preview_assistant_name": "Assistant",
    "dataset_format": "ChatML",
    "confirm_delete_entries": True,
    "default_dataset_directory": str(get_default_training_data_dir()),
    "auto_backups_enabled": True,
    "backup_directory": str(get_backups_dir()),
    "backups_per_dataset": 25,
    "auto_normalize_on_load": True,
}


def load_preferences() -> dict:
    """Load preferences, falling back to defaults on missing or invalid data."""

    try:
        if PREFS_FILE.exists():
            data = json.loads(PREFS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**DEFAULTS, **data}
    except Exception:
        pass
    return dict(DEFAULTS)


def save_preferences(prefs: dict) -> None:
    """Write preferences to disk as UTF-8 JSON."""

    ensure_app_directories()
    PREFS_FILE.write_text(
        json.dumps(prefs, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_initial_dir(prefs: dict, path_key: str = "", dir_key: str = "last_open_directory") -> str | None:
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
