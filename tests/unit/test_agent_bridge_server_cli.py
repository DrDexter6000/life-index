"""Unit tests for the ``life-index server`` CLI.

Tests use dependency injection to avoid spawning real subprocesses or binding
real network sockets.
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
    """Minimal subprocess.Popen stand-in."""

    def __init__(self, pid: int = 12345) -> None:
        self.pid = pid


def _make_state_file(tmp_path: Path) -> Path:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "server.json"


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


def test_probe_healthz_returns_none_when_nothing_listens():
    # Pick a port that is extremely unlikely to be listening.
    assert _probe_healthz("127.0.0.1", 65432) is None


def test_is_running_false_when_probe_fails():
    assert _is_running("127.0.0.1", 65432) is False


def test_wait_for_healthz_returns_none_on_timeout():
    assert _wait_for_healthz("127.0.0.1", 65432, timeout=0.05) is None


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


def test_start_detects_existing_service_and_exits_zero(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm", "pid": 12345}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        code = cmd_start(["--state-file", str(state_file)])

    assert code == 0
    captured = capsys.readouterr()
    assert "already running" in captured.out
    assert "127.0.0.1:8765" in captured.out
    assert not state_file.exists()


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


def test_start_fails_when_service_does_not_respond(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    fake_process = _FakePopen(pid=12345)

    with patch("tools.agent_bridge.server_cli._start_service_process", return_value=fake_process):
        with patch("tools.agent_bridge.server_cli._is_running", return_value=False):
            with patch("tools.agent_bridge.server_cli._wait_for_healthz", return_value=None):
                code = cmd_start(["--state-file", str(state_file)])

    assert code == 1
    captured = capsys.readouterr()
    assert "did not respond" in captured.err.lower()


def test_status_reports_running_with_warm_state(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm", "pid": 12345}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
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
        code = cmd_status(["--state-file", str(state_file)])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is True
    assert result["state"] == "degraded"
    assert result["degraded"] is True


def test_status_reports_not_running_with_stale_state(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    with patch("tools.agent_bridge.server_cli._probe_healthz", return_value=None):
        code = cmd_status(["--state-file", str(state_file)])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is False
    assert result["state"] == "not running"
    assert result["pid"] == 12345


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
        code = cmd_status(["--host", "127.0.0.1", "--port", "9999"])

    assert code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["running"] is True
    assert result["port"] == 9999
    assert result["pid"] is None


def test_stop_gracefully_shuts_down_via_endpoint_and_removes_state(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    shutdown_requested = [False]

    def _fake_probe(host: str, port: int, timeout: float = 1.0):
        if shutdown_requested[0]:
            return None
        return {"status": "ok", "state": "warm"}

    def _fake_urlopen(req, timeout=None):
        shutdown_requested[0] = True
        return _FakeResponse(b'{"status": "shutting down"}')

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch(
            "tools.agent_bridge.server_cli.urllib.request.urlopen",
            side_effect=_fake_urlopen,
        ):
            code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    assert not state_file.exists()
    captured = capsys.readouterr()
    assert "server stopped" in captured.out


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self) -> bytes:
        return self._body


def test_stop_falls_back_to_signal_when_endpoint_fails(tmp_path: Path, capsys):
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
            with patch("os.kill", side_effect=_fake_kill):
                code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    assert killed[0]
    assert not state_file.exists()


def test_stop_is_safe_when_no_service_running(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765, "pid": 12345}),
        encoding="utf-8",
    )

    with patch("tools.agent_bridge.server_cli._probe_healthz", return_value=None):
        with patch("os.kill") as mock_kill:
            code = cmd_stop(["--state-file", str(state_file)])

    assert code == 0
    mock_kill.assert_not_called()
    assert not state_file.exists()
    captured = capsys.readouterr()
    assert "server stopped" in captured.out


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


def test_stop_handles_missing_pid(tmp_path: Path, capsys):
    state_file = _make_state_file(tmp_path)
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 8765}),
        encoding="utf-8",
    )

    def _fake_probe(*args, **kwargs):
        return {"status": "ok", "state": "warm"}

    with patch("tools.agent_bridge.server_cli._probe_healthz", side_effect=_fake_probe):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            with patch("os.kill") as mock_kill:
                code = cmd_stop(["--state-file", str(state_file)])

    assert code == 1
    mock_kill.assert_not_called()
    assert not state_file.exists()


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
