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
    _ACP_WARMUP_PROMPT_DISABLE_VALUES,
    _ACP_WARMUP_PROMPT_ENV,
    _build_server,
    _make_signal_handler,
    _schedule_async_shutdown,
    is_loopback,
)

# For RED tests and monkeypatching the L3 deterministic scaffold builder.
import tools.agent_bridge.handoff as _handoff_mod

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


def _scaffold_with_evidence() -> dict:
    """Deterministic scaffold returned by the L2 smart-search builder."""
    return {
        "intent": "recall",
        "queries": ["park"],
        "filters": {},
        "evidence_pack": {
            "items": [
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-04_001.md",
                        "title": "Park day",
                        "date": "2026-06-04",
                    },
                    "snippet": "Spent the afternoon at Central Park.",
                },
            ],
        },
    }


def _envelope_with_real_evidence(answer: str = "ok") -> dict:
    """Internal envelope that references the real journal IDs from _scaffold_with_evidence."""
    return {
        "schema_version": QUERY_SCHEMA_VERSION,
        "status": "GROUNDED",
        "answer": answer,
        "insights": [
            {
                "text": "t",
                "evidence_refs": ["Journals/2026/06/life-index_2026-06-04_001.md"],
            },
        ],
        "evidence_refs": ["Journals/2026/06/life-index_2026-06-04_001.md"],
        "gap": None,
        "provenance": {
            "transport": "acp",
            "model": "test",
            "runtime": "test",
            "degraded": False,
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
    """Streams raw model-like fragments that must not leak into ``delta``."""

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
            # Emit raw JSON/markdown/schema fragments.  The gateway must NOT
            # forward these as delta; the delta must be the validated answer
            # summary from the final rich envelope.
            stream_callback("```json\n")
            stream_callback('{\n  "schema_version": "m35.agent_bridge_query.v0",\n')
            stream_callback('  "status": "GROUNDED",\n')
            stream_callback(f'  "answer": "{query}",\n')
            stream_callback('  "evidence_refs": ["E1"],\n')
            stream_callback('  "provenance": {"transport": "acp"}\n')
            stream_callback("}\n```\n")
        return _success_envelope(answer=query)

    def close(self) -> None:
        self.closed = True

    def health(self) -> dict:
        return {"status": "ok", "state": "warm", "last_warm_error": None}


class _FakeManagerStreamingDegraded:
    """Streams fragments but returns a degraded UNGROUNDED result."""

    def __init__(self) -> None:
        self._cfg = _brain_config()
        self.queries: list[tuple[str, dict, Any]] = []
        self.closed = False

    def start(self) -> "_FakeManagerStreamingDegraded":
        return self

    def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
        self.queries.append((query, scaffold, stream_callback))
        if stream_callback is not None:
            stream_callback("```json\n")
            stream_callback('{"schema_version": "m35.agent_bridge_query.v0"}\n')
            stream_callback("```\n")
        return _degraded_envelope("no answer available")

    def close(self) -> None:
        self.closed = True

    def health(self) -> dict:
        return {"status": "ok", "state": "warm", "last_warm_error": None}


class _FakeManagerWithEvidence:
    """Returns a grounded envelope with real journal evidence refs."""

    def __init__(self) -> None:
        self._cfg = _brain_config()
        self.started = False
        self.closed = False
        self.queries: list[tuple[str, dict, Any]] = []

    def start(self) -> "_FakeManagerWithEvidence":
        self.started = True
        return self

    def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
        self.queries.append((query, scaffold, stream_callback))
        return _envelope_with_real_evidence(answer=query)

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


class _FakeManagerUngrounded:
    """Always returns a deterministic UNGROUNDED envelope."""

    def __init__(self) -> None:
        self._cfg = _brain_config()
        self.queries: list[tuple[str, dict, Any]] = []
        self.closed = False

    def start(self) -> "_FakeManagerUngrounded":
        return self

    def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
        self.queries.append((query, scaffold, stream_callback))
        return _degraded_envelope("no relevant evidence")

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
        session_id = "fake-session"
        initialize_result = {"serverInfo": {"name": "fake-acp"}}
        session_new_result = {"sessionId": "fake-session", "model": "fake-model"}
        rpc_calls: list[tuple[str, dict]] = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def is_alive(self):
            return True

        def close(self):
            pass

        def rpc(self, method, params):
            self.rpc_calls.append((method, params))
            return {"result": {"ok": True}}

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


def test_build_server_calls_scaffold_warmup(monkeypatch):
    """_build_server calls warm_gateway_scaffold_path exactly once after manager.start."""
    warm_calls: list[str] = []

    def _record_warm(query: str = "__warmup__") -> dict:
        warm_calls.append(query)
        return {"ok": True, "error_message": None}

    monkeypatch.setattr(_handoff_mod, "warm_gateway_scaffold_path", _record_warm)

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
        # Warmup was called exactly once with the default query.
        assert len(warm_calls) == 1, f"expected 1 warm call, got {len(warm_calls)}"
        assert warm_calls[0] == "__warmup__"
        # Manager was started before warmup (started check in _build_server).
        assert manager._last_warm_error is None
    finally:
        server.shutdown_and_close()


def test_scaffold_warmup_failure_does_not_crash_build_server(monkeypatch):
    """Warmup failure in warm_gateway_scaffold_path() does not crash _build_server()."""

    def _failing_warm(query: str = "__warmup__") -> dict:
        raise RuntimeError("scaffold warmup exploded")

    monkeypatch.setattr(_handoff_mod, "warm_gateway_scaffold_path", _failing_warm)

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
        # Server must still start and serve healthz.
        status, body = _request(server, "/healthz")
        assert status == 200
        assert body["state"] == "warm"
        assert body["pid"] == 12345
    finally:
        server.shutdown_and_close()


def test_warm_gateway_scaffold_path_returns_ok_on_success(monkeypatch):
    """Direct unit test: warm_gateway_scaffold_path returns ok when build succeeds."""
    read_top_calls: list[tuple[str, int]] = []

    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", lambda _q: _scaffold_with_evidence())
    monkeypatch.setattr(
        _handoff_mod,
        "_cli_search_read_top",
        lambda q, limit=10: read_top_calls.append((q, limit))
        or {"success": True, "merged_results": []},
    )

    result = _handoff_mod.warm_gateway_scaffold_path("warm query")
    assert result == {"ok": True, "error_message": None}
    assert read_top_calls == [("warm query", 1)]


def test_warm_gateway_scaffold_path_swallows_exceptions(monkeypatch):
    """Direct unit test: warm_gateway_scaffold_path swallows exceptions and reports them."""
    monkeypatch.setattr(
        _handoff_mod,
        "_cli_smart_search",
        lambda _q: (_ for _ in ()).throw(RuntimeError("subprocess refused")),
    )

    result = _handoff_mod.warm_gateway_scaffold_path()
    assert result["ok"] is False
    assert "subprocess refused" in result["error_message"]


def test_query_json_returns_rich_envelope():
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
        assert body["success"] is True
        assert body["command"] == "agent-bridge query"
        assert body["source"] == "host-agent"
        assert body["query"] == "hello"
        assert body["mode"] == "GROUNDED"
        assert body["answer"]["mode"] == "GROUNDED"
        assert body["answer"]["summary"] == "hello"
        assert body["synthesis"] == "hello"
        assert body["events"] == []
        assert body["provenance"]["evidence_source"] == "life-index search"
        assert body["provenance"]["degraded"] is False
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


def _parse_sse_events(raw: bytes) -> list[tuple[str, Any]]:
    """Parse raw SSE response bytes into a list of (event_name, data) tuples."""
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
    return events


def test_query_sse_emits_contract_events_in_order(monkeypatch):
    """SSE /query emits status -> scaffold -> evidence -> delta -> final."""
    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", lambda _q: {})

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
        events = _parse_sse_events(raw)
        names = [e[0] for e in events]

        assert names == [
            "status",
            "scaffold",
            "evidence",
            "delta",
            "final",
        ], f"got {names}"
        assert events[0][1] == {"state": "active"}
        assert events[1][1] == {
            "intent": "",
            "date_from": "",
            "date_to": "",
            "queries": [],
            "filters": {},
        }
        assert events[2][1] == []
        delta = events[3][1]
        assert delta == "stream me"
        final = events[4][1]
        assert final["schema_version"] == QUERY_SCHEMA_VERSION
        assert final["success"] is True
        assert final["mode"] == "GROUNDED"
        assert final["answer"]["summary"] == "stream me"
        assert final["synthesis"] == "stream me"

        # The gateway must pass a stream_callback into the manager.
        assert len(manager.queries) == 1
        assert manager.queries[0][2] is not None
    finally:
        server.shutdown_and_close()


def test_sse_exception_path_emits_error_with_rich_degraded_envelope():
    """SSE /query error event carries a rich UNGROUNDED degraded envelope."""
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
        events = _parse_sse_events(raw)
        names = [e[0] for e in events]

        assert "status" in names
        assert "scaffold" in names
        assert "error" in names
        error_event = [e for e in events if e[0] == "error"][0]
        envelope = error_event[1]["envelope"]
        assert envelope["schema_version"] == QUERY_SCHEMA_VERSION
        assert envelope["success"] is True
        assert envelope["mode"] == "UNGROUNDED"
        assert envelope["answer"]["mode"] == "UNGROUNDED"
        assert envelope["answer"]["summary"] == ""
        assert envelope["provenance"]["degraded"] is True
        assert "SSE query failed" in envelope["answer"]["gap"]
    finally:
        server.shutdown_and_close()


def test_query_stream_path_emits_sse_contract():
    """POST /query/stream always emits SSE contract events."""
    manager = _FakeManagerStreaming()
    server = _start_server_with_manager(manager)
    try:
        status, raw = _request_raw(
            server,
            "/query/stream",
            method="POST",
            data={"query": "stream via path", "scaffold": {}},
        )
        assert status == 200
        events = _parse_sse_events(raw)
        names = [e[0] for e in events]
        assert names == [
            "status",
            "scaffold",
            "evidence",
            "delta",
            "final",
        ], f"got {names}"
        assert events[3][1] == "stream via path"
        assert events[4][1]["answer"]["summary"] == "stream via path"
    finally:
        server.shutdown_and_close()


def test_sse_delta_excludes_raw_model_fragments():
    """Raw JSON/markdown/schema fragments streamed by the adapter do not leak into delta."""
    manager = _FakeManagerStreaming()
    server = _start_server_with_manager(manager)
    try:
        status, raw = _request_raw(
            server,
            "/query/stream",
            method="POST",
            data={"query": "raw fragments", "scaffold": {}},
        )
        assert status == 200
        events = _parse_sse_events(raw)
        deltas = [data for name, data in events if name == "delta"]
        assert len(deltas) == 1
        delta = deltas[0]
        assert delta == "raw fragments"

        forbidden = [
            "schema_version",
            "evidence_refs",
            "provenance",
            "status",
            "GROUNDED",
            "```",
            "{",
            "}",
        ]
        for substring in forbidden:
            assert (
                substring not in delta
            ), f"delta contains forbidden substring {substring!r}: {delta!r}"
    finally:
        server.shutdown_and_close()


def test_sse_degraded_emits_no_delta():
    """A degraded UNGROUNDED result with no answer text emits no delta event."""
    manager = _FakeManagerStreamingDegraded()
    server = _start_server_with_manager(manager)
    try:
        status, raw = _request_raw(
            server,
            "/query/stream",
            method="POST",
            data={"query": "degraded", "scaffold": {}},
        )
        assert status == 200
        events = _parse_sse_events(raw)
        names = [e[0] for e in events]
        assert names == ["status", "scaffold", "evidence", "final"], f"got {names}"
        assert "delta" not in names
        final = events[3][1]
        assert final["mode"] == "UNGROUNDED"
        assert final["answer"]["summary"] == ""
        assert final["answer"]["gap"] == "no answer available"
    finally:
        server.shutdown_and_close()


def test_query_json_degraded_returns_rich_ungrounded():
    """A degraded manager result is returned as a rich UNGROUNDED envelope."""
    manager = _FakeManagerWarmFails()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={"query": "hello", "scaffold": {}},
        )
        assert status == 200
        assert body["success"] is True
        assert body["mode"] == "UNGROUNDED"
        assert body["answer"]["mode"] == "UNGROUNDED"
        assert body["answer"]["summary"] == ""
        assert body["provenance"]["degraded"] is True
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


# ─── V6-CA L3 evidence assembly RED/regression tests ────────────────────


def test_bare_json_query_assembles_scaffold_and_returns_evidence(monkeypatch):
    """Bare /query with no scaffold fetches deterministic scaffold and returns rich evidence."""
    calls: list[str] = []
    monkeypatch.setattr(
        _handoff_mod,
        "_cli_smart_search",
        lambda q: calls.append(q) or _scaffold_with_evidence(),
    )

    manager = _FakeManagerWithEvidence()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={"query": "hello bare"},
        )
        assert status == 200
        assert body["mode"] == "GROUNDED"
        assert len(body["evidence"]) == 1
        assert body["evidence"][0]["id"] == "2026/06/life-index_2026-06-04_001"
        assert "Central Park" in body["evidence"][0]["snippet"]

        # L2 smart-search builder was invoked exactly once for the bare query.
        assert calls == ["hello bare"]
        # The resolved scaffold (with evidence) was passed to the manager.
        assert len(manager.queries) == 1
        assert manager.queries[0][0] == "hello bare"
        passed_scaffold = manager.queries[0][1]
        assert passed_scaffold["intent"] == "recall"
        assert passed_scaffold["evidence_pack"]["items"][0]["document"]["doc_id"] == (
            "Journals/2026/06/life-index_2026-06-04_001.md"
        )
    finally:
        server.shutdown_and_close()


