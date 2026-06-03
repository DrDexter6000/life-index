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
