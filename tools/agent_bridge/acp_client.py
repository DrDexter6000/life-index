from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import time
from typing import Any, TextIO

from tools.agent_bridge.config import ACPConfigError, BrainConfig, require_ack


class UnsupportedTransportError(ValueError):
    """Raised when an unknown transport value is passed to synthesize()."""


# ─── Constants ────────────────────────────────────────────────────────
_RPC_TIMEOUT = 60  # seconds per RPC call
_SUBPROCESS_JOIN_TIMEOUT = 30  # seconds to wait for subprocess after stdin close

# Provider-key env vars that must NEVER be passed into the ACP subprocess.
# The ACP runtime owns its own credentials; Life Index must not inject keys
# from the parent process. Keep this list conservative and auditable.
_PROVIDER_KEY_DENYLIST: frozenset[str] = frozenset(
    {
        "LIFE_INDEX_LLM_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY",
        "KIMI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "COHERE_API_KEY",
        "MISTRAL_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "REPLICATE_API_KEY",
    }
)

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

    Safety rationale: Hermes (and other ACP runtimes) loads its own
    credentials from ``~/.hermes/.env`` (or equivalent) at startup —
    it does **not** depend on inheriting provider keys from the parent
    process.  Stripping those keys from the subprocess environment is
    therefore safe and prevents accidental credential leakage.

    Steps:
    1. Start from *base_env* (defaults to ``os.environ`` snapshot).
    2. Remove every key in the explicit ``_PROVIDER_KEY_DENYLIST``.
    3. Remove any key whose name (case-insensitive) ends with
       ``_API_KEY`` or ``_TOKEN``, or contains ``SECRET`` or ``PASSWORD``.
    4. Overlay ``cfg.acp_env_allowlist`` (user-requested non-provider vars).
    5. Remove denylisted keys again (denylist always wins over allowlist).
    """
    env = dict(base_env if base_env is not None else os.environ)

    # Step 2: explicit denylist
    for key in _PROVIDER_KEY_DENYLIST:
        env.pop(key, None)

    # Step 3: pattern-based credential stripping
    to_strip = [k for k in env if _CREDENTIAL_PATTERNS.search(k)]
    for key in to_strip:
        env.pop(key, None)

    # Step 4: overlay user allowlist
    if cfg.acp_env_allowlist:
        env.update(cfg.acp_env_allowlist)

    # Step 5: denylist always wins — strip again after allowlist overlay
    for key in _PROVIDER_KEY_DENYLIST:
        env.pop(key, None)
    to_strip2 = [k for k in env if _CREDENTIAL_PATTERNS.search(k)]
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


def acp_synthesize(cfg: BrainConfig, system_prompt: str, user_prompt: str) -> str:
    """Run a prompt through an ACP-compatible agent via stdio JSON-RPC.

    Contract:
    1. Enforces ``data_exposure_ack`` (raises ``AckRequiredError``).
    2. Validates ``acp_command`` is configured (raises ``ACPConfigError``).
    3. Spawns bounded stdio subprocess with a daemon reader thread + deadline queue.
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

    # Build subprocess environment — strip provider keys, overlay allowlist,
    # then strip again (denylist always wins).
    proc_env = _build_acp_subprocess_env(cfg)

    try:
        proc = subprocess.Popen(
            cfg.acp_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cfg.acp_workdir,
            env=proc_env,
            text=True,
            encoding="utf-8",
        )
    except (FileNotFoundError, PermissionError, OSError) as exc:
        raise ACPConfigError(
            f"Failed to start ACP subprocess with command {cfg.acp_command!r}: {exc}"
        ) from exc

    assert proc.stdin is not None
    assert proc.stdout is not None
    _stdin = proc.stdin
    _stdout = proc.stdout

    # ── Bounded reader thread ──────────────────────────────────────────
    msg_queue: queue.Queue[dict[Any, Any]] = queue.Queue()
    stop_event = threading.Event()
    reader = threading.Thread(
        target=_read_stdout_lines,
        args=(_stdout, msg_queue, stop_event),
        daemon=True,
    )
    reader.start()

    collected: list[dict] = []
    _id = 0

    def _rpc(method: str, params: dict | None = None) -> dict[Any, Any]:
        """Send a JSON-RPC request and return the parsed response.

        Collects ``session/update`` notifications encountered before the
        matching response into the outer ``collected`` list.

        Raises ``RuntimeError`` on deadline expiry, broken pipe,
        subprocess exit, or JSON-RPC error response.
        """
        nonlocal _id
        _id += 1
        request = {
            "jsonrpc": "2.0",
            "id": _id,
            "method": method,
            "params": params or {},
        }
        msg = json.dumps(request, ensure_ascii=False) + "\n"
        try:
            _stdin.write(msg)
            _stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(f"ACP subprocess closed before {method} completed: {exc}") from exc

        deadline = time.monotonic() + _RPC_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"ACP RPC deadline ({_RPC_TIMEOUT}s) expired during {method}")
            try:
                line_msg = msg_queue.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue

            # Check for matching JSON-RPC response by id
            if line_msg.get("id") == _id:
                if "error" in line_msg:
                    err = line_msg["error"]
                    raise RuntimeError(
                        f"ACP JSON-RPC error during {method}: "
                        f"code={err.get('code')} message={err.get('message')}"
                    )
                return line_msg

            # Not a response for us — collect as notification
            collected.append(line_msg)

    try:
        # 1. initialize
        init_resp = _rpc(
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

        # 2. authenticate — auto-select first non-setup method when none configured
        auth_method = cfg.acp_auth_method
        if not auth_method:
            auth_methods = init_resp.get("result", {}).get("authMethods", [])
            for method_info in auth_methods:
                mid = (
                    method_info.get("id") or method_info.get("methodId") or method_info.get("name")
                )
                if mid and "setup" not in str(mid).lower():
                    auth_method = mid
                    break
            # When no auth methods are advertised by the server, skip
            # authenticate entirely — the transport may not require auth.

        if auth_method:
            _rpc("authenticate", {"methodId": auth_method})

        # 3. session/new
        session_resp = _rpc(
            "session/new",
            {
                "cwd": cfg.acp_workdir or os.getcwd(),
                "mcpServers": [],
            },
        )
        session_id = session_resp.get("result", {}).get("sessionId", "")

        # 4. session/prompt
        _rpc(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": f"{system_prompt}\n\n{user_prompt}"}],
            },
        )

    finally:
        # ── Subprocess cleanup ─────────────────────────────────────────
        try:
            _stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=_SUBPROCESS_JOIN_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        # ── Drain remaining queue messages ─────────────────────────────
        stop_event.set()
        reader.join(timeout=3)
        while True:
            try:
                remaining_msg = msg_queue.get_nowait()
                collected.append(remaining_msg)
            except queue.Empty:
                break

    return parse_acp_stream(collected)