def test_bare_sse_query_emits_assembled_scaffold(monkeypatch):
    """Bare /query/stream emits status -> fetched scaffold -> evidence -> delta -> final."""
    calls: list[str] = []
    monkeypatch.setattr(
        _handoff_mod,
        "_cli_smart_search",
        lambda q: calls.append(q) or _scaffold_with_evidence(),
    )

    manager = _FakeManagerWithEvidence()
    server = _start_server_with_manager(manager)
    try:
        status, raw = _request_raw(
            server,
            "/query/stream",
            method="POST",
            data={"query": "stream bare"},
        )
        assert status == 200
        events = _parse_sse_events(raw)
        names = [e[0] for e in events]
        assert names == ["status", "scaffold", "evidence", "delta", "final"], f"got {names}"

        # The scaffold event is the fetched scaffold, not empty defaults.
        scaffold_event = events[1][1]
        assert scaffold_event["intent"] == "recall"
        assert scaffold_event["queries"] == ["park"]

        # Evidence is populated from the assembled scaffold.
        evidence_event = events[2][1]
        assert len(evidence_event) == 1
        assert evidence_event[0]["id"] == "2026/06/life-index_2026-06-04_001"

        # Delta remains clean answer text from the validated final envelope.
        assert events[3][1] == "stream bare"

        # Smart-search was invoked exactly once.
        assert calls == ["stream bare"]
    finally:
        server.shutdown_and_close()


