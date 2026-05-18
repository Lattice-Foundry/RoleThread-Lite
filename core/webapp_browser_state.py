"""Targeted browser-side cleanup for RoleThread Edge webapp troubleshooting."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime


ROLETHREAD_LOCALHOST_URL_PREFIXES = (
    "http://localhost:8501",
    "http://127.0.0.1:8501",
)
ROLETHREAD_CACHE_MARKERS = (
    b"http://localhost:8501",
    b"http://127.0.0.1:8501",
    b"localhost:8501",
    b"127.0.0.1:8501",
)
EDGE_CACHE_DIR_NAMES = (
    "Code Cache",
    "Cache",
)
MAX_SCANNED_CACHE_FILE_BYTES = 20 * 1024 * 1024
WEBAPP_BROWSER_STATE_RESET_MARKER_NAME = "webapp_browser_state_reset.json"


@dataclass(frozen=True)
class WebappBrowserStateResetResult:
    """Structured result for Settings/UI reporting."""

    success: bool
    profile_path: Path | None = None
    items_cleared: list[str] = field(default_factory=list)
    items_skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WebappBrowserStateResetScheduleResult:
    """Result for scheduling a reset that should run before the next webapp launch."""

    scheduled: bool
    marker_path: Path
    message: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PendingWebappBrowserStateResetResult:
    """Result for a launcher/startup attempt to consume a pending reset request."""

    pending: bool
    attempted: bool
    completed: bool
    marker_path: Path
    reset_result: WebappBrowserStateResetResult | None = None
    message: str = ""


def reset_rolethread_webapp_browser_state(
    *,
    profile_path: Path | None = None,
    env: Mapping[str, str] | None = None,
    running_process_names: Iterable[str] | None = None,
) -> WebappBrowserStateResetResult:
    """Clear targeted Edge localhost state used by RoleThread webapp mode.

    This intentionally avoids global browser cache, cookies, passwords, and
    unrelated browsing data. If Edge is running, the reset skips mutation rather
    than editing an active Chromium profile.
    """

    # WEBAPP_LIFECYCLE_TODO: reset execution belongs immediately before the
    # launcher-owned Edge app window opens, when Edge should be closed.
    resolved_profile = profile_path or get_default_edge_profile_path(env=env)
    cleared: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    if resolved_profile is None:
        return WebappBrowserStateResetResult(
            success=False,
            items_skipped=["Microsoft Edge profile path could not be resolved."],
            warnings=[
                "Webapp browser state reset is currently available only for Windows Edge profiles."
            ],
        )

    if not resolved_profile.exists():
        return WebappBrowserStateResetResult(
            success=False,
            profile_path=resolved_profile,
            items_skipped=[f"Edge profile was not found: {resolved_profile}"],
            warnings=["No browser-side webapp state was cleared."],
        )

    processes = (
        tuple(running_process_names)
        if running_process_names is not None
        else _detect_running_process_names()
    )
    if _edge_is_running(processes):
        return WebappBrowserStateResetResult(
            success=False,
            profile_path=resolved_profile,
            items_skipped=[
                "Edge appears to be running, so browser profile files were left untouched."
            ],
            warnings=[
                "Close Edge/RoleThread webapp windows before running this reset from a non-Edge browser or another launch mode."
            ],
        )

    _clear_app_window_placement(resolved_profile, cleared, skipped, errors)
    _clear_history_entries(resolved_profile, cleared, skipped, errors)
    _clear_cache_files(resolved_profile, cleared, skipped, errors)

    skipped.append(
        "Edge session/app restore files were not edited; they are binary Chromium profile state."
    )
    skipped.append(
        "Edge Service Worker storage was not edited; it may contain Chromium database state."
    )
    skipped.append(
        "Global Edge cache, cookies, passwords, and unrelated browsing data were not touched."
    )

    return WebappBrowserStateResetResult(
        success=not errors,
        profile_path=resolved_profile,
        items_cleared=cleared,
        items_skipped=skipped,
        warnings=warnings,
        errors=errors,
    )


def resolve_webapp_browser_state_reset_marker_path(
    *,
    app_data_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Return the app-data marker used to schedule a browser-state reset."""

    root = app_data_root or _resolve_rolethread_app_data_root(env=env)
    return root / WEBAPP_BROWSER_STATE_RESET_MARKER_NAME


