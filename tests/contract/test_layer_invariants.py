"""Contract tests for Foundation Freeze layer invariants.

These tests are intentionally static and dependency-light.  They guard the
project structure that keeps L2 deterministic while allowing explicit L3 /
developer-only LLM entry points.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

L2_PRODUCTION_ROOTS = (
    REPO_ROOT / "tools" / "aggregate",
    REPO_ROOT / "tools" / "build_index",
    REPO_ROOT / "tools" / "entity",
    REPO_ROOT / "tools" / "generate_index",
    REPO_ROOT / "tools" / "lib",
    REPO_ROOT / "tools" / "search_journals",
    REPO_ROOT / "tools" / "timeline",
    REPO_ROOT / "tools" / "verify",
    REPO_ROOT / "tools" / "write_journal",
)

L2_ALLOWED_FILES = {
    # L3 orchestrator lives beside search primitives for historical import
    # compatibility, but it is the explicit intelligence-layer boundary.
    REPO_ROOT / "tools" / "search_journals" / "orchestrator.py",
    # Backward-compatible lazy shim; direct provider code remains in tools/_optional.
    REPO_ROOT / "tools" / "lib" / "llm_extract.py",
}

DISALLOWED_PROVIDER_IMPORTS = {
    "anthropic",
    "openai",
}

DISALLOWED_L3_IMPORTS = {
    "tools.smart_search",
    "tools.search_journals.orchestrator",
}


def _production_l2_files() -> list[Path]:
    files: list[Path] = []
    for root in L2_PRODUCTION_ROOTS:
        files.extend(path for path in root.rglob("*.py") if path not in L2_ALLOWED_FILES)
    return sorted(files)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def test_contract_gate_is_hard_required_check() -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    )
    contract_job = workflow["jobs"]["contract"]

    assert contract_job.get("continue-on-error") is not True


def test_l2_production_modules_do_not_import_llm_providers() -> None:
    offenders: list[str] = []
    for path in _production_l2_files():
        imports = _imported_modules(path)
        if imports & DISALLOWED_PROVIDER_IMPORTS:
            rel = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{rel}: {sorted(imports & DISALLOWED_PROVIDER_IMPORTS)}")

    assert offenders == []


def test_l2_production_modules_do_not_import_l3_orchestrators() -> None:
    offenders: list[str] = []
    for path in _production_l2_files():
        imports = _imported_modules(path)
        for imported in imports:
            if any(
                imported == disallowed or imported.startswith(f"{disallowed}.")
                for disallowed in DISALLOWED_L3_IMPORTS
            ):
                rel = path.relative_to(REPO_ROOT).as_posix()
                offenders.append(f"{rel}: {imported}")

    assert offenders == []