def test_explicit_evidence_scaffold_skips_smart_search(monkeypatch):
    """An explicit evidence-bearing scaffold is respected and not re-fetched."""
    calls: list[str] = []
    monkeypatch.setattr(
        _handoff_mod,
        "_cli_smart_search",
        lambda q: calls.append(q) or _scaffold_with_evidence(),
    )

    explicit_scaffold = {
        "intent": "explicit",
        "queries": ["work"],
        "evidence_pack": {
            "items": [
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-05_001.md",
                        "title": "Work day",
                        "date": "2026-06-05",
                    },
                    "snippet": "Busy day at the office.",
                },
            ],
        },
    }

    manager = _FakeManagerWithEvidence()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={"query": "hello explicit", "scaffold": explicit_scaffold},
        )
        assert status == 200
        # Smart-search must NOT be called for an explicit evidence-bearing scaffold.
        assert calls == []
        # Manager received the explicit scaffold unchanged.
        assert len(manager.queries) == 1
        passed_scaffold = manager.queries[0][1]
        assert passed_scaffold["intent"] == "explicit"
        assert passed_scaffold["evidence_pack"]["items"][0]["document"]["doc_id"] == (
            "Journals/2026/06/life-index_2026-06-05_001.md"
        )
    finally:
        server.shutdown_and_close()