def is_webapp_browser_state_reset_pending(
    *,
    marker_path: Path | None = None,
    app_data_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Return whether a manual browser-state reset is pending."""

    path = marker_path or resolve_webapp_browser_state_reset_marker_path(
        app_data_root=app_data_root,
        env=env,
    )
    return path.exists()


def schedule_webapp_browser_state_reset(
    *,
    marker_path: Path | None = None,
    app_data_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> WebappBrowserStateResetScheduleResult:
    """Persist a request for the launcher to reset Edge state before webapp launch."""

    path = marker_path or resolve_webapp_browser_state_reset_marker_path(
        app_data_root=app_data_root,
        env=env,
    )
    payload = {
        "requested_at": _utc_timestamp(),
        "status": "pending",
        "purpose": "Reset targeted RoleThread Lite Edge webapp browser state before next webapp launch.",
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        return WebappBrowserStateResetScheduleResult(
            scheduled=False,
            marker_path=path,
            message="Could not schedule webapp browser state reset.",
            errors=[str(exc)],
        )
    return WebappBrowserStateResetScheduleResult(
        scheduled=True,
        marker_path=path,
        message=(
            "Reset scheduled. Close RoleThread Lite completely, then reopen it. "
            "The reset will run before the next webapp window opens."
        ),
    )


def consume_pending_webapp_browser_state_reset(
    *,
    marker_path: Path | None = None,
    app_data_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    profile_path: Path | None = None,
    running_process_names: Iterable[str] | None = None,
) -> PendingWebappBrowserStateResetResult:
    """Run a pending reset request and clear it only after successful cleanup."""

    # WEBAPP_LIFECYCLE_TODO: future shared dev/manual and packaged launchers
    # should both consume this marker before opening Edge app-mode.
    path = marker_path or resolve_webapp_browser_state_reset_marker_path(
        app_data_root=app_data_root,
        env=env,
    )
    if not path.exists():
        return PendingWebappBrowserStateResetResult(
            pending=False,
            attempted=False,
            completed=False,
            marker_path=path,
            message="No webapp browser state reset is pending.",
        )

    result = reset_rolethread_webapp_browser_state(
        profile_path=profile_path,
        env=env,
        running_process_names=running_process_names,
    )
    if result.success:
        try:
            path.unlink(missing_ok=True)
        except Exception as exc:
            _write_pending_reset_attempt(
                path,
                status="cleanup_succeeded_marker_clear_failed",
                reset_result=result,
                errors=[f"Could not clear pending reset marker: {exc}"],
            )
            return PendingWebappBrowserStateResetResult(
                pending=True,
                attempted=True,
                completed=False,
                marker_path=path,
                reset_result=result,
                message="Browser state reset succeeded, but the pending marker could not be cleared.",
            )
        return PendingWebappBrowserStateResetResult(
            pending=False,
            attempted=True,
            completed=True,
            marker_path=path,
            reset_result=result,
            message="Pending webapp browser state reset completed.",
        )

    _write_pending_reset_attempt(path, status="pending_after_failed_attempt", reset_result=result)
    return PendingWebappBrowserStateResetResult(
        pending=True,
        attempted=True,
        completed=False,
        marker_path=path,
        reset_result=result,
        message="Pending webapp browser state reset could not run and remains scheduled.",
    )


def _write_pending_reset_attempt(
    marker_path: Path,
    *,
    status: str,
    reset_result: WebappBrowserStateResetResult,
    errors: list[str] | None = None,
) -> None:
    payload = _read_pending_reset_payload(marker_path)
    payload.update(
        {
            "status": status,
            "last_attempt_at": _utc_timestamp(),
            "profile_path": str(reset_result.profile_path) if reset_result.profile_path else None,
            "items_cleared": reset_result.items_cleared,
            "items_skipped": reset_result.items_skipped,
            "warnings": reset_result.warnings,
            "errors": [*reset_result.errors, *(errors or [])],
        }
    )
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        return


def _read_pending_reset_payload(marker_path: Path) -> dict[str, object]:
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def _resolve_rolethread_app_data_root(
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    environment = env or os.environ
    local_app_data = environment.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "RoleThread"
    return Path.home() / "AppData" / "Local" / "RoleThread"


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_default_edge_profile_path(
    *,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Return the default Windows Edge profile path when it can be resolved."""

    if os.name != "nt":
        return None
    environment = env or os.environ
    local_app_data = environment.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    return Path(local_app_data) / "Microsoft" / "Edge" / "User Data" / "Default"


def _edge_is_running(process_names: Iterable[str]) -> bool:
    return any(name.lower() == "msedge.exe" for name in process_names)


def _detect_running_process_names() -> tuple[str, ...]:
    if os.name != "nt":
        return ()
    try:
        completed = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except Exception:
        return ()
    if completed.returncode != 0:
        return ()
    names: list[str] = []
    for line in completed.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first = stripped.split(",", 1)[0].strip().strip('"')
        if first:
            names.append(first)
    return tuple(names)


def _clear_app_window_placement(
    profile_path: Path,
    cleared: list[str],
    skipped: list[str],
    errors: list[str],
) -> None:
    preferences_path = profile_path / "Preferences"
    if not preferences_path.exists():
        skipped.append("Edge Preferences file was not found.")
        return
    try:
        data = json.loads(preferences_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Could not read Edge Preferences: {exc}")
        return

    placement = (
        data.get("browser", {})
        .get("app_window_placement", {})
    )
    if not isinstance(placement, dict):
        skipped.append("Edge app-window placement metadata was not present.")
        return

    removed_keys = [
        key
        for key in list(placement)
        if "localhost" in key.lower() or "127.0.0.1" in key
    ]
    for key in removed_keys:
        placement.pop(key, None)

    if not removed_keys:
        skipped.append("No RoleThread localhost app-window placement metadata was found.")
        return

    try:
        preferences_path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    except Exception as exc:
        errors.append(f"Could not update Edge Preferences: {exc}")
        return
    cleared.append(
        "Removed Edge app-window placement metadata for RoleThread localhost URLs."
    )


def _clear_history_entries(
    profile_path: Path,
    cleared: list[str],
    skipped: list[str],
    errors: list[str],
) -> None:
    history_path = profile_path / "History"
    if not history_path.exists():
        skipped.append("Edge History database was not found.")
        return
    try:
        with sqlite3.connect(history_path) as connection:
            url_ids = _rolethread_history_url_ids(connection)
            if not url_ids:
                skipped.append("No RoleThread localhost history entries were found.")
                return
            placeholders = ",".join("?" for _ in url_ids)
            if _sqlite_table_exists(connection, "visits"):
                connection.execute(
                    f"DELETE FROM visits WHERE url IN ({placeholders})",
                    url_ids,
                )
            if _sqlite_table_exists(connection, "keyword_search_terms"):
                connection.execute(
                    f"DELETE FROM keyword_search_terms WHERE url_id IN ({placeholders})",
                    url_ids,
                )
            connection.execute(
                f"DELETE FROM urls WHERE id IN ({placeholders})",
                url_ids,
            )
            connection.commit()
    except Exception as exc:
        errors.append(f"Could not update Edge History entries: {exc}")
        return
    cleared.append(
        f"Removed {len(url_ids)} RoleThread localhost history entr"
        f"{'y' if len(url_ids) == 1 else 'ies'}."
    )


def _rolethread_history_url_ids(connection: sqlite3.Connection) -> list[int]:
    if not _sqlite_table_exists(connection, "urls"):
        return []
    conditions = " OR ".join("url LIKE ?" for _ in ROLETHREAD_LOCALHOST_URL_PREFIXES)
    rows = connection.execute(
        f"SELECT id FROM urls WHERE {conditions}",
        tuple(f"{prefix}%" for prefix in ROLETHREAD_LOCALHOST_URL_PREFIXES),
    ).fetchall()
    return [int(row[0]) for row in rows]


def _clear_cache_files(
    profile_path: Path,
    cleared: list[str],
    skipped: list[str],
    errors: list[str],
) -> None:
    scanned = 0
    removed = 0
    for dirname in EDGE_CACHE_DIR_NAMES:
        root = profile_path / dirname
        if not root.exists():
            skipped.append(f"Edge {dirname} directory was not found.")
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            scanned += 1
            try:
                if path.stat().st_size > MAX_SCANNED_CACHE_FILE_BYTES:
                    continue
                data = path.read_bytes()
                if not any(marker in data for marker in ROLETHREAD_CACHE_MARKERS):
                    continue
                path.unlink()
                removed += 1
            except Exception as exc:
                errors.append(f"Could not inspect/remove Edge cache file {path}: {exc}")
    if removed:
        cleared.append(f"Removed {removed} Edge cache file(s) referencing RoleThread localhost URLs.")
    elif scanned:
        skipped.append("No Edge cache files referencing RoleThread localhost URLs were found.")


def _sqlite_table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None
