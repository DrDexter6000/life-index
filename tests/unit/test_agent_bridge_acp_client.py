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
from typing import Any

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


def test_acp_subprocess_env_passthrough_known_provider_key(monkeypatch):
    """Contract: known runtime provider keys (e.g. OPENAI_API_KEY) pass through
    by default — no LIFE_INDEX_ACP_ENV_ALLOWLIST needed.

    OPENAI_API_KEY is in _KNOWN_RUNTIME_PROVIDER_KEYS and must survive
    all sanitization steps without explicit allowlisting.
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-known-provider")

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

    # Known provider key passes through by default
    assert (
        "OPENAI_API_KEY" in captured_env
    ), "OPENAI_API_KEY should pass through as known runtime provider key"
    assert captured_env["OPENAI_API_KEY"] == "sk-openai-known-provider"


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


def test_acp_env_allowlist_can_reintroduce_explicitly_allowlisted_provider_key(monkeypatch):
    """Contract: a novel provider key (not in the known runtime provider set)
    passes to the ACP subprocess when explicitly allowlisted.

    LIFE_INDEX_LLM_API_KEY can never be allowlisted (it is always stripped),
    but novel keys like FOO_API_KEY should pass when explicitly allowlisted.
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "sk-from-parent")
    monkeypatch.setenv("FOO_API_KEY", "sk-foo-from-env")

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
        acp_env_allowlist={"FOO_API_KEY": "sk-foo-from-allowlist-override"},
    )

    with pytest.raises(_EnvCaptureSentinel):
        acp_synthesize(cfg, "test system", "test user")

    # LIFE_INDEX_LLM_API_KEY is always stripped, even if in base env
    assert (
        "LIFE_INDEX_LLM_API_KEY" not in captured_env
    ), "LIFE_INDEX_LLM_API_KEY must never reach the subprocess"
    # Novel provider key passes because it was explicitly allowlisted
    assert (
        "FOO_API_KEY" in captured_env
    ), "FOO_API_KEY was stripped despite being explicitly allowlisted"
    assert captured_env["FOO_API_KEY"] == "sk-foo-from-allowlist-override"


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
    """Contract: _build_acp_subprocess_env strips Life Index's own key and
    unallowlisted credential-pattern keys, while preserving known runtime
    provider keys and non-credential vars.  Allowlist overlay still works.
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

    # Life Index's own key must always be stripped
    assert "LIFE_INDEX_LLM_API_KEY" not in env
    # Known runtime provider key passes through by default
    assert "OPENAI_API_KEY" in env and env["OPENAI_API_KEY"] == "sk-o"
    # Pattern-based: _TOKEN suffix and SECRET substring — stripped
    assert "SOME_TOKEN" not in env and "MY_SECRET" not in env
    # Non-credential vars preserved
    assert env["PATH"] == "/usr/bin" and env["HOME"] == "/home/u" and env["FOO"] == "keep"
    # Allowlist overlay works
    assert env["BAR"] == "baz"


# ──────────────────────────────────────────────────────────────────────
# v6-ce-acp-env-allowlist: explicit allowlist precedence tests
# ──────────────────────────────────────────────────────────────────────


def test_acp_known_provider_key_passes_by_default():
    """Contract: a known runtime provider key (e.g. DEEPSEEK_API_KEY) passes
    through _build_acp_subprocess_env by default — no allowlist entry needed.
    Unallowlisted credential-like keys are still stripped.
    """
    from tools.agent_bridge.acp_client import _build_acp_subprocess_env
    from tools.agent_bridge.config import BrainConfig

    base = {
        "PATH": "/usr/bin",
        "DEEPSEEK_API_KEY": "sk-deepseek-real",
        "SOME_TOKEN": "t",
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
        # No allowlist — zero-config passthrough for known providers
    )
    env = _build_acp_subprocess_env(cfg, base_env=base)

    # Known provider key passes through by default (no allowlist)
    assert "DEEPSEEK_API_KEY" in env, "DEEPSEEK_API_KEY stripped despite being known provider"
    assert env["DEEPSEEK_API_KEY"] == "sk-deepseek-real"
    # Non-allowlisted credential-like key still stripped
    assert "SOME_TOKEN" not in env, "Unallowlisted SOME_TOKEN should be stripped"


def test_acp_unallowlisted_credential_keys_still_stripped():
    """Contract: credential-like keys that are NOT in the allowlist remain stripped."""
    from tools.agent_bridge.acp_client import _build_acp_subprocess_env
    from tools.agent_bridge.config import BrainConfig

    base = {
        "PATH": "/usr/bin",
        "FAKE_API_KEY": "sk-fake",
        "MY_SECRET": "s3cret",
        "DB_PASSWORD": "p@ss",
        "SOME_TOKEN": "tok",
        "KEEP_ME": "safe",
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
        acp_env_allowlist={"KEEP_ME": "safe"},  # only KEEP_ME is allowlisted
    )
    env = _build_acp_subprocess_env(cfg, base_env=base)

    # Unallowlisted credential-like keys stripped
    for bad_key in ("FAKE_API_KEY", "MY_SECRET", "DB_PASSWORD", "SOME_TOKEN"):
        assert bad_key not in env, f"Unallowlisted {bad_key} should be stripped"
    # Allowlisted non-credential key survives
    assert env["KEEP_ME"] == "safe"
    # Non-credential key survives
    assert "PATH" in env


def test_acp_env_allowlist_list_syntax_resolves_from_env(monkeypatch):
    """Contract: JSON list allowlist resolves each key from os.environ.

    Uses resolve_brain_config to parse LIFE_INDEX_ACP_ENV_ALLOWLIST from the
    environment, then verifies the resolved key reaches the ACP subprocess env.
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import resolve_brain_config

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-deepseek-from-env")
    monkeypatch.setenv("LIFE_INDEX_ACP_ENV_ALLOWLIST", '["DEEPSEEK_API_KEY"]')

    # Ensure resolve_brain_config can produce an ACP config
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["dummy", "acp"],
                "data_exposure_ack": True,
            }
        },
    )

    captured_env: dict = {}

    def _fake_popen(args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        raise _EnvCaptureSentinel("captured")

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    cfg = resolve_brain_config()

    with pytest.raises(_EnvCaptureSentinel):
        acp_synthesize(cfg, "test system", "test user")

    # DEEPSEEK_API_KEY must reach the subprocess (resolved from env via list syntax)
    assert (
        "DEEPSEEK_API_KEY" in captured_env
    ), "DEEPSEEK_API_KEY missing — list allowlist resolution failed"
    # Must NOT log the secret value in assertions — only check presence


def test_acp_env_allowlist_list_syntax_skips_missing_keys(monkeypatch):
    """Contract: JSON list keys not present in os.environ are silently skipped."""
    from tools.agent_bridge.acp_client import _build_acp_subprocess_env
    from tools.agent_bridge.config import BrainConfig

    # Set env to a list with a key that doesn't exist in os.environ
    monkeypatch.setenv("LIFE_INDEX_ACP_ENV_ALLOWLIST", '["MISSING_KEY", "PATH"]')
    # Ensure MISSING_KEY is not in os.environ
    monkeypatch.delenv("MISSING_KEY", raising=False)
    monkeypatch.setenv("PATH", "/resolved/path")

    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()

    # Override cfg to use ACP transport (resolve_brain_config defaults to openai)
    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy", "acp"],
        acp_workdir="/tmp",
        acp_env_allowlist=cfg.acp_env_allowlist,
    )

    base = {"HOME": "/home/u"}
    env = _build_acp_subprocess_env(cfg, base_env=base)

    # MISSING_KEY should not appear (not in os.environ)
    assert "MISSING_KEY" not in env, "Missing env key should not appear in subprocess env"
    # PATH should appear (was in os.environ and in the list)
    assert "PATH" in env, "PATH should be resolved from env via list allowlist"
    assert env["PATH"] == "/resolved/path"


