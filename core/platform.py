"""Central platform detection and optional OS integration helpers."""
from __future__ import annotations

from dataclasses import dataclass
import os
import platform as _platform
from pathlib import Path
import shutil


OS_WINDOWS = "windows"
OS_LINUX = "linux"
OS_MACOS = "macos"
OS_UNKNOWN = "unknown"

SUPPORT_PRIMARY = "primary"
SUPPORT_BETA = "beta"
SUPPORT_UNSUPPORTED = "unsupported"
PATH_SOURCE_PLATFORM_DEFAULT = "platform_default"
PATH_SOURCE_USER_OVERRIDE = "user_override"


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
class PlatformPaths:
    """Platform-aware default local paths for future storage integration."""

    app_data_root: Path
    workspace_root: Path
    training_data_dir: Path
    exports_dir: Path
    imports_dir: Path
    backups_dir: Path
    logs_dir: Path
    cache_dir: Path
    database_path: Path
    preferences_path: Path


@dataclass(frozen=True)
class PlatformPathResolution:
    """One resolved path plus whether it came from defaults or preferences."""

    path: Path
    source: str
    platform_default: Path

    @property
    def is_user_override(self) -> bool:
        return self.source == PATH_SOURCE_USER_OVERRIDE


@dataclass(frozen=True)
class PlatformPathSources:
    """Path origin metadata keyed to PlatformPaths fields."""

    app_data_root: str
    workspace_root: str
    training_data_dir: str
    exports_dir: str
    imports_dir: str
    backups_dir: str
    logs_dir: str
    cache_dir: str
    database_path: str
    preferences_path: str


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
class PlatformSupportMessage:
    """User-facing platform support note for Settings/About."""

    label: str
    message: str


@dataclass(frozen=True)
class BrowserInfo:
    """Detected local browser availability details."""

    edge_detected: bool
    edge_path: Path | None
    edge_detection_method: str


@dataclass(frozen=True)
class BrowserCapabilities:
    """Browser workflow capability metadata for the current platform."""

    supports_default_browser: bool
    supports_edge_webapp: bool
    edge_available: bool
    edge_webapp_available: bool
    fallback_to_default_browser: bool


@dataclass(frozen=True)
class BrowserDetectionResult:
    """Combined platform browser capability and availability result."""

    platform: PlatformInfo
    browser: BrowserInfo
    capabilities: BrowserCapabilities
    message: str


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


def get_platform_support_messages(
    platform_info: PlatformInfo | None = None,
) -> tuple[PlatformSupportMessage, ...]:
    """Return centralized user-facing support notes for a platform."""

    info = platform_info or detect_platform()
    capabilities = info.capabilities

    if capabilities.supports_linux_manual_run:
        return (
            PlatformSupportMessage(
                "Support",
                "Linux is a primary V1 support platform.",
            ),
            PlatformSupportMessage(
                "Run model",
                "Manual or git-clone setup is the expected Linux workflow for V1.",
            ),
        )

    if capabilities.supports_macos_beta:
        return (
            PlatformSupportMessage(
                "Support",
                "macOS is beta-supported for V1.",
            ),
            PlatformSupportMessage(
                "Testing",
                "macOS behavior is community-tested until maintainer hardware is available.",
            ),
            PlatformSupportMessage(
                "Installer",
                "A macOS installer is not planned for V1.",
            ),
        )

    if info.support_level == SUPPORT_UNSUPPORTED:
        return (
            PlatformSupportMessage(
                "Support",
                "This platform is not officially supported for V1.",
            ),
            PlatformSupportMessage(
                "Behavior",
                "Platform-specific features are disabled where support is unknown.",
            ),
        )

    messages = [
        PlatformSupportMessage(
            "Support",
            f"{info.display_name} is a primary V1 support platform.",
        )
    ]
    if capabilities.supports_installer:
        messages.append(
            PlatformSupportMessage(
                "Installer",
                "Installer support is planned for V1 distribution.",
            )
        )
    if capabilities.supports_edge_webapp:
        messages.append(
            PlatformSupportMessage(
                "Web app",
                "Edge web app support is planned for a later launcher pass.",
            )
        )
    return tuple(messages)


