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


# ──────────────────────────────────────────────────────────────────────
# Phase C-2: Probe live handshake tests
# ──────────────────────────────────────────────────────────────────────


def _acp_probe_config(monkeypatch, *, acp_command=None, ack=True, network=True):
    """Set up config for ACP probe testing."""
    for k in (
        "LIFE_INDEX_LLM_API_KEY",
        "LIFE_INDEX_LLM_BASE_URL",
        "LIFE_INDEX_LLM_MODEL",
        "LIFE_INDEX_BRAIN_MODE",
        "LIFE_INDEX_BRAIN_ENDPOINT",
    ):
        monkeypatch.delenv(k, raising=False)
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


def test_probe_live_handshake_success_with_fake_acp(monkeypatch):
    """Contract: probe live_handshake reports pass when fake ACP agent responds.

    Uses the fake ACP agent fixture that responds to handshake methods.
    The probe must report status='pass' and include steps/duration.
    """
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent / "fixtures" / "agent_bridge" / "fake_acp_agent.py"
    )
    _acp_probe_config(
        monkeypatch,
        acp_command=[sys.executable, str(fake_script)],
        ack=True,
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=5.0)

    assert result["transport"] == "acp"
    assert (
        "live_handshake" in result
    ), f"ACP transport must include live_handshake field: {list(result.keys())}"
    handshake = result["live_handshake"]
    assert handshake["status"] == "pass", f"Expected pass, got {handshake}"
    assert "duration_ms" in handshake
    assert "steps" in handshake
    # steps must be a dict, not a list
    steps = handshake["steps"]
    assert isinstance(steps, dict), f"steps must be dict, got {type(steps).__name__}"
    assert "initialize" in steps, f"steps missing initialize key: {list(steps.keys())}"
    assert "authenticate" in steps, f"steps missing authenticate key: {list(steps.keys())}"
    assert "session_new" in steps, f"steps missing session_new key: {list(steps.keys())}"


def test_probe_live_handshake_command_missing(monkeypatch):
    """Contract: probe live_handshake reports fail when acp_command binary is missing.

    Uses a non-existent command path; the probe must catch FileNotFoundError
    and report status='fail' with a sanitized error message (no secrets).
    """
    _acp_probe_config(
        monkeypatch,
        acp_command=["/nonexistent/path/to/acp-binary-that-does-not-exist"],
        ack=True,
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=5.0)

    assert result["transport"] == "acp"
    assert "live_handshake" in result
    handshake = result["live_handshake"]
    assert handshake["status"] == "fail", f"Expected fail for missing command, got {handshake}"
    assert "error" in handshake
    # Error message must not contain secrets
    assert "sk-" not in str(handshake.get("error", ""))
    # steps must be a dict on failure
    assert (
        "steps" in handshake
    ), f"handshake must include steps on failure: {list(handshake.keys())}"
    failed_steps = handshake["steps"]
    assert isinstance(failed_steps, dict), f"steps must be dict, got {type(failed_steps).__name__}"


def test_probe_live_handshake_no_network_skip(monkeypatch):
    """Contract: --no-network must report skip for live_handshake.

    When network=False, the probe must not attempt any subprocess and
    report live_handshake status='skip'.
    """
    _acp_probe_config(
        monkeypatch,
        acp_command=["echo", "should-not-be-called"],
        ack=True,
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=False)

    assert result["transport"] == "acp"
    assert "live_handshake" in result
    handshake = result["live_handshake"]
    assert handshake["status"] == "skip", f"Expected skip for --no-network, got {handshake}"


def test_probe_live_handshake_timeout_cleanup(monkeypatch):
    """Contract: probe live_handshake times out gracefully with cleanup.

    Uses the hang variant fake ACP agent that never responds.
    The probe must report fail after timeout and must not leak subprocesses.
    """
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "agent_bridge"
        / "fake_acp_agent_hang.py"
    )
    _acp_probe_config(
        monkeypatch,
        acp_command=[sys.executable, str(fake_script)],
        ack=True,
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=2.0)

    assert result["transport"] == "acp"
    assert "live_handshake" in result
    handshake = result["live_handshake"]
    assert handshake["status"] == "fail", f"Expected fail for timeout, got {handshake}"
    assert "error" in handshake
    assert handshake.get("duration_ms", 0) > 0
    # steps must be a dict on failure
    assert (
        "steps" in handshake
    ), f"handshake must include steps on failure: {list(handshake.keys())}"
    failed_steps = handshake["steps"]
    assert isinstance(failed_steps, dict), f"steps must be dict, got {type(failed_steps).__name__}"


