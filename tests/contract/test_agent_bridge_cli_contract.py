import json
import subprocess
import sys


def _invoke(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    return json.loads(result.stdout)


def test_top_level_agent_bridge_probe_json_no_network():
    result = _invoke("-m", "tools", "agent-bridge", "probe", "--json", "--no-network")

    payload = _json(result)
    assert payload["schema_version"] == "m35.agent_bridge_probe.v0"
    assert payload["command"] == "agent-bridge probe"
    assert payload["sends_journal_evidence"] is False
    assert "scaffold" not in payload
    assert "synthesis" not in payload


def test_module_agent_bridge_probe_json_no_network():
    result = _invoke("-m", "tools.agent_bridge", "probe", "--json", "--no-network")

    payload = _json(result)
    assert payload["success"] is True
    assert payload["sends_journal_evidence"] is False


def test_agent_bridge_help_mentions_probe():
    result = _invoke("-m", "tools", "agent-bridge", "--help")

    assert result.returncode == 0
    assert "probe" in result.stdout
    assert "--no-network" in result.stdout


def test_probe_requires_json_flag():
    result = _invoke("-m", "tools", "agent-bridge", "probe", "--no-network")

    assert result.returncode != 0
    assert "--json is required" in result.stderr
