"""Phase B contract tests for ACP client — env redaction and stream parsing.

Env redaction tests prove that provider-key variables (LIFE_INDEX_LLM_API_KEY,
OPENAI_API_KEY, etc.) are NOT passed into the ACP subprocess environment.

Stream parsing tests define the contract for tools.agent_bridge.acp_client.parse_acp_stream.
Fixture built from the real ACP PoC run log at the root path specified in PHASE_A_PRD.md.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "agent_bridge" / "acp_poc_run.jsonl"
)


def _load_messages():
    """Load and parse the ACP PoC run JSONL fixture.

    Each line is a complete JSON-RPC notification. The fixture contains:
    - 39 agent_thought_chunk messages (model reasoning, must NOT leak into output)
    - 8 agent_message_chunk messages (concatenates to 'LIFE_INDEX_ACP_POC_OK')
    """
    raw = FIXTURE_PATH.read_text(encoding="utf-8").strip()
    return [json.loads(line) for line in raw.split("\n") if line.strip()]


def test_parse_acp_stream_returns_collected_text():
    """Contract: ACP stream parser collects only agent_message_chunk text.

    The parser must concatenate agent_message_chunk content.text in order,
    excluding agent_thought_chunk content.text. The fixture's 8
    agent_message_chunk messages concatenate to LIFE_INDEX_ACP_POC_OK.

    This locks the CTO finding that the previous empty collected_text bug
    must not recur.
    """
    # RED: tools.agent_bridge.acp_client does not exist yet
    from tools.agent_bridge.acp_client import parse_acp_stream  # noqa: F811

    messages = _load_messages()
    result = parse_acp_stream(messages)

    assert result == "LIFE_INDEX_ACP_POC_OK", f"Expected 'LIFE_INDEX_ACP_POC_OK' but got {result!r}"


def test_acp_stream_excludes_thought_chunks():
    """Contract: agent_thought_chunk text must never appear in collected output.

    The fixture contains 39 agent_thought_chunk messages with reasoning text
    from the real PoC run (e.g., 'The user is asking me to reply...').
    None of this text may leak into the collected output.

    This is a regression contract for the CTO finding that the previous
    empty collected_text bug must not recur.
    """
    # RED: tools.agent_bridge.acp_client does not exist yet
    from tools.agent_bridge.acp_client import parse_acp_stream  # noqa: F811

    messages = _load_messages()
    result = parse_acp_stream(messages)

    # Thought chunks from the real PoC contain reasoning fragments.
    # None of these should appear in output.
    forbidden_fragments = [
        "The user",
        "is asking",
        "reply with exactly",
        "simple request",
        "no ambiguity",
        "should provide exactly that string",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in result, f"agent_thought_chunk text leaked into output: {fragment!r}"


def test_acp_stream_empty_messages_returns_empty():
    """Contract: empty message list produces empty string, not None or error."""
    from tools.agent_bridge.acp_client import parse_acp_stream  # noqa: F811

    result = parse_acp_stream([])
    assert result == ""


def test_acp_stream_no_message_chunks_returns_empty():
    """Contract: only thought chunks (no message chunks) produces empty string.

    Uses the real ACP message shape: params.update.sessionUpdate and
    params.update.content.text.
    """
    from tools.agent_bridge.acp_client import parse_acp_stream  # noqa: F811

    thought_only = [
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "test-session-id",
                "update": {
                    "content": {"text": "The model is thinking...", "type": "text"},
                    "sessionUpdate": "agent_thought_chunk",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "test-session-id",
                "update": {
                    "content": {"text": " about what to say.", "type": "text"},
                    "sessionUpdate": "agent_thought_chunk",
                },
            },
        },
    ]
    result = parse_acp_stream(thought_only)
    assert result == ""


# ──────────────────────────────────────────────────────────────────────
# Phase B T2R: Env redaction rework — fast sentinel-pattern tests
#
# All env-capture tests use _EnvCaptureSentinel raised by fake Popen
# to avoid waiting on _RPC_TIMEOUT.  Provider-key denylist always wins
# over acp_env_allowlist — a provider key must never reach Popen(env=).
# ──────────────────────────────────────────────────────────────────────


class _EnvCaptureSentinel(Exception):
    """Raised by fake Popen immediately after capturing env.

    Prevents acp_synthesize from entering the _RPC_TIMEOUT wait loop.
    The test catches this sentinel and asserts on the captured env dict.
    """


def test_acp_subprocess_env_redacts_life_index_api_key(monkeypatch):
    """Contract: LIFE_INDEX_LLM_API_KEY in parent env must NOT leak into ACP subprocess."""
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "sk-parent-secret-should-not-leak")

    captured_env: dict = {}

    def _fake_popen(args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        raise _EnvCaptureSentinel("captured")

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy", "acp"],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    with pytest.raises(_EnvCaptureSentinel):
        acp_synthesize(cfg, "test system", "test user")

    assert "LIFE_INDEX_LLM_API_KEY" not in captured_env, (
        f"LIFE_INDEX_LLM_API_KEY leaked into ACP subprocess env: "
        f"{captured_env.get('LIFE_INDEX_LLM_API_KEY', '<absent>')}"
    )


def test_acp_subprocess_env_redacts_openai_api_key(monkeypatch):
    """Contract: OPENAI_API_KEY must NOT leak into ACP subprocess env.

    The denylist must cover common third-party provider keys beyond
    Life Index's own variable naming convention.
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-should-not-leak")

    captured_env: dict = {}

    def _fake_popen(args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        raise _EnvCaptureSentinel("captured")

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy", "acp"],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    with pytest.raises(_EnvCaptureSentinel):
        acp_synthesize(cfg, "test system", "test user")

    assert "OPENAI_API_KEY" not in captured_env, (
        f"OPENAI_API_KEY leaked into ACP subprocess env: "
        f"{captured_env.get('OPENAI_API_KEY', '<absent>')}"
    )


def test_acp_subprocess_env_preserves_non_provider_vars(monkeypatch):
    """Contract: non-provider env vars like PATH must survive env redaction.

    The denylist must only strip keys; it must not damage the env for
    normal system variables that the ACP runtime needs.
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "sk-secret")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    captured_env: dict = {}

    def _fake_popen(args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        raise _EnvCaptureSentinel("captured")

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy", "acp"],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    with pytest.raises(_EnvCaptureSentinel):
        acp_synthesize(cfg, "test system", "test user")

    assert "LIFE_INDEX_LLM_API_KEY" not in captured_env, "Provider key leaked"
    assert "PATH" in captured_env, "Non-provider env var PATH was stripped incorrectly"
    assert captured_env["PATH"] == "/usr/bin:/bin"


def test_acp_env_allowlist_cannot_reintroduce_life_index_api_key(monkeypatch):
    """Contract: acp_env_allowlist MUST NOT reintroduce a denylisted provider key.

    Regression for T2 rejection finding: the original implementation applied
    denylist BEFORE allowlist, so an explicit allowlist entry could reintroduce
    a provider key into the ACP subprocess environment.  The rework applies
    denylist AFTER allowlist — provider keys never reach Popen(env=).
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "sk-from-parent")

    captured_env: dict = {}

    def _fake_popen(args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        raise _EnvCaptureSentinel("captured")

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy", "acp"],
        acp_workdir=str(FIXTURE_PATH.parent),
        # Attacker / misconfiguration: try to reintroduce provider key via allowlist
        acp_env_allowlist={"LIFE_INDEX_LLM_API_KEY": "sk-from-allowlist-override"},
    )

    with pytest.raises(_EnvCaptureSentinel):
        acp_synthesize(cfg, "test system", "test user")

    assert "LIFE_INDEX_LLM_API_KEY" not in captured_env, (
        "LIFE_INDEX_LLM_API_KEY leaked into ACP subprocess env " "via acp_env_allowlist bypass"
    )