def test_empty_scaffold_still_no_llm_fallback(monkeypatch):
    """Empty smart-search result is passed through; manager decides UNGROUNDED honestly."""
    calls: list[str] = []
    monkeypatch.setattr(
        _handoff_mod,
        "_cli_smart_search",
        lambda q: calls.append(q) or {},
    )

    manager = _FakeManagerUngrounded()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={"query": "hello empty"},
        )
        assert status == 200
        assert body["mode"] == "UNGROUNDED"
        assert body["answer"]["gap"] == "no relevant evidence"
        # No LLM fallback happened: manager was called with the empty scaffold.
        assert len(manager.queries) == 1
        assert manager.queries[0][1] == {}
    finally:
        server.shutdown_and_close()


def test_scaffold_builder_failure_degrades_honestly(monkeypatch):
    """Smart-search failure degrades to UNGROUNDED without a direct LLM fallback."""
    calls: list[str] = []

    def _failing_search(query: str) -> dict:
        calls.append(query)
        raise RuntimeError("smart-search subprocess failed")

    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", _failing_search)

    manager = _FakeManagerWithEvidence()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={"query": "hello failure"},
        )
        assert status == 200
        assert body["mode"] == "UNGROUNDED"
        assert body["provenance"]["degraded"] is True
        assert (
            "scaffold" in body["answer"]["gap"].lower() or "search" in body["answer"]["gap"].lower()
        )
        # Manager (ACP synthesis) must NOT be called when scaffold assembly fails.
        assert len(manager.queries) == 0
    finally:
        server.shutdown_and_close()


def test_scaffold_builder_failure_sse_emits_error_event(monkeypatch):
    """Smart-search failure on SSE emits an error event carrying a degraded envelope."""
    calls: list[str] = []
    monkeypatch.setattr(
        _handoff_mod,
        "_cli_smart_search",
        lambda q: calls.append(q) or (_ for _ in ()).throw(RuntimeError("search failed")),
    )

    manager = _FakeManagerWithEvidence()
    server = _start_server_with_manager(manager)
    try:
        status, raw = _request_raw(
            server,
            "/query/stream",
            method="POST",
            data={"query": "stream failure"},
        )
        assert status == 200
        events = _parse_sse_events(raw)
        names = [e[0] for e in events]
        assert "status" in names
        assert "scaffold" in names
        assert "error" in names
        # The error envelope is rich UNGROUNDED/degraded.
        error_event = [e for e in events if e[0] == "error"][0]
        envelope = error_event[1]["envelope"]
        assert envelope["mode"] == "UNGROUNDED"
        assert envelope["provenance"]["degraded"] is True
        # No ACP synthesis happened.
        assert len(manager.queries) == 0
    finally:
        server.shutdown_and_close()


def _real_shape_blank_evidence_scaffold() -> dict:
    """Return the real smart-search shape observed in lead WSL smoke.

    The evidence item carries a doc_id but an empty snippet; filtered_results
    has no snippet/abstract/content.  The gateway must hydrate this via the L2
    ``search --read-top`` CLI before ACP synthesis.
    """
    return {
        "intent": "recall",
        "query_plan": {
            "raw_query": "TB1_HERMES_ACP_SANDBOX_MARKER",
            "expanded_query": "TB1_HERMES_ACP_SANDBOX_MARKER",
            "sub_queries": ["TB1_HERMES_ACP_SANDBOX_MARKER"],
            "strategy": "keyword_only",
        },
        "evidence_pack": {
            "items": [
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-10_001.md",
                        "title": "Team offsite",
                        "date": "2026-06-10",
                    },
                    "snippet": "",
                },
            ],
        },
        "filtered_results": [
            {
                "rel_path": "Journals/2026/06/life-index_2026-06-10_001.md",
                "title": "Team offsite",
                "date": "2026-06-10",
            },
        ],
    }


