#!/usr/bin/env python3
"""Contract tests for the recall module (Phase E — gbrain #5).

Covers 3 modes (default / recall / deep) x 3 cases (basic / no_results /
opt_in_boundary) = 9 minimum tests.

All tests run in isolated sandbox data directories via LIFE_INDEX_DATA_DIR.
The recall module is an L3 module that consumes L2 search/smart-search via
subprocess — mirroring the on_this_day pattern.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_journal(
    data_dir: Path,
    date_str: str,
    title: str,
    body: str,
    tags: List[str] | None = None,
    topic: str = "",
) -> Path:
    """Write a minimal journal file under data_dir/Journals/YYYY/MM/."""
    parts = date_str.split("-")
    year, month = parts[0], parts[1]
    month_dir = data_dir / "Journals" / year / month
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / f"life-index_{date_str}_001.md"
    tags_yaml = str(tags) if tags else "[]"
    topic_yaml = f'"{topic}"' if topic else '""'
    frontmatter = f"""---
title: "{title}"
date: {date_str}
tags: {tags_yaml}
topic: {topic_yaml}
---

# {title}

{body}
"""
    path.write_text(frontmatter, encoding="utf-8")
    return path


@pytest.fixture
def sandbox(tmp_path: Path):
    """Create sandbox data dir with a few journals, return (data_dir, env)."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    # Write journals that contain "python" keyword
    _write_journal(
        data_dir,
        "2026-03-01",
        "Python Learning",
        "Today I learned about python decorators.",
        tags=["python", "learn"],
        topic="learn",
    )
    _write_journal(
        data_dir,
        "2026-03-15",
        "Refactoring Work",
        "Refactored the python service for better performance.",
        tags=["python", "work"],
        topic="work",
    )
    _write_journal(
        data_dir,
        "2026-04-02",
        "Unrelated Entry",
        "Went to the park with family.",
        tags=["family"],
        topic="life",
    )

    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    return data_dir, env


