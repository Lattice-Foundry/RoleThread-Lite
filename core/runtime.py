"""Python runtime compatibility checks for RoleThread Lite."""
from __future__ import annotations

from dataclasses import dataclass
import sys

from core.version import (
    MAX_TESTED_PYTHON,
    MIN_SUPPORTED_PYTHON,
    OFFICIAL_PYTHON_VERSION,
)


RUNTIME_STATUS_SUPPORTED = "Supported"
RUNTIME_STATUS_UNTESTED_NEWER = "Untested newer version"
RUNTIME_STATUS_UNSUPPORTED_OLDER = "Unsupported older version"


@dataclass(frozen=True)
class PythonRuntimeStatus:
    """Compatibility details for the active Python runtime."""

    current_version: str
    current_version_info: tuple[int, int, int]
    official_version: str
    minimum_supported: tuple[int, int, int]
    maximum_tested: tuple[int, int, int]
    is_officially_supported: bool
    is_below_minimum: bool
    is_newer_than_tested: bool
    status_label: str
    message: str

    @property
    def is_allowed(self) -> bool:
        return not self.is_below_minimum


def get_python_runtime_status(
    version_info: tuple[int, int, int] | None = None,
) -> PythonRuntimeStatus:
    """Return RoleThread's support status for a Python runtime version."""

    current = version_info or tuple(sys.version_info[:3])
    current_version = ".".join(str(part) for part in current)
    is_official = current == MIN_SUPPORTED_PYTHON
    is_below_minimum = current < MIN_SUPPORTED_PYTHON
    is_newer_than_tested = current > MAX_TESTED_PYTHON

    if is_below_minimum:
        status_label = RUNTIME_STATUS_UNSUPPORTED_OLDER
        message = (
            "RoleThread Lite officially supports Python "
            f"{OFFICIAL_PYTHON_VERSION}. Current runtime is Python "
            f"{current_version}. Please install Python {OFFICIAL_PYTHON_VERSION} "
            "and recreate your virtual environment."
        )
    elif is_newer_than_tested:
        status_label = RUNTIME_STATUS_UNTESTED_NEWER
        message = (
            "RoleThread Lite officially supports Python "
            f"{OFFICIAL_PYTHON_VERSION}. Current runtime is Python "
            f"{current_version}, which is newer than the tested V1 runtime. "
            "The app may run, but this runtime is not officially supported yet."
        )
    else:
        status_label = RUNTIME_STATUS_SUPPORTED
        message = (
            "RoleThread Lite is running on the official supported Python "
            f"runtime: {OFFICIAL_PYTHON_VERSION}."
        )

    return PythonRuntimeStatus(
        current_version=current_version,
        current_version_info=current,
        official_version=OFFICIAL_PYTHON_VERSION,
        minimum_supported=MIN_SUPPORTED_PYTHON,
        maximum_tested=MAX_TESTED_PYTHON,
        is_officially_supported=is_official,
        is_below_minimum=is_below_minimum,
        is_newer_than_tested=is_newer_than_tested,
        status_label=status_label,
        message=message,
    )


def validate_python_runtime(
    version_info: tuple[int, int, int] | None = None,
) -> PythonRuntimeStatus:
    """Return runtime status, raising a clear error for unsupported runtimes."""

    status = get_python_runtime_status(version_info)
    if status.is_below_minimum:
        raise RuntimeError(status.message)
    return status

