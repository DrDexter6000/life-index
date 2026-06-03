"""P1 spike exit criterion: real Hermes round-trip.

Skipped unless LIFE_INDEX_BRAIN_ENDPOINT points at a reachable Hermes and
LIFE_INDEX_BRAIN_ACK=1 is set (explicit data-exposure acknowledgement for the probe).
"""

import os
import sys
from pathlib import Path
import urllib.request

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

ENDPOINT = os.environ.get("LIFE_INDEX_BRAIN_ENDPOINT", "")


def _hermes_reachable() -> bool:
    if not ENDPOINT or os.environ.get("LIFE_INDEX_BRAIN_ACK") != "1":
        return False
    try:
        base = ENDPOINT.rsplit("/v1", 1)[0]
        urllib.request.urlopen(base, timeout=1.5)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _hermes_reachable(), reason="Hermes endpoint not reachable / ack not set")
def test_p1_round_trip_via_real_hermes(monkeypatch):
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "endpoint": ENDPOINT,
                "transport": "openai",
                "api_key": os.environ.get("LIFE_INDEX_LLM_API_KEY", "local"),
                "model": os.environ.get("LIFE_INDEX_LLM_MODEL", "hermes"),
                "data_exposure_ack": True,
            },
        },
    )
    from tools.agent_bridge.handoff import handoff_search

    env = handoff_search("我和家人有哪些温暖的回忆？", in_context_agent=False)
    assert env["source"] == "P1"
    assert env["scaffold"]["smart_search_mode"] == "deterministic_scaffold"
    assert isinstance(env["synthesis"], str) and env["synthesis"].strip() != ""


def test_degrade_path_no_endpoint(monkeypatch):
    """Always-on: with no brain configured, handoff degrades to scaffold-only (no LLM)."""
    for k in (
        "LIFE_INDEX_BRAIN_ENDPOINT",
        "LIFE_INDEX_LLM_BASE_URL",
        "LIFE_INDEX_BRAIN_MODE",
        "LIFE_INDEX_LLM_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    from tools.agent_bridge.handoff import handoff_search

    env = handoff_search("test query", in_context_agent=False)
    assert env["source"] == "deterministic_only"
    assert env["synthesis"] is None
    assert env["scaffold"]["smart_search_mode"] == "deterministic_scaffold"
