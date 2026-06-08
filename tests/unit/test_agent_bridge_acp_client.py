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
        acp_workdir="/tmp",
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
        acp_workdir="/tmp",
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
        acp_workdir="/tmp",
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
        acp_workdir="/tmp",
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
        acp_workdir="/tmp",
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
        acp_workdir="/tmp",
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
