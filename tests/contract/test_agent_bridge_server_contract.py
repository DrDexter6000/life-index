"""Contract tests for ``life-index server`` through the unified CLI.

These tests exercise the real ``tools.__main__`` routing and argument parsing.
Tests that need a running service start a tiny local HTTP server in-process so
no real ACP runtime is required.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest


def _invoke(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "tools", *extra_args],
        capture_output=True,
        text=True,
        timeout=30,
    )


class _HealthzHandler(BaseHTTPRequestHandler):
    """Minimal handler that responds to GET /healthz and POST /shutdown."""

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_json(200, {"status": "ok", "state": "warm"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/shutdown":
            self._send_json(200, {"status": "shutting down"})
        else:
            self._send_json(404, {"error": "not found"})


@pytest.fixture
def fake_service_port():
    """Yield an ephemeral loopback HTTP server and its port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthzHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def fake_service_process():
    """Yield a real subprocess-backed fake service port and pid.

    Stop lifecycle tests must not run the listener inside the pytest process:
    the server CLI discovers the OS listener pid and may signal it during
    escalation.
    """
    script = r"""
import json
import os as _os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, status, body):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/healthz":
            self._send_json(200, {"status": "ok", "state": "warm"})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/shutdown":
            self._send_json(200, {"status": "shutting down"})
            self.wfile.flush()
            _os._exit(0)
        else:
            self._send_json(404, {"error": "not found"})


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
server.server_close()
"""
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    port_line = process.stdout.readline().strip()
    if not port_line:
        process.kill()
        stderr = process.stderr.read() if process.stderr is not None else ""
        pytest.fail(f"fake service process failed to start: {stderr}")
    try:
        yield int(port_line), process.pid
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_server_help_appears_in_main_help():
    result = _invoke("--help")
    assert result.returncode == 0
    assert "server" in result.stdout
    assert "Start/status/stop" in result.stdout


def test_server_start_non_loopback_is_rejected():
    result = _invoke("server", "start", "--host", "0.0.0.0")
    assert result.returncode == 1
    assert "non-loopback" in result.stderr.lower()


def test_server_status_reports_not_running_when_no_service(tmp_path: Path):
    state_file = tmp_path / "server.json"
    result = _invoke("server", "status", "--state-file", str(state_file), "--port", "65432")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["running"] is False
    assert data["state"] == "not running"
    assert data["port"] == 65432


def test_server_stop_is_safe_when_no_service(tmp_path: Path):
    state_file = tmp_path / "server.json"
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": 65432, "pid": 12345}),
        encoding="utf-8",
    )
    result = _invoke("server", "stop", "--state-file", str(state_file), "--port", "65432")
    assert result.returncode == 0
    assert "server stopped" in result.stdout
    assert not state_file.exists()


def test_server_start_detects_existing_service(fake_service_port: int, tmp_path: Path):
    state_file = tmp_path / "server.json"
    result = _invoke(
        "server",
        "start",
        "--state-file",
        str(state_file),
        "--port",
        str(fake_service_port),
    )
    assert result.returncode == 0
    assert "already running" in result.stdout
    assert f"127.0.0.1:{fake_service_port}" in result.stdout
    assert state_file.exists()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["host"] == "127.0.0.1"
    assert data["port"] == fake_service_port
    assert isinstance(data["pid"], int)
    assert data["pid"] > 0