def test_bare_gateway_hydrates_blank_evidence_from_l2_search(monkeypatch):
    """Bare /query triggers smart-search and then hydrates blank snippets from L2 search."""
    smart_calls: list[str] = []
    search_calls: list[list[str]] = []

    def _fake_smart_search(q: str) -> dict:
        smart_calls.append(q)
        return _real_shape_blank_evidence_scaffold()

    def _fake_search_read_top(*args: str) -> dict:
        search_calls.append(list(args))
        return {
            "success": True,
            "merged_results": [
                {
                    "rel_path": "Journals/2026/06/life-index_2026-06-10_001.md",
                    "snippet": "We discussed the <mark>roadmap</mark> for Q3.",
                    "full_content": "Full journal body with <mark>roadmap</mark> details.",
                },
            ],
        }

    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", _fake_smart_search)
    monkeypatch.setattr(_handoff_mod, "_cli_search_read_top", _fake_search_read_top)

    class _FakeManagerHydratedEvidence(_FakeManagerWithEvidence):
        def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
            self.queries.append((query, scaffold, stream_callback))
            return {
                "schema_version": QUERY_SCHEMA_VERSION,
                "status": "GROUNDED",
                "answer": query,
                "insights": [
                    {
                        "text": "t",
                        "evidence_refs": ["Journals/2026/06/life-index_2026-06-10_001.md"],
                    },
                ],
                "evidence_refs": ["Journals/2026/06/life-index_2026-06-10_001.md"],
                "gap": None,
                "provenance": {
                    "transport": "acp",
                    "model": "test",
                    "runtime": "test",
                    "degraded": False,
                },
                "usage": None,
            }

    manager = _FakeManagerHydratedEvidence()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={"query": "hello hydrate"},
        )
        assert status == 200
        assert body["mode"] == "GROUNDED"
        assert len(body["evidence"]) == 1
        # Hydrated text prefers full_content and strips <mark> tags.
        assert body["evidence"][0]["snippet"] == "Full journal body with roadmap details."
        assert body["evidence"][0]["id"] == "2026/06/life-index_2026-06-10_001"

        # The resolved scaffold passed to the manager has hydrated snippets.
        assert len(manager.queries) == 1
        passed_scaffold = manager.queries[0][1]
        assert passed_scaffold["evidence_pack"]["items"][0]["snippet"] == (
            "Full journal body with roadmap details."
        )
        assert passed_scaffold["filtered_results"][0].get("snippet") == (
            "Full journal body with roadmap details."
        )

        # smart-search was invoked exactly once.
        assert smart_calls == ["hello hydrate"]
        # L2 hydration was invoked exactly once because the evidence was blank.
        assert len(search_calls) == 1
    finally:
        server.shutdown_and_close()


def test_bare_gateway_hydrates_blank_evidence_sse(monkeypatch):
    """Bare SSE query hydrates blank evidence and emits a populated scaffold event."""
    smart_calls: list[str] = []
    search_calls: list[list[str]] = []

    def _fake_smart_search(q: str) -> dict:
        smart_calls.append(q)
        return _real_shape_blank_evidence_scaffold()

    def _fake_search_read_top(*args: str) -> dict:
        search_calls.append(list(args))
        return {
            "success": True,
            "merged_results": [
                {
                    "rel_path": "Journals/2026/06/life-index_2026-06-10_001.md",
                    "snippet": "We discussed the <mark>roadmap</mark> for Q3.",
                    "full_content": "Full journal body with <mark>roadmap</mark> details.",
                },
            ],
        }

    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", _fake_smart_search)
    monkeypatch.setattr(_handoff_mod, "_cli_search_read_top", _fake_search_read_top)

    class _FakeManagerHydratedEvidence(_FakeManagerWithEvidence):
        def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
            self.queries.append((query, scaffold, stream_callback))
            return {
                "schema_version": QUERY_SCHEMA_VERSION,
                "status": "GROUNDED",
                "answer": query,
                "insights": [
                    {
                        "text": "t",
                        "evidence_refs": ["Journals/2026/06/life-index_2026-06-10_001.md"],
                    },
                ],
                "evidence_refs": ["Journals/2026/06/life-index_2026-06-10_001.md"],
                "gap": None,
                "provenance": {
                    "transport": "acp",
                    "model": "test",
                    "runtime": "test",
                    "degraded": False,
                },
                "usage": None,
            }

    manager = _FakeManagerHydratedEvidence()
    server = _start_server_with_manager(manager)
    try:
        status, raw = _request_raw(
            server,
            "/query/stream",
            method="POST",
            data={"query": "stream hydrate"},
        )
        assert status == 200
        events = _parse_sse_events(raw)
        names = [e[0] for e in events]
        assert names == ["status", "scaffold", "evidence", "delta", "final"], f"got {names}"

        # Scaffold event now carries real smart-search shape with sub_queries fallback.
        scaffold_event = events[1][1]
        assert scaffold_event["queries"] == ["TB1_HERMES_ACP_SANDBOX_MARKER"]

        # Evidence event is populated from hydrated snippets.
        evidence_event = events[2][1]
        assert len(evidence_event) == 1
        assert evidence_event[0]["snippet"] == "Full journal body with roadmap details."

        assert smart_calls == ["stream hydrate"]
        assert len(search_calls) == 1
    finally:
        server.shutdown_and_close()


