"""Windows packaged launcher adapter for RoleThread Lite.

This module keeps RoleThread-specific packaged concerns at the edge and lets
LitLaunch own runtime process, browser, window, and shutdown lifecycle.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, replace
import os
from pathlib import Path
import sys
from typing import Callable, Mapping, Sequence, TextIO

from litlaunch import (
    BackendCommand,
    BackendCommandContext,
    LaunchPlan,
    LaunchProfile,
    MonitoredRunResult,
    PlatformDetector,
    PlatformInfo,
    StreamlitLauncher,
    WindowMonitor,
    run_monitored_webapp,
)
from litlaunch.console import ConsoleMode, ConsoleRenderer, ConsoleTheme
from litlaunch.redaction import format_command_preview

from core.product_log import (
    PRODUCT_LOG_FILE_NAME,
    PRODUCT_LOG_PATH_ENV,
    write_product_log,
)
from core.runtime_profiles import (
    ROLETHREAD_APP_TITLE,
    ROLETHREAD_WEBAPP_PROFILE,
    load_rolethread_profile,
)
from core.runtime_shutdown import ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV


APP_NAME = ROLETHREAD_APP_TITLE
APP_DATA_DIR_NAME = "RoleThread"
PREFERENCES_FILE_NAME = "preferences.json"
INTERNAL_STREAMLIT_FLAG = "--rolethread-run-streamlit"


class LauncherConfigurationError(RuntimeError):
    """Raised when the packaged launcher cannot build a runnable runtime."""


@dataclass(frozen=True)
class PackagedLauncherConfig:
    """RoleThread product configuration for packaged LitLaunch runs."""

    app_root: Path
    launcher_executable: Path
    preferences_path: Path
    log_path: Path
    bundled_mode: bool
    diagnostics_enabled: bool = False


class PackagedRoleThreadBackendProvider:
    """Build the packaged backend command LitLaunch should own."""

    description = "RoleThread packaged Streamlit backend"
    backend_kind = "rolethread-packaged"

    def __init__(
        self,
        *,
        launcher_executable: str | Path,
        app_root: str | Path,
    ) -> None:
        self.launcher_executable = Path(launcher_executable)
        self.app_root = validate_app_root(Path(app_root))

    def build_backend_command(
        self,
        context: BackendCommandContext,
    ) -> BackendCommand:
        app_script = self.app_root / "app.py"
        return BackendCommand(
            (
                str(self.launcher_executable),
                INTERNAL_STREAMLIT_FLAG,
                str(app_script),
                "--global.developmentMode=false",
                "--server.address",
                context.host,
                "--server.headless",
                "true" if context.headless else "false",
                "--server.port",
                str(context.port),
            ),
            description=self.description,
            backend_kind=self.backend_kind,
        )


def validate_app_root(app_root: Path) -> Path:
    resolved = Path(app_root).resolve()
    if not (resolved / "app.py").is_file():
        raise LauncherConfigurationError(
            f"Could not find RoleThread app.py under app root: {resolved}"
        )
    return resolved


def resolve_app_root(
    *,
    start_path: Path | None = None,
    frozen: bool | None = None,
) -> Path:
    """Resolve the RoleThread app root for source or bundled launcher runs."""

    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        bundled_root = Path(
            getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)
        )
        return validate_app_root(bundled_root)

    current = Path(start_path or Path(__file__)).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "app.py").is_file():
            return candidate
    return validate_app_root(Path.cwd())


def resolve_app_data_root(env: Mapping[str, str] | None = None) -> Path:
    env_map = env if env is not None else os.environ
    local_app_data = env_map.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DATA_DIR_NAME
    return Path.home() / "AppData" / "Local" / APP_DATA_DIR_NAME


def resolve_preferences_path(env: Mapping[str, str] | None = None) -> Path:
    return resolve_app_data_root(env) / PREFERENCES_FILE_NAME


def resolve_launcher_log_path(env: Mapping[str, str] | None = None) -> Path:
    return resolve_app_data_root(env) / "logs" / PRODUCT_LOG_FILE_NAME


def resolve_launcher_executable(
    *,
    current_executable: str | None = None,
    frozen: bool | None = None,
) -> Path:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    executable = Path(current_executable or sys.executable)
    if is_frozen and not executable.is_file():
        raise LauncherConfigurationError(
            "Could not find the bundled RoleThread launcher executable."
        )
    return executable


def build_launcher_config(
    *,
    app_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    current_executable: str | None = None,
    frozen: bool | None = None,
    diagnostics_enabled: bool = False,
) -> PackagedLauncherConfig:
    """Build RoleThread product config for the packaged LitLaunch launcher."""

    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    resolved_root = (
        validate_app_root(app_root)
        if app_root is not None
        else resolve_app_root(frozen=is_frozen)
    )
    return PackagedLauncherConfig(
        app_root=resolved_root,
        launcher_executable=resolve_launcher_executable(
            current_executable=current_executable,
            frozen=is_frozen,
        ),
        preferences_path=resolve_preferences_path(env),
        log_path=resolve_launcher_log_path(env),
        bundled_mode=is_frozen,
        diagnostics_enabled=diagnostics_enabled,
    )


def build_launch_profile(config: PackagedLauncherConfig) -> LaunchProfile:
    """Load the RoleThread webapp profile and apply packaged product settings."""

    extra_env = {
        PRODUCT_LOG_PATH_ENV: str(config.log_path),
    }
    if config.diagnostics_enabled:
        extra_env[ROLETHREAD_SHUTDOWN_DIAGNOSTICS_ENV] = "1"

    profile = load_rolethread_profile(ROLETHREAD_WEBAPP_PROFILE, root=config.app_root)
    profile_config = profile.config
    return replace(
        profile,
        config=replace(
            profile_config,
            app_path=config.app_root / "app.py",
            cwd=config.app_root,
            extra_env={**dict(profile_config.extra_env), **extra_env},
        ),
    )


def build_litlaunch_config(config: PackagedLauncherConfig):
    """Return the packaged LitLaunch config for launch-plan tests."""

    return build_launch_profile(config).config


def build_backend_provider(
    config: PackagedLauncherConfig,
) -> PackagedRoleThreadBackendProvider:
    return PackagedRoleThreadBackendProvider(
        launcher_executable=config.launcher_executable,
        app_root=config.app_root,
    )


def build_streamlit_launcher(
    config: PackagedLauncherConfig,
    *,
    console_renderer: ConsoleRenderer | None = None,
) -> StreamlitLauncher:
    return StreamlitLauncher(
        build_launch_profile(config).config,
        backend_command_provider=build_backend_provider(config),
        console_renderer=console_renderer,
    )


def build_launch_plan(config: PackagedLauncherConfig) -> LaunchPlan:
    """Build a redacted packaged launch plan without starting anything."""

    return build_streamlit_launcher(config).build_launch_plan()


def log_launch_plan(config: PackagedLauncherConfig, plan: LaunchPlan) -> None:
    write_product_log(
        config.log_path,
        (
            f"app_root={config.app_root}",
            f"app_version={get_app_version()}",
            f"bundled_mode={config.bundled_mode}",
            f"preferences_path={config.preferences_path}",
            f"backend_kind={plan.backend_kind}",
            f"command={plan.command_display}",
            f"app_url={plan.app_url}",
        ),
    )


def log_runtime_result(
    config: PackagedLauncherConfig,
    result: MonitoredRunResult,
) -> None:
    monitor_status = (
        result.monitor_result.status.value
        if result.monitor_result is not None
        else "none"
    )
    write_product_log(
        config.log_path,
        (
            f"exit_code={result.exit_code}",
            f"launched={result.launched}",
            f"stopped_cleanly={result.stopped_cleanly}",
            f"monitor_status={monitor_status}",
            f"message={result.message}",
        ),
    )


def get_app_version() -> str:
    try:
        from core.version import ROLETHREAD_VERSION
    except Exception:
        return "unknown"
    return ROLETHREAD_VERSION


def show_failure_message(message: str, *, title: str = APP_NAME) -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x00000010)
    except Exception:
        return


def run_packaged_runtime(
    config: PackagedLauncherConfig,
    *,
    launcher_factory: Callable[..., StreamlitLauncher] = build_streamlit_launcher,
    monitored_runner: Callable[..., MonitoredRunResult] = run_monitored_webapp,
    console_renderer: ConsoleRenderer | None = None,
    platform_detector: PlatformDetector | None = None,
    window_monitor_factory: Callable[[PlatformInfo], WindowMonitor] | None = None,
    monitor: WindowMonitor | None = None,
) -> int:
    """Run packaged RoleThread through LitLaunch."""

    renderer = console_renderer or _build_console_renderer()
    launcher = launcher_factory(config, console_renderer=renderer)
    plan = launcher.build_launch_plan()
    log_launch_plan(config, plan)
    profile = build_launch_profile(config)
    runner_kwargs = {
        "window_monitor_config": profile.window_monitor_config,
        "graceful_timeout_seconds": profile.graceful_timeout_seconds,
        "platform_detector": platform_detector,
        "monitor": monitor,
    }
    if window_monitor_factory is not None:
        runner_kwargs["window_monitor_factory"] = window_monitor_factory
    result = monitored_runner(launcher, **runner_kwargs)
    log_runtime_result(config, result)
    if result.exit_code != 0 and result.monitor_result is not None:
        renderer.render_window_monitor_result(result.monitor_result)
    return result.exit_code


def _build_console_renderer() -> ConsoleRenderer:
    return ConsoleRenderer(
        mode=ConsoleMode.NORMAL,
        theme=ConsoleTheme(),
        stream=_safe_output_stream(),
    )


def run_bundled_streamlit(argv: Sequence[str] | None = None) -> int:
    """Run Streamlit from inside the frozen PyInstaller runtime."""

    args = list(sys.argv[2:] if argv is None else argv)
    if not args:
        raise LauncherConfigurationError("Bundled Streamlit mode requires an app.py path.")

    app_script = Path(args[0]).resolve()
    if not app_script.is_file():
        raise LauncherConfigurationError(f"Could not find bundled app.py: {app_script}")

    streamlit_args = ["streamlit", "run", str(app_script), *args[1:]]
    sys.path.insert(0, str(app_script.parent))
    sys.argv = streamlit_args

    from streamlit.web.cli import main as streamlit_main

    streamlit_main()
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == INTERNAL_STREAMLIT_FLAG:
        return run_bundled_streamlit()

    try:
        config = build_launcher_config()
        _safe_print(f"Starting {APP_NAME} through LitLaunch...")
        plan = build_launch_plan(config)
        _safe_print(format_command_preview(plan.command))
        return run_packaged_runtime(config)
    except Exception as exc:
        try:
            log_path = resolve_launcher_log_path()
            write_product_log(log_path, (f"error={exc}",))
            show_failure_message(
                f"RoleThread could not start.\n\n{exc}\n\nDetails were written to:\n{log_path}"
            )
            _safe_print(f"Launcher error: {exc}")
            _safe_print(f"Details written to {log_path}")
        except Exception:
            show_failure_message(f"RoleThread could not start.\n\n{exc}")
            _safe_print(f"Launcher error: {exc}")
        return 1


class _NullTextStream:
    def write(self, text: str) -> int:
        return len(str(text))

    def flush(self) -> None:
        return None


def _safe_output_stream() -> TextIO:
    stream = sys.stdout
    if stream is not None and callable(getattr(stream, "write", None)):
        return stream
    return _NullTextStream()  # type: ignore[return-value]


def _safe_print(message: object) -> None:
    stream = _safe_output_stream()
    stream.write(f"{message}\n")
    stream.flush()


if __name__ == "__main__":
    raise SystemExit(main())
