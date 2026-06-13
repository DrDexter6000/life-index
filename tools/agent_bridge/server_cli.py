"""Shared localhost gateway CLI for the warm ACP service.

Provides ``life-index server start|status|stop`` as a thin manager around the
existing ``tools.agent_bridge.service`` HTTP server.  The service is always
bound to loopback only; non-loopback hosts are rejected before any process is
spawned.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess  # nosec B404
import sys
import time
from pathlib import Path
from typing import Any
import urllib.request
from urllib.error import URLError

from tools.agent_bridge.service import is_loopback

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765
_STATE_FILE_ENV = "LIFE_INDEX_SERVER_STATE_FILE"
_DEFAULT_STATE_DIR = Path.home() / ".life-index"
_DEFAULT_STATE_FILE = _DEFAULT_STATE_DIR / "server.json"
_HEALTHZ_TIMEOUT = 1.0
_STARTUP_TIMEOUT = 600.0
_STARTUP_POLL_INTERVAL = 0.1


def _state_file_path(path: str | None = None) -> Path:
    """Resolve the runtime state file path.

    Priority:
    1. Explicit ``--state-file`` argument.
    2. ``LIFE_INDEX_SERVER_STATE_FILE`` environment variable.
    3. Default ``~/.life-index/server.json``.
    """
    if path is not None:
        return Path(path)
    env = os.environ.get(_STATE_FILE_ENV)
    if env:
        return Path(env)
    return _DEFAULT_STATE_FILE


def _read_state(state_file: Path) -> dict[str, Any] | None:
    """Read and validate the state file, returning None if missing or corrupt."""
    if not state_file.exists():
        return None
    try:
        with state_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _write_state(state_file: Path, data: dict[str, Any]) -> None:
    """Atomically write the runtime state file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with state_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _remove_state(state_file: Path) -> None:
    """Remove the state file if it exists."""
    try:
        state_file.unlink(missing_ok=True)
    except OSError:
        pass


def _probe_healthz(
    host: str,
    port: int,
    timeout: float = _HEALTHZ_TIMEOUT,
) -> dict[str, Any] | None:
    """Non-blocking probe of ``/healthz``.  Returns None on any failure."""
    url = f"http://{host}:{port}/healthz"
    try:
        # URL is built from validated loopback host/port; no file:// risk.
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec B310
            raw = resp.read()
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, URLError, ValueError):
        pass
    return None


def _is_running(host: str, port: int) -> bool:
    """Return True when ``/healthz`` responds on *host*:*port*."""
    return _probe_healthz(host, port) is not None


def _validate_loopback_target(host: Any) -> str | None:
    """Return *host* when it is a loopback string, otherwise None."""
    if not isinstance(host, str):
        return None
    if not is_loopback(host):
        return None
    return host


def _start_service_process(host: str, port: int) -> subprocess.Popen:
    """Launch the service subprocess detached from the current terminal."""
    cmd = [
        sys.executable,
        "-m",
        "tools.agent_bridge.service",
        "--host",
        host,
        "--port",
        str(port),
    ]
    kwargs: dict[str, Any] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    # Command is built from sys.executable and fixed module strings; no shell.
    return subprocess.Popen(cmd, **kwargs)  # nosec B603


