"""App-side diagnostic flag helpers.

Runtime launch, browser/app-mode behavior, and shutdown lifecycle are owned by
LitLaunch. The Streamlit app only keeps a small dev diagnostics flag for source
workflows such as ``streamlit run app.py -- dev``.
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Sequence


DEV_FLAG = "dev"


@dataclass(frozen=True)
class LaunchFlags:
    """Runtime flags passed after Streamlit's app arguments separator."""

    dev: bool = False


def parse_launch_flags(argv: Sequence[str] | None = None) -> LaunchFlags:
    """Parse app-side RoleThread runtime flags from command-line arguments."""

    args = tuple(sys.argv[1:] if argv is None else argv)
    return LaunchFlags(dev=DEV_FLAG in args)


def should_show_dev_diagnostics(flags: LaunchFlags) -> bool:
    """Return whether raw/internal diagnostics should be visible in the UI."""

    return flags.dev