def detect_browser_capabilities(
    system_name: str | None = None,
    *,
    platform_info: PlatformInfo | None = None,
    home: Path | str | None = None,
    env: dict[str, str] | None = None,
    which_fn=None,
    path_exists_fn=None,
) -> BrowserDetectionResult:
    """Detect browser workflow availability without launching anything."""

    info = platform_info or detect_platform(system_name)
    env_values = os.environ if env is None else env
    home_path = Path(home).expanduser() if home is not None else Path.home()
    edge_info = _detect_edge_browser(
        info,
        home=home_path,
        env=env_values,
        which_fn=which_fn or shutil.which,
        path_exists_fn=path_exists_fn or _path_exists,
    )
    edge_webapp_available = (
        info.capabilities.supports_edge_webapp
        and edge_info.edge_detected
    )
    fallback_to_default_browser = (
        info.capabilities.supports_default_browser
        and not edge_webapp_available
    )
    capabilities = BrowserCapabilities(
        supports_default_browser=info.capabilities.supports_default_browser,
        supports_edge_webapp=info.capabilities.supports_edge_webapp,
        edge_available=edge_info.edge_detected,
        edge_webapp_available=edge_webapp_available,
        fallback_to_default_browser=fallback_to_default_browser,
    )
    return BrowserDetectionResult(
        platform=info,
        browser=edge_info,
        capabilities=capabilities,
        message=_browser_detection_message(info, capabilities),
    )


def _detect_edge_browser(
    platform_info: PlatformInfo,
    *,
    home: Path,
    env: dict[str, str],
    which_fn,
    path_exists_fn,
) -> BrowserInfo:
    if not platform_info.capabilities.supports_edge_webapp:
        return BrowserInfo(False, None, "not_applicable")

    which_path = which_fn("msedge")
    if which_path:
        return BrowserInfo(True, Path(which_path).expanduser(), "path")

    for candidate in _edge_candidate_paths(env, home):
        if path_exists_fn(candidate):
            return BrowserInfo(True, candidate, "common_install_path")

    return BrowserInfo(False, None, "not_found")


