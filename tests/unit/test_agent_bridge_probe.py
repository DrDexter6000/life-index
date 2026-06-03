import json
import subprocess


def _clear_env(mp):
    for k in (
        "LIFE_INDEX_LLM_API_KEY",
        "LIFE_INDEX_LLM_BASE_URL",
        "LIFE_INDEX_LLM_MODEL",
        "LIFE_INDEX_BRAIN_MODE",
        "LIFE_INDEX_BRAIN_ENDPOINT",
    ):
        mp.delenv(k, raising=False)


def test_probe_degrades_without_endpoint_or_token(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["success"] is True
    assert result["source"] == "deterministic_only"
    assert result["sends_journal_evidence"] is False
    assert result["ready_to_send_evidence"] is False
    assert result["ack"]["data_exposure_ack"] is False
    assert result["token"]["configured"] is False


def test_probe_reports_token_source_without_secret(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "secret-token-value")
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "endpoint": "http://127.0.0.1:8642/v1",
                "transport": "openai",
                "model": "hermes-agent",
                "data_exposure_ack": True,
            }
        },
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["source"] == "P1"
    assert result["token"] == {
        "configured": True,
        "source": "env:LIFE_INDEX_LLM_API_KEY",
        "persisted_in_config": False,
    }
    assert result["model"]["configured"] is True
    assert result["ready_to_send_evidence"] is False
    assert "secret-token-value" not in json.dumps(result, ensure_ascii=False)


def test_probe_does_not_call_smart_search_or_handoff(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr("tools.lib.config.USER_CONFIG", {})

    def fail_subprocess_run(*_args, **_kwargs):
        raise AssertionError("probe must not run smart-search subprocesses")

    def fail_handoff(*_args, **_kwargs):
        raise AssertionError("probe must not call handoff_search")

    monkeypatch.setattr(subprocess, "run", fail_subprocess_run)
    monkeypatch.setattr("tools.agent_bridge.handoff.handoff_search", fail_handoff)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["sends_journal_evidence"] is False
    assert result["source"] == "deterministic_only"
