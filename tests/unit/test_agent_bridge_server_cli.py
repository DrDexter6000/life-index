"""Unit tests for the ``life-index server`` CLI lifecycle hardening (V6-CB).

Tests use dependency injection to avoid spawning real subprocesses or binding
real network sockets.  Lifecycle verification primitives (port occupancy,
process liveness, polling) are mocked to isolate command-level logic.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from tools.agent_bridge.server_cli import (
    _STATE_FILE_ENV,
    _is_port_occupied,
    _is_running,
    _probe_healthz,
    _read_state,
    _state_file_path,
    _start_service_process,
    _wait_for_healthz,
    cmd_start,
    cmd_status,
    cmd_stop,
    main,
)


class _FakePopen:
    """Minimal subprocess.Popen stand-in with kill/wait support."""

    def __init__(self, pid: int = 12345) -> None:
        self.pid = pid
        self._killed = False
        self._waited = False

    def kill(self) -> None:
        self._killed = True

    def wait(self, timeout: float | None = None) -> int:
        self._waited = True
        return 0


def _make_state_file(tmp_path: Path) -> Path:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "server.json"


# -- State file path resolution -----------------------------------------


def test_state_file_path_defaults_to_home_dot_life_index():
    with patch.dict(os.environ, {}, clear=True):
        path = _state_file_path()
    assert path == Path.home() / ".life-index" / "server.json"


def test_state_file_path_respects_env_variable(tmp_path: Path):
    env_path = tmp_path / "custom.json"
    with patch.dict(os.environ, {_STATE_FILE_ENV: str(env_path)}):
        assert _state_file_path() == env_path


def test_state_file_path_prefers_argument(tmp_path: Path):
    env_path = tmp_path / "env.json"
    arg_path = tmp_path / "arg.json"
    with patch.dict(os.environ, {_STATE_FILE_ENV: str(env_path)}):
        assert _state_file_path(str(arg_path)) == arg_path


def test_read_state_missing_returns_none(tmp_path: Path):
    assert _read_state(tmp_path / "missing.json") is None


def test_read_state_corrupt_returns_none(tmp_path: Path):
    state_file = tmp_path / "corrupt.json"
    state_file.write_text("not json", encoding="utf-8")
    assert _read_state(state_file) is None


# -- Low-level probes (live network - expected to fail) ------------------


def test_probe_healthz_returns_none_when_nothing_listens():
    # Pick a port that is extremely unlikely to be listening.
    assert _probe_healthz("127.0.0.1", 65432) is None


def test_is_running_false_when_probe_fails():
    assert _is_running("127.0.0.1", 65432) is False


def test_wait_for_healthz_returns_none_on_timeout():
    assert _wait_for_healthz("127.0.0.1", 65432, timeout=0.05) is None


def test_is_port_occupied_false_when_nothing_listens():
    assert _is_port_occupied("127.0.0.1", 65432) is False


# -- start: non-loopback rejection --------------------------------------


def test_start_rejects_non_loopback_host(capsys):
    code = cmd_start(["--host", "0.0.0.0", "--port", "8765"])
    assert code == 1
    captured = capsys.readouterr()
    assert "non-loopback" in captured.err.lower()


def test_start_rejects_public_host(capsys):
    code = cmd_start(["--host", "192.168.1.1", "--port", "8765"])
    assert code == 1
    captured = capsys.readouterr()
    assert "non-loopback" in captured.err.lower()


# -- start: healthy server already running ------------------------------


def test_start_detects_existing_service_reconciles_state_and_exits_zero(
    tmp_path: Path,
    capsys,
):
    state_file = _make_state_file(tmp_path)

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm", "pid": 12345}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli._find_listener_pid",
            return_value=12345,
        ):
            code = cmd_start(["--state-file", str(state_file)])

    assert code == 0
    captured = capsys.readouterr()
    assert "already running" in captured.out
    assert "127.0.0.1:8765" in captured.out
    data = _read_state(state_file)
    assert data is not None
    assert data["pid"] == 12345


# -- start: normal spawn with healthz response --------------------------


def test_start_spawns_service_writes_state_and_reports(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)

    probe_count = [0]

    def _fake_probe(host: str, port: int, timeout: float = 1.0):
        probe_count[0] += 1
        if probe_count[0] >= 2:
            return {"status": "ok", "state": "degraded"}
        return None

    fake_process = _FakePopen(pid=12345)

    with patch("tools.agent_bridge.server_cli._start_service_process", return_value=fake_process):
        with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
            code = cmd_start(["--state-file", str(state_file)])

    assert code == 0
    captured = capsys.readouterr()
    assert "server started" in captured.out
    assert "127.0.0.1:8765" in captured.out
    assert "degraded" in captured.out

    data = _read_state(state_file)
    assert data is not None
    assert data["host"] == "127.0.0.1"
    assert data["port"] == 8765
    assert data["pid"] == 12345
    assert "started_at" in data


# -- start: cleanup on startup failure ----------------------------------


def test_start_cleans_up_process_and_state_on_failure(tmp_path: Path, capsys):
    """When the spawned service never responds, start must kill the process
    and remove the state file."""
    state_file = _make_state_file(tmp_path)
    fake_process = _FakePopen(pid=12345)

    with patch("tools.agent_bridge.server_cli._start_service_process", return_value=fake_process):
        with patch("tools.agent_bridge.server_cli._is_running", return_value=False):
            with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=False):
                with patch("tools.agent_bridge.server_cli._wait_for_healthz", return_value=None):
                    code = cmd_start(["--state-file", str(state_file)])

    assert code == 1
    captured = capsys.readouterr()
    assert "did not respond" in captured.err.lower()
    # Process must be killed.
    assert fake_process._killed
    assert fake_process._waited
    # State must be cleaned up.
    assert not state_file.exists()


# -- start: port occupied by foreign process ----------------------------


def test_start_fails_when_port_occupied_by_foreign_process(tmp_path: Path, capsys):
    """When healthz fails but the port is occupied by an unknown process,
    start must fail with a clear port-occupied error."""
    state_file = _make_state_file(tmp_path)
    # No state file - unknown occupant.

    with patch("tools.agent_bridge.server_cli._is_running", return_value=False):
        with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=True):
            with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=99999):
                code = cmd_start(["--state-file", str(state_file)])

    assert code == 1
    captured = capsys.readouterr()
    assert "already occupied" in captured.err.lower()
    assert "99999" in captured.err


# -- start: reap state-owned zombie -------------------------------------


def test_start_reaps_state_owned_zombie_and_replaces(tmp_path: Path, capsys):
    """When the port is occupied by a state-owned zombie (healthz dead but
    pid alive), start must reap it, clean state, and launch a new server."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 99999}),
        encoding="utf-8",
    )

    zombie_killed = [False]
    fake_process = _FakePopen(pid=12345)

    def _fake_probe(host: str, port: int, timeout: float = 1.0):
        if zombie_killed[0]:
            return {"status": "ok", "state": "warm"}
        return None

    def _fake_kill(pid: int, sig: int) -> None:
        if pid == 99999 and sig == signal.SIGTERM:
            zombie_killed[0] = True

    with patch("tools.agent_bridge.server_cli._is_running", return_value=False):
        with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=True):
            with patch("tools.agent_bridge.server_cli._is_process_alive", return_value=True):
                with patch(
                    "tools.agent_bridge.server_cli._find_listener_pid",
                    return_value=99999,
                ):
                    with patch(
                        "tools.agent_bridge.server_cli._poll_process_dead", return_value=True
                    ):
                        with patch("os.kill", side_effect=_fake_kill):
                            with patch(
                                "tools.agent_bridge.server_cli._start_service_process",
                                return_value=fake_process,
                            ):
                                with patch(
                                    "tools.agent_bridge.server_cli._probe_healthz",
                                    side_effect=_fake_probe,
                                ):
                                    code = cmd_start(["--state-file", str(state_file)])

    assert code == 0
    assert zombie_killed[0]
    captured = capsys.readouterr()
    assert "server started" in captured.out
    assert "127.0.0.1:8765" in captured.out
    # State must record the *new* pid.
    data = _read_state(state_file)
    assert data is not None
    assert data["pid"] == 12345


