"""Central platform detection and optional OS integration helpers."""
from __future__ import annotations

from dataclasses import dataclass
import os
import platform as _platform
from pathlib import Path


OS_WINDOWS = "windows"
OS_LINUX = "linux"
OS_MACOS = "macos"
OS_UNKNOWN = "unknown"

SUPPORT_PRIMARY = "primary"
SUPPORT_BETA = "beta"
SUPPORT_UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class PlatformCapabilities:
    """Feature availability flags for the detected platform."""

    supports_installer: bool
    supports_edge_webapp: bool
    supports_default_browser: bool
    supports_onedrive: bool
    supports_safe_cloud_sync: bool
    supports_linux_manual_run: bool
    supports_macos_beta: bool


@dataclass(frozen=True)
class PlatformDiagnostics:
    """Raw OS and Python runtime details for support diagnostics."""

    raw_system: str
    release: str
    version: str
    platform_string: str
    machine: str
    processor: str
    python_version: str
    python_implementation: str
    python_architecture: str


@dataclass(frozen=True)
class PlatformInfo:
    """Normalized LoreForge platform support information."""

    os_name: str
    platform_slug: str
    display_name: str
    support_level: str
    capabilities: PlatformCapabilities
    diagnostics: PlatformDiagnostics


@dataclass(frozen=True)
class _PlatformProfile:
    os_name: str
    display_name: str
    support_level: str
    capabilities: PlatformCapabilities


_PLATFORM_BY_SYSTEM_NAME = {
    "Windows": _PlatformProfile(
        OS_WINDOWS,
        "Windows",
        SUPPORT_PRIMARY,
        PlatformCapabilities(
            supports_installer=True,
            supports_edge_webapp=True,
            supports_default_browser=True,
            supports_onedrive=True,
            supports_safe_cloud_sync=True,
            supports_linux_manual_run=False,
            supports_macos_beta=False,
        ),
    ),
    "Linux": _PlatformProfile(
        OS_LINUX,
        "Linux",
        SUPPORT_PRIMARY,
        PlatformCapabilities(
            supports_installer=False,
            supports_edge_webapp=False,
            supports_default_browser=True,
            supports_onedrive=False,
            supports_safe_cloud_sync=True,
            supports_linux_manual_run=True,
            supports_macos_beta=False,
        ),
    ),
    "Darwin": _PlatformProfile(
        OS_MACOS,
        "macOS",
        SUPPORT_BETA,
        PlatformCapabilities(
            supports_installer=False,
            supports_edge_webapp=False,
            supports_default_browser=True,
            supports_onedrive=False,
            supports_safe_cloud_sync=True,
            supports_linux_manual_run=False,
            supports_macos_beta=True,
        ),
    ),
}

UNKNOWN_PLATFORM_PROFILE = _PlatformProfile(
    OS_UNKNOWN,
    "Unknown",
    SUPPORT_UNSUPPORTED,
    PlatformCapabilities(
        supports_installer=False,
        supports_edge_webapp=False,
        supports_default_browser=False,
        supports_onedrive=False,
        supports_safe_cloud_sync=False,
        supports_linux_manual_run=False,
        supports_macos_beta=False,
    ),
)


def collect_platform_diagnostics(system_name: str | None = None) -> PlatformDiagnostics:
    """Collect raw platform/runtime details for support reports."""

    raw_system = system_name if system_name is not None else _platform.system()
    python_architecture, _python_linkage = _platform.architecture()
    return PlatformDiagnostics(
        raw_system=raw_system,
        release=_platform.release(),
        version=_platform.version(),
        platform_string=_platform.platform(),
        machine=_platform.machine(),
        processor=_platform.processor(),
        python_version=_platform.python_version(),
        python_implementation=_platform.python_implementation(),
        python_architecture=python_architecture,
    )


def detect_platform(system_name: str | None = None) -> PlatformInfo:
    """Return normalized LoreForge support information for the current OS."""

    detected_name = system_name if system_name is not None else _platform.system()
    profile = _PLATFORM_BY_SYSTEM_NAME.get(detected_name, UNKNOWN_PLATFORM_PROFILE)
    return PlatformInfo(
        os_name=profile.os_name,
        platform_slug=profile.os_name,
        display_name=profile.display_name,
        support_level=profile.support_level,
        capabilities=profile.capabilities,
        diagnostics=collect_platform_diagnostics(detected_name),
    )


IS_WINDOWS = detect_platform().os_name == OS_WINDOWS


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
