"""Unit tests for the V5b-2 localhost warm ACP service.

Tests use fake managers / adapters so no real Hermes runtime is required.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.agent_bridge.acp_session_manager import ACPWarmSessionManager
from tools.agent_bridge.config import BrainConfig
from tools.agent_bridge.service import (
    ACPServiceHandler,
    ACPThreadingServer,
    _build_server,
    _make_signal_handler,
    _schedule_async_shutdown,
    is_loopback,
)

QUERY_SCHEMA_VERSION = "m35.agent_bridge_query.v0"


def _brain_config() -> BrainConfig:
    return BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model="test-model",
        data_exposure_ack=True,
        acp_command=["dummy"],
        acp_workdir=str(REPO_ROOT),
    )


def _success_envelope(answer: str = "ok") -> dict:
    return {
        "schema_version": QUERY_SCHEMA_VERSION,
        "status": "GROUNDED",
        "answer": answer,
        "insights": [{"text": "t", "evidence_refs": ["E1"]}],
        "evidence_refs": ["E1"],
        "gap": None,
        "provenance": {
            "transport": "acp",
            "model": "test",
            "runtime": "test",
            "degraded": False,
        },
        "usage": None,
    }


def _degraded_envelope(gap: str = "dead") -> dict:
    return {
        "schema_version": QUERY_SCHEMA_VERSION,
        "status": "UNGROUNDED",
        "answer": None,
        "insights": [],
        "evidence_refs": [],
        "gap": gap,
        "provenance": {
            "transport": "acp",
            "model": "unknown",
            "runtime": "acp",
            "degraded": True,
        },
        "usage": None,
    }


class _FakeManagerWarmOk:
    def __init__(self) -> None:
        self._cfg = _brain_config()
        self.started = False
        self.closed = False
        self.queries: list[tuple[str, dict, Any]] = []

    def start(self) -> "_FakeManagerWarmOk":
        self.started = True
        return self

    def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
        self.queries.append((query, scaffold, stream_callback))
        return _success_envelope(answer=query)

    def close(self) -> None:
        self.closed = True

    def health(self) -> dict:
        return {
            "status": "ok",
            "state": "warm",
            "transport": "acp",
            "runtime": "fake-runtime",
            "model": "fake-model",
            "pid": 12345,
            "is_alive": True,
            "last_warm_error": None,
        }


class _FakeManagerWarmFails:
    def __init__(self) -> None:
        self._cfg = _brain_config()
        self.started = False
        self.closed = False
        self._last_warm_error: str | None = None

    def start(self) -> "_FakeManagerWarmFails":
        self.started = True
        self._last_warm_error = "warm-up failed: dummy"
        return self

    def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
        return _degraded_envelope("warm session unavailable")

    def close(self) -> None:
        self.closed = True

    def health(self) -> dict:
        return {
            "status": "ok",
            "state": "degraded",
            "transport": "acp",
            "runtime": "acp",
            "model": "test-model",
            "pid": None,
            "is_alive": False,
            "last_warm_error": self._last_warm_error,
        }


class _FakeManagerStreaming:
    def __init__(self, raise_on_query: bool = False) -> None:
        self._cfg = _brain_config()
        self.queries: list[tuple[str, dict, Any]] = []
        self.closed = False
        self.raise_on_query = raise_on_query

    def start(self) -> "_FakeManagerStreaming":
        return self

    def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
        self.queries.append((query, scaffold, stream_callback))
        if self.raise_on_query:
            raise RuntimeError("boom")
        if stream_callback is not None:
            stream_callback("chunk-alpha")
            stream_callback("chunk-beta")
        return _success_envelope(answer=query)

    def close(self) -> None:
        self.closed = True

    def health(self) -> dict:
        return {"status": "ok", "state": "warm", "last_warm_error": None}


class _DummyConn:
    def __init__(self) -> None:
        self.alive = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def is_alive(self):
        return self.alive

    def close(self):
        self.alive = False


def _start_server_with_manager(manager) -> ACPThreadingServer:
    """Bind a service server on 127.0.0.1 with an ephemeral port."""
    manager.start()
    ACPServiceHandler.manager = manager
    server = ACPThreadingServer(("127.0.0.1", 0), ACPServiceHandler)
    ACPServiceHandler.server_instance = server
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _request_raw(
    server: ThreadingHTTPServer,
    path: str,
    method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
) -> tuple[int, bytes]:
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}{path}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    req = Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)
    try:
        with urlopen(req) as resp:
            return resp.status, resp.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def _request(
    server: ACPThreadingServer,
    path: str,
    method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
) -> tuple[int, dict]:
    status, raw = _request_raw(server, path, method=method, data=data, headers=headers)
    payload = json.loads(raw.decode("utf-8"))
    return status, payload


def test_loopback_validation_accepts_localhost():
    assert is_loopback("127.0.0.1") is True
    assert is_loopback("localhost") is True


def test_loopback_validation_rejects_broadcast_and_public():
    assert is_loopback("0.0.0.0") is False
    assert is_loopback("192.168.1.1") is False
    assert is_loopback("10.0.0.1") is False
    assert is_loopback("8.8.8.8") is False
    assert is_loopback("") is False


def test_service_starts_even_when_warm_fails():
    manager = _FakeManagerWarmFails()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(server, "/healthz")
        assert status == 200
        assert body["state"] == "degraded"
        assert "warm-up failed" in (body["last_warm_error"] or "")
    finally:
        server.shutdown_and_close()


def test_healthz_reports_non_blocking_state():
    manager = _FakeManagerWarmOk()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(server, "/healthz")
        assert status == 200
        assert body["state"] == "warm"
        assert body["transport"] == "acp"
        assert body["runtime"] == "fake-runtime"
        assert body["model"] == "fake-model"
        assert body["pid"] == 12345
        assert body["is_alive"] is True
        assert "last_warm_error" in body
    finally:
        server.shutdown_and_close()


def _fake_warm_conn():
    """Return a connection stand-in that looks alive for health checks."""

    class _Conn:
        pid = 12345
        initialize_result = {"serverInfo": {"name": "fake-acp"}}
        session_new_result = {"sessionId": "fake-session", "model": "fake-model"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def is_alive(self):
            return True

        def close(self):
            pass

    return _Conn()


def test_build_server_warms_on_start():
    """_build_server calls manager.start() and starts listening on loopback."""
    cfg = _brain_config()

    server, manager = _build_server(
        "127.0.0.1",
        0,
        cfg,
        connection_factory=lambda *a, **k: _fake_warm_conn(),
        adapter=lambda *a, **k: _success_envelope(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        assert isinstance(server, ACPThreadingServer)
        assert isinstance(manager, ACPWarmSessionManager)
        # manager.start() was invoked eagerly.
        assert manager._last_warm_error is None
        host, port = server.server_address[:2]
        assert host == "127.0.0.1"
        assert port > 0
        status, body = _request(server, "/healthz")
        assert status == 200
        assert body["state"] == "warm"
        assert body["pid"] == 12345
    finally:
        server.shutdown_and_close()


def test_build_server_keeps_running_when_warm_fails():
    """Warm-up failure during _build_server does not crash the service."""
    cfg = _brain_config()

    def _factory(*args, **kwargs):
        raise RuntimeError("warm-up always fails")

    server, manager = _build_server(
        "127.0.0.1",
        0,
        cfg,
        connection_factory=_factory,
        adapter=lambda *a, **k: _success_envelope(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _request(server, "/healthz")
        assert status == 200
        assert body["state"] == "degraded"
        assert body["last_warm_error"] is not None
        # The recorded error may be the root cause or the manager's wrapper;
        # either proves warm failure was captured and the service stayed up.
        assert (
            "warm-up always fails" in body["last_warm_error"]
            or "Failed to establish" in body["last_warm_error"]
        )
    finally:
        server.shutdown_and_close()


def test_query_json_returns_envelope():
    manager = _FakeManagerWarmOk()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={"query": "hello", "scaffold": {"evidence_pack": {}}},
        )
        assert status == 200
        assert body["schema_version"] == QUERY_SCHEMA_VERSION
        assert body["status"] == "GROUNDED"
        assert body["answer"] == "hello"
        assert len(manager.queries) == 1
        assert manager.queries[0][0] == "hello"
    finally:
        server.shutdown_and_close()


def test_query_json_rejects_invalid_json():
    manager = _FakeManagerWarmOk()
    server = _start_server_with_manager(manager)
    try:
        host, port = server.server_address[:2]
        url = f"http://{host}:{port}/query"
        req = Request(url, data=b"not json", method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req) as resp:
                status = resp.status
                body = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            status = exc.code
            body = json.loads(exc.read().decode("utf-8"))
        assert status == 400
        assert "invalid json" in body.get("error", "").lower()
    finally:
        server.shutdown_and_close()


def test_query_json_rejects_missing_query():
    manager = _FakeManagerWarmOk()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(server, "/query", method="POST", data={"scaffold": {}})
        assert status == 400
        assert "query" in body.get("error", "").lower()
    finally:
        server.shutdown_and_close()


def test_query_sse_emits_chunks_before_result():
    manager = _FakeManagerStreaming()
    server = _start_server_with_manager(manager)
    try:
        status, raw = _request_raw(
            server,
            "/query",
            method="POST",
            data={"query": "stream me", "scaffold": {}},
            headers={"Accept": "text/event-stream"},
        )
        assert status == 200
        text = raw.decode("utf-8")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        events: list[tuple[str, Any]] = []
        current_event: str | None = None
        for line in lines:
            if line.startswith("event:"):
                current_event = line[len("event:") :].strip()
            elif line.startswith("data:") and current_event is not None:
                data = json.loads(line[len("data:") :].strip())
                events.append((current_event, data))
                current_event = None

        chunk_events = [e for e in events if e[0] == "chunk"]
        result_events = [e for e in events if e[0] == "result"]
        assert len(chunk_events) == 2, f"expected 2 chunks, got {events}"
        assert chunk_events[0][1] == "chunk-alpha"
        assert chunk_events[1][1] == "chunk-beta"
        assert len(result_events) == 1
        assert result_events[0][1]["status"] == "GROUNDED"
        assert result_events[0][1]["answer"] == "stream me"
        assert events.index(chunk_events[0]) < events.index(result_events[0])
        assert events.index(chunk_events[1]) < events.index(result_events[0])
    finally:
        server.shutdown_and_close()


def test_sse_exception_path_emits_degraded_result():
    manager = _FakeManagerStreaming(raise_on_query=True)
    server = _start_server_with_manager(manager)
    try:
        status, raw = _request_raw(
            server,
            "/query",
            method="POST",
            data={"query": "fail", "scaffold": {}},
            headers={"Accept": "text/event-stream"},
        )
        assert status == 200
        text = raw.decode("utf-8")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        events: list[tuple[str, Any]] = []
        current_event: str | None = None
        for line in lines:
            if line.startswith("event:"):
                current_event = line[len("event:") :].strip()
            elif line.startswith("data:") and current_event is not None:
                data = json.loads(line[len("data:") :].strip())
                events.append((current_event, data))
                current_event = None

        chunk_events = [e for e in events if e[0] == "chunk"]
        result_events = [e for e in events if e[0] == "result"]
        assert len(chunk_events) == 0
        assert len(result_events) == 1
        result = result_events[0][1]
        assert result["schema_version"] == QUERY_SCHEMA_VERSION
        assert result["status"] == "UNGROUNDED"
        assert result["provenance"]["degraded"] is True
        assert "SSE query failed" in result["gap"]
    finally:
        server.shutdown_and_close()


def test_concurrent_queries_serialized_through_manager_lock():
    active = [0]
    max_active = [0]
    lock = threading.Lock()

    def adapter(
        query: str,
        scaffold: dict,
        cfg: Any,
        *,
        connection: Any = None,
        stream_callback: Any = None,
    ):
        with lock:
            active[0] += 1
            max_active[0] = max(max_active[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return _success_envelope(answer=query)

    mgr = ACPWarmSessionManager(
        _brain_config(), connection_factory=lambda *a, **k: _DummyConn(), adapter=adapter
    )
    server = _start_server_with_manager(mgr)
    try:
        results: list[dict] = []
        errors: list[Exception] = []

        def call(q: str) -> None:
            try:
                _, body = _request(server, "/query", method="POST", data={"query": q})
                results.append(body)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=call, args=("q1",))
        t2 = threading.Thread(target=call, args=("q2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        assert len(results) == 2
        assert max_active[0] == 1, "manager lock did not serialize concurrent queries"
    finally:
        server.shutdown_and_close()


def test_shutdown_calls_manager_close():
    manager = _FakeManagerWarmOk()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(server, "/shutdown", method="POST")
        assert status == 200
        # Give the shutdown thread a moment to run.
        time.sleep(0.1)
        assert manager.closed is True
    finally:
        if not manager.closed:
            server.shutdown_and_close()


def test_main_rejects_non_loopback_host():
    from tools.agent_bridge.service import main

    assert main(["--host", "0.0.0.0", "--port", "0"]) == 1


def test_help_does_not_crash():
    from tools.agent_bridge.service import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


class _RecordingManager:
    def __init__(self) -> None:
        self.closed = False
        self.close_thread_id: int | None = None

    def close(self) -> None:
        self.closed = True
        self.close_thread_id = threading.current_thread().ident


class _RecordingServer:
    def __init__(self, block_event: threading.Event | None = None) -> None:
        self.shutdown_and_close_called = False
        self.shutdown_and_close_thread_id: int | None = None
        self.block_event = block_event

    def shutdown_and_close(self) -> None:
        self.shutdown_and_close_called = True
        self.shutdown_and_close_thread_id = threading.current_thread().ident
        if self.block_event is not None:
            self.block_event.wait()


def _wait_for(condition: Callable[[], bool], timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.001)


def test_schedule_async_shutdown_does_not_block():
    """The async shutdown helper starts teardown in a daemon thread."""
    block = threading.Event()
    manager = _RecordingManager()
    server = _RecordingServer(block_event=block)

    start = time.monotonic()
    _schedule_async_shutdown(manager, server)
    elapsed = time.monotonic() - start

    assert elapsed < 0.1
    block.set()
    _wait_for(lambda: server.shutdown_and_close_called)

    assert manager.closed is True
    assert server.shutdown_and_close_called is True
    assert manager.close_thread_id != threading.current_thread().ident
    assert server.shutdown_and_close_thread_id != threading.current_thread().ident


def test_signal_handler_schedules_async_shutdown():
    """SIGTERM/SIGINT handlers schedule async teardown instead of blocking."""
    block = threading.Event()
    manager = _RecordingManager()
    server = _RecordingServer(block_event=block)
    handler = _make_signal_handler(manager, server)

    start = time.monotonic()
    handler(15, None)
    elapsed = time.monotonic() - start

    assert elapsed < 0.1
    block.set()
    _wait_for(lambda: server.shutdown_and_close_called)

    assert manager.closed is True
    assert server.shutdown_and_close_called is True
    assert manager.close_thread_id != threading.current_thread().ident
    assert server.shutdown_and_close_thread_id != threading.current_thread().ident