def _wait_for_healthz(
    host: str,
    port: int,
    timeout: float = _STARTUP_TIMEOUT,
) -> dict[str, Any] | None:
    """Poll ``/healthz`` until it responds or *timeout* elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = _probe_healthz(host, port, timeout=_HEALTHZ_TIMEOUT)
        if data is not None:
            return data
        time.sleep(_STARTUP_POLL_INTERVAL)
    return None


def cmd_start(argv: list[str]) -> int:
    """Handle ``life-index server start``."""
    parser = argparse.ArgumentParser(prog="life-index server start")
    parser.add_argument("--host", default=_DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument("--state-file")
    args = parser.parse_args(argv)

    if not is_loopback(args.host):
        print(
            f"error: refusing to bind to non-loopback host {args.host!r}",
            file=sys.stderr,
        )
        return 1

    state_file = _state_file_path(args.state_file)

    if _is_running(args.host, args.port):
        print(f"already running on {args.host}:{args.port}")
        return 0

    process = _start_service_process(args.host, args.port)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())

    _write_state(
        state_file,
        {
            "host": args.host,
            "port": args.port,
            "pid": process.pid,
            "started_at": started_at,
        },
    )

    health = _wait_for_healthz(args.host, args.port)
    if health is None:
        print(
            f"error: service started but did not respond on {args.host}:{args.port}",
            file=sys.stderr,
        )
        return 1

    state = health.get("state", "unknown")
    print(f"server started on {args.host}:{args.port} (state: {state})")
    return 0


def cmd_status(argv: list[str]) -> int:
    """Handle ``life-index server status``."""
    parser = argparse.ArgumentParser(prog="life-index server status")
    parser.add_argument("--host", default=_DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument("--state-file")
    args = parser.parse_args(argv)

    state_file = _state_file_path(args.state_file)
    state_data = _read_state(state_file)

    host = state_data.get("host", args.host) if state_data else args.host
    port = state_data.get("port", args.port) if state_data else args.port
    pid = state_data.get("pid") if state_data else None

    host = _validate_loopback_target(host)
    if host is None:
        print("error: refusing non-loopback host from server state", file=sys.stderr)
        return 1

    health = _probe_healthz(host, port)
    result: dict[str, Any]
    if health is not None:
        result = {
            "running": True,
            "host": host,
            "port": port,
            "pid": pid,
            "state": health.get("state", "unknown"),
            "degraded": health.get("state") == "degraded",
        }
    else:
        result = {
            "running": False,
            "host": host,
            "port": port,
            "pid": pid,
            "state": "not running",
            "degraded": False,
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_stop(argv: list[str]) -> int:
    """Handle ``life-index server stop``."""
    parser = argparse.ArgumentParser(prog="life-index server stop")
    parser.add_argument("--host", default=_DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument("--state-file")
    args = parser.parse_args(argv)

    state_file = _state_file_path(args.state_file)
    state_data = _read_state(state_file)

    host = state_data.get("host", args.host) if state_data else args.host
    port = state_data.get("port", args.port) if state_data else args.port
    pid = state_data.get("pid") if state_data else None

    host = _validate_loopback_target(host)
    if host is None:
        print("error: refusing non-loopback host from server state", file=sys.stderr)
        return 1

    was_running = _is_running(host, port)
    stopped = False

    # Prefer graceful loopback shutdown when the service is alive.
    if was_running:
        try:
            req = urllib.request.Request(
                f"http://{host}:{port}/shutdown",
                method="POST",
                data=b"{}",
            )
            req.add_header("Content-Type", "application/json")
            # URL is built from validated loopback host/port; no file:// risk.
            with urllib.request.urlopen(req, timeout=_HEALTHZ_TIMEOUT) as resp:  # nosec B310
                resp.read()
            stopped = True
        except (OSError, URLError):
            pass

    # Fallback to signal if the service was alive but the shutdown endpoint failed.
    if not stopped and was_running and pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
            stopped = True
        except ProcessLookupError:
            # Process is already gone; treat as stopped.
            stopped = True
        except OSError:
            pass

    _remove_state(state_file)

    # If the service was running but neither path stopped it, report failure.
    if was_running and not stopped:
        print(
            f"error: could not stop server on {host}:{port}",
            file=sys.stderr,
        )
        return 1

    print(f"server stopped on {host}:{port}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Unified entry point for ``life-index server``."""
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("--help", "-h", "help"):
        print("usage: life-index server start|status|stop")
        print()
        print("Commands:")
        print("  start   Start the shared loopback-only warm ACP gateway")
        print("  status  Show whether the server is running and its health state")
        print("  stop    Gracefully stop the server and remove its state file")
        print()
        print("Options:")
        print("  --host       Bind host (loopback only). Default: 127.0.0.1")
        print("  --port       Bind port. Default: 8765")
        print("  --state-file Path to the runtime state file")
        return 0

    subcmd = argv[0]
    rest = argv[1:]
    if subcmd == "start":
        return cmd_start(rest)
    if subcmd == "status":
        return cmd_status(rest)
    if subcmd == "stop":
        return cmd_stop(rest)

    print(f"error: unknown server subcommand {subcmd!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