def test_explicit_nonblank_evidence_scaffold_skips_hydration(monkeypatch):
    """An explicit non-blank scaffold is respected; no smart-search or hydration."""
    smart_calls: list[str] = []
    search_calls: list[list[str]] = []

    monkeypatch.setattr(
        _handoff_mod,
        "_cli_smart_search",
        lambda q: smart_calls.append(q) or _real_shape_blank_evidence_scaffold(),
    )
    monkeypatch.setattr(
        _handoff_mod,
        "_cli_search_read_top",
        lambda *args: search_calls.append(list(args)) or {"success": True, "merged_results": []},
    )

    explicit_scaffold = {
        "intent": "explicit",
        "queries": ["work"],
        "evidence_pack": {
            "items": [
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-05_001.md",
                        "title": "Work day",
                        "date": "2026-06-05",
                    },
                    "snippet": "Busy day at the office.",
                },
            ],
        },
    }

    manager = _FakeManagerWithEvidence()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={"query": "hello explicit", "scaffold": explicit_scaffold},
        )
        assert status == 200
        # No smart-search or hydration for explicit evidence-bearing scaffolds.
        assert smart_calls == []
        assert search_calls == []
        # Manager received the explicit scaffold unchanged.
        assert len(manager.queries) == 1
        passed_scaffold = manager.queries[0][1]
        assert passed_scaffold["intent"] == "explicit"
        assert passed_scaffold["evidence_pack"]["items"][0]["snippet"] == "Busy day at the office."
    finally:
        server.shutdown_and_close()


def test_explicit_blank_evidence_scaffold_hydrates_without_smart_search(monkeypatch):
    """An explicit blank evidence scaffold is hydrated without repeating smart-search."""
    smart_calls: list[str] = []
    search_calls: list[tuple[str, int]] = []

    def _fake_smart_search(q: str) -> dict:
        smart_calls.append(q)
        raise AssertionError("explicit evidence scaffold must not re-run smart-search")

    def _fake_search_read_top(query: str, limit: int = 10) -> dict:
        search_calls.append((query, limit))
        return {
            "success": True,
            "merged_results": [
                {
                    "rel_path": "Journals/2026/06/life-index_2026-06-10_001.md",
                    "snippet": "",
                    "full_content": (
                        "Explicit scaffold content with <mark>Hermes ACP</mark> detail."
                    ),
                },
            ],
        }

    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", _fake_smart_search)
    monkeypatch.setattr(_handoff_mod, "_cli_search_read_top", _fake_search_read_top)

    class _FakeManagerHydratedExplicit(_FakeManagerWithEvidence):
        def query(self, query: str, scaffold: dict, stream_callback: Any = None) -> dict:
            self.queries.append((query, scaffold, stream_callback))
            return {
                "schema_version": QUERY_SCHEMA_VERSION,
                "status": "GROUNDED",
                "answer": query,
                "insights": [
                    {
                        "text": "t",
                        "evidence_refs": ["Journals/2026/06/life-index_2026-06-10_001.md"],
                    },
                ],
                "evidence_refs": ["Journals/2026/06/life-index_2026-06-10_001.md"],
                "gap": None,
                "provenance": {
                    "transport": "acp",
                    "model": "test",
                    "runtime": "test",
                    "degraded": False,
                },
                "usage": None,
            }

    manager = _FakeManagerHydratedExplicit()
    server = _start_server_with_manager(manager)
    try:
        status, body = _request(
            server,
            "/query",
            method="POST",
            data={
                "query": "hello explicit blank",
                "scaffold": _real_shape_blank_evidence_scaffold(),
            },
        )
        assert status == 200
        assert body["mode"] == "GROUNDED"
        assert body["evidence"][0]["snippet"] == (
            "Explicit scaffold content with Hermes ACP detail."
        )

        assert smart_calls == []
        assert search_calls == [("Journals/2026/06/life-index_2026-06-10_001.md", 1)]
        assert len(manager.queries) == 1
        passed_scaffold = manager.queries[0][1]
        assert passed_scaffold["evidence_pack"]["items"][0]["snippet"] == (
            "Explicit scaffold content with Hermes ACP detail."
        )
    finally:
        server.shutdown_and_close()


# ─── V6-CA Fixup 2 RED tests: hydration fallback + skip-when-present ─────


def test_build_gateway_scaffold_skips_hydration_when_evidence_has_text(monkeypatch):
    """When smart-search items already carry text, no _cli_search_read_top call is made."""
    search_calls: list[tuple[str, int]] = []

    def _fake_search_read_top(query: str, limit: int = 10) -> dict:
        search_calls.append((query, limit))
        return {"success": True, "merged_results": []}

    monkeypatch.setattr(_handoff_mod, "_cli_search_read_top", _fake_search_read_top)

    scaffold_with_text = {
        "intent": "recall",
        "evidence_pack": {
            "items": [
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-10_001.md",
                        "title": "Team offsite",
                        "date": "2026-06-10",
                    },
                    "snippet": "Already have text.",
                },
            ],
        },
        "filtered_results": [
            {
                "rel_path": "Journals/2026/06/life-index_2026-06-10_001.md",
                "title": "Team offsite",
                "date": "2026-06-10",
                "abstract": "Filtered result already has text.",
            },
        ],
    }
    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", lambda _q: scaffold_with_text)

    result = _handoff_mod.build_gateway_scaffold("query with text")

    assert result == scaffold_with_text
    assert search_calls == []


