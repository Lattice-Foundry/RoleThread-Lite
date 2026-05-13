"""Small platform-detection helpers for optional OS integrations."""
from __future__ import annotations

import os
import platform as _platform
from pathlib import Path


IS_WINDOWS = _platform.system() == "Windows"


def detect_onedrive_path() -> Path | None:
    """Return the local OneDrive folder on Windows, if it can be found."""

    if not IS_WINDOWS:
        return None

    candidates: list[Path] = []
    env_path = os.environ.get("ONEDRIVE")
    if env_path:
        candidates.append(Path(env_path).expanduser())

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.append(Path(user_profile).expanduser() / "OneDrive")

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    return None


def default_onedrive_backup_path() -> Path | None:
    """Return LoreForge Lite's default OneDrive backup folder."""

    root = detect_onedrive_path()
    if root is None:
        return None
    return root / "LoreForge Lite" / "backups"
