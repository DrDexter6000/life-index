import json
import subprocess


def _clear_env(mp):
    for key in (
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
        mp.delenv(key, raising=False)


def _acp_probe_config(monkeypatch, *, acp_command=None, ack=True):
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        "tools.lib.config.USER_CONFIG",
        {
            "brain": {
                "mode": "host_agent",
                "transport": "acp",
                "data_exposure_ack": ack,
                "acp_command": acp_command,
            }
        },
    )


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


def test_acp_configured_executable_resolvable(monkeypatch):
    _acp_probe_config(monkeypatch, acp_command=["hermes", "acp"], ack=True)
    fake_path = "/usr/local/bin/hermes"
    monkeypatch.setattr("shutil.which", lambda cmd: fake_path if cmd == "hermes" else None)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["transport"] == "acp"
    assert result["acp"]["command_configured"] is True
    assert result["acp"]["command"] == ["hermes", "acp"]
    assert result["acp"]["executable_resolved"] == fake_path
    assert result["acp"]["live_handshake"]["status"] == "skip"
    assert result["ready_to_send_evidence"] is True

    check_names = {check["name"] for check in result["checks"]}
    assert "acp_command" in check_names
    assert "acp_executable" in check_names


def test_acp_configured_executable_not_resolvable(monkeypatch):
    _acp_probe_config(monkeypatch, acp_command=["hermes", "acp"], ack=True)
    monkeypatch.setattr("shutil.which", lambda _cmd: None)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["transport"] == "acp"
    assert result["acp"]["command_configured"] is True
    assert result["acp"]["command"] == ["hermes", "acp"]
    assert result["acp"]["executable_resolved"] is None
    assert result["ready_to_send_evidence"] is False

    exec_checks = [check for check in result["checks"] if check["name"] == "acp_executable"]
    assert len(exec_checks) == 1
    assert exec_checks[0]["status"] == "fail"


def test_acp_no_command_configured(monkeypatch):
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


def test_acp_no_subprocess_spawning_when_network_false(monkeypatch):
    _acp_probe_config(monkeypatch, acp_command=["hermes", "acp"], ack=True)
    monkeypatch.setattr("shutil.which", lambda _cmd: "/fake/path/hermes")

    def _fail_popen(*_args, **_kwargs):
        raise AssertionError("ACP --no-network probe must not spawn subprocess.Popen")

    monkeypatch.setattr(subprocess, "Popen", _fail_popen)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["transport"] == "acp"
    assert result["acp"]["executable_resolved"] == "/fake/path/hermes"
    assert result["live_handshake"]["status"] == "skip"


def test_acp_no_secret_leakage(monkeypatch):
    _acp_probe_config(monkeypatch, acp_command=["hermes", "acp"], ack=True)
    monkeypatch.setenv("LIFE_INDEX_LLM_API_KEY", "acp-secret-12345")
    monkeypatch.setattr("shutil.which", lambda _cmd: "/usr/local/bin/hermes")

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)
    serialized = json.dumps(result, ensure_ascii=False)

    assert "acp-secret-12345" not in serialized
    assert "secret-token-value" not in serialized


def test_probe_live_handshake_success_with_fake_acp(monkeypatch):
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent / "fixtures" / "agent_bridge" / "fake_acp_agent.py"
    )
    _acp_probe_config(monkeypatch, acp_command=[sys.executable, str(fake_script)], ack=True)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=5.0)

    assert result["transport"] == "acp"
    handshake = result["live_handshake"]
    assert result["acp"]["live_handshake"] == handshake
    assert handshake["status"] == "pass"
    assert "duration_ms" in handshake
    steps = handshake["steps"]
    assert isinstance(steps, dict)
    assert "initialize" in steps
    assert "authenticate" in steps
    assert "session_new" in steps


def test_probe_live_handshake_command_missing(monkeypatch):
    _acp_probe_config(
        monkeypatch,
        acp_command=["/nonexistent/path/to/acp-binary-that-does-not-exist"],
        ack=True,
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=5.0)

    handshake = result["live_handshake"]
    assert handshake["status"] == "fail"
    assert "error" in handshake
    assert "sk-" not in str(handshake.get("error", ""))
    assert isinstance(handshake["steps"], dict)


def test_probe_live_handshake_no_network_skip(monkeypatch):
    _acp_probe_config(monkeypatch, acp_command=["echo", "should-not-be-called"], ack=True)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["transport"] == "acp"
    assert result["live_handshake"]["status"] == "skip"


def test_probe_live_handshake_timeout_cleanup(monkeypatch):
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "agent_bridge"
        / "fake_acp_agent_hang.py"
    )
    _acp_probe_config(monkeypatch, acp_command=[sys.executable, str(fake_script)], ack=True)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=2.0)

    handshake = result["live_handshake"]
    assert handshake["status"] == "fail"
    assert "error" in handshake
    assert handshake.get("duration_ms", 0) > 0
    assert isinstance(handshake["steps"], dict)


def test_acp_live_handshake_enforces_overall_deadline(monkeypatch):
    import sys
    import time
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "agent_bridge"
        / "fake_acp_agent_slow_handshake.py"
    )
    _acp_probe_config(monkeypatch, acp_command=[sys.executable, str(fake_script)], ack=True)

    from tools.agent_bridge.config import resolve_brain_config
    from tools.agent_bridge.probe import _acp_live_handshake

    cfg = resolve_brain_config()

    start = time.monotonic()
    handshake = _acp_live_handshake(cfg, timeout=0.6, network=True)
    elapsed = time.monotonic() - start

    assert handshake["status"] == "fail"
    assert "handshake deadline" in handshake.get("error", "").lower()
    assert elapsed < 3.0
    assert handshake.get("duration_ms", 0) < 3000


def test_probe_never_sends_session_prompt(monkeypatch):
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent / "fixtures" / "agent_bridge" / "fake_acp_agent.py"
    )
    _acp_probe_config(monkeypatch, acp_command=[sys.executable, str(fake_script)], ack=True)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=10.0)

    handshake = result["live_handshake"]
    assert handshake["status"] != "fail" or "timeout" not in str(handshake.get("error", "")).lower()


def test_probe_ready_to_send_evidence_for_acp(monkeypatch):
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent / "fixtures" / "agent_bridge" / "fake_acp_agent.py"
    )
    _acp_probe_config(monkeypatch, acp_command=[sys.executable, str(fake_script)], ack=True)

    from tools.agent_bridge.probe import probe_agent_bridge

    result_net = probe_agent_bridge(network=True, timeout=10.0)
    assert result_net["sends_journal_evidence"] is False
    assert result_net["transport"] == "acp"
    if result_net.get("live_handshake", {}).get("status") == "pass":
        assert result_net["ready_to_send_evidence"] is True

    result_no_net = probe_agent_bridge(network=False)
    assert result_no_net["sends_journal_evidence"] is False
    assert result_no_net["ready_to_send_evidence"] is True


def test_probe_live_handshake_authenticate_skip(monkeypatch):
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "agent_bridge"
        / "fake_acp_agent_noauth.py"
    )
    _acp_probe_config(monkeypatch, acp_command=[sys.executable, str(fake_script)], ack=True)

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=10.0)

    handshake = result["live_handshake"]
    assert handshake["status"] == "pass"
    steps = handshake.get("steps", {})
    assert isinstance(steps, dict)
    assert steps.get("initialize") == "pass"
    assert steps.get("authenticate") == "skip"
    assert steps.get("session_new") == "pass"
