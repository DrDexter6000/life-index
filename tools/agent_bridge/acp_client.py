from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
from typing import Any, Callable, TextIO

from tools.agent_bridge.config import ACPConfigError, BrainConfig, require_ack


class UnsupportedTransportError(ValueError):
    """Raised when an unknown transport value is passed to synthesize()."""


# ─── Constants ────────────────────────────────────────────────────────
_RPC_TIMEOUT = 60  # seconds per RPC call
_SUBPROCESS_JOIN_TIMEOUT = 30  # seconds to wait for subprocess after stdin close

# Known runtime provider API-key env vars — these pass through to the ACP
# subprocess by default WITHOUT requiring LIFE_INDEX_ACP_ENV_ALLOWLIST.
# The ACP runtime needs its own provider credentials; these are well-known
# standard env var names for 11 major LLM providers.
# Keep this set readable and auditable — no branchy provider logic.
_KNOWN_RUNTIME_PROVIDER_KEYS: frozenset[str] = frozenset(
    {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "KIMI_API_KEY",
        "GEMINI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "COHERE_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "REPLICATE_API_KEY",
    }
)

# Life Index's own API key — MUST NEVER be passed to the ACP subprocess.
# This key belongs to Life Index, not to any runtime provider.
# It is always stripped, even if someone tries to allowlist it.
_ALWAYS_STRIP_KEYS: frozenset[str] = frozenset({"LIFE_INDEX_LLM_API_KEY"})

# Case-insensitive suffix/pattern patterns for env var names that indicate
# credentials.  Any key whose upper-cased name ends with ``_API_KEY`` or
# ``_TOKEN``, or contains ``SECRET`` or ``PASSWORD``, is stripped regardless
# of whether it appears in the explicit denylist above.
_CREDENTIAL_PATTERNS = re.compile(
    r"(_API_KEY|_TOKEN)$|SECRET|PASSWORD",
    re.IGNORECASE,
)


def _build_acp_subprocess_env(
    cfg: BrainConfig, base_env: dict[str, str] | None = None
) -> dict[str, str]:
    """Build a sanitized environment dict for the ACP subprocess.

    Safety contract (owner-approved):

    * Known runtime provider API keys (11 providers in
      ``_KNOWN_RUNTIME_PROVIDER_KEYS``) pass through to the ACP subprocess
      by default — no ``LIFE_INDEX_ACP_ENV_ALLOWLIST`` needed.
    * Life Index's own ``LIFE_INDEX_LLM_API_KEY`` is **always** stripped.
    * Credential-like variables outside the known provider set are stripped
      by default, unless explicitly allowlisted.
    * ``LIFE_INDEX_ACP_ENV_ALLOWLIST`` acts as a fallback for novel
      provider keys (e.g. ``FOO_API_KEY``).

    Steps:
    1. Start from *base_env* (defaults to ``os.environ`` snapshot).
    2. Remove every key in ``_ALWAYS_STRIP_KEYS`` (always, no exceptions).
    3. Remove any credential-pattern key NOT in the known runtime
       provider set (preserves known provider keys by default).
    4. Overlay ``cfg.acp_env_allowlist`` (user-requested vars).
    5. Final strip: remove always-strip keys (again); remove remaining
       credential-pattern keys unless they are known providers or
       explicitly allowlisted.
    """
    env = dict(base_env if base_env is not None else os.environ)

    # Build the set of keys that the user explicitly allowlisted
    allowlisted_names: frozenset[str] = frozenset(cfg.acp_env_allowlist.keys())

    # Step 2: always-strip keys (Life Index internal)
    for key in _ALWAYS_STRIP_KEYS:
        env.pop(key, None)

    # Step 3: pattern-based credential stripping — preserve known
    # runtime provider keys (they pass through by default)
    to_strip = [
        k for k in env if _CREDENTIAL_PATTERNS.search(k) and k not in _KNOWN_RUNTIME_PROVIDER_KEYS
    ]
    for key in to_strip:
        env.pop(key, None)

    # Step 4: overlay user allowlist
    if cfg.acp_env_allowlist:
        env.update(cfg.acp_env_allowlist)

    # Step 5: final credential strip
    #   - always-strip keys: unconditionally removed (no allowlist override)
    #   - credential-pattern keys: preserved if known provider OR allowlisted
    for key in _ALWAYS_STRIP_KEYS:
        env.pop(key, None)
    to_strip2 = [
        k
        for k in env
        if _CREDENTIAL_PATTERNS.search(k)
        and k not in _KNOWN_RUNTIME_PROVIDER_KEYS
        and k not in allowlisted_names
    ]
    for key in to_strip2:
        env.pop(key, None)

    return env


