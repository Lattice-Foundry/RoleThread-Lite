"""Application-managed storage paths.

This module centralizes LoreForge's local directories and creates them on
startup. It must stay independent of Streamlit.
"""
from pathlib import Path

from core.platform import get_platform_paths


APP_ROOT = Path(__file__).resolve().parent.parent
LEGACY_APP_DATA_DIR = APP_ROOT / "app_data"
_PLATFORM_PATHS = get_platform_paths()


def _legacy_app_data_has_state(path: Path = LEGACY_APP_DATA_DIR) -> bool:
    """Return whether an existing repo-local app state folder should be honored."""

    return any(
        (path / name).exists()
        for name in ("loreforge.db", "preferences.json", "backup_config.json")
    )


APP_DATA_DIR = (
    LEGACY_APP_DATA_DIR
    if _legacy_app_data_has_state()
    else _PLATFORM_PATHS.app_data_root
)
BACKUPS_DIR = _PLATFORM_PATHS.backups_dir
TEMP_DIR = _PLATFORM_PATHS.cache_dir
TRAINING_DATA_DIR = _PLATFORM_PATHS.training_data_dir


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