def test_acp_live_handshake_enforces_overall_deadline(monkeypatch):
    """Contract: ACP live probe has one overall handshake deadline.

    The slow fixture responds to each RPC within the per-RPC timeout, but
    the cumulative handshake exceeds the total deadline. The helper must
    fail quickly instead of allowing one full timeout per handshake RPC.
    """
    import sys
    import time
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "agent_bridge"
        / "fake_acp_agent_slow_handshake.py"
    )
    _acp_probe_config(
        monkeypatch,
        acp_command=[sys.executable, str(fake_script)],
        ack=True,
    )

    from tools.agent_bridge.config import resolve_brain_config
    from tools.agent_bridge.probe import _acp_live_handshake

    cfg = resolve_brain_config()

    start = time.monotonic()
    handshake = _acp_live_handshake(cfg, timeout=0.6, network=True)
    elapsed = time.monotonic() - start

    assert handshake["status"] == "fail", f"Expected overall deadline fail, got {handshake}"
    assert "handshake deadline" in handshake.get("error", "").lower()
    assert elapsed < 3.0, f"Overall deadline cleanup took too long: {elapsed:.2f}s"
    assert handshake.get("duration_ms", 0) < 3000


def test_probe_never_sends_session_prompt(monkeypatch):
    """Contract: Probe live handshake must NEVER call session/prompt.

    The fake ACP agent hangs on session/prompt. If the probe sent it,
    the handshake would hang forever and timeout. A successful handshake
    with the fake agent proves session/prompt was never sent.
    """
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent / "fixtures" / "agent_bridge" / "fake_acp_agent.py"
    )
    _acp_probe_config(
        monkeypatch,
        acp_command=[sys.executable, str(fake_script)],
        ack=True,
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=10.0)

    # If session/prompt was sent, the fake agent would hang and we'd timeout
    assert result["transport"] == "acp"
    if "live_handshake" in result:
        handshake = result["live_handshake"]
        # Should NOT be a timeout failure
        assert (
            handshake["status"] != "fail"
            or "timeout" not in str(handshake.get("error", "")).lower()
        ), f"Handshake timed out — session/prompt may have been sent: {handshake}"


def test_probe_ready_to_send_evidence_for_acp(monkeypatch):
    """Contract: ready_to_send_evidence for ACP requires live_handshake pass when network=True.

    - network=True, live_handshake pass → ready_to_send_evidence may be True (if config-ready)
    - network=False → config-ready semantics only (no live_handshake required)
    - sends_journal_evidence is ALWAYS False
    """
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent / "fixtures" / "agent_bridge" / "fake_acp_agent.py"
    )
    _acp_probe_config(
        monkeypatch,
        acp_command=[sys.executable, str(fake_script)],
        ack=True,
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    # Network=True: live handshake must pass for ready_to_send_evidence
    result_net = probe_agent_bridge(network=True, timeout=10.0)
    assert result_net["sends_journal_evidence"] is False
    assert result_net["transport"] == "acp"
    # With successful handshake and ack=True, ready_to_send_evidence should be True
    if result_net.get("live_handshake", {}).get("status") == "pass":
        assert result_net["ready_to_send_evidence"] is True, (
            f"Expected ready_to_send_evidence=True when handshake passes, " f"got {result_net}"
        )

    # Network=False: config-ready semantics (ACP preserves source=P1 + ack=True = ready=True)
    result_no_net = probe_agent_bridge(network=False)
    assert result_no_net["sends_journal_evidence"] is False
    # ACP with network=False maintains config-ready semantics (not forced to False)
    assert result_no_net["ready_to_send_evidence"] is True


def test_probe_live_handshake_authenticate_skip(monkeypatch):
    """Contract: authenticate step is 'skip' when no auth methods available.

    Uses the noauth fixture (empty authMethods). The handshake must pass
    with steps["authenticate"] == "skip".
    """
    import sys
    from pathlib import Path

    fake_script = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "agent_bridge"
        / "fake_acp_agent_noauth.py"
    )
    _acp_probe_config(
        monkeypatch,
        acp_command=[sys.executable, str(fake_script)],
        ack=True,
    )

    from tools.agent_bridge.probe import probe_agent_bridge

    result = probe_agent_bridge(network=True, timeout=10.0)

    assert result["transport"] == "acp"
    assert "live_handshake" in result
    handshake = result["live_handshake"]
    assert handshake["status"] == "pass", f"Expected pass, got {handshake}"
    steps = handshake.get("steps", {})
    assert isinstance(steps, dict), f"steps must be dict, got {type(steps).__name__}"
    assert steps.get("initialize") == "pass"
    assert (
        steps.get("authenticate") == "skip"
    ), f"Expected authenticate=skip for no-auth agent, got {steps}"
    assert steps.get("session_new") == "pass"