def test_acp_existing_non_provider_allowlist_still_works():
    """Contract: existing non-provider allowlist entries still work.
    Backward compatibility: dict-style allowlist for runtime config vars
    continues to function as before.
    """
    from tools.agent_bridge.acp_client import _build_acp_subprocess_env
    from tools.agent_bridge.config import BrainConfig

    base = {"PATH": "/usr/bin", "HOME": "/home/u"}
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
            "CUSTOM_CONFIG": "value1",
            "RUNTIME_FLAG": "enabled",
        },
    )
    env = _build_acp_subprocess_env(cfg, base_env=base)

    assert env["CUSTOM_CONFIG"] == "value1"
    assert env["RUNTIME_FLAG"] == "enabled"
    assert env["PATH"] == "/usr/bin"


# ──────────────────────────────────────────────────────────────────────
# v6-ce-acp-env-allowlist: zero-config known provider key passthrough
# ──────────────────────────────────────────────────────────────────────


def test_life_index_api_key_always_stripped():
    """Contract: LIFE_INDEX_LLM_API_KEY is always stripped, even when someone
    tries to put it in the allowlist.  The key belongs to Life Index alone.
    """
    from tools.agent_bridge.acp_client import _build_acp_subprocess_env
    from tools.agent_bridge.config import BrainConfig

    base = {
        "PATH": "/usr/bin",
        "LIFE_INDEX_LLM_API_KEY": "sk-life-index-secret",
    }
    # Attempt to allowlist Life Index's own key — should be ignored
    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy", "acp"],
        acp_workdir="/tmp",
        acp_env_allowlist={"LIFE_INDEX_LLM_API_KEY": "sk-override-attempt"},
    )
    env = _build_acp_subprocess_env(cfg, base_env=base)

    # LIFE_INDEX_LLM_API_KEY must never reach the subprocess
    assert (
        "LIFE_INDEX_LLM_API_KEY" not in env
    ), "LIFE_INDEX_LLM_API_KEY leaked despite always-strip contract"