def test_hydration_reads_doc_id_before_original_query_fallback(monkeypatch):
    """Blank items are hydrated by doc_id/rel_path before trying the original query."""
    smart_calls: list[str] = []
    search_calls: list[tuple[str, int]] = []

    def _fake_smart_search(q: str) -> dict:
        smart_calls.append(q)
        return _real_shape_blank_evidence_scaffold()

    def _fake_search_read_top(query: str, limit: int = 10) -> dict:
        search_calls.append((query, limit))
        if query == "hello fallback":
            return {
                "success": True,
                "merged_results": [
                    {
                        "rel_path": "Journals/2026/06/life-index_2026-06-10_001.md",
                        "snippet": "",
                        "full_content": None,
                    },
                ],
            }
        if query == "Journals/2026/06/life-index_2026-06-10_001.md":
            return {
                "success": True,
                "merged_results": [
                    {
                        "rel_path": "Journals/2026/06/life-index_2026-06-10_001.md",
                        "snippet": "Doc id search snippet.",
                        "full_content": "Doc id search full content.",
                    },
                ],
            }
        return {"success": True, "merged_results": []}

    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", _fake_smart_search)
    monkeypatch.setattr(_handoff_mod, "_cli_search_read_top", _fake_search_read_top)

    result = _handoff_mod.build_gateway_scaffold("hello fallback")

    # Hydrated from doc_id fallback search (full_content preferred, mark tags stripped).
    assert result["evidence_pack"]["items"][0]["snippet"] == "Doc id search full content."
    assert result["filtered_results"][0].get("snippet") == "Doc id search full content."

    assert smart_calls == ["hello fallback"]
    assert search_calls == [("Journals/2026/06/life-index_2026-06-10_001.md", 1)]


def test_hydration_normalizes_absolute_and_journal_paths(monkeypatch):
    """Absolute Windows paths and Journals/... IDs both resolve to the same lookup key."""

    def _fake_smart_search(_q: str) -> dict:
        return {
            "intent": "recall",
            "evidence_pack": {
                "items": [
                    {
                        "document": {
                            "doc_id": "Journals/2026/06/life-index_2026-06-10_001.md",
                            "title": "Team offsite",
                        },
                        "snippet": "",
                    },
                ],
            },
        }

    def _fake_search_read_top(query: str, limit: int = 10) -> dict:
        if query == "hello normalize":
            # Return with an absolute-style path to exercise normalization.
            return {
                "success": True,
                "merged_results": [
                    {
                        "path": "D:/Life Index/Journals/2026/06/life-index_2026-06-10_001.md",
                        "snippet": "Absolute path snippet.",
                    },
                ],
            }
        return {"success": True, "merged_results": []}

    monkeypatch.setattr(_handoff_mod, "_cli_smart_search", _fake_smart_search)
    monkeypatch.setattr(_handoff_mod, "_cli_search_read_top", _fake_search_read_top)

    result = _handoff_mod.build_gateway_scaffold("hello normalize")

    assert result["evidence_pack"]["items"][0]["snippet"] == "Absolute path snippet."


# ─── V6-CA ACP prompt warmup integration tests ────────────────────────


