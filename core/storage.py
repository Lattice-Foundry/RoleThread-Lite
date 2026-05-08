"""Application-managed storage paths.

This module centralizes LoreForge's local directories and creates them on
startup. It must stay independent of Streamlit.
"""
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent.parent
APP_DATA_DIR = APP_ROOT / "app_data"
BACKUPS_DIR = APP_DATA_DIR / "backups"
TEMP_DIR = APP_DATA_DIR / "temp"
TRAINING_DATA_DIR = APP_ROOT / "training_data"


def ensure_app_directories() -> None:
    """Create LoreForge-managed directories if they are missing."""
    for path in (APP_DATA_DIR, BACKUPS_DIR, TEMP_DIR, TRAINING_DATA_DIR):
        path.mkdir(parents=True, exist_ok=True)


def get_default_training_data_dir() -> Path:
    """Return the default folder for user datasets."""

    return TRAINING_DATA_DIR


def get_backups_dir() -> Path:
    """Return the default backup root."""

    return BACKUPS_DIR


def get_temp_dir() -> Path:
    """Return the app-managed temporary directory."""

    return TEMP_DIR
