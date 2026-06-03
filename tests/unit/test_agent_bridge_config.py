import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _clear_env(mp):
    for k in (
        "LIFE_INDEX_LLM_API_KEY",
        "LIFE_INDEX_LLM_BASE_URL",
        "LIFE_INDEX_LLM_MODEL",
        "LIFE_INDEX_BRAIN_MODE",
        "LIFE_INDEX_BRAIN_ENDPOINT",
    ):
        mp.delenv(k, raising=False)


def test_resolve_brain_config_reads_brain_section(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "endpoint": "http://localhost:8642/v1",
                "transport": "openai",
                "data_exposure_ack": True,
            }
        },
    )
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    assert cfg.mode == "host_agent"
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.data_exposure_ack is True


def test_brain_falls_back_to_llm_section(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {"llm": {"api_key": "k", "base_url": "http://localhost:8642/v1", "model": "hermes"}},
    )
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.model == "hermes"


def test_env_overrides_config(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})
    monkeypatch.setenv("LIFE_INDEX_BRAIN_ENDPOINT", "http://localhost:8642/v1")
    monkeypatch.setenv("LIFE_INDEX_BRAIN_MODE", "host_agent")
    from tools.agent_bridge.config import resolve_brain_config

    cfg = resolve_brain_config()
    assert cfg.endpoint == "http://localhost:8642/v1"
    assert cfg.mode == "host_agent"


def test_ack_required_raises_without_ack(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {"brain": {"mode": "host_agent", "endpoint": "http://x/v1", "data_exposure_ack": False}},
    )
    from tools.agent_bridge.config import resolve_brain_config, require_ack, AckRequiredError

    cfg = resolve_brain_config()
    import pytest

    with pytest.raises(AckRequiredError):
        require_ack(cfg)