def test_build_server_calls_acp_prompt_warmup_by_default(monkeypatch):
    """_build_server calls manager.warm_acp_prompt() by default after scaffold warmup."""
    cfg = _brain_config()

    # Use a fake warm connection that records rpc calls.
    warm_calls: list[str] = []
    call_order: list[str] = []
    monkeypatch.setattr(
        _handoff_mod,
        "warm_gateway_scaffold_path",
        lambda: call_order.append("scaffold") or {"ok": True, "error_message": None},
    )

    class _TrackedConn:
        pid = 12345
        session_id = "tracked-session"
        initialize_result = {"serverInfo": {"name": "tracked-acp"}}
        session_new_result = {"sessionId": "tracked-session", "model": "tracked-model"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def is_alive(self):
            return True

        def close(self):
            pass

        def rpc(self, method, params):
            warm_calls.append(method)
            call_order.append(method)
            return {"result": {"ok": True}}

    server, manager = _build_server(
        "127.0.0.1",
        0,
        cfg,
        connection_factory=lambda *a, **k: _TrackedConn(),
        adapter=lambda *a, **k: _success_envelope(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # scaffold warmup was called first (it's part of _build_server)
        # ACP prompt warmup was called after scaffold warmup
        assert (
            "session/prompt" in warm_calls
        ), f"ACP prompt warmup not called; warm_calls={warm_calls}"
        assert call_order == ["scaffold", "session/prompt"]
        # Manager was started before warmup.
        assert manager._last_warm_error is None
    finally:
        server.shutdown_and_close()


def test_build_server_skips_acp_warmup_when_env_opt_out(monkeypatch):
    """_build_server does NOT call warm_acp_prompt when env var opts out."""
    monkeypatch.setenv(_ACP_WARMUP_PROMPT_ENV, "0")
    monkeypatch.setattr(
        _handoff_mod,
        "warm_gateway_scaffold_path",
        lambda: {"ok": True, "error_message": None},
    )

    cfg = _brain_config()
    warm_calls: list[str] = []

    class _TrackedConn:
        pid = 12345
        session_id = "tracked-session"
        initialize_result = {"serverInfo": {"name": "tracked-acp"}}
        session_new_result = {"sessionId": "tracked-session", "model": "tracked-model"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def is_alive(self):
            return True

        def close(self):
            pass

        def rpc(self, method, params):
            warm_calls.append(method)
            return {"result": {"ok": True}}

    server, manager = _build_server(
        "127.0.0.1",
        0,
        cfg,
        connection_factory=lambda *a, **k: _TrackedConn(),
        adapter=lambda *a, **k: _success_envelope(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # session/prompt must NOT appear — opt-out suppressed the warmup.
        assert (
            "session/prompt" not in warm_calls
        ), f"ACP prompt warmup was called despite opt-out; warm_calls={warm_calls}"
    finally:
        server.shutdown_and_close()


def test_acp_warmup_failure_does_not_crash_build_server(monkeypatch):
    """warm_acp_prompt() failure does NOT crash _build_server()."""
    cfg = _brain_config()
    monkeypatch.setattr(
        _handoff_mod,
        "warm_gateway_scaffold_path",
        lambda: {"ok": True, "error_message": None},
    )

    class _FailingConn:
        pid = 12345
        session_id = "failing-session"
        initialize_result = {"serverInfo": {"name": "failing-acp"}}
        session_new_result = {"sessionId": "failing-session", "model": "failing-model"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def is_alive(self):
            return True

        def close(self):
            pass

        def rpc(self, method, params):
            raise RuntimeError("ACP prompt warmup exploded")

    server, manager = _build_server(
        "127.0.0.1",
        0,
        cfg,
        connection_factory=lambda *a, **k: _FailingConn(),
        adapter=lambda *a, **k: _success_envelope(),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Server must still start and serve healthz.
        status, body = _request(server, "/healthz")
        assert status == 200
        # Health must remain warm — warmup failure does not degrade.
        assert body["state"] == "warm"
        assert body["pid"] == 12345
        assert body["last_warm_error"] is None
    finally:
        server.shutdown_and_close()


def test_env_opt_out_accepts_all_disable_values(monkeypatch):
    """All documented opt-out values suppress the warmup."""
    monkeypatch.setattr(
        _handoff_mod,
        "warm_gateway_scaffold_path",
        lambda: {"ok": True, "error_message": None},
    )
    for disable_val in sorted(_ACP_WARMUP_PROMPT_DISABLE_VALUES):
        monkeypatch.setenv(_ACP_WARMUP_PROMPT_ENV, disable_val)

        cfg = _brain_config()
        warm_calls: list[str] = []

        class _TrackedConn:
            pid = 12345
            session_id = f"s-{disable_val}"
            initialize_result = {"serverInfo": {"name": "tracked-acp"}}
            session_new_result = {"sessionId": f"s-{disable_val}", "model": "tracked-model"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def is_alive(self):
                return True

            def close(self):
                pass

            def rpc(self, method, params):
                warm_calls.append(method)
                return {"result": {"ok": True}}

        server, manager = _build_server(
            "127.0.0.1",
            0,
            cfg,
            connection_factory=lambda *a, **k: _TrackedConn(),
            adapter=lambda *a, **k: _success_envelope(),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            assert (
                "session/prompt" not in warm_calls
            ), f"ACP prompt warmup called despite env={disable_val!r}"
        finally:
            server.shutdown_and_close()


def test_build_server_acp_warmup_uses_existing_connection(monkeypatch):
    """The ACP prompt warmup uses the warm connection, not manager.query()."""
    cfg = _brain_config()
    monkeypatch.setattr(
        _handoff_mod,
        "warm_gateway_scaffold_path",
        lambda: {"ok": True, "error_message": None},
    )

    query_calls: list[str] = []
    rpc_calls: list[str] = []

    class _TrackedConn:
        pid = 12345
        session_id = "existing-session"
        initialize_result = {"serverInfo": {"name": "existing-acp"}}
        session_new_result = {"sessionId": "existing-session", "model": "existing-model"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def is_alive(self):
            return True

        def close(self):
            pass

        def rpc(self, method, params):
            rpc_calls.append(method)
            return {"result": {"ok": True}}

    def tracking_adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        query_calls.append(query)
        return _success_envelope()

    server, manager = _build_server(
        "127.0.0.1",
        0,
        cfg,
        connection_factory=lambda *a, **k: _TrackedConn(),
        adapter=tracking_adapter,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # The warmup used conn.rpc() (direct), NOT the query adapter.
        assert "session/prompt" in rpc_calls
        assert (
            len(query_calls) == 0
        ), "manager.query() was called during warmup; expected conn.rpc() only"
    finally:
        server.shutdown_and_close()
