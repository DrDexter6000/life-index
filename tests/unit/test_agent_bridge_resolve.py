import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from tools.agent_bridge.config import BrainConfig
from tools.agent_bridge.resolve import resolve_source


def _cfg(mode="auto", endpoint=None, api_key=None, ack=False):
    return BrainConfig(
        mode=mode,
        endpoint=endpoint,
        transport="openai",
        api_key=api_key,
        model="m",
        data_exposure_ack=ack,
    )


def test_p0_when_in_context():
    assert resolve_source(_cfg(), in_context_agent=True) == "P0"


def test_p1_when_host_endpoint_and_ack():
    assert (
        resolve_source(
            _cfg(endpoint="http://localhost:8642/v1", api_key="k", ack=True), in_context_agent=False
        )
        == "P1"
    )


def test_p2_label_when_byol_endpoint():
    # P1 vs P2 differ only by intent; both are endpoints. mode pins it when set.
    assert (
        resolve_source(
            _cfg(mode="byol", endpoint="https://api.openai.com/v1", api_key="k", ack=True),
            in_context_agent=False,
        )
        == "P2"
    )


def test_degrade_when_no_endpoint():
    assert resolve_source(_cfg(endpoint=None), in_context_agent=False) == "deterministic_only"


def test_degrade_when_no_ack():
    assert (
        resolve_source(_cfg(endpoint="http://x/v1", api_key="k", ack=False), in_context_agent=False)
        == "deterministic_only"
    )


def test_explicit_in_context_mode_forces_p0():
    assert resolve_source(_cfg(mode="in_context"), in_context_agent=False) == "P0"


# ──────────────────────────────────────────────────────────────────────
# Phase C-2: ACP-aware resolve_source tests
# ──────────────────────────────────────────────────────────────────────


def _acp_cfg(mode="auto", ack=False, acp_command=None):
    """Create a BrainConfig with ACP transport."""
    return BrainConfig(
        mode=mode,
        endpoint=None,
        transport="acp",
        api_key=None,
        model="m",
        data_exposure_ack=ack,
        acp_command=acp_command,
    )


def test_usable_acp_returns_p1_when_acp_configured():
    """Contract: ACP transport + acp_command + ack → P1."""
    assert (
        resolve_source(
            _acp_cfg(mode="auto", ack=True, acp_command=["acp", "serve"]),
            in_context_agent=False,
        )
        == "P1"
    )


def test_usable_acp_returns_p2_when_byol_mode():
    """Contract: ACP + byol mode → P2 (same intent-label semantics as endpoint P2)."""
    assert (
        resolve_source(
            _acp_cfg(mode="byol", ack=True, acp_command=["acp", "serve"]),
            in_context_agent=False,
        )
        == "P2"
    )


def test_explicit_deterministic_only_with_acp_still_returns_deterministic_only():
    """Contract: mode='deterministic_only' is respected even with full ACP config.

    The early return for deterministic_only must fire before any ACP check.
    """
    assert (
        resolve_source(
            _acp_cfg(mode="deterministic_only", ack=True, acp_command=["acp", "serve"]),
            in_context_agent=False,
        )
        == "deterministic_only"
    )


def test_acp_without_ack_returns_deterministic_only():
    """Contract: ACP without data_exposure_ack → deterministic_only (same as endpoint)."""
    assert (
        resolve_source(
            _acp_cfg(mode="auto", ack=False, acp_command=["acp", "serve"]),
            in_context_agent=False,
        )
        == "deterministic_only"
    )


def test_acp_without_command_returns_deterministic_only():
    """Contract: ACP transport without acp_command → deterministic_only (nothing usable)."""
    assert (
        resolve_source(
            _acp_cfg(mode="auto", ack=True, acp_command=None),
            in_context_agent=False,
        )
        == "deterministic_only"
    )