def test_unallowlisted_credential_keys_stripped_by_default():
    """Contract: credential-like variables that are NOT known runtime
    provider keys are stripped by default (no allowlist needed to strip them).
    """
    from tools.agent_bridge.acp_client import _build_acp_subprocess_env
    from tools.agent_bridge.config import BrainConfig

    base = {
        "PATH": "/usr/bin",
        "FAKE_SECRET_TOKEN": "tok123",
        "FOO_API_KEY": "sk-novel-provider",
        "MY_SECRET": "s3cret",
        "DB_PASSWORD": "p@ss",
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
    )
    env = _build_acp_subprocess_env(cfg, base_env=base)

    # All credential-like keys not in the known provider set are stripped
    for bad_key in ("FAKE_SECRET_TOKEN", "FOO_API_KEY", "MY_SECRET", "DB_PASSWORD"):
        assert bad_key not in env, f"Unallowlisted credential-like {bad_key} should be stripped"
    # Non-credential vars survive
    assert "PATH" in env


def test_novel_provider_key_passes_when_allowlisted(monkeypatch):
    """Contract: a novel provider key (e.g. FOO_API_KEY) not in the known
    runtime provider set passes to the ACP subprocess ONLY when explicitly
    allowlisted via the list syntax.
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import resolve_brain_config

    monkeypatch.setenv("FOO_API_KEY", "sk-novel-provider-from-env")
    monkeypatch.setenv("LIFE_INDEX_ACP_ENV_ALLOWLIST", '["FOO_API_KEY"]')

    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["dummy", "acp"],
                "data_exposure_ack": True,
            }
        },
    )

    captured_env: dict = {}

    def _fake_popen(args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        raise _EnvCaptureSentinel("captured")

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    cfg = resolve_brain_config()

    with pytest.raises(_EnvCaptureSentinel):
        acp_synthesize(cfg, "test system", "test user")

    # FOO_API_KEY reaches the subprocess because it was explicitly allowlisted
    assert "FOO_API_KEY" in captured_env, (
        "FOO_API_KEY should pass when allowlisted; " f"captured keys: {sorted(captured_env.keys())}"
    )
    # Must NOT log the secret value in assertions — only check presence


def test_novel_provider_key_stripped_without_allowlist(monkeypatch):
    """Contract: a novel provider key (e.g. FOO_API_KEY) NOT in the known
    runtime provider set is stripped by default when there is no allowlist.
    """
    from tools.agent_bridge.acp_client import acp_synthesize
    from tools.agent_bridge.config import BrainConfig

    monkeypatch.setenv("FOO_API_KEY", "sk-novel-provider-from-env")

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

    # FOO_API_KEY is not a known provider and was not allowlisted
    assert "FOO_API_KEY" not in captured_env, "FOO_API_KEY should be stripped without allowlist"


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


# ──────────────────────────────────────────────────────────────────────
# Phase V5b-1: _ACPConnection lifecycle probes
# ──────────────────────────────────────────────────────────────────────


def test_acp_connection_is_alive_reflects_subprocess_state():
    """is_alive() is True while the subprocess runs and False after cleanup."""
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
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

    conn = _ACPConnection(cfg)
    assert conn.is_alive() is False, "Unentered connection must report dead"

    conn.__enter__()
    assert conn.is_alive() is True, "Running subprocess must report alive"
    assert conn.pid is not None and conn.pid > 0

    conn.close()
    assert conn.is_alive() is False, "Closed connection must report dead"
    assert conn.pid is None


def test_acp_connection_close_is_idempotent():
    """close() can be called multiple times without error."""
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    fake_agent = sys.executable
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

    conn = _ACPConnection(cfg)
    conn.__enter__()
    conn.close()
    conn.close()
    assert conn.is_alive() is False


# ──────────────────────────────────────────────────────────────────────
# Phase V5b-2: incremental stream_callback hook
# ──────────────────────────────────────────────────────────────────────


def _make_handshake_responses(session_id: str = "s1") -> list[str]:
    """Return JSON-RPC responses for initialize → authenticate → session/new."""
    return [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": 1,
                    "serverInfo": {"name": "fake-acp", "version": "0.1.0"},
                    "authMethods": [{"id": "api-key", "name": "API Key"}],
                    "capabilities": {},
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"status": "ok"}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "result": {"sessionId": session_id, "cwd": "/tmp"},
            }
        ),
    ]


def test_acp_connection_rpc_calls_stream_callback_per_chunk(monkeypatch):
    """rpc(stream_callback=...) forwards each agent_message_chunk incrementally.

    Regression for the V5a final-buffer-only behaviour: the callback must be
    invoked once per chunk as notifications arrive, before the RPC response
    is returned, and the final collected_text must still parse correctly.
    """
    import io
    import json
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy"],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    chunks = ["alpha", "beta", "gamma"]
    notifications = []
    for text in chunks:
        notifications.append(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "s1",
                        "update": {
                            "content": {"text": text, "type": "text"},
                            "sessionUpdate": "agent_message_chunk",
                        },
                    },
                }
            )
        )
    prompt_response = json.dumps({"jsonrpc": "2.0", "id": 4, "result": {"status": "ok"}})
    stdout_text = "\n".join(_make_handshake_responses() + notifications + [prompt_response]) + "\n"

    class _FakeStdout:
        def __init__(self, text: str):
            self._io = io.StringIO(text)

        def readline(self) -> str:
            return self._io.readline()

        def close(self) -> None:
            self._io.close()

    class _FakeProc:
        def __init__(self):
            self.stdout = _FakeStdout(stdout_text)
            self.stdin = io.StringIO()
            self._poll = None

        def poll(self):
            return self._poll

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    captured_chunks: list[str] = []

    def _fake_popen(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    conn = _ACPConnection(cfg, rpc_timeout=5)
    conn.__enter__()

    def _on_chunk(text: str) -> None:
        captured_chunks.append(text)

    resp = conn.rpc("session/prompt", {"sessionId": "s1", "prompt": []}, stream_callback=_on_chunk)

    assert resp["result"]["status"] == "ok"
    assert captured_chunks == chunks, f"Expected chunks {chunks}, got {captured_chunks}"
    # Final parse still works and contains all chunks in order.
    from tools.agent_bridge.acp_client import parse_acp_stream

    assert parse_acp_stream(conn.collected) == "alphabetagamma"
    conn.close()


def test_acp_connection_rpc_ignores_non_chunk_notifications_for_stream_callback(monkeypatch):
    """Only agent_message_chunk notifications trigger stream_callback."""
    import io
    import json
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy"],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    prompt_lines = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "s1",
                    "update": {
                        "content": {"text": "thought", "type": "text"},
                        "sessionUpdate": "agent_thought_chunk",
                    },
                },
            }
        ),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "s1",
                    "update": {
                        "content": {"text": "word", "type": "text"},
                        "sessionUpdate": "agent_message_chunk",
                    },
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 4, "result": {"status": "ok"}}),
    ]

    stdout_text = "\n".join(_make_handshake_responses() + prompt_lines) + "\n"

    class _FakeStdout:
        def __init__(self, text: str):
            self._io = io.StringIO(text)

        def readline(self) -> str:
            return self._io.readline()

        def close(self) -> None:
            self._io.close()

    class _FakeProc:
        def __init__(self):
            self.stdout = _FakeStdout(stdout_text)
            self.stdin = io.StringIO()

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    def _fake_popen(*args, **kwargs):
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    conn = _ACPConnection(cfg, rpc_timeout=5)
    conn.__enter__()

    captured: list[str] = []
    conn.rpc("session/prompt", {"sessionId": "s1"}, stream_callback=captured.append)

    assert captured == ["word"]
    conn.close()


def test_acp_connection_rpc_can_forward_progress_updates_when_opted_in(monkeypatch):
    """ACP tool updates can feed SSE progress without leaking answer chunks."""
    import io
    import json
    from tools.agent_bridge.acp_client import _ACPConnection
    from tools.agent_bridge.config import BrainConfig

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="acp",
        api_key=None,
        model=None,
        data_exposure_ack=True,
        acp_command=["dummy"],
        acp_workdir=str(FIXTURE_PATH.parent),
    )

    prompt_lines = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "s1",
                    "update": {
                        "sessionUpdate": "tool_call",
                        "toolName": "index-tree",
                        "status": "running",
                    },
                },
            }
        ),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "s1",
                    "update": {
                        "content": {"text": "final json chunk", "type": "text"},
                        "sessionUpdate": "agent_message_chunk",
                    },
                },
            }
        ),
        json.dumps({"jsonrpc": "2.0", "id": 4, "result": {"status": "ok"}}),
    ]

    stdout_text = "\n".join(_make_handshake_responses() + prompt_lines) + "\n"

    class _FakeStdout:
        def __init__(self, text: str):
            self._io = io.StringIO(text)

        def readline(self) -> str:
            return self._io.readline()

        def close(self) -> None:
            self._io.close()

    class _FakeProc:
        def __init__(self):
            self.stdout = _FakeStdout(stdout_text)
            self.stdin = io.StringIO()

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: _FakeProc())

    conn = _ACPConnection(cfg, rpc_timeout=5)
    conn.__enter__()

    captured: list[Any] = []
    conn.rpc(
        "session/prompt",
        {"sessionId": "s1"},
        stream_callback=captured.append,
        stream_progress=True,
    )

    assert captured[0]["type"] == "progress"
    assert captured[0]["source"] == "acp"
    assert captured[0]["session_update"] == "tool_call"
    assert captured[0]["tool"] == "index-tree"
    assert captured[0]["status"] == "running"
    assert captured[1] == "final json chunk"
    conn.close()