# -- start: ownership verification before zombie reaping --------------


def test_start_fails_when_state_pid_alive_but_not_listener(tmp_path: Path, capsys):
    """When the state pid is alive but does NOT own the listening socket,
    start must fail with an occupied/unowned error - not kill the pid."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 99999}),
        encoding="utf-8",
    )

    with patch("tools.agent_bridge.server_cli._is_running", return_value=False):
        with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=True):
            with patch("tools.agent_bridge.server_cli._is_process_alive", return_value=True):
                with patch(
                    "tools.agent_bridge.server_cli._find_listener_pid",
                    return_value=88888,
                ):
                    with patch("os.kill") as mock_kill:
                        code = cmd_start(["--state-file", str(state_file)])

    assert code == 1
    mock_kill.assert_not_called()
    captured = capsys.readouterr()
    assert "already occupied" in captured.err.lower()
    assert "88888" in captured.err


def test_start_reaps_when_state_pid_equals_listener_pid(tmp_path: Path, capsys):
    """When the state pid is alive AND equals the OS listener pid, start
    must reap and replace - ownership is proven."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 99999}),
        encoding="utf-8",
    )

    zombie_killed = [False]
    fake_process = _FakePopen(pid=12345)

    def _fake_probe(host: str, port: int, timeout: float = 1.0):
        if zombie_killed[0]:
            return {"status": "ok", "state": "warm"}
        return None

    def _fake_kill(pid: int, sig: int) -> None:
        if pid == 99999 and sig == signal.SIGTERM:
            zombie_killed[0] = True

    with patch("tools.agent_bridge.server_cli._is_running", return_value=False):
        with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=True):
            with patch("tools.agent_bridge.server_cli._is_process_alive", return_value=True):
                with patch(
                    "tools.agent_bridge.server_cli._find_listener_pid",
                    return_value=99999,
                ):
                    with patch(
                        "tools.agent_bridge.server_cli._poll_process_dead", return_value=True
                    ):
                        with patch("os.kill", side_effect=_fake_kill):
                            with patch(
                                "tools.agent_bridge.server_cli._start_service_process",
                                return_value=fake_process,
                            ):
                                with patch(
                                    "tools.agent_bridge.server_cli._probe_healthz",
                                    side_effect=_fake_probe,
                                ):
                                    code = cmd_start(["--state-file", str(state_file)])

    assert code == 0
    assert zombie_killed[0]
    data = _read_state(state_file)
    assert data is not None
    assert data["pid"] == 12345


