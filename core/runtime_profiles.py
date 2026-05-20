"""RoleThread product profile helpers for LitLaunch."""

from __future__ import annotations

from pathlib import Path

from litlaunch import LaunchProfile, load_profile


ROLETHREAD_APP_TITLE = "RoleThread Lite"
ROLETHREAD_WEBAPP_PROFILE = "rolethread-webapp"
ROLETHREAD_BROWSER_PROFILE = "rolethread-browser"
ROLETHREAD_PROFILE_FILE = "litlaunch.toml"


def resolve_rolethread_root() -> Path:
    """Return the active RoleThread project root."""

    return Path(__file__).resolve().parents[1]


def rolethread_profile_path(root: str | Path | None = None) -> Path:
    """Return the LitLaunch profile config path for a project or bundle root."""

    resolved_root = Path(root).resolve() if root is not None else resolve_rolethread_root()
    return resolved_root / ROLETHREAD_PROFILE_FILE


def load_rolethread_profile(
    name: str = ROLETHREAD_WEBAPP_PROFILE,
    *,
    root: str | Path | None = None,
) -> LaunchProfile:
    """Load one RoleThread LitLaunch profile from ``litlaunch.toml``."""

    config_path = rolethread_profile_path(root)
    return load_profile(name, config_path)
