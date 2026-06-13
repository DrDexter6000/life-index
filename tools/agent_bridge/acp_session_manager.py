"""Warm ACP session manager for the Life Index agent bridge.

V5b phase 1: owns one warm ``_ACPConnection`` and one lock.  Provides
``start()``, ``ensure_warm()``, ``query()``, and ``close()``.  Queries are
serialized through the manager lock; a dead connection triggers one reconnect
and one retry before returning a deterministic degraded envelope.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

from tools.agent_bridge.acp_client import _ACPConnection
from tools.agent_bridge.acp_query import (
    acp_query_adapter,
    build_degraded_result,
    build_provenance,
)
from tools.agent_bridge.config import BrainConfig

# Warm-up is intentionally wider than normal query RPCs because spawning and
# handshaking an ACP runtime can take longer than a single in-session prompt.
# V5b-1 spec: generous cold-start budget for ACP runtime boot + handshake.
_WARM_RPC_TIMEOUT = 180.0
_WARM_HANDSHAKE_TIMEOUT = 180.0
_DEFAULT_WARM_ATTEMPTS = 3


class ACPWarmSessionManager:
    """Owns a single warm ACP connection and serializes queries over it."""

    def __init__(
        self,
        cfg: BrainConfig,
        *,
        connection_factory: Callable[..., _ACPConnection] = _ACPConnection,
        adapter: Callable[..., dict[str, Any]] = acp_query_adapter,
        warm_attempts: int = _DEFAULT_WARM_ATTEMPTS,
        warm_rpc_timeout: float = _WARM_RPC_TIMEOUT,
        warm_handshake_timeout: float | None = _WARM_HANDSHAKE_TIMEOUT,
    ) -> None:
        self._cfg = cfg
        self._connection_factory = connection_factory
        self._adapter = adapter
        self._warm_attempts = max(1, warm_attempts)
        self._warm_rpc_timeout = warm_rpc_timeout
        self._warm_handshake_timeout = warm_handshake_timeout

        self._lock = threading.RLock()
        self._warm_conn: _ACPConnection | None = None
        self._closed = False
        self._last_warm_error: str | None = None

    # ── Public lifecycle ────────────────────────────────────────────────

    def start(self) -> "ACPWarmSessionManager":
        """Eagerly prewarm the connection.

        If warm-up fails, the manager records the error and returns without
        raising so that callers (e.g. a localhost service) can start in a
        degraded state.
        """
        try:
            self.ensure_warm()
        except Exception as exc:
            self._last_warm_error = str(exc)
        return self

    def close(self) -> None:
        """Idempotently tear down the warm connection."""
        with self._lock:
            self._drop_warm_conn()
            self._closed = True

    def health(self) -> dict[str, Any]:
        """Return a non-blocking health snapshot.

        Must not trigger a live probe or warm-up attempt.  Includes warm/cold/
        degraded state, transport/runtime/model metadata, and the last warm
        error if any.
        """
        with self._lock:
            conn = self._warm_conn
            alive = conn is not None and self._is_alive(conn)
            if alive:
                state = "warm"
            elif self._closed or self._last_warm_error:
                state = "degraded"
            else:
                state = "cold"

            conn_meta = self._conn_meta(conn)
            provenance = build_provenance(
                self._cfg, conn_meta=conn_meta, degraded=(state == "degraded")
            )

            return {
                "status": "ok",
                "state": state,
                "transport": provenance.get("transport", "acp"),
                "runtime": provenance.get("runtime", "acp"),
                "model": provenance.get("model", "unknown"),
                "pid": getattr(conn, "pid", None),
                "is_alive": alive,
                "last_warm_error": self._last_warm_error,
            }

    def _conn_meta(self, conn: _ACPConnection | None) -> dict | None:
        """Build conn_meta dict for provenance from a warm connection."""
        if conn is None:
            return None
        return {
            "session_id": getattr(conn, "session_id", ""),
            "initialize_result": getattr(conn, "initialize_result", None),
            "session_new_result": getattr(conn, "session_new_result", None),
        }

    def ensure_warm(self, cfg: BrainConfig | None = None) -> _ACPConnection:
        """Return a live warm connection, creating one if necessary.

        Retries failed warm-up attempts up to ``self._warm_attempts``.  Raises
        ``RuntimeError`` if no attempt succeeds; callers (e.g. ``query``) are
        expected to degrade deterministically instead of crashing.
        """
        cfg = cfg if cfg is not None else self._cfg
        with self._lock:
            if self._closed:
                raise RuntimeError("ACPWarmSessionManager is closed")

            if self._warm_conn is not None and self._is_alive(self._warm_conn):
                return self._warm_conn

            self._drop_warm_conn()
            last_error: Exception | None = None
            for _ in range(self._warm_attempts):
                conn: _ACPConnection | None = None
                try:
                    conn = self._connection_factory(
                        cfg,
                        rpc_timeout=self._warm_rpc_timeout,
                        handshake_timeout=self._warm_handshake_timeout,
                    )
                    conn.__enter__()
                    self._warm_conn = conn
                    return conn
                except Exception as exc:
                    self._last_warm_error = str(exc)
                    last_error = exc
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass

            raise RuntimeError(
                f"Failed to establish warm ACP session after {self._warm_attempts} attempts"
            ) from last_error

    def query(
        self,
        query: str,
        scaffold: dict,
        cfg: BrainConfig | None = None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run a query through the warm connection, reconnecting once if it died.

        The call is serialized through the manager lock.  If the connection
        dies during the query, it is discarded, a new warm connection is
        created, and the query is retried once.  If the retry still fails, a
        deterministic ``m35.agent_bridge_query.v0`` degraded envelope is
        returned.  No OpenAI-compatible fallback path is created.
        """
        cfg = cfg if cfg is not None else self._cfg
        with self._lock:
            if self._closed:
                return self._degraded(cfg, "ACPWarmSessionManager is closed")

            try:
                conn = self.ensure_warm(cfg)
            except Exception as exc:
                return self._degraded(cfg, f"ACP warm session unavailable: {exc}")

            result = self._run_query(query, scaffold, cfg, conn, stream_callback)
            if self._is_alive(conn):
                return result

            # Connection died during the query. Reconnect once and retry once.
            self._drop_warm_conn()
            try:
                conn = self.ensure_warm(cfg)
            except Exception:
                return result
            return self._run_query(query, scaffold, cfg, conn, stream_callback)

    # ── Internals ───────────────────────────────────────────────────────

    def _run_query(
        self,
        query: str,
        scaffold: dict,
        cfg: BrainConfig,
        conn: _ACPConnection,
        stream_callback: Callable[[str], None] | None,
    ) -> dict[str, Any]:
        try:
            return self._adapter(
                query,
                scaffold,
                cfg,
                connection=conn,
                stream_callback=stream_callback,
            )
        except Exception as exc:
            return self._degraded(cfg, f"ACP query adapter failed: {exc}")

    def _is_alive(self, conn: _ACPConnection) -> bool:
        try:
            return conn.is_alive()
        except Exception:
            return False

    def _drop_warm_conn(self) -> None:
        conn = self._warm_conn
        self._warm_conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _degraded(self, cfg: BrainConfig, gap: str) -> dict[str, Any]:
        provenance = build_provenance(cfg, conn_meta=None, degraded=True)
        return build_degraded_result("UNGROUNDED", gap, provenance)
