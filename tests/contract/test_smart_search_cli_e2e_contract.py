#!/usr/bin/env python3
"""CLI-level E2E contract tests for `python -m tools.smart_search`.

These tests invoke the smart-search CLI as a real subprocess.  The subprocess
results are session-scoped because the first isolated-data run builds an empty
index and costs several seconds on Windows.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_smart_search(
    *extra_args: str,
    data_dir: Path,
) -> subprocess.CompletedProcess[str]:
    """Run smart-search CLI as a subprocess with an isolated data dir."""
    env = {**os.environ, "LIFE_INDEX_DATA_DIR": str(data_dir)}
    return subprocess.run(
        [sys.executable, "-m", "tools.smart_search", *extra_args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
        timeout=30,
    )


def _json(proc: subprocess.CompletedProcess[str]) -> dict:
    """Parse JSON stdout from a smart-search subprocess result."""
    return json.loads(proc.stdout)


@pytest.fixture(scope="session")
def sandbox(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a process-isolated empty Life Index data directory."""
    data_dir = tmp_path_factory.mktemp("life-index-r2f") / "Life-Index"
    (data_dir / "Journals").mkdir(parents=True, exist_ok=True)
    (data_dir / ".index").mkdir(parents=True, exist_ok=True)
    (data_dir / ".cache").mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture(scope="session")
def default_proc(sandbox: Path) -> subprocess.CompletedProcess[str]:
    return _run_smart_search("--query", "test", "--no-llm", data_dir=sandbox)


@pytest.fixture(scope="session")
def evidence_proc(sandbox: Path) -> subprocess.CompletedProcess[str]:
    return _run_smart_search(
        "--query",
        "test",
        "--no-llm",
        "--include-evidence",
        data_dir=sandbox,
    )


@pytest.fixture(scope="session")
def synthesize_proc(sandbox: Path) -> subprocess.CompletedProcess[str]:
    return _run_smart_search("--query", "test", "--no-llm", "--synthesize", data_dir=sandbox)


@pytest.fixture(scope="session")
def combined_proc(sandbox: Path) -> subprocess.CompletedProcess[str]:
    return _run_smart_search(
        "--query",
        "test",
        "--no-llm",
        "--include-evidence",
        "--synthesize",
        data_dir=sandbox,
    )


@pytest.fixture(scope="session")
def explain_proc(sandbox: Path) -> subprocess.CompletedProcess[str]:
    return _run_smart_search("--query", "test", "--no-llm", "--explain", data_dir=sandbox)


@pytest.fixture(scope="session")
def help_proc(sandbox: Path) -> subprocess.CompletedProcess[str]:
    return _run_smart_search("--help", data_dir=sandbox)


class TestDefaultOutputContract:
    """Default output has the stable public shape."""

    def test_exit_code_zero(self, default_proc: subprocess.CompletedProcess[str]) -> None:
        assert default_proc.returncode == 0, f"stderr: {default_proc.stderr}"

    def test_stdout_is_valid_json(self, default_proc: subprocess.CompletedProcess[str]) -> None:
        assert isinstance(_json(default_proc), dict)

    def test_no_unhandled_traceback(self, default_proc: subprocess.CompletedProcess[str]) -> None:
        assert default_proc.returncode == 0

    def test_stable_fields_present(self, default_proc: subprocess.CompletedProcess[str]) -> None:
        result = _json(default_proc)
        for field in (
            "success",
            "query",
            "rewritten_query",
            "filtered_results",
            "summary",
            "citations",
            "agent_unavailable",
            "performance",
        ):
            assert field in result, f"Missing stable field: {field}"

    def test_internal_fields_absent_by_default(
        self, default_proc: subprocess.CompletedProcess[str]
    ) -> None:
        result = _json(default_proc)
        assert "evidence_pack" not in result
        assert "answer" not in result
        assert "agent_decisions" not in result

    def test_agent_decisions_summary_present(
        self, default_proc: subprocess.CompletedProcess[str]
    ) -> None:
        result = _json(default_proc)
        assert "agent_decisions_summary" in result
        assert isinstance(result["agent_decisions_summary"], str)


class TestIncludeEvidenceContract:
    """--include-evidence output contract."""

    def test_success_with_evidence_flag(
        self, evidence_proc: subprocess.CompletedProcess[str]
    ) -> None:
        assert evidence_proc.returncode == 0, f"stderr: {evidence_proc.stderr}"
        assert _json(evidence_proc)["success"] is True

    def test_evidence_build_ms_in_performance(
        self, evidence_proc: subprocess.CompletedProcess[str]
    ) -> None:
        result = _json(evidence_proc)
        assert "performance" in result
        assert "evidence_build_ms" in result["performance"]

    def test_evidence_pack_may_be_absent_in_empty_dir(
        self, evidence_proc: subprocess.CompletedProcess[str]
    ) -> None:
        result = _json(evidence_proc)
        assert result["success"] is True


class TestSynthesizeNoLlmContract:
    """--synthesize --no-llm: no answer, agent_unavailable true."""

    def test_success_without_answer(
        self, synthesize_proc: subprocess.CompletedProcess[str]
    ) -> None:
        assert synthesize_proc.returncode == 0, f"stderr: {synthesize_proc.stderr}"
        result = _json(synthesize_proc)
        assert result["success"] is True
        assert "answer" not in result

    def test_agent_unavailable_true(
        self, synthesize_proc: subprocess.CompletedProcess[str]
    ) -> None:
        assert _json(synthesize_proc)["agent_unavailable"] is True


class TestCombinedEvidenceSynthesizeNoLlmContract:
    """Combined flags do not produce answer; evidence performance stays stable."""

    def test_combined_no_answer(self, combined_proc: subprocess.CompletedProcess[str]) -> None:
        assert combined_proc.returncode == 0, f"stderr: {combined_proc.stderr}"
        result = _json(combined_proc)
        assert result["success"] is True
        assert "answer" not in result

    def test_combined_evidence_build_ms(
        self, combined_proc: subprocess.CompletedProcess[str]
    ) -> None:
        assert "evidence_build_ms" in _json(combined_proc)["performance"]


class TestExplainContract:
    """--explain: agent_decisions present, agent_decisions_summary absent."""

    def test_explain_keeps_agent_decisions(
        self, explain_proc: subprocess.CompletedProcess[str]
    ) -> None:
        assert explain_proc.returncode == 0, f"stderr: {explain_proc.stderr}"
        result = _json(explain_proc)
        assert "agent_decisions" in result
        assert isinstance(result["agent_decisions"], list)

    def test_explain_no_summary(self, explain_proc: subprocess.CompletedProcess[str]) -> None:
        assert "agent_decisions_summary" not in _json(explain_proc)


class TestHelpContract:
    """--help includes key smart-search flags."""

    def test_help_includes_include_evidence(
        self, help_proc: subprocess.CompletedProcess[str]
    ) -> None:
        assert "--include-evidence" in help_proc.stdout

    def test_help_includes_synthesize(self, help_proc: subprocess.CompletedProcess[str]) -> None:
        assert "--synthesize" in help_proc.stdout

    def test_help_includes_explain(self, help_proc: subprocess.CompletedProcess[str]) -> None:
        assert "--explain" in help_proc.stdout