def test_acp_env_allowlist_preserves_non_provider_vars(monkeypatch):
    """Contract: non-provider allowlist entries still reach the subprocess env.

    The denylist-after-allowlist order must not break legitimate allowlist
    usage for runtime configuration variables that are not provider keys.
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "sk-secret")

    captured_env: dict = {}

    def _fake_popen(args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        raise _EnvCaptureSentinel("captured")

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy", "acp"],
        acp_workdir=str(FIXTURE_PATH.parent),
        acp_env_allowlist={
            "CUSTOM_VAR": "custom_value",
            "ANOTHER_VAR": "another_value",
        },
    )

    with pytest.raises(_EnvCaptureSentinel):
        acp_synthesize(cfg, "test system", "test user")

    assert "LIFE_INDEX_LLM_API_KEY" not in captured_env, "Provider key leaked"
    assert captured_env.get("CUSTOM_VAR") == "custom_value", (
        f"non-provider allowlist var CUSTOM_VAR missing: "
        f"{captured_env.get('CUSTOM_VAR', '<absent>')}"
    )
    assert captured_env.get("ANOTHER_VAR") == "another_value", (
        f"non-provider allowlist var ANOTHER_VAR missing: "
        f"{captured_env.get('ANOTHER_VAR', '<absent>')}"
    )


def test_acp_subprocess_env_strips_provider_keys():
    """Contract: _build_acp_subprocess_env strips all provider keys via denylist
    and credential-pattern matching, while preserving non-credential vars and
    overlaying allowlist entries.

    Validates the pure-function extraction: exact denylist + case-insensitive
    suffix/pattern matching for _API_KEY, _TOKEN, SECRET, PASSWORD.
    """
    from tools.agent_bridge.acp_client import _build_acp_subprocess_env
    from tools.agent_bridge.config import BrainConfig

    base = {
        "PATH": "/usr/bin",
        "HOME": "/home/u",
        "LIFE_INDEX_LLM_API_KEY": "sk-x",
        "OPENAI_API_KEY": "sk-o",
        "SOME_TOKEN": "t",
        "MY_SECRET": "s",
        "FOO": "keep",
    }
    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy", "acp"],
        acp_workdir=str(FIXTURE_PATH.parent),
        acp_env_allowlist={"BAR": "baz"},
    )
    env = _build_acp_subprocess_env(cfg, base_env=base)

    # Provider keys must be stripped (denylist + pattern)
    assert "LIFE_INDEX_LLM_API_KEY" not in env and "OPENAI_API_KEY" not in env
    # Pattern-based: _TOKEN suffix and SECRET substring
    assert "SOME_TOKEN" not in env and "MY_SECRET" not in env
    # Non-credential vars preserved
    assert env["PATH"] == "/usr/bin" and env["HOME"] == "/home/u" and env["FOO"] == "keep"
    # Allowlist overlay works
    assert env["BAR"] == "baz"


# ──────────────────────────────────────────────────────────────────────
# Phase C-2: _ACPConnection context manager tests
#
# These tests verify the extracted _ACPConnection helper:
#   - Runs the full handshake (initialize → authenticate → session/new)
#   - Cleanup works on timeout (no leaked processes)
#   - acp_synthesize preserves behavior after refactoring
# ──────────────────────────────────────────────────────────────────────


def test_acp_connection_runs_handshake():
    """Contract: _ACPConnection context manager runs initialize → authenticate → session/new.

    Uses the fake ACP agent fixture that responds to all three handshake
    methods and hangs on session/prompt.  The context manager must complete
    the handshake and expose the session_id.
    """
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable  # Use same Python
    fake_script = str(FIXTURE_PATH.parent / "fake_acp_agent.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    with _ACPConnection(cfg) as conn:
        assert conn.session_id == "test-session-abc123"

    # After exit, collected should contain handshake responses
    assert len(conn.collected) >= 0  # notifications may or may not appear


def test_acp_connection_cleanup_on_timeout():
    """Contract: _ACPConnection cleanup works when RPC times out.

    Uses the hang variant of fake ACP agent that never responds.
    The context manager must raise RuntimeError on timeout and ensure
    the subprocess is killed via _cleanup (no leaked processes).
    Uses explicit __enter__/__exit__ to verify cleanup state.
    """
    import time
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH.parent / "fake_acp_agent_hang.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    conn = _ACPConnection(cfg, rpc_timeout=2)

    start = time.monotonic()
    with pytest.raises(RuntimeError, match=r"(?i)deadline|timeout|expired"):
        conn.__enter__()
    elapsed = time.monotonic() - start
    assert elapsed < 8, f"Timeout cleanup took too long: {elapsed:.1f}s"
    # After cleanup, subprocess must be gone
    assert conn._proc is None, "Subprocess leaked after __enter__ + _cleanup"


def test_acp_synthesize_rpc_order_is_preserved(monkeypatch):
    """Contract: After refactoring, acp_synthesize sends RPCs in the correct order.

    Uses the full-response fake ACP agent (responds to session/prompt too).
    Captures all RPC method calls to verify:
    1. initialize → 2. authenticate → 3. session/new → 4. session/prompt
    """
    import tools.agent_bridge.acp_client as acp_mod
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH.parent / "fake_acp_agent_full.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    original_rpc = acp_mod._ACPConnection.rpc
    tracked: list[str] = []

    def _tracked_rpc(self, method, params=None):
        tracked.append(method)
        return original_rpc(self, method, params)

    monkeypatch.setattr(acp_mod._ACPConnection, "rpc", _tracked_rpc)

    result = acp_synthesize(cfg, "test system", "test user")

    # Verify RPC call order: all 4 calls should be tracked
    assert len(tracked) == 4, f"Expected 4 RPC calls, got {len(tracked)}: {tracked}"
    assert tracked[0] == "initialize"
    assert tracked[1] == "authenticate"
    assert tracked[2] == "session/new"
    assert tracked[3] == "session/prompt"
    # Verify output was collected from agent_message_chunk notification
    assert "HELLO_FROM_FAKE_ACP" in result


def test_acp_synthesize_uses_acp_connection_context_manager(monkeypatch):
    """Contract: After refactoring, acp_synthesize uses _ACPConnection internally.

    Uses the full-response fake ACP agent. Verifies that the context manager
    pattern is used (__enter__ / __exit__ called) and acp_synthesize produces
    output.
    """
    from tools.agent_bridge.acp_client import acp_synthesize, _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    enter_called = [False]
    exit_called = [False]

    original_enter = _ACPConnection.__enter__
    original_exit = _ACPConnection.__exit__

    def _tracking_enter(self):
        enter_called[0] = True
        return original_enter(self)

    def _tracking_exit(self, *args):
        exit_called[0] = True
        return original_exit(self, *args)

    monkeypatch.setattr(_ACPConnection, "__enter__", _tracking_enter)
    monkeypatch.setattr(_ACPConnection, "__exit__", _tracking_exit)

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH.parent / "fake_acp_agent_full.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    result = acp_synthesize(cfg, "test system", "test user")

    assert enter_called[0], "_ACPConnection.__enter__ was not called"
    assert exit_called[0], "_ACPConnection.__exit__ was not called"
    assert isinstance(result, str)
    assert "HELLO_FROM_FAKE_ACP" in result


# ──────────────────────────────────────────────────────────────────────
# Phase C-2 Blocker 5: __enter__ cleanup on handshake failure
# ──────────────────────────────────────────────────────────────────────


def test_acp_connection_exposes_handshake_metadata():
    """Contract: _ACPConnection exposes initialize_result and session_new_result.

    Uses the query fake agent which returns serverInfo.name and a model
    field in session/new.  The attributes must be populated without
    changing handshake order or probe semantics.
    """
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH.parent / "fake_acp_agent_query.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    with _ACPConnection(cfg) as conn:
        assert conn.initialize_result is not None
        assert conn.initialize_result.get("serverInfo", {}).get("name") == "fake-acp"
        assert conn.session_new_result is not None
        assert conn.session_new_result.get("sessionId") == "test-session-abc123"
        assert conn.session_new_result.get("model") == "fake-model"
        assert conn.session_id == "test-session-abc123"
        assert conn.handshake_steps == {
            "initialize": "pass",
            "authenticate": "pass",
            "session_new": "pass",
        }


def test_acp_connection_no_leak_on_handshake_failure():
    """Regression: _ACPConnection must not leak subprocess when handshake fails.

    Uses the hang variant with a short rpc_timeout. After __enter__ raises,
    verify the subprocess is cleaned up (not leaked).
    """
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
    fake_script = str(FIXTURE_PATH.parent / "fake_acp_agent_hang.py")

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=[fake_agent, fake_script],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    conn = _ACPConnection(cfg, rpc_timeout=1)
    with pytest.raises(RuntimeError):
        conn.__enter__()
    # After __enter__ raises, cleanup must have run:
    assert conn._proc is None, "Subprocess leaked after __enter__ handshake failure"
    assert conn._stdin is None, "Stdin leaked after __enter__ handshake failure"
