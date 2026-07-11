from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

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
