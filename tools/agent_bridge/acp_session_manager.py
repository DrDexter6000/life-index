"""Warm ACP session manager for the Life Index agent bridge.

V5b phase 1: owns one warm ``_ACPConnection`` and one lock.  Provides
``start()``, ``ensure_warm()``, ``query()``, and ``close()``.  Queries are
serialized through the manager lock; a dead connection triggers one reconnect
and one retry before returning a deterministic degraded envelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import re
import threading
import time
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
_MAX_WARM_ERROR_CHARS = 500
_DEFAULT_MAX_CONVERSATION_SESSIONS = 16
_DEFAULT_CONVERSATION_IDLE_TTL_SECONDS = 30 * 60
_DEFAULT_MAX_CONVERSATION_TRACE_REFS = 256

_SENSITIVE_VALUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)\b(?:api[_\s-]*key|token|authorization)\b\s*[:=]\s*" r"['\"]?[^\s,'\";\]}]+"
        ),
        "[redacted]",
    ),
    (re.compile(r"(?i)\bbearer\s+['\"]?[^\s,'\";\]}]+"), "[redacted]"),
    (re.compile(r"\b(?:sk|pk|rk|sess)-[A-Za-z0-9_-]{8,}\b"), "[redacted]"),
    (
        re.compile(r"(?i)(?:[A-Za-z]:)?(?:[/\\][^\s'\",;:]+)*[/\\]\.env" r"(?:[^\s'\",;:]*)?"),
        "[redacted]",
    ),
    (
        re.compile(
            r"(?i)(?:[A-Za-z]:)?(?:[/\\][^\s'\",;:]+)*[/\\]"
            r"(?:Documents[/\\]Life-Index|Life-Index[/\\]Journals|Journals)"
            r"(?:[/\\][^\s'\",;:]+)*"
        ),
        "[redacted]",
    ),
    (re.compile(r"(?i)\.env(?:\.[A-Za-z0-9_-]+)?"), "[redacted]"),
    (re.compile(r"(?i)\bjournals?\b"), "[redacted]"),
    (
        re.compile(r"(?i)\b(?:api[_\s-]*key|token|authorization|bearer)\b"),
        "[redacted]",
    ),
)

# Data-free prompt used for ACP session/prompt warmup on server start.
# Must contain no journal evidence, scaffold text, or user query content.
_DATA_FREE_READY_PROMPT = "READY"


@dataclass
class _ConversationSession:
    conn: _ACPConnection
    last_used: float
    tool_trace_refs: list[str] = field(default_factory=list)


def _sanitize_warm_error(error: object) -> str:
    """Return a health-safe warm error string with secrets/user-data paths removed."""
    text = str(error)
    for pattern, replacement in _SENSITIVE_VALUE_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > _MAX_WARM_ERROR_CHARS:
        return f"{text[:_MAX_WARM_ERROR_CHARS]}... [truncated]"
    return text


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
        max_conversation_sessions: int = _DEFAULT_MAX_CONVERSATION_SESSIONS,
        conversation_idle_ttl_seconds: float = _DEFAULT_CONVERSATION_IDLE_TTL_SECONDS,
        max_conversation_trace_refs: int = _DEFAULT_MAX_CONVERSATION_TRACE_REFS,
    ) -> None:
        self._cfg = cfg
        self._connection_factory = connection_factory
        self._adapter = adapter
        self._warm_attempts = max(1, warm_attempts)
        self._warm_rpc_timeout = warm_rpc_timeout
        self._warm_handshake_timeout = warm_handshake_timeout
        self._max_conversation_sessions = max(1, max_conversation_sessions)
        self._conversation_idle_ttl_seconds = max(1.0, conversation_idle_ttl_seconds)
        self._max_conversation_trace_refs = max(1, max_conversation_trace_refs)

        self._lock = threading.RLock()
        self._warm_conn: _ACPConnection | None = None
        self._conversation_sessions: dict[str, _ConversationSession] = {}
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
            if self._last_warm_error is None:
                self._last_warm_error = _sanitize_warm_error(exc)
        return self

    def warm_acp_prompt(self, prompt: str = _DATA_FREE_READY_PROMPT) -> None:
        """Send a data-free ``session/prompt`` RPC through the warm ACP connection.

        This is best-effort only: any exception is swallowed silently so that
        callers (e.g. a localhost service) can start without crashing.  The
        method uses the existing warm connection directly via ``conn.rpc()``
        rather than ``manager.query()`` to avoid the m35 evidence-bound query
        path.  No journal evidence, scaffold text, or user query content may
        appear in *prompt*.

        If the warm connection is not available, the method returns
        immediately without attempting a warm-up.
        """
        try:
            with self._lock:
                conn = self._warm_conn
                if conn is None or not self._is_alive(conn):
                    return
                conn.rpc(
                    "session/prompt",
                    {
                        "sessionId": conn.session_id,
                        "prompt": [{"type": "text", "text": prompt}],
                    },
                )
        except Exception:
            pass

    def close(self) -> None:
        """Idempotently tear down the warm connection."""
        with self._lock:
            self._drop_warm_conn()
            self._drop_all_conversation_sessions()
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
                    self._last_warm_error = None
                    return conn
                except Exception as exc:
                    self._last_warm_error = _sanitize_warm_error(exc)
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
        stream_callback: Callable[[Any], None] | None = None,
        conversation_id: str | None = None,
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

            if conversation_id:
                return self._query_conversation(
                    conversation_id,
                    query,
                    scaffold,
                    cfg,
                    stream_callback,
                )

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

    def _query_conversation(
        self,
        conversation_id: str,
        query: str,
        scaffold: dict,
        cfg: BrainConfig,
        stream_callback: Callable[[Any], None] | None,
    ) -> dict[str, Any]:
        try:
            conn = self._ensure_conversation_conn(conversation_id, cfg)
        except Exception as exc:
            return self._degraded(cfg, f"ACP conversation session unavailable: {exc}")

        prior_trace_refs = self._conversation_trace_snapshot(conversation_id)
        result = self._run_query(
            query,
            scaffold,
            cfg,
            conn,
            stream_callback,
            tool_trace_refs=prior_trace_refs,
            turn_trace_callback=lambda refs: self._add_conversation_trace_refs(
                conversation_id, conn, refs
            ),
        )
        if self._is_alive(conn):
            self._touch_conversation(conversation_id, conn)
            return result

        prior_trace_refs = self._conversation_trace_snapshot(conversation_id)
        self._drop_conversation_session(conversation_id)
        try:
            conn = self._ensure_conversation_conn(conversation_id, cfg)
        except Exception:
            return result
        self._set_conversation_trace_refs(conversation_id, prior_trace_refs)
        result = self._run_query(
            query,
            scaffold,
            cfg,
            conn,
            stream_callback,
            tool_trace_refs=prior_trace_refs,
            turn_trace_callback=lambda refs: self._add_conversation_trace_refs(
                conversation_id, conn, refs
            ),
        )
        if self._is_alive(conn):
            self._touch_conversation(conversation_id, conn)
        return result

    def _ensure_conversation_conn(self, conversation_id: str, cfg: BrainConfig) -> _ACPConnection:
        now = time.monotonic()
        self._prune_conversation_sessions(now)

        session = self._conversation_sessions.get(conversation_id)
        if session is not None and self._is_alive(session.conn):
            session.last_used = now
            return session.conn

        self._drop_conversation_session(conversation_id)
        self._evict_conversation_if_needed()

        conn = self._connection_factory(
            cfg,
            rpc_timeout=self._warm_rpc_timeout,
            handshake_timeout=self._warm_handshake_timeout,
        )
        try:
            conn.__enter__()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            raise

        self._conversation_sessions[conversation_id] = _ConversationSession(
            conn=conn,
            last_used=now,
        )
        return conn

    def _touch_conversation(self, conversation_id: str, conn: _ACPConnection) -> None:
        session = self._conversation_sessions.get(conversation_id)
        if session is None or session.conn is not conn:
            return
        session.last_used = time.monotonic()

    def _conversation_trace_snapshot(self, conversation_id: str) -> list[str]:
        session = self._conversation_sessions.get(conversation_id)
        if session is None:
            return []
        return list(session.tool_trace_refs)

    def _set_conversation_trace_refs(self, conversation_id: str, refs: list[str]) -> None:
        session = self._conversation_sessions.get(conversation_id)
        if session is None:
            return
        session.tool_trace_refs = refs[-self._max_conversation_trace_refs :]

    def _run_query(
        self,
        query: str,
        scaffold: dict,
        cfg: BrainConfig,
        conn: _ACPConnection,
        stream_callback: Callable[[Any], None] | None,
        *,
        tool_trace_refs: list[str] | None = None,
        turn_trace_callback: Callable[[list[str]], None] | None = None,
    ) -> dict[str, Any]:
        try:
            adapter_kwargs: dict[str, Any] = {
                "connection": conn,
                "stream_callback": stream_callback,
            }
            if tool_trace_refs is not None and self._adapter_supports_kw("tool_trace_refs"):
                adapter_kwargs["tool_trace_refs"] = tool_trace_refs
            if turn_trace_callback is not None and self._adapter_supports_kw("turn_trace_callback"):
                adapter_kwargs["turn_trace_callback"] = turn_trace_callback
            return self._adapter(
                query,
                scaffold,
                cfg,
                **adapter_kwargs,
            )
        except Exception as exc:
            return self._degraded(cfg, f"ACP query adapter failed: {exc}")

    def _adapter_supports_kw(self, name: str) -> bool:
        try:
            parameters = inspect.signature(self._adapter).parameters
        except (TypeError, ValueError):
            return False
        return name in parameters or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
        )

    def _add_conversation_trace_refs(
        self,
        conversation_id: str,
        conn: _ACPConnection,
        refs: list[str],
    ) -> None:
        session = self._conversation_sessions.get(conversation_id)
        if session is None or session.conn is not conn:
            return
        seen = set(session.tool_trace_refs)
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                session.tool_trace_refs.append(ref)
        overflow = len(session.tool_trace_refs) - self._max_conversation_trace_refs
        if overflow > 0:
            del session.tool_trace_refs[:overflow]

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

    def _drop_conversation_session(self, conversation_id: str) -> None:
        session = self._conversation_sessions.pop(conversation_id, None)
        if session is not None:
            try:
                session.conn.close()
            except Exception:
                pass

    def _drop_all_conversation_sessions(self) -> None:
        ids = list(self._conversation_sessions)
        for conversation_id in ids:
            self._drop_conversation_session(conversation_id)

    def _prune_conversation_sessions(self, now: float) -> None:
        stale: list[str] = []
        for conversation_id, session in self._conversation_sessions.items():
            if now - session.last_used > self._conversation_idle_ttl_seconds:
                stale.append(conversation_id)
            elif not self._is_alive(session.conn):
                stale.append(conversation_id)
        for conversation_id in stale:
            self._drop_conversation_session(conversation_id)

    def _evict_conversation_if_needed(self) -> None:
        if len(self._conversation_sessions) < self._max_conversation_sessions:
            return
        oldest_id = min(
            self._conversation_sessions,
            key=lambda cid: self._conversation_sessions[cid].last_used,
        )
        self._drop_conversation_session(oldest_id)

    def _degraded(self, cfg: BrainConfig, gap: str) -> dict[str, Any]:
        provenance = build_provenance(cfg, conn_meta=None, degraded=True)
        return build_degraded_result("UNGROUNDED", gap, provenance)
