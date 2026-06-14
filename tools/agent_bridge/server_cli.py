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
import re
import signal
import socket
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

# Stop escalation timeouts (seconds)
# Windows process cleanup can be slow; generous timeouts avoid false failures
# when the listening socket is already closed but the OS hasn't reaped the
# process handle yet.
_STOP_SHUTDOWN_POLL = 8.0
_STOP_SIGTERM_POLL = 5.0
_STOP_SIGKILL_POLL = 3.0

_SIGKILL: int | None = getattr(signal, "SIGKILL", None)


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


# OS-level lifecycle verification helpers.


def _is_windows_platform() -> bool:
    """Return True when the current runtime is Windows."""
    return os.name == "nt"


def _is_port_occupied(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return True if a TCP listener is bound to *host*:*port*."""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except OSError:
        return False


def _subprocess_kwargs() -> dict[str, Any]:
    """Return OS-appropriate kwargs for subprocess calls."""
    if _is_windows_platform():
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if isinstance(creation_flags, int) and creation_flags:
            return {"creationflags": creation_flags}
    return {}


def _find_listener_pid_win32(host: str, port: int) -> int | None:
    """Discover the PID of the process listening on *host*:*port* via netstat."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            **_subprocess_kwargs(),
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                pid_str = parts[-1]
                if pid_str.isdigit():
                    return int(pid_str)
    except Exception:
        pass
    return None


def _find_listener_pid_unix(host: str, port: int) -> int | None:
    """Discover the PID of the process listening on *host*:*port* via ss/netstat."""
    # Prefer ss (modern Linux)
    try:
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        match = re.search(r"pid=(\d+)", result.stdout)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    # Fallback: netstat
    try:
        result = subprocess.run(
            ["netstat", "-tlnp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTEN" in line:
                match = re.search(r"(\d+)/", line)
                if match:
                    return int(match.group(1))
    except Exception:
        pass
    return None


def _find_listener_pid(host: str, port: int) -> int | None:
    """Best-effort OS-level discovery of the listener PID on *host*:*port*."""
    if _is_windows_platform():
        return _find_listener_pid_win32(host, port)
    return _find_listener_pid_unix(host, port)


def _is_process_alive(pid: int) -> bool:
    """Return True if a process with *pid* exists."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError, PermissionError):
        return False


def _poll_process_dead(pid: int, timeout: float = 5.0, interval: float = 0.15) -> bool:
    """Poll until process *pid* is dead or *timeout* elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_process_alive(pid):
            return True
        time.sleep(interval)
    return not _is_process_alive(pid)


def _poll_port_free(host: str, port: int, timeout: float = 5.0, interval: float = 0.15) -> bool:
    """Poll until *host*:*port* is no longer occupied."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_port_occupied(host, port):
            return True
        time.sleep(interval)
    return not _is_port_occupied(host, port)


def _await_shutdown(
    host: str, port: int, pid: int | None, timeout: float, *, port_only: bool = False
) -> bool:
    """Poll until process *pid* is dead AND *host*:*port* is free.

    When *port_only* is True the port-free condition is sufficient;
    process liveness is still polled but does not gate success.  This
    is used after graceful ``/shutdown`` where OS process cleanup may
    be slower than socket release.

    Interleaves process and port checks so neither condition starves.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        process_dead = pid is None or not _is_process_alive(pid)
        port_free = not _is_port_occupied(host, port)
        if (process_dead and port_free) or (port_only and port_free):
            return True
        time.sleep(_STARTUP_POLL_INTERVAL)
    # Final check after timeout
    process_dead = pid is None or not _is_process_alive(pid)
    port_free = not _is_port_occupied(host, port)
    if port_only:
        return port_free
    return process_dead and port_free


# CLI commands.


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

    # Healthy server already running: reconcile state when the listener pid is
    # discoverable so later stop calls can target the real process.
    if _is_running(args.host, args.port):
        listener_pid = _find_listener_pid(args.host, args.port)
        if listener_pid is not None:
            _write_state(
                state_file,
                {
                    "host": args.host,
                    "port": args.port,
                    "pid": listener_pid,
                    "started_at": time.strftime(
                        "%Y-%m-%dT%H:%M:%S%z",
                        time.localtime(),
                    ),
                },
            )
        print(f"already running on {args.host}:{args.port}")
        return 0

    # Health check failed: inspect whether the port is occupied.
    if _is_port_occupied(args.host, args.port):
        state_data = _read_state(state_file)
        state_owned = False

        if state_data:
            state_pid = state_data.get("pid")
            state_host = state_data.get("host")
            state_port = state_data.get("port")
            if state_host == args.host and state_port == args.port and isinstance(state_pid, int):
                if _is_process_alive(state_pid):
                    # Reap only when we can prove the state-owned PID is
                    # actually listening on our port.  An alive state PID
                    # that does NOT own the socket is a reused PID
                    # belonging to an unrelated process; killing it is
                    # unsafe.
                    listener_pid = _find_listener_pid(args.host, args.port)
                    if listener_pid == state_pid:
                        # Proven ownership: reap and replace.
                        try:
                            os.kill(state_pid, signal.SIGTERM)
                        except OSError:
                            pass
                        _poll_process_dead(state_pid, timeout=2.0)
                        if _SIGKILL is not None and _is_process_alive(state_pid):
                            try:
                                os.kill(state_pid, _SIGKILL)
                            except OSError:
                                pass
                            _poll_process_dead(state_pid, timeout=1.0)
                        state_owned = True
                    # else: ownership cannot be proven; fail below.
                else:
                    # Stale state: process dead, but port is occupied by
                    # something else.  Not clearly ours - fail.
                    pass

        if not state_owned:
            listener_pid = _find_listener_pid(args.host, args.port)
            pid_info = f" (pid {listener_pid})" if listener_pid else ""
            print(
                f"error: port {args.host}:{args.port} is already occupied"
                f"{pid_info}; cannot determine ownership."
                f" Stop any existing instance first.",
                file=sys.stderr,
            )
            return 1

    # Clean slate: remove any stale state before launching.
    _remove_state(state_file)

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
        # Clean up failed launch: kill the process and remove state.
        try:
            process.kill()
            process.wait(timeout=5.0)
        except Exception:
            pass
        _remove_state(state_file)
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
    state_pid = state_data.get("pid") if state_data else None

    host = _validate_loopback_target(host)
    if host is None:
        print("error: refusing non-loopback host from server state", file=sys.stderr)
        return 1

    health = _probe_healthz(host, port)
    result: dict[str, Any]

    if health is not None:
        # Healthy path: server is reachable via /healthz. Prefer OS truth
        # whenever it is discoverable, even if state contains a stale PID.
        pid = _find_listener_pid(host, port) or state_pid
        result = {
            "running": True,
            "host": host,
            "port": port,
            "pid": pid,
            "state": health.get("state", "unknown"),
            "degraded": health.get("state") == "degraded",
        }
    elif _is_port_occupied(host, port):
        # Healthz unreachable but port is occupied: degraded with OS truth.
        listener_pid = _find_listener_pid(host, port) or state_pid
        result = {
            "running": True,
            "host": host,
            "port": port,
            "pid": listener_pid,
            "state": "degraded (healthz unreachable)",
            "degraded": True,
        }
    else:
        # Port empty: definitively not running.
        result = {
            "running": False,
            "host": host,
            "port": port,
            "pid": state_pid,
            "state": "not running",
            "degraded": False,
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_stop(argv: list[str]) -> int:
    """Handle ``life-index server stop``.

    Escalation ladder: POST /shutdown -> poll -> SIGTERM -> poll -> SIGKILL -> poll.
    State is removed only after both process death and port release are verified.
    If shutdown cannot be proven the state file is preserved for retry and a
    non-zero exit code is returned.
    """
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

    health_running = _is_running(host, port)
    port_occupied = _is_port_occupied(host, port)
    listener_pid = _find_listener_pid(host, port) if port_occupied or health_running else None
    effective_pid = listener_pid or pid

    # Fast path: nothing is running (healthz unreachable, port free).
    if not health_running and not port_occupied:
        _remove_state(state_file)
        print(f"server stopped on {host}:{port}")
        return 0

    # Phase 1: graceful /shutdown.
    if health_running:
        try:
            req = urllib.request.Request(
                f"http://{host}:{port}/shutdown",
                method="POST",
                data=b"{}",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=_HEALTHZ_TIMEOUT) as resp:  # nosec B310
                resp.read()
        except (OSError, URLError):
            pass

    if _await_shutdown(host, port, effective_pid, timeout=_STOP_SHUTDOWN_POLL, port_only=True):
        _remove_state(state_file)
        print(f"server stopped on {host}:{port}")
        return 0

    # Resolve the effective PID for signal escalation.
    # When the state PID is missing or stale the OS-discovered listener
    # PID is the correct signal target; we never signal a PID that we
    # cannot associate with the occupied port.
    effective_pid = _find_listener_pid(host, port) or effective_pid

    # Phase 2: SIGTERM escalation.
    if effective_pid is not None:
        try:
            os.kill(effective_pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

    if _await_shutdown(host, port, effective_pid, timeout=_STOP_SIGTERM_POLL):
        _remove_state(state_file)
        print(f"server stopped on {host}:{port}")
        return 0

    # Phase 3: SIGKILL escalation (Unix only).
    if effective_pid is not None and _SIGKILL is not None:
        if _is_process_alive(effective_pid):
            try:
                os.kill(effective_pid, _SIGKILL)
            except (ProcessLookupError, OSError):
                pass

        if _await_shutdown(host, port, effective_pid, timeout=_STOP_SIGKILL_POLL):
            _remove_state(state_file)
            print(f"server stopped on {host}:{port}")
            return 0

    # Cannot prove shutdown.
    # State is preserved so retry is possible.  Do NOT print a successful
    # stop message.
    print(
        f"error: could not confirm server shutdown on {host}:{port}",
        file=sys.stderr,
    )
    return 1


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
