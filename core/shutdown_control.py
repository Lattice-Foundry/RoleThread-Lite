"""Local launcher shutdown control for bundled RoleThread sessions."""

from __future__ import annotations

import atexit
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import sys
import threading
from typing import Callable, Mapping


SHUTDOWN_PORT_ENV = "ROLETHREAD_LAUNCHER_SHUTDOWN_PORT"
SHUTDOWN_TOKEN_ENV = "ROLETHREAD_LAUNCHER_SHUTDOWN_TOKEN"
SHUTDOWN_HEADER = "X-RoleThread-Launcher-Token"

_server_started = False


@dataclass(frozen=True)
class LauncherShutdownControl:
    """Local shutdown control information provided by the Windows launcher."""

    port: int
    token: str


def resolve_launcher_shutdown_control(
    env: Mapping[str, str] | None = None,
) -> LauncherShutdownControl | None:
    """Return launcher shutdown control metadata when explicitly configured."""

    env_map = os.environ if env is None else env
    raw_port = env_map.get(SHUTDOWN_PORT_ENV)
    token = env_map.get(SHUTDOWN_TOKEN_ENV)
    if not raw_port or not token:
        return None
    try:
        port = int(raw_port)
    except ValueError:
        return None
    if port <= 0 or port > 65535:
        return None
    return LauncherShutdownControl(port=port, token=token)


def run_graceful_process_exit() -> None:
    """Run registered exit hooks, then end the process without a second cleanup pass."""

    try:
        run_exitfuncs = getattr(atexit, "_run_exitfuncs", None)
        if callable(run_exitfuncs):
            run_exitfuncs()
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            os._exit(0)


def start_launcher_shutdown_server(
    control: LauncherShutdownControl | None = None,
    *,
    shutdown_fn: Callable[[], None] = run_graceful_process_exit,
) -> bool:
    """Start a local-only shutdown endpoint when launched by the Windows launcher."""

    global _server_started

    resolved = control or resolve_launcher_shutdown_control()
    if resolved is None or _server_started:
        return False

    class ShutdownRequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            if self.path != "/shutdown":
                self.send_error(404)
                return
            if self.headers.get(SHUTDOWN_HEADER) != resolved.token:
                self.send_error(403)
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"shutdown accepted")
            threading.Thread(target=shutdown_fn, daemon=True).start()

        def log_message(self, format: str, *args: object) -> None:
            return

    try:
        server = ThreadingHTTPServer(("127.0.0.1", resolved.port), ShutdownRequestHandler)
    except OSError:
        return False

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _server_started = True
    return True

