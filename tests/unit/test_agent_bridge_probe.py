import json
import subprocess


def _clear_env(mp):
    for k in (
        "LIFE_INDEX_LLM_API_KEY",
        "LIFE_INDEX_LLM_BASE_URL",
        "LIFE_INDEX_LLM_MODEL",
        "LIFE_INDEX_BRAIN_MODE",
        "LIFE_INDEX_BRAIN_ENDPOINT",
        "LIFE_INDEX_ACP_COMMAND",
        "LIFE_INDEX_ACP_WORKDIR",
        "LIFE_INDEX_ACP_AUTH_METHOD",
        "LIFE_INDEX_ACP_ENV_ALLOWLIST",
    ):
        mp.delenv(k, raising=False)


# ── openai transport tests (existing) ──────────────────────────────────────


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


# ── ACP transport tests (new) ──────────────────────────────────────────────


def test_acp_configured_executable_resolvable(monkeypatch):
    """ACP transport with acp_command configured and executable in PATH."""
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["hermes", "acp"],
                "data_exposure_ack": True,
            }
        },
    )

    fake_path = "/usr/local/bin/hermes"

    def _fake_which(cmd):
        return fake_path if cmd == "hermes" else None

    monkeypatch.setattr("shutil.which", _fake_which)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["transport"] == "acp"
    assert result["acp"]["command_configured"] is True
    assert result["acp"]["command"] == ["hermes", "acp"]
    assert result["acp"]["executable_resolved"] == fake_path
    assert result["acp"]["live_handshake"]["status"] == "not_checked"
    assert result["acp"]["live_handshake"]["reason"] == "deferred to Phase C-2"
    assert result["ready_to_send_evidence"] is True

    # Verify checks list has ACP entries
    check_names = {c["name"] for c in result["checks"]}
    assert "acp_command" in check_names
    assert "acp_executable" in check_names


def test_acp_configured_executable_not_resolvable(monkeypatch):
    """ACP transport with acp_command configured but executable NOT in PATH."""
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["hermes", "acp"],
                "data_exposure_ack": True,
            }
        },
    )

    monkeypatch.setattr("shutil.which", lambda _cmd: None)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["transport"] == "acp"
    assert result["acp"]["command_configured"] is True
    assert result["acp"]["command"] == ["hermes", "acp"]
    assert result["acp"]["executable_resolved"] is None
    assert result["ready_to_send_evidence"] is False

    # acp_executable check should be fail
    exec_checks = [c for c in result["checks"] if c["name"] == "acp_executable"]
    assert len(exec_checks) == 1
    assert exec_checks[0]["status"] == "fail"


def test_acp_no_command_configured(monkeypatch):
    """ACP transport but acp_command is None → command_configured False."""
    _clear_env(monkeypatch)

    from tools.agent_bridge.config import BrainConfig

    def _mock_resolve():
        return BrainConfig(
            mode="host_agent",
            endpoint=None,
            transport="acp",
            api_key=None,
            model=None,
            data_exposure_ack=True,
            acp_command=None,
        )

    monkeypatch.setattr("tools.agent_bridge.probe.resolve_brain_config", _mock_resolve)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["transport"] == "acp"
    assert result["acp"]["command_configured"] is False
    assert result["acp"]["command"] is None
    assert result["acp"]["executable_resolved"] is None
    assert result["ready_to_send_evidence"] is False


def test_acp_no_subprocess_spawning(monkeypatch):
    """ACP probe path must not spawn subprocess.Popen — only shutil.which."""
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["hermes", "acp"],
                "data_exposure_ack": True,
            }
        },
    )

    import subprocess as sp

    def _fail_popen(*_args, **_kwargs):
        raise AssertionError("ACP probe must not spawn subprocess.Popen")

    monkeypatch.setattr(sp, "Popen", _fail_popen)

    # shutil.which returns a fake path to exercise the ACP path
    monkeypatch.setattr("shutil.which", lambda _cmd: "/fake/path/hermes")

    from tools.agent_bridge.probe import probe_agent_bridge

    # Must not raise AssertionError
    result = probe_agent_bridge(network=False)
    assert result["transport"] == "acp"
    assert result["acp"]["executable_resolved"] == "/fake/path/hermes"


def test_acp_no_secret_leakage(monkeypatch):
    """json.dumps of ACP probe result must not contain secret values."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "acp-secret-12345")
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "acp_command": ["hermes", "acp"],
                "data_exposure_ack": True,
            }
        },
    )
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/local/bin/hermes")

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)
    serialized = json.dumps(result, ensure_ascii=False)
    assert "acp-secret-12345" not in serialized
    assert "secret-token-value" not in serialized
