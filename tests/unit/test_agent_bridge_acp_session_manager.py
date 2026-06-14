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
    """Stand-in for ``_ACPConnection`` that tracks liveness, close calls, and rpc."""

    def __init__(self, name: str = "fake", alive: bool = True) -> None:
        self.name = name
        self.alive = alive
        self.closed = False
        self.session_id = "fake-session-id"
        self.rpc_calls: list[tuple[str, dict]] = []

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def is_alive(self) -> bool:
        return self.alive and not self.closed

    def close(self) -> None:
        self.closed = True
        self.alive = False

    def rpc(self, method: str, params: dict) -> dict:
        self.rpc_calls.append((method, params))
        return {"result": {"ok": True}}


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


# ─── Data-free ACP prompt warmup tests ─────────────────────────────────


def test_warm_acp_prompt_sends_session_prompt_rpc():
    """warm_acp_prompt() sends a session/prompt RPC through the warm connection."""
    conn = _FakeConn()

    def factory(*args, **kwargs):
        return conn

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.ensure_warm()

    assert len(conn.rpc_calls) == 0
    mgr.warm_acp_prompt()
    assert len(conn.rpc_calls) == 1
    method, params = conn.rpc_calls[0]
    assert method == "session/prompt"
    assert params["sessionId"] == "fake-session-id"
    assert params["prompt"] == [{"type": "text", "text": "READY"}]


def test_warm_acp_prompt_uses_default_ready_prompt():
    """The default warmup prompt is the READY constant — data-free."""
    conn = _FakeConn()

    def factory(*args, **kwargs):
        return conn

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.ensure_warm()
    mgr.warm_acp_prompt()
    assert len(conn.rpc_calls) == 1
    _, params = conn.rpc_calls[0]
    # The prompt payload must contain no journal evidence, scaffold text,
    # or user query content.
    prompt_text = params["prompt"][0]["text"]
    assert prompt_text == "READY"
    assert "evidence" not in prompt_text.lower()
    assert "journal" not in prompt_text.lower()
    assert "scaffold" not in prompt_text.lower()
    assert "query" not in prompt_text.lower()


def test_warm_acp_prompt_accepts_custom_prompt():
    """warm_acp_prompt() forwards a custom prompt string."""
    conn = _FakeConn()

    def factory(*args, **kwargs):
        return conn

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.ensure_warm()
    mgr.warm_acp_prompt(prompt="CUSTOM_PROMPT")
    _, params = conn.rpc_calls[0]
    assert params["prompt"][0]["text"] == "CUSTOM_PROMPT"


def test_warm_acp_prompt_skips_when_no_warm_connection():
    """warm_acp_prompt() returns immediately when no warm connection exists."""
    conn = _FakeConn()

    def factory(*args, **kwargs):
        return conn

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    # No ensure_warm() call — _warm_conn is None.
    mgr.warm_acp_prompt()
    assert len(conn.rpc_calls) == 0


def test_warm_acp_prompt_skips_when_connection_dead():
    """warm_acp_prompt() returns immediately when the connection is dead."""
    conn = _FakeConn(alive=False)

    def factory(*args, **kwargs):
        return conn

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.ensure_warm()
    mgr.warm_acp_prompt()
    assert len(conn.rpc_calls) == 0


def test_warm_acp_prompt_swallows_rpc_exception():
    """warm_acp_prompt() does not raise when rpc() fails."""
    conn = _FakeConn()

    def failing_rpc(method, params):
        raise RuntimeError("rpc exploded")

    conn.rpc = failing_rpc  # type: ignore[method-assign]

    def factory(*args, **kwargs):
        return conn

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.ensure_warm()

    # Must not raise.
    mgr.warm_acp_prompt()
    # Health must remain unchanged (not degraded by warmup failure).
    assert mgr._last_warm_error is None


def test_warm_acp_prompt_uses_warm_connection_not_manager_query():
    """warm_acp_prompt() uses conn.rpc() directly, not manager.query().

    This proves the warmup does not run the m35 evidence-bound query path.
    """
    conn = _FakeConn()
    query_called = [False]

    def factory(*args, **kwargs):
        return conn

    def fake_adapter(query, scaffold, cfg, *, connection=None, stream_callback=None):
        query_called[0] = True
        return _success_envelope()

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory, adapter=fake_adapter)
    mgr.ensure_warm()
    mgr.warm_acp_prompt()

    # rpc() was called directly, not through the query/adapter pipeline.
    assert len(conn.rpc_calls) == 1
    assert query_called[0] is False


def test_warm_acp_prompt_does_not_change_health_state():
    """warm_acp_prompt() failure does not mark the session manager as degraded."""
    conn = _FakeConn()

    def failing_rpc(method, params):
        raise RuntimeError("rpc exploded")

    conn.rpc = failing_rpc  # type: ignore[method-assign]

    def factory(*args, **kwargs):
        return conn

    mgr = ACPWarmSessionManager(_brain_config(), connection_factory=factory)
    mgr.ensure_warm()
    mgr.warm_acp_prompt()

    health = mgr.health()
    assert health["state"] == "warm"
    assert health["is_alive"] is True
    assert health["last_warm_error"] is None