# -- status: healthy server ---------------------------------------------


def test_status_reports_running_with_warm_state(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm", "pid": 12345}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=None):
            code = cmd_status(["--state-file", str(state_file)])

    assert code == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["running"] is True
    assert result["host"] == "127.0.0.1"
    assert result["port"] == 8765
    assert result["pid"] == 12345
    assert result["state"] == "warm"
    assert result["degraded"] is False


def test_status_reports_degraded_state(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "degraded", "last_warm_error": "boom"}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=None):
            code = cmd_status(["--state-file", str(state_file)])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is True
    assert result["state"] == "degraded"
    assert result["degraded"] is True


# -- status: healthz success with no state pid -------------------------


def test_status_reports_os_pid_when_healthz_ok_but_no_state_pid(tmp_path: Path, capsys):
    """When /healthz responds but the state file is missing (no pid),
    status must discover and report the OS listener pid."""
    # No state file - simulate missing state.
    non_existent = tmp_path / "no-state.json"

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli._find_listener_pid",
            return_value=54321,
        ):
            code = cmd_status(
                ["--state-file", str(non_existent)],
            )

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is True
    assert result["pid"] == 54321


def test_status_prefers_os_pid_over_stale_state_when_healthz_ok(tmp_path: Path, capsys):
    """When healthz responds and state has a stale pid, status reports the listener pid."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 11111}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli._find_listener_pid",
            return_value=22222,
        ):
            code = cmd_status(["--state-file", str(state_file)])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is True
    assert result["pid"] == 22222


# -- status: healthz fails, port occupied -> degraded with OS truth ------


def test_status_reports_degraded_when_healthz_fails_but_port_occupied(tmp_path: Path, capsys):
    """When /healthz is unreachable but the port is occupied by a live
    listener, status must report running=True, degraded=True with the
    real listener pid."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    with patch("tools.agent_bridge.server_cli._probe_healthz", return_value=None):
        with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=True):
            with patch(
                "tools.agent_bridge.server_cli._find_listener_pid",
                return_value=12345,
            ):
                code = cmd_status(["--state-file", str(state_file)])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is True
    assert result["degraded"] is True
    assert "healthz unreachable" in result["state"]
    assert result["pid"] == 12345


