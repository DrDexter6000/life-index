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
    REPO_ROOT / "tools" / "backup",
    REPO_ROOT / "tools" / "build_index",
    REPO_ROOT / "tools" / "edit_journal",
    REPO_ROOT / "tools" / "entity",
    REPO_ROOT / "tools" / "evidence",
    REPO_ROOT / "tools" / "generate_index",
    REPO_ROOT / "tools" / "lib",
    REPO_ROOT / "tools" / "migrate",
    REPO_ROOT / "tools" / "query_weather",
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

# Deterministic L2 module roots that MUST be covered by layer-invariant tests.
# Every tool module that is purely deterministic (no LLM calls, no L3 orchestration)
# must appear here so that the invariant scan covers it.
REQUIRED_L2_ROOTS = {
    "aggregate",
    "backup",
    "build_index",
    "edit_journal",
    "entity",
    "evidence",
    "generate_index",
    "lib",
    "migrate",
    "query_weather",
    "search_journals",
    "timeline",
    "verify",
    "write_journal",
}

DISALLOWED_PROVIDER_IMPORTS = {
    "anthropic",
    "openai",
}

DISALLOWED_L3_IMPORTS = {
    "tools.smart_search",
    "tools.search_journals.orchestrator",
}

# L2 modules that must not import from L3 packages even if they are in
# L2_ALLOWED_FILES (whitelisted for other reasons).  This catches upward
# dependencies that the generic _production_l2_files scan skips.
L2_STRICT_L3_FREE_FILES = {
    REPO_ROOT / "tools" / "search_journals" / "orchestrator.py",
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


def test_l2_production_roots_cover_all_deterministic_modules() -> None:
    """L2_PRODUCTION_ROOTS must include every deterministic L2 tool module.

    Missing roots mean new deterministic code can ship without layer-invariant
    coverage — a coverage gap that the architecture audit flagged as HIGH.
    """
    actual_names = {p.name for p in L2_PRODUCTION_ROOTS}
    missing = sorted(REQUIRED_L2_ROOTS - actual_names)
    assert missing == [], f"L2_PRODUCTION_ROOTS is missing deterministic modules: {missing}"


def test_l2_whitelisted_files_do_not_import_l3() -> None:
    """Even whitelisted L2 files must not import from L3 packages.

    This catches the specific orchestrator.py -> tools.smart_search.planner
    upward dependency that was flagged in the cross-agent architecture audit.
    """
    offenders: list[str] = []
    for path in L2_STRICT_L3_FREE_FILES:
        if not path.exists():
            continue
        imports = _imported_modules(path)
        for imported in imports:
            if any(
                imported == disallowed or imported.startswith(f"{disallowed}.")
                for disallowed in DISALLOWED_L3_IMPORTS
            ):
                rel = path.relative_to(REPO_ROOT).as_posix()
                offenders.append(f"{rel}: {imported}")

    assert offenders == [], f"Whitelisted L2 files import from L3 packages: {offenders}"


# --- Phase E (gbrain #5): recall module L3 invariant tests ---


L3_RECALL_ROOT = REPO_ROOT / "tools" / "recall"


def _recall_files() -> list[Path]:
    """All .py files in the recall module, if it exists."""
    if not L3_RECALL_ROOT.exists():
        return []
    return sorted(L3_RECALL_ROOT.rglob("*.py"))


def test_recall_module_does_not_import_llm_providers() -> None:
    """tools/recall/ must not import anthropic/openai anywhere.

    The recall module delegates LLM work to smart-search via subprocess.
    It must never import LLM providers directly — that would violate
    the CHARTER §1.5 L2-no-LLM invariant and the L3 subprocess boundary.
    """
    offenders: list[str] = []
    for path in _recall_files():
        imports = _imported_modules(path)
        if imports & DISALLOWED_PROVIDER_IMPORTS:
            rel = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{rel}: {sorted(imports & DISALLOWED_PROVIDER_IMPORTS)}")

    assert offenders == [], f"recall module imports LLM providers: {offenders}"


def test_recall_module_uses_subprocess_not_direct_import() -> None:
    """tools/recall/ must use subprocess to call L2, not direct imports.

    The L3 subprocess boundary requires recall to invoke search/smart-search
    via subprocess (like on_this_day), never importing L2 internals.
    """
    disallowed_l2_imports = {
        "tools.search_journals",
        "tools.smart_search",
    }

    offenders: list[str] = []
    for path in _recall_files():
        imports = _imported_modules(path)
        for imported in imports:
            if any(
                imported == disallowed or imported.startswith(f"{disallowed}.")
                for disallowed in disallowed_l2_imports
            ):
                rel = path.relative_to(REPO_ROOT).as_posix()
                offenders.append(f"{rel}: {imported}")

    assert (
        offenders == []
    ), f"recall module directly imports L2 internals (should use subprocess): {offenders}"