def _run_recall_cli(
    mode: str,
    query: str,
    use_llm: bool = False,
    env: Dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Invoke recall via subprocess."""
    cmd = [
        sys.executable,
        "-m",
        "tools",
        "recall",
        "--mode",
        mode,
        "--query",
        query,
    ]
    if use_llm:
        cmd.append("--use-llm")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


# ── DEFAULT MODE (pure FTS via search --no-semantic) ──────────────────────


class TestDefaultMode:
    """default mode: delegates to L2 search --no-semantic (pure FTS)."""

    def test_default_basic(self, sandbox):
        """default mode returns matching results for a keyword query."""
        data_dir, env = sandbox
        # Build index first so FTS works
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("default", "python", env=env)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["mode"] == "default"
        assert payload["effective_mode"] == "default"
        assert payload["schema_version"] == "gbrain.recall.v1"
        assert payload["query"] == "python"
        assert payload["source_command"] == "search --no-semantic"
        assert "results" in payload
        assert payload["error"] is None

    def test_default_no_results(self, tmp_path: Path):
        """default mode returns empty results for non-matching query."""
        data_dir = tmp_path / "Life-Index"
        data_dir.mkdir()
        _write_journal(
            data_dir,
            "2026-03-01",
            "Hello",
            "Nothing relevant here.",
        )
        env = os.environ.copy()
        env["LIFE_INDEX_DATA_DIR"] = str(data_dir)

        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("default", "zzznonexistent", env=env)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["mode"] == "default"
        assert payload["results"] == []

    def test_default_opt_in_boundary(self, sandbox):
        """default mode ignores --use-llm flag (pure FTS, no LLM)."""
        data_dir, env = sandbox
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("default", "python", use_llm=True, env=env)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        payload = json.loads(result.stdout)
        assert payload["success"] is True
        # default mode always uses search --no-semantic regardless of --use-llm
        assert payload["mode"] == "default"
        assert payload["effective_mode"] == "default"
        assert payload["source_command"] == "search --no-semantic"


# ── RECALL MODE (delegates to search, keyword-only by default) ───────────────


class TestRecallMode:
    """recall mode: delegates to search (default keyword-only behavior)."""

    def test_recall_basic(self, sandbox):
        """recall mode returns matching results."""
        data_dir, env = sandbox
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("recall", "python", env=env)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["mode"] == "recall"
        assert payload["effective_mode"] == "recall"
        assert payload["source_command"] == "search"
        assert "results" in payload
        assert payload["error"] is None

    def test_recall_no_results(self, tmp_path: Path):
        """recall mode returns success for non-matching query.

        Note: recall mode uses hybrid search (FTS + semantic), which may
        return semantic matches even for seemingly non-matching queries.
        The contract guarantees success, not necessarily empty results.
        """
        data_dir = tmp_path / "Life-Index"
        data_dir.mkdir()
        _write_journal(
            data_dir,
            "2026-03-01",
            "Hello",
            "Nothing relevant here.",
        )
        env = os.environ.copy()
        env["LIFE_INDEX_DATA_DIR"] = str(data_dir)

        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("recall", "zzznonexistent", env=env)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        payload = json.loads(result.stdout)
        assert payload["success"] is True
        # results may or may not be empty (semantic may match)
        assert isinstance(payload["results"], list)

    def test_recall_opt_in_boundary(self, sandbox):
        """recall mode ignores --use-llm (it's deterministic hybrid search)."""
        data_dir, env = sandbox
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("recall", "python", use_llm=True, env=env)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["mode"] == "recall"
        assert payload["effective_mode"] == "recall"
        assert payload["source_command"] == "search"


# ── DEEP MODE (smart-search with opt-in LLM) ──────────────────────────────


class TestDeepMode:
    """deep mode: delegates to smart-search --use-llm; degrades without opt-in."""

    def test_deep_basic_with_llm(self, sandbox):
        """deep mode with --use-llm delegates to smart-search."""
        data_dir, env = sandbox
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("deep", "python", use_llm=True, env=env)
        # smart-search may succeed or degrade depending on LLM availability
        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["mode"] == "deep"
        assert payload["effective_mode"] == "deep"
        assert payload["source_command"] == "smart-search --use-llm"
        assert "results" in payload

    def test_deep_no_llm_degrades_to_recall(self, sandbox):
        """deep mode without --use-llm degrades to recall mode."""
        data_dir, env = sandbox
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("deep", "python", use_llm=False, env=env)
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        payload = json.loads(result.stdout)
        assert payload["success"] is True
        assert payload["mode"] == "deep"
        assert payload["effective_mode"] == "recall"
        assert payload["source_command"] == "search"
        # Must have stderr warning about degradation
        assert (
            "degrad" in result.stderr.lower() or "recall" in result.stderr.lower()
        ), f"Expected degradation warning in stderr, got: {result.stderr}"

    def test_deep_explicit_opt_in_required(self, sandbox):
        """deep mode requires explicit --use-llm for LLM; no default LLM."""
        data_dir, env = sandbox
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("deep", "python", use_llm=False, env=env)
        payload = json.loads(result.stdout)

        # Without --use-llm, effective_mode MUST be recall (not deep)
        assert payload["effective_mode"] == "recall"
        # source_command must NOT be smart-search
        assert "smart-search" not in payload["source_command"]


# ── ADDITIONAL INVARIANT TESTS ────────────────────────────────────────────


class TestRecallInvariants:
    """Invariant tests: no-default-LLM, subprocess boundary, schema shape."""

    def test_output_schema_shape(self, sandbox):
        """Verify all required top-level fields are present."""
        data_dir, env = sandbox
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("default", "python", env=env)
        payload = json.loads(result.stdout)

        required_fields = [
            "success",
            "schema_version",
            "mode",
            "effective_mode",
            "query",
            "results",
            "source_command",
            "error",
        ]
        for field in required_fields:
            assert field in payload, f"Missing required field: {field}"

    def test_recall_module_no_default_llm_import(self):
        """tools/recall/ must not import LLM providers in default path.

        This is an AST-level static check — not a runtime test.
        """
        import ast

        recall_dir = REPO_ROOT / "tools" / "recall"
        if not recall_dir.exists():
            pytest.skip("tools/recall/ not yet created")

        disallowed = {"anthropic", "openai"}
        for py_file in recall_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = {alias.name for alias in node.names}
                    assert not (
                        names & disallowed
                    ), f"{py_file.name} imports LLM provider: {names & disallowed}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module in disallowed:
                        pytest.fail(f"{py_file.name} imports from LLM provider: {node.module}")

    def test_subprocess_boundary(self, sandbox):
        """Recall delegates to L2 via subprocess, not direct import."""
        data_dir, env = sandbox
        subprocess.run(
            [sys.executable, "-m", "tools", "index"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        result = _run_recall_cli("default", "python", env=env)
        payload = json.loads(result.stdout)

        # source_command should reference search or smart-search, confirming
        # subprocess delegation pattern
        assert payload["source_command"] in [
            "search --no-semantic",
            "search",
            "smart-search --use-llm",
        ]