def test_status_reports_degraded_discovers_real_pid(tmp_path: Path, capsys):
    """When /healthz fails and port is occupied, status discovers the real
    listener pid even when the state file pid is stale."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 11111}),
        encoding="utf-8",
    )

    with patch("tools.agent_bridge.server_cli._probe_healthz", return_value=None):
        with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=True):
            with patch(
                "tools.agent_bridge.server_cli._find_listener_pid",
                return_value=22222,
            ):
                code = cmd_status(["--state-file", str(state_file)])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is True
    assert result["degraded"] is True
    # Real listener pid wins over stale state pid.
    assert result["pid"] == 22222


# -- status: healthz fails, port empty -> not running --------------------


def test_status_reports_not_running_when_healthz_fails_and_port_empty(tmp_path: Path, capsys):
    """When /healthz is unreachable AND the port is empty, status must
    report definitively not running."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    with patch("tools.agent_bridge.server_cli._probe_healthz", return_value=None):
        with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=False):
            code = cmd_status(["--state-file", str(state_file)])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is False
    assert result["state"] == "not running"
    assert result["degraded"] is False


# -- status: non-loopback rejection -------------------------------------


def test_status_rejects_non_loopback_host_from_state(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "0.0.0.0", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    code = cmd_status(["--state-file", str(state_file)])

    assert code == 1
    captured = capsys.readouterr()
    assert "non-loopback" in captured.err.lower()


def test_status_uses_args_when_state_file_missing(capsys):
    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=None):
            code = cmd_status(["--host", "127.0.0.1", "--port", "9999"])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is True
    assert result["port"] == 9999
    assert result["pid"] is None


# -- stop: graceful /shutdown with poll verification --------------------


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self) -> bytes:
        return self._body


def test_stop_gracefully_shuts_down_via_endpoint_polls_and_removes_state(tmp_path: Path, capsys):
    """stop sends /shutdown, polls for death+port release, then removes state."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    def _fake_probe(host: str, port: int, timeout: float = 1.0):
        return {"status": "ok", "state": "warm"}

    def _fake_urlopen(req, timeout=None):
        return _FakeResponse(b'{"status": "shutting down"}')

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli.urllib.request.urlopen",
            side_effect=_fake_urlopen,
        ):
            with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=12345):
                with patch("tools.agent_bridge.server_cli._await_shutdown", return_value=True):
                    code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    assert not state_file.exists()
    captured = capsys.readouterr()
    assert "server stopped" in captured.out


# -- stop: escalation to SIGTERM ----------------------------------------


def test_stop_escalates_to_sigterm_when_shutdown_fails(tmp_path: Path, capsys):
    """When /shutdown does not lead to verified death, stop escalates to SIGTERM."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    killed = [False]

    def _fake_kill(pid: int, sig: int) -> None:
        assert pid == 12345
        assert sig == signal.SIGTERM
        killed[0] = True

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=None):
                with patch(
                    "tools.agent_bridge.server_cli._await_shutdown",
                    side_effect=[False, True],
                ) as mock_await:
                    with patch("os.kill", side_effect=_fake_kill):
                        code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    assert killed[0]
    assert not state_file.exists()
    # Verify _await_shutdown was called twice: once after /shutdown, once after SIGTERM.
    assert mock_await.call_count == 2