def parse_acp_stream(messages: list[dict]) -> str:
    """Collect only agent_message_chunk text from ACP session/update notifications.

    Filters for ``params.update.sessionUpdate == "agent_message_chunk"``
    and concatenates ``params.update.content.text`` in arrival order.
    Ignores ``agent_thought_chunk`` notifications entirely.
    """
    collected: list[str] = []
    for msg in messages:
        try:
            update = msg.get("params", {}).get("update", {})
            if update.get("sessionUpdate") == "agent_message_chunk":
                text = update.get("content", {}).get("text", "")
                collected.append(text)
        except (AttributeError, TypeError):
            continue
    return "".join(collected)


def _read_stdout_lines(
    proc_stdout: TextIO, msg_queue: queue.Queue, stop_event: threading.Event
) -> None:
    """Daemon thread target: read lines from subprocess stdout, queue parsed JSON."""
    try:
        while not stop_event.is_set():
            line = proc_stdout.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                msg_queue.put(msg)
            except json.JSONDecodeError:
                continue
    except Exception:
        pass


class _ACPConnection:
    """Context manager for ACP agent stdio JSON-RPC handshake.

    Extracts the connect + handshake logic from ``acp_synthesize`` into
    a reusable helper.  On ``__enter__`` the context manager:

    1. Spawns the ACP subprocess with sanitized env.
    2. Starts a daemon reader thread.
    3. Runs initialize → authenticate (auto-select first non-setup
       auth method) → session/new.
    4. Exposes ``.session_id`` and ``.rpc()`` for further calls.

    On ``__exit__`` it guarantees cleanup: close stdin, wait/kill the
    subprocess, drain the message queue.
    """

    def __init__(
        self,
        cfg: BrainConfig,
        *,
        rpc_timeout: float | None = None,
        handshake_timeout: float | None = None,
    ) -> None:
        self._cfg = cfg
        self._rpc_timeout = rpc_timeout if rpc_timeout is not None else _RPC_TIMEOUT
        self._handshake_timeout = handshake_timeout
        self._handshake_deadline: float | None = None

        self.session_id: str = ""
        self.handshake_steps: dict[str, str] = {}
        self.collected: list[dict] = []

        # Additive metadata from matched handshake responses.  These are
        # populated during __enter__ and are read-only after handshake.
        self.initialize_result: dict | None = None
        self.session_new_result: dict | None = None

        # Mutable state populated during __enter__
        self._proc: subprocess.Popen | None = None
        self._stdin: TextIO | None = None
        self._msg_queue: queue.Queue[dict[Any, Any]] = queue.Queue()
        self._stop_event: threading.Event = threading.Event()
        self._reader: threading.Thread | None = None
        self._id: int = 0

    def __enter__(self) -> "_ACPConnection":
        require_ack(self._cfg)

        if not self._cfg.acp_command:
            raise ACPConfigError(
                "ACP transport requires acp_command to be configured. "
                "Set acp_command in brain config or LIFE_INDEX_ACP_COMMAND env var."
            )

        proc_env = _build_acp_subprocess_env(self._cfg)

        try:
            self._proc = subprocess.Popen(
                self._cfg.acp_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self._cfg.acp_workdir,
                env=proc_env,
                text=True,
                encoding="utf-8",
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            raise ACPConfigError(
                f"Failed to start ACP subprocess with command {self._cfg.acp_command!r}: {exc}"
            ) from exc

        assert self._proc.stdin is not None
        assert self._proc.stdout is not None
        self._stdin = self._proc.stdin  # type: ignore[assignment]

        # ── Bounded reader thread ──────────────────────────────────
        self._msg_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._reader = threading.Thread(
            target=_read_stdout_lines,
            args=(self._proc.stdout, self._msg_queue, self._stop_event),
            daemon=True,
        )
        self._reader.start()

        self._id = 0

        # ── Handshake ──────────────────────────────────────────────
        if self._handshake_timeout is not None:
            self._handshake_deadline = time.monotonic() + self._handshake_timeout
        try:
            self._handshake()
        except Exception:
            self._cleanup(kill_first=True)
            raise
        self._handshake_deadline = None

        return self

    def __exit__(self, *args: Any) -> None:
        self._cleanup()

    def is_alive(self) -> bool:
        """Return True if the subprocess is still running.

        Treats a process that has never been started or has already exited
        as dead.  This is a cheap poll; it does not probe the transport.
        """
        proc = self._proc
        if proc is None:
            return False
        return proc.poll() is None

    @property
    def pid(self) -> int | None:
        """Return the subprocess PID, or None if no process is running."""
        proc = self._proc
        return proc.pid if proc is not None else None

    def close(self) -> None:
        """Idempotent teardown alias for the context manager exit path."""
        self._cleanup()

    def _maybe_stream_chunk(
        self,
        line_msg: dict,
        stream_callback: Callable[[str], None] | None,
    ) -> None:
        """Forward a single ``agent_message_chunk`` to *stream_callback*.

        Isolated in a helper so the RPC loop is not broken by a misbehaving
        callback and the control flow stays simple for static analysis.
        """
        if stream_callback is None:
            return
        try:
            update = line_msg.get("params", {}).get("update", {})
            if update.get("sessionUpdate") == "agent_message_chunk":
                text = update.get("content", {}).get("text", "")
                if isinstance(text, str) and text:
                    stream_callback(text)
        except Exception:
            # A misbehaving callback must not break the RPC loop.
            return

    # ── Public API ────────────────────────────────────────────────────

    def rpc(
        self,
        method: str,
        params: dict | None = None,
        stream_callback: Callable[[str], None] | None = None,
    ) -> dict[Any, Any]:
        """Send a JSON-RPC request and return the parsed response.

        Collects ``session/update`` notifications encountered before the
        matching response into ``self.collected``.  When ``stream_callback``
        is provided, each ``agent_message_chunk`` notification is forwarded
        incrementally as it arrives, enabling true streaming without final-
        buffer splitting in callers.

        Raises ``RuntimeError`` on deadline expiry, broken pipe,
        subprocess exit, or JSON-RPC error response.
        """
        if self._stdin is None:
            raise RuntimeError("ACPConnection not entered — stdin unavailable.")

        self._id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or {},
        }
        msg = json.dumps(request, ensure_ascii=False) + "\n"
        try:
            self._stdin.write(msg)
            self._stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(f"ACP subprocess closed before {method} completed: {exc}") from exc

        rpc_deadline = time.monotonic() + self._rpc_timeout
        deadline = rpc_deadline
        deadline_label = f"ACP RPC deadline ({self._rpc_timeout:.0f}s)"
        if self._handshake_deadline is not None and self._handshake_deadline < deadline:
            deadline = self._handshake_deadline
            deadline_label = f"ACP handshake deadline ({self._handshake_timeout:.1f}s)"
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"{deadline_label} expired during {method}")
            try:
                line_msg = self._msg_queue.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue

            if line_msg.get("id") == self._id:
                if "error" in line_msg:
                    err = line_msg["error"]
                    raise RuntimeError(
                        f"ACP JSON-RPC error during {method}: "
                        f"code={err.get('code')} message={err.get('message')}"
                    )
                return line_msg

            self.collected.append(line_msg)
            self._maybe_stream_chunk(line_msg, stream_callback)

    # ── Internals ─────────────────────────────────────────────────────

    def _handshake(self) -> None:
        """Run initialize → authenticate → session/new handshake."""
        self.handshake_steps = {}

        # 1. initialize
        init_resp = self.rpc(
            "initialize",
            {
                "protocolVersion": 1,
                "clientInfo": {
                    "name": "life-index-acp-adapter",
                    "version": "0.1.0",
                },
                "capabilities": {},
            },
        )
        self.initialize_result = init_resp.get("result")
        self.handshake_steps["initialize"] = "pass"

        # 2. authenticate — auto-select first non-setup method when none configured
        auth_method = self._cfg.acp_auth_method
        if not auth_method:
            auth_methods = init_resp.get("result", {}).get("authMethods", [])
            for method_info in auth_methods:
                mid = (
                    method_info.get("id") or method_info.get("methodId") or method_info.get("name")
                )
                if mid and "setup" not in str(mid).lower():
                    auth_method = mid
                    break

        if auth_method:
            self.rpc("authenticate", {"methodId": auth_method})
            self.handshake_steps["authenticate"] = "pass"
        else:
            self.handshake_steps["authenticate"] = "skip"

        # 3. session/new
        session_resp = self.rpc(
            "session/new",
            {
                "cwd": self._cfg.acp_workdir or os.getcwd(),
                "mcpServers": [],
            },
        )
        self.session_new_result = session_resp.get("result")
        self.handshake_steps["session_new"] = "pass"
        self.session_id = (self.session_new_result or {}).get("sessionId", "")

    def _cleanup(self, *, kill_first: bool = False) -> None:
        """Guaranteed subprocess cleanup: close stdin, wait/kill, drain queue."""
        _stdin = self._stdin
        if _stdin is not None:
            try:
                _stdin.close()
            except OSError:
                pass
            self._stdin = None

        _proc = self._proc
        if _proc is not None:
            if kill_first and _proc.poll() is None:
                try:
                    _proc.kill()
                except OSError:
                    pass
            try:
                _proc.wait(timeout=3 if kill_first else _SUBPROCESS_JOIN_TIMEOUT)
            except subprocess.TimeoutExpired:
                _proc.kill()
                _proc.wait()
            self._proc = None

        self._stop_event.set()
        _reader = self._reader
        if _reader is not None:
            _reader.join(timeout=3)
            self._reader = None

        while True:
            try:
                remaining_msg = self._msg_queue.get_nowait()
                self.collected.append(remaining_msg)
            except queue.Empty:
                break