def test_server_status_reports_running_service(fake_service_port: int, tmp_path: Path):
    state_file = tmp_path / "server.json"
    result = _invoke(
        "server",
        "status",
        "--state-file",
        str(state_file),
        "--port",
        str(fake_service_port),
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["running"] is True
    assert data["state"] == "warm"
    assert data["port"] == fake_service_port


def test_server_stop_gracefully_shuts_down_service(fake_service_process, tmp_path: Path):
    fake_service_port, fake_service_pid = fake_service_process
    state_file = tmp_path / "server.json"
    state_file.write_text(
        json.dumps({"host": "127.0.0.1", "port": fake_service_port, "pid": fake_service_pid}),
        encoding="utf-8",
    )
    result = _invoke(
        "server",
        "stop",
        "--state-file",
        str(state_file),
        "--port",
        str(fake_service_port),
    )
    assert result.returncode == 0
    assert "server stopped" in result.stdout
    assert not state_file.exists()


def test_agent_bridge_query_rich_contract_shape():
    """The warm gateway rich query contract exposes the expected top-level fields."""
    from tools.agent_bridge.query_envelope import map_to_rich_envelope

    internal = {
        "schema_version": "m35.agent_bridge_query.v0",
        "status": "GROUNDED",
        "answer": "A grounded summary.",
        "insights": [],
        "evidence_refs": [],
        "gap": None,
        "provenance": {
            "transport": "acp",
            "model": "hermes-agent",
            "runtime": "fake-acp",
            "degraded": False,
        },
    }

    rich = map_to_rich_envelope("What happened?", {"intent": "recall"}, internal)

    assert rich["success"] is True
    assert rich["schema_version"] == "m35.agent_bridge_query.v0"
    assert rich["command"] == "agent-bridge query"
    assert rich["source"] == "host-agent"
    assert rich["query"] == "What happened?"
    assert rich["mode"] == "GROUNDED"
    assert set(rich.keys()) >= {
        "success",
        "schema_version",
        "command",
        "source",
        "query",
        "mode",
        "scaffold",
        "evidence",
        "answer",
        "synthesis",
        "events",
        "provenance",
    }
    assert rich["answer"]["mode"] == "GROUNDED"
    assert rich["answer"]["summary"] == "A grounded summary."
    assert rich["synthesis"] == "A grounded summary."
    assert rich["provenance"]["evidence_source"] == "life-index search"
    assert rich["provenance"]["degraded"] is False


def test_agent_bridge_query_rich_contract_preserves_ungrounded_answer_with_reason():
    """UNGROUNDED rich final is an honest label, not answer suppression."""
    from tools.agent_bridge.query_envelope import map_to_rich_envelope

    internal = {
        "schema_version": "m35.agent_bridge_query.v0",
        "status": "UNGROUNDED",
        "answer": "First pass answer text that failed grounding.",
        "insights": [],
        "evidence_refs": [],
        "gap": "Unknown evidence IDs in response: Z99.",
        "reason": "Unknown evidence IDs in response: Z99.",
        "provenance": {
            "transport": "acp",
            "model": "hermes-agent",
            "runtime": "fake-acp",
            "degraded": True,
        },
    }

    rich = map_to_rich_envelope("What happened?", {"intent": "recall"}, internal)

    assert rich["mode"] == "UNGROUNDED"
    assert rich["reason"] == "Unknown evidence IDs in response: Z99."
    assert rich["answer"]["mode"] == "UNGROUNDED"
    assert rich["answer"]["summary"] == "First pass answer text that failed grounding."
    assert rich["answer"]["gap"] == "Unknown evidence IDs in response: Z99."
    assert rich["synthesis"] == "First pass answer text that failed grounding."
    assert rich["provenance"]["degraded"] is True


def test_agent_bridge_query_rich_contract_preserves_unverifiable_answer_with_reason():
    """UNVERIFIABLE rich final is advisory metadata, not answer suppression."""
    from tools.agent_bridge.query_envelope import map_to_rich_envelope

    internal = {
        "schema_version": "m35.agent_bridge_query.v0",
        "status": "UNVERIFIABLE",
        "answer": "First pass answer text with citations.",
        "insights": [
            {
                "quote": "Listed evidence.",
                "interpretation": "The answer cites this evidence.",
                "evidence_refs": ["Journals/2026/06/life-index_2026-06-10_001.md"],
            }
        ],
        "evidence_refs": ["Journals/2026/06/life-index_2026-06-10_001.md"],
        "gap": "Runtime could not verify cited journal reads.",
        "reason": "Runtime could not verify cited journal reads.",
        "provenance": {
            "transport": "acp",
            "model": "runtime-without-trace",
            "runtime": "fake-acp",
            "degraded": True,
        },
    }
    scaffold = {
        "intent": "recall",
        "evidence_pack": {
            "items": [
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-10_001.md",
                        "title": "Trace-free runtime",
                        "date": "2026-06-10",
                    },
                    "snippet": "Listed evidence.",
                }
            ]
        },
    }

    rich = map_to_rich_envelope("What happened?", scaffold, internal)

    assert rich["mode"] == "UNVERIFIABLE"
    assert rich["reason"] == "Runtime could not verify cited journal reads."
    assert rich["answer"]["mode"] == "UNVERIFIABLE"
    assert rich["answer"]["summary"] == "First pass answer text with citations."
    assert rich["answer"]["gap"] == "Runtime could not verify cited journal reads."
    assert rich["answer"]["explanation"] == "Runtime could not verify cited journal reads."
    assert rich["synthesis"] == "First pass answer text with citations."
    assert rich["evidence"][0]["id"] == "2026/06/life-index_2026-06-10_001"
    assert rich["provenance"]["degraded"] is True