# -- stop: escalation to SIGKILL (Unix) ----------------------------------


def test_stop_escalates_to_sigkill_when_sigterm_fails(tmp_path: Path, capsys):
    """When SIGTERM does not kill the process, stop escalates to SIGKILL."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    kill_calls = []

    def _fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=None):
                with patch(
                    "tools.agent_bridge.server_cli._await_shutdown",
                    side_effect=[False, False, True],
                ):
                    with patch(
                        "tools.agent_bridge.server_cli._SIGKILL",
                        signal.SIGTERM,
                    ):
                        with patch(
                            "tools.agent_bridge.server_cli._is_process_alive",
                            return_value=True,
                        ):
                            with patch("os.kill", side_effect=_fake_kill):
                                code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    # SIGTERM then SIGKILL (patched to SIGTERM on platforms without SIGKILL)
    assert len(kill_calls) >= 2
    assert kill_calls[0] == (12345, signal.SIGTERM)
    assert not state_file.exists()


def test_stop_uses_listener_pid_for_graceful_shutdown_wait(tmp_path: Path, capsys):
    """If state pid is stale, the first shutdown wait uses the real listener pid."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 11111}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    def _fake_urlopen(req, timeout=None):
        return _FakeResponse(b'{"status": "shutting down"}')

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli.urllib.request.urlopen",
            side_effect=_fake_urlopen,
        ):
            with patch(
                "tools.agent_bridge.server_cli._find_listener_pid",
                return_value=22222,
            ):
                with patch(
                    "tools.agent_bridge.server_cli._await_shutdown",
                    return_value=True,
                ) as mock_await:
                    with patch("os.kill") as mock_kill:
                        code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    mock_kill.assert_not_called()
    assert mock_await.call_args.args[2] == 22222
    assert not state_file.exists()


# -- stop: escalation with discovered PID when state missing ------------


def test_stop_escalates_with_discovered_pid_when_state_missing(tmp_path: Path, capsys):
    """When state has no pid but a real listener PID is discoverable,
    /shutdown fails, escalation must target the discovered listener PID."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    kill_calls = []

    def _fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with patch(
                "tools.agent_bridge.server_cli._await_shutdown",
                side_effect=[False, True],
            ):
                with patch(
                    "tools.agent_bridge.server_cli._find_listener_pid",
                    return_value=54321,
                ):
                    with patch("os.kill", side_effect=_fake_kill):
                        code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    assert len(kill_calls) == 1
    assert kill_calls[0] == (54321, signal.SIGTERM)
    assert not state_file.exists()
    captured = capsys.readouterr()
    assert "server stopped" in captured.out


def test_stop_targets_listener_pid_not_stale_state_pid(tmp_path: Path, capsys):
    """When state pid is stale (different from real listener pid), stop
    must signal the OS-discovered listener pid, not the stale state pid."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 11111}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    kill_calls = []

    def _fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with patch(
                "tools.agent_bridge.server_cli._await_shutdown",
                side_effect=[False, True],
            ):
                with patch(
                    "tools.agent_bridge.server_cli._find_listener_pid",
                    return_value=22222,
                ):
                    with patch("os.kill", side_effect=_fake_kill):
                        code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    assert len(kill_calls) == 1
    # Must signal 22222 (real listener), NOT 11111 (stale state).
    assert kill_calls[0][0] == 22222
    assert kill_calls[0][1] == signal.SIGTERM
    assert not state_file.exists()


