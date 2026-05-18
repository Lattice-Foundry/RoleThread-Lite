"""Persistent local diagnostics for observed Microsoft Edge versions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
from collections.abc import Callable

from core.db import SessionLocal, init_db
from core.models import EdgeVersionHistory


EDGE_BROWSER_NAME = "Microsoft Edge"
EDGE_VERSION_UNKNOWN = "unknown"


@dataclass(frozen=True)
class EdgeVersionHistoryRecord:
    """Lightweight diagnostic row for UI/debug reporting."""

    browser_name: str
    version: str
    first_seen: datetime
    last_seen: datetime
    encounter_count: int
    source: str | None = None


def read_edge_version(
    edge_path: Path | str | None,
    *,
    run_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str | None:
    """Read the local installed Edge version without network access."""

    if edge_path is None:
        return None
    path = Path(edge_path)
    if not path.exists():
        return None
    version_from_dir = _read_edge_version_from_install_dir(path)
    if version_from_dir:
        return version_from_dir
    escaped = str(path).replace("'", "''")
    script = (
        "$item = Get-Item -LiteralPath "
        f"'{escaped}' -ErrorAction Stop; "
        "$item.VersionInfo.ProductVersion"
    )
    try:
        result = run_fn(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    version = _normalize_edge_version(result.stdout)
    return version or None


def record_edge_version(
    version: str | None,
    *,
    browser_name: str = EDGE_BROWSER_NAME,
    source: str | None = None,
) -> EdgeVersionHistoryRecord | None:
    """Upsert one locally observed Edge version into persistent diagnostics."""

    normalized_version = _normalize_edge_version(version)
    if not normalized_version:
        return None

    init_db()
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        row = (
            session.query(EdgeVersionHistory)
            .filter_by(browser_name=browser_name, version=normalized_version)
            .one_or_none()
        )
        if row is None:
            row = EdgeVersionHistory(
                browser_name=browser_name,
                version=normalized_version,
                first_seen=now,
                last_seen=now,
                encounter_count=1,
                source=source,
            )
            session.add(row)
        else:
            row.last_seen = now
            row.encounter_count += 1
            row.source = source
        session.commit()
        session.refresh(row)
        return _to_record(row)
    finally:
        session.close()


def record_installed_edge_version(
    edge_path: Path | str | None,
    *,
    source: str,
    version_reader: Callable[[Path | str | None], str | None] = read_edge_version,
) -> EdgeVersionHistoryRecord | None:
    """Read and persist the installed Edge version for diagnostics."""

    version = version_reader(edge_path)
    try:
        return record_edge_version(version, source=source)
    except Exception:
        return None


def get_edge_version_history(
    *,
    limit: int = 10,
) -> tuple[EdgeVersionHistoryRecord, ...]:
    """Return recent Edge version history ordered by last encounter."""

    init_db()
    session = SessionLocal()
    try:
        rows = (
            session.query(EdgeVersionHistory)
            .order_by(EdgeVersionHistory.last_seen.desc())
            .limit(max(1, limit))
            .all()
        )
        return tuple(_to_record(row) for row in rows)
    finally:
        session.close()


def _normalize_edge_version(version: str | None) -> str:
    value = (version or "").strip()
    if not value:
        return ""
    match = re.search(r"\d+(?:\.\d+)+", value)
    return match.group(0) if match else value


def _read_edge_version_from_install_dir(edge_path: Path) -> str | None:
    candidates: list[str] = []
    try:
        for child in edge_path.parent.iterdir():
            if not child.is_dir():
                continue
            version = _normalize_edge_version(child.name)
            if version:
                candidates.append(version)
    except Exception:
        return None
    if not candidates:
        return None
    return sorted(candidates, key=_version_sort_key)[-1]


def _version_sort_key(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return (0,)


def _to_record(row: EdgeVersionHistory) -> EdgeVersionHistoryRecord:
    return EdgeVersionHistoryRecord(
        browser_name=row.browser_name,
        version=row.version,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
        encounter_count=row.encounter_count,
        source=row.source,
    )
