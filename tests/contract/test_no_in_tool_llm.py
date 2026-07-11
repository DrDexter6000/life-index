from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = REPO_ROOT / ".github" / "scripts" / "check_l2_no_llm.py"
SEARCH_PRODUCTION_ROOTS = (
    REPO_ROOT / "tools" / "search_journals",
    REPO_ROOT / "tools" / "smart_search",
)
FORBIDDEN_SEARCH_OWNERSHIP_SYMBOLS = {
    "LLMClient",
    "llm_client",
    "_llm",
    "_call_llm",
    "post_filter_and_summarize",
    "synthesize_answer",
    "_build_synthesis_prompt",
    "_evidence_to_synthesis_context",
    "_parse_synthesis_response",
    "_apply_trust_gate",
    "_compute_transparency",
    "_build_rewrite_prompt",
    "_parse_rewrite_response",
    "_build_filter_prompt",
    "_parse_filter_response",
    "_citation_matches_query",
    "_normalized_tokens",
}


def _owned_forbidden_symbols(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in FORBIDDEN_SEARCH_OWNERSHIP_SYMBOLS:
                found.add(node.name)
        elif isinstance(node, ast.arg):
            if node.arg in FORBIDDEN_SEARCH_OWNERSHIP_SYMBOLS:
                found.add(node.arg)
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_SEARCH_OWNERSHIP_SYMBOLS:
                found.add(node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_SEARCH_OWNERSHIP_SYMBOLS:
                found.add(node.attr)
    return sorted(found)


def test_search_production_tree_contains_no_dormant_or_injectable_llm_implementation() -> None:
    violations: list[str] = []
    for root in SEARCH_PRODUCTION_ROOTS:
        for path in sorted(root.rglob("*.py")):
            for symbol in _owned_forbidden_symbols(path):
                violations.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{symbol}")

    assert violations == [], "forbidden in-tool LLM ownership remains:\n" + "\n".join(violations)


def test_public_no_llm_hard_check_executes_full_search_ownership_scan(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    orchestrator = root / "tools" / "search_journals" / "orchestrator.py"
    orchestrator.parent.mkdir(parents=True)
    orchestrator.write_text(
        "class SmartSearchOrchestrator:\n"
        "    def __init__(self, llm_client=None):\n"
        "        self.client = llm_client\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "tools/search_journals/orchestrator.py" in proc.stdout
    assert "llm_client" in proc.stdout


@pytest.mark.parametrize(
    ("source", "expected_marker"),
    [
        (
            "class Search:\n"
            "    def __init__(self, backend):\n"
            "        self.provider = backend\n",
            "provider",
        ),
        ("model_client = object()\n", "model_client"),
        ("llmClient = object()\n", "llmClient"),
        (
            "from tools.eval.llm_client import LLMClient as JudgeClient\n",
            "tools.eval.llm_client",
        ),
        ("import litellm\n", "litellm"),
        ("provider.chat([{'role': 'user', 'content': 'x'}])\n", "provider.chat"),
        ("provider.complete('x')\nprovider.generate('x')\n", "provider.complete"),
        (
            "import importlib as loader\n" "provider_module = loader.import_module('openai')\n",
            "dynamic import openai",
        ),
        (
            "from openai import OpenAI as SearchBackend\n" "backend = SearchBackend()\n",
            "openai",
        ),
    ],
)
def test_public_no_llm_hard_check_rejects_structural_search_ownership_bypasses(
    tmp_path: Path,
    source: str,
    expected_marker: str,
) -> None:
    root = tmp_path / "repo"
    search_file = root / "tools" / "search_journals" / "structural_bypass.py"
    search_file.parent.mkdir(parents=True)
    search_file.write_text(source, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "tools/search_journals/structural_bypass.py" in proc.stdout
    assert expected_marker in proc.stdout


def test_public_no_llm_hard_check_allows_deterministic_query_planning_terms(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    search_file = root / "tools" / "smart_search" / "planner.py"
    search_file.parent.mkdir(parents=True)
    search_file.write_text(
        "def rewrite_query(query):\n"
        "    model = {'strategy': 'keyword_only', 'query': query}\n"
        "    query_plan = {'rewritten_query': query, 'model': model}\n"
        "    return query_plan\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stdout


def test_public_no_llm_hard_check_treats_search_ast_parse_failure_as_non_green(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    search_file = root / "tools" / "search_journals" / "broken.py"
    search_file.parent.mkdir(parents=True)
    search_file.write_text("def broken(:\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), "--root", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "SyntaxError" in proc.stderr