# -- stop: fast path when nothing is running ----------------------------


def test_stop_is_safe_when_no_service_running(tmp_path: Path, capsys):
    """When neither healthz responds nor the port is occupied, stop is a no-op."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    with patch("tools.agent_bridge.server_cli._probe_healthz", return_value=None):
        with patch("tools.agent_bridge.server_cli._is_port_occupied", return_value=False):
            with patch("os.kill") as mock_kill:
                code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    mock_kill.assert_not_called()
    assert not state_file.exists()
    captured = capsys.readouterr()
    assert "server stopped" in captured.out


# -- stop: non-loopback rejection ---------------------------------------


def test_stop_rejects_non_loopback_host_from_state(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "0.0.0.0", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    with patch("os.kill") as mock_kill:
        code = cmd_stop(["--state-file", str(state_file)])

    assert code == 1
    mock_kill.assert_not_called()
    captured = capsys.readouterr()
    assert "non-loopback" in captured.err.lower()


# -- stop: honest failure when shutdown cannot be proven ----------------


def test_stop_fails_honestly_and_preserves_state_when_unprovable(tmp_path: Path, capsys):
    """When all escalation phases fail, stop returns non-zero, preserves state,
    and does NOT print 'server stopped'."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=None):
                with patch("tools.agent_bridge.server_cli._await_shutdown", return_value=False):
                    with patch("os.kill"):
                        with patch("tools.agent_bridge.server_cli._SIGKILL", None):
                            code = cmd_stop(["--state-file", str(state_file)])

    assert code == 1
    captured = capsys.readouterr()
    assert "could not confirm" in captured.err.lower()
    assert "server stopped" not in captured.out
    assert "server stopped" not in captured.err.lower()
    # State file must be preserved for retry.
    assert state_file.exists()
    data = _read_state(state_file)
    assert data is not None
    assert data["pid"] == 12345


# -- stop: missing pid without escalation path --------------------------


def test_stop_fails_with_missing_pid_when_port_occupied(tmp_path: Path, capsys):
    """When the state has no pid and the port stays occupied after /shutdown
    fails, stop returns non-zero because it cannot escalate to signals."""
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            with patch("tools.agent_bridge.server_cli._find_listener_pid", return_value=None):
                with patch("tools.agent_bridge.server_cli._await_shutdown", return_value=False):
                    with patch("os.kill") as mock_kill:
                        code = cmd_stop(["--state-file", str(state_file)])

    assert code == 1
    mock_kill.assert_not_called()
    captured = capsys.readouterr()
    assert "could not confirm" in captured.err.lower()
    # State preserved for retry.
    assert state_file.exists()


# -- main / help --------------------------------------------------------


def test_main_help_exits_zero(capsys):
    code = main(["--help"])
    assert code == 0
    captured = capsys.readouterr()
    assert "start|status|stop" in captured.out


def test_main_unknown_subcommand_exits_nonzero(capsys):
    code = main(["restart"])
    assert code == 1
    captured = capsys.readouterr()
    assert "unknown" in captured.err.lower()


# -- process launch -----------------------------------------------------


def test_start_service_process_spawns_detached_subprocess():
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = _FakePopen(pid=42)
        proc = _start_service_process("127.0.0.1", 8765)

    assert proc.pid == 42
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0][0] == sys.executable
    assert args[0][2] == "tools.agent_bridge.service"
    assert "--host" in args[0]
    assert "127.0.0.1" in args[0]
    assert "--port" in args[0]
    assert "8765" in args[0]

    if sys.platform == "win32":
        assert "creationflags" in kwargs
        assert kwargs["creationflags"] & subprocess.DETACHED_PROCESS
        assert kwargs["creationflags"] & subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        assert kwargs.get("start_new_session") is True