def _edge_candidate_paths(env: dict[str, str], home: Path) -> tuple[Path, ...]:
    roots = [
        env.get("PROGRAMFILES"),
        env.get("PROGRAMFILES(X86)"),
        env.get("LOCALAPPDATA"),
    ]
    candidates: list[Path] = []
    for root in roots:
        if not root:
            continue
        root_path = Path(root).expanduser()
        candidates.append(root_path / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    candidates.append(
        home / "AppData" / "Local" / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    )
    return tuple(dict.fromkeys(candidates))


def _browser_detection_message(
    platform_info: PlatformInfo,
    capabilities: BrowserCapabilities,
) -> str:
    if capabilities.edge_webapp_available:
        return "Microsoft Edge is available for future Windows web-app workflows."
    if platform_info.capabilities.supports_edge_webapp:
        return (
            "Microsoft Edge was not detected. Future browser launch flows should "
            "fall back to the default browser."
        )
    if capabilities.supports_default_browser:
        return "Default browser workflows are supported on this platform."
    return "Browser workflows are not supported on this platform."


def _path_exists(path: Path) -> bool:
    return path.exists()


def get_platform_paths(
    system_name: str | None = None,
    *,
    home: Path | str | None = None,
    env: dict[str, str] | None = None,
    preferences: dict | None = None,
) -> PlatformPaths:
    """Return platform-aware default paths without creating directories."""

    resolved_paths = get_platform_path_resolutions(
        system_name,
        home=home,
        env=env,
        preferences=preferences,
    )

    return PlatformPaths(
        app_data_root=resolved_paths.app_data_root.path,
        workspace_root=resolved_paths.workspace_root.path,
        training_data_dir=resolved_paths.training_data_dir.path,
        exports_dir=resolved_paths.exports_dir.path,
        imports_dir=resolved_paths.imports_dir.path,
        backups_dir=resolved_paths.backups_dir.path,
        logs_dir=resolved_paths.logs_dir.path,
        cache_dir=resolved_paths.cache_dir.path,
        database_path=resolved_paths.database_path.path,
        preferences_path=resolved_paths.preferences_path.path,
    )


@dataclass(frozen=True)
class PlatformPathResolutions:
    """Resolved platform paths with source metadata for each path."""

    app_data_root: PlatformPathResolution
    workspace_root: PlatformPathResolution
    training_data_dir: PlatformPathResolution
    exports_dir: PlatformPathResolution
    imports_dir: PlatformPathResolution
    backups_dir: PlatformPathResolution
    logs_dir: PlatformPathResolution
    cache_dir: PlatformPathResolution
    database_path: PlatformPathResolution
    preferences_path: PlatformPathResolution


def get_platform_path_resolutions(
    system_name: str | None = None,
    *,
    home: Path | str | None = None,
    env: dict[str, str] | None = None,
    preferences: dict | None = None,
) -> PlatformPathResolutions:
    """Return platform-aware paths with source metadata."""

    platform_info = detect_platform(system_name)
    home_path = Path(home).expanduser() if home is not None else Path.home()
    env_values = os.environ if env is None else env

    if platform_info.os_name == OS_WINDOWS:
        user_profile = Path(env_values.get("USERPROFILE") or home_path).expanduser()
        local_app_data = Path(
            env_values.get("LOCALAPPDATA")
            or user_profile / "AppData" / "Local"
        ).expanduser()
        app_data_root = local_app_data / "LoreForge"
        workspace_root = user_profile / "LoreForge"
    elif platform_info.os_name == OS_LINUX:
        app_data_root = home_path / ".local" / "share" / "loreforge"
        workspace_root = home_path / "LoreForge"
    elif platform_info.os_name == OS_MACOS:
        app_data_root = home_path / "Library" / "Application Support" / "LoreForge"
        workspace_root = home_path / "LoreForge"
    else:
        workspace_root = home_path / "LoreForge"
        app_data_root = workspace_root

    configured_training_dir = str(
        (preferences or {}).get("default_dataset_directory") or ""
    ).strip()
    configured_backup_dir = str(
        (preferences or {}).get("backup_directory") or ""
    ).strip()
    training_data = _resolve_platform_path(
        workspace_root / "training_data",
        configured_training_dir,
    )
    backups = _resolve_platform_path(
        workspace_root / "backups",
        configured_backup_dir,
    )

    return PlatformPathResolutions(
        app_data_root=PlatformPathResolution(
            app_data_root,
            PATH_SOURCE_PLATFORM_DEFAULT,
            app_data_root,
        ),
        workspace_root=PlatformPathResolution(
            workspace_root,
            PATH_SOURCE_PLATFORM_DEFAULT,
            workspace_root,
        ),
        training_data_dir=training_data,
        exports_dir=PlatformPathResolution(
            workspace_root / "exports",
            PATH_SOURCE_PLATFORM_DEFAULT,
            workspace_root / "exports",
        ),
        imports_dir=PlatformPathResolution(
            workspace_root / "imports",
            PATH_SOURCE_PLATFORM_DEFAULT,
            workspace_root / "imports",
        ),
        backups_dir=backups,
        logs_dir=PlatformPathResolution(
            app_data_root / "logs",
            PATH_SOURCE_PLATFORM_DEFAULT,
            app_data_root / "logs",
        ),
        cache_dir=PlatformPathResolution(
            app_data_root / "cache",
            PATH_SOURCE_PLATFORM_DEFAULT,
            app_data_root / "cache",
        ),
        database_path=PlatformPathResolution(
            app_data_root / "loreforge.db",
            PATH_SOURCE_PLATFORM_DEFAULT,
            app_data_root / "loreforge.db",
        ),
        preferences_path=PlatformPathResolution(
            app_data_root / "preferences.json",
            PATH_SOURCE_PLATFORM_DEFAULT,
            app_data_root / "preferences.json",
        ),
    )


def get_platform_path_sources(
    system_name: str | None = None,
    *,
    home: Path | str | None = None,
    env: dict[str, str] | None = None,
    preferences: dict | None = None,
) -> PlatformPathSources:
    """Return only path source labels for callers that already have paths."""

    resolutions = get_platform_path_resolutions(
        system_name,
        home=home,
        env=env,
        preferences=preferences,
    )
    return PlatformPathSources(
        app_data_root=resolutions.app_data_root.source,
        workspace_root=resolutions.workspace_root.source,
        training_data_dir=resolutions.training_data_dir.source,
        exports_dir=resolutions.exports_dir.source,
        imports_dir=resolutions.imports_dir.source,
        backups_dir=resolutions.backups_dir.source,
        logs_dir=resolutions.logs_dir.source,
        cache_dir=resolutions.cache_dir.source,
        database_path=resolutions.database_path.source,
        preferences_path=resolutions.preferences_path.source,
    )


def _resolve_platform_path(default_path: Path, configured_path: str) -> PlatformPathResolution:
    if configured_path:
        return PlatformPathResolution(
            Path(configured_path).expanduser(),
            PATH_SOURCE_USER_OVERRIDE,
            default_path,
        )
    return PlatformPathResolution(
        default_path,
        PATH_SOURCE_PLATFORM_DEFAULT,
        default_path,
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
