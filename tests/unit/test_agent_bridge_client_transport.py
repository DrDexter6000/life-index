"""Phase A RED transport contract tests for agent_bridge client.

Tests covering transport-level contracts:
- openai transport unchanged (GREEN - existing code)
- ACP prompt-safety requires data_exposure_ack (RED - ACP client missing)
- Unsupported transport raises UnsupportedTransportError via synthesize()
  (RED - error class + routing missing)
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


# ──────────────────────────────────────────────────────────────────────
# Transport: openai — unchanged behavior contract
# ──────────────────────────────────────────────────────────────────────


def test_transport_openai_unchanged(monkeypatch):
    """Contract: transport='openai' behavior must remain unchanged.

    This test monkeypatches openai.OpenAI and asserts the existing
    synthesize() call shape. When ACP adapter is added, this test
    must continue to pass — proving openai transport is not broken.

    Expected: GREEN (uses existing code path, no ACP dependency).

    The openai package is an optional L3 dependency and may not be
    installed in CI blocker gates. We inject a stub 'openai' module
    with an 'OpenAI' attribute into sys.modules so the test works
    regardless of whether the real package is installed.
    """
    from unittest.mock import MagicMock

    from tools.agent_bridge.client import synthesize
    from tools.agent_bridge.config import BrainConfig

    # Ensure 'openai' module exists in sys.modules with an 'OpenAI'
    # attribute, so monkeypatch.setattr("openai.OpenAI", ...) works
    # even without the real package installed.
    if "openai" not in sys.modules or not hasattr(sys.modules["openai"], "OpenAI"):
        import types

        _stub = types.ModuleType("openai")
        _stub.OpenAI = object  # placeholder; will be overwritten by monkeypatch
        sys.modules["openai"] = _stub

    # Build a fake OpenAI client
    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = "openai contract response"
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    # Monkeypatch openai.OpenAI to return our fake client
    monkeypatch.setattr("openai.OpenAI", lambda **kw: fake_client)

    cfg = BrainConfig(
        mode="host_agent",
        endpoint="http://localhost:8642/v1",
        transport="openai",
        api_key="test-api-key",
        model="test-model",
        data_exposure_ack=True,
    )

    result = synthesize(cfg, "system prompt", "user prompt")

    # Assert result
    assert result == "openai contract response"

    # Assert chat-completions call shape
    fake_client.chat.completions.create.assert_called_once()
    call_kwargs = fake_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "test-model"
    assert len(call_kwargs["messages"]) == 2
    assert call_kwargs["messages"][0] == {"role": "system", "content": "system prompt"}
    assert call_kwargs["messages"][1] == {"role": "user", "content": "user prompt"}


# ──────────────────────────────────────────────────────────────────────
# Transport: ACP — prompt-safety contract
# ──────────────────────────────────────────────────────────────────────


def test_acp_synthesis_requires_data_exposure_ack():
    """Contract: ACP transport must require data_exposure_ack before
    sending any prompt that may contain journal evidence.

    RED: tools.agent_bridge.acp_client.acp_synthesize does not exist yet.
    """
    # RED — intended failure: ACP client module not implemented
    from tools.agent_bridge.acp_client import acp_synthesize  # noqa: F811

    from tools.agent_bridge.config import AckRequiredError, BrainConfig

    cfg = BrainConfig(
        mode="byol",
        endpoint=None,
        transport="acp",
        api_key=None,
        model="hermes",
        data_exposure_ack=False,
    )

    with pytest.raises(AckRequiredError):
        acp_synthesize(cfg, "system", "user prompt with potential journal data")


# ──────────────────────────────────────────────────────────────────────
# Transport: unsupported
# ──────────────────────────────────────────────────────────────────────


def test_unsupported_transport_raises():
    """Contract: unknown transport must raise UnsupportedTransportError.

    Constructs a BrainConfig with an unknown transport value and asserts
    that the synthesize() path raises UnsupportedTransportError.
    The error class is expected to live in tools.agent_bridge.acp_client.

    RED: UnsupportedTransportError does not exist yet.
    May fail at import (ModuleNotFoundError) — intended RED.
    """
    # RED — intended failure: error class not implemented
    from tools.agent_bridge.acp_client import (  # noqa: F811
        UnsupportedTransportError,
    )

    from tools.agent_bridge.client import synthesize
    from tools.agent_bridge.config import BrainConfig

    cfg = BrainConfig(
        mode="host_agent",
        endpoint=None,
        transport="unknown_transport_xyz",
        api_key=None,
        model=None,
        data_exposure_ack=True,
    )

    with pytest.raises(UnsupportedTransportError):
        synthesize(cfg, "system prompt", "user prompt")
