"""Unit tests for the warm ACP session manager."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.agent_bridge.acp_session_manager import (  # noqa: E402
    ACPWarmSessionManager,
    _WARM_HANDSHAKE_TIMEOUT,
    _WARM_RPC_TIMEOUT,
)
from tools.agent_bridge.config import BrainConfig  # noqa: E402

QUERY_SCHEMA_VERSION = "m35.agent_bridge_query.v0"


def _brain_config() -> BrainConfig:
    return BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
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


class _FakeConn:
    """Stand-in for ``_ACPConnection`` that tracks liveness and close calls."""

    def __init__(self, name: str = "fake", alive: bool = True) -> None:
        self.name = name
        self.alive = alive
        self.closed = False

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def is_alive(self) -> bool:
        return self.alive and not self.closed

    def close(self) -> None:
        self.closed = True
        self.alive = False


def test_ensure_warm_retries_and_reuses_successful_connection():
    """Failed warm-up attempts are retried; a successful conn is reused."""
    created = []

    def factory(*args, **kwargs):
        created.append(len(created) + 1)
        if len(created) < 3:
            raise RuntimeError(f"warm-up failure #{len(created)}")
        return _FakeConn(name=f"conn-{len(created)}")

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, warm_attempts=3)

    conn = mgr.ensure_warm()
    assert conn is not None
    assert conn.name == "conn-3"
    assert len(created) == 3

    # A second call must reuse the same connection.
    conn2 = mgr.ensure_warm()
    assert conn2 is conn
    assert len(created) == 3


def test_ensure_warm_uses_wider_timeouts():
    """Warm-up connections are created with wider RPC/handshake timeouts."""
    captured = {}

    def factory(cfg, *, rpc_timeout=None, handshake_timeout=None):
        captured["rpc_timeout"] = rpc_timeout
        captured["handshake_timeout"] = handshake_timeout
        return _FakeConn()

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.ensure_warm()

    assert captured["rpc_timeout"] == _WARM_RPC_TIMEOUT
    assert captured["handshake_timeout"] == _WARM_HANDSHAKE_TIMEOUT


def test_query_reuses_warm_connection():
    """Two sequential queries on one manager share a single warm connection."""
    created = []

    def factory(*args, **kwargs):
        created.append(_FakeConn(name=f"conn-{len(created) + 1}"))
        return created[-1]

    calls = []

    def adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        calls.append((query, connection))
        return _success_envelope(answer=query)

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, adapter=adapter)

    r1 = mgr.query("q1", {})
    r2 = mgr.query("q2", {})

    assert len(created) == 1
    assert len(calls) == 2
    assert calls[0][0] == "q1"
    assert calls[1][0] == "q2"
    assert calls[0][1] is created[0]
    assert calls[1][1] is created[0]
    assert r1["answer"] == "q1"
    assert r2["answer"] == "q2"


def test_query_reconnects_when_connection_dies():
    """A dead connection during query is replaced and the query is retried."""
    created = []

    def factory(*args, **kwargs):
        created.append(_FakeConn(name=f"conn-{len(created) + 1}", alive=True))
        return created[-1]

    def adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        if connection.name == "conn-1":
            # Simulate a transport death that the adapter degrades on.
            connection.alive = False
            return _degraded_envelope(gap="transport died")
        return _success_envelope(answer="retry-ok")

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, adapter=adapter)

    result = mgr.query("q", {})

    assert len(created) == 2
    assert created[0].closed is True
    assert result["status"] == "GROUNDED"
    assert result["answer"] == "retry-ok"


def test_query_retry_exhaustion_returns_degraded_envelope():
    """When reconnect + retry also fails, a degraded envelope is returned."""
    created = []

    def factory(*args, **kwargs):
        created.append(_FakeConn(name=f"conn-{len(created) + 1}", alive=True))
        return created[-1]

    def adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        # Every query sees a dead connection and degrades.
        connection.alive = False
        return _degraded_envelope(gap="still dead")

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, adapter=adapter)

    result = mgr.query("q", {})

    # First warm connection + one reconnect = 2 total creations.
    assert len(created) == 2
    assert created[0].closed is True
    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "UNGROUNDED"
    assert result["provenance"]["degraded"] is True


def test_query_serializes_concurrent_calls():
    """Concurrent queries do not overlap inside the manager lock."""

    def factory(*args, **kwargs):
        return _FakeConn()

    active = [0]
    max_active = [0]
    lock = threading.Lock()

    def adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        with lock:
            active[0] += 1
            max_active[0] = max(max_active[0], active[0])
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return _success_envelope(answer=query)

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, adapter=adapter)

    results = []

    def run(query):
        results.append(mgr.query(query, {}))

    t1 = threading.Thread(target=run, args=("q1",))
    t2 = threading.Thread(target=run, args=("q2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert max_active[0] == 1
    assert len(results) == 2


def test_query_forwards_stream_callback():
    """The stream_callback argument is passed through to the adapter."""

    def factory(*args, **kwargs):
        return _FakeConn()

    captured = {}

    def adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        captured["stream_callback"] = stream_callback
        return _success_envelope()

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, adapter=adapter)

    def cb(chunk: str) -> None:
        pass

    mgr.query("q", {}, stream_callback=cb)
    assert captured["stream_callback"] is cb


def test_close_is_idempotent_and_tears_down_connection():
    """close() shuts down the warm connection and can be called repeatedly."""
    conn = _FakeConn()

    def factory(*args, **kwargs):
        return conn

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.ensure_warm()
    assert conn.closed is False

    mgr.close()
    assert conn.closed is True
    assert mgr._closed is True

    # Idempotent: no exception on second close.
    mgr.close()
    assert conn.closed is True


def test_query_after_close_returns_degraded():
    """Queries after close() degrade deterministically instead of crashing."""

    def factory(*args, **kwargs):
        return _FakeConn()

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.close()

    result = mgr.query("q", {})
    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "UNGROUNDED"
    assert result["provenance"]["degraded"] is True


def test_start_prewarms_connection():
    """start() eagerly creates the warm connection."""
    created = []

    def factory(*args, **kwargs):
        created.append(_FakeConn())
        return created[-1]

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.start()

    assert len(created) == 1
    assert mgr._warm_conn is created[0]


def test_ensure_warm_failure_leads_to_degraded_query():
    """If warm-up fails entirely, query returns a degraded envelope."""

    def factory(*args, **kwargs):
        raise RuntimeError("warm-up always fails")

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, warm_attempts=2)

    result = mgr.query("q", {})
    assert result["schema_version"] == QUERY_SCHEMA_VERSION
    assert result["status"] == "UNGROUNDED"
    assert result["provenance"]["degraded"] is True
    assert "unavailable" in result["gap"].lower()


def test_query_uses_passed_cfg():
    """The cfg argument to query() is forwarded to the adapter."""
    passed_cfg = []

    def factory(cfg, *, rpc_timeout=None, handshake_timeout=None):
        passed_cfg.append(("factory", cfg))
        return _FakeConn()

    def adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        passed_cfg.append(("adapter", cfg))
        return _success_envelope()

    cfg = _brain_config()
    mgr = ACPWarmSessionManager(cfg, connection_factory=factory, adapter=adapter)
    mgr.query("q", {}, cfg)

    assert ("factory", cfg) in passed_cfg
    assert ("adapter", cfg) in passed_cfg


def test_query_does_not_retry_on_validation_degrade_with_alive_connection():
    """A degraded result with a still-alive connection does not trigger retry."""
    created = []

    def factory(*args, **kwargs):
        created.append(_FakeConn(alive=True))
        return created[-1]

    calls = [0]

    def adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        calls[0] += 1
        # Degraded for a non-transport reason, connection stays alive.
        return _degraded_envelope(gap="model validation failed")

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, adapter=adapter)

    result = mgr.query("q", {})

    assert len(created) == 1
    assert calls[0] == 1
    assert result["status"] == "UNGROUNDED"
    assert "validation failed" in result["gap"]