def acp_synthesize(cfg: BrainConfig, system_prompt: str, user_prompt: str) -> str:
    """Run a prompt through an ACP-compatible agent via stdio JSON-RPC.

    Contract:
    1. Enforces ``data_exposure_ack`` (raises ``AckRequiredError``).
    2. Validates ``acp_command`` is configured (raises ``ACPConfigError``).
    3. Uses ``_ACPConnection`` for subprocess lifecycle and handshake.
    4. JSON-RPC flow::

          initialize → authenticate (auto-select first non-setup
          auth method from initialize response when none configured)
          → session/new → session/prompt

    5. Matches responses by request ``id``; collects ``session/update``
        notifications emitted before each matching response.
    6. Returns only ``agent_message_chunk`` text via ``parse_acp_stream``.
    """
    require_ack(cfg)

    if not cfg.acp_command:
        raise ACPConfigError(
            "ACP transport requires acp_command to be configured. "
            "Set acp_command in brain config or LIFE_INDEX_ACP_COMMAND env var."
        )

    with _ACPConnection(cfg) as conn:
        conn.rpc(
            "session/prompt",
            {
                "sessionId": conn.session_id,
                "prompt": [{"type": "text", "text": f"{system_prompt}\n\n{user_prompt}"}],
            },
        )

    return parse_acp_stream(conn.collected)
