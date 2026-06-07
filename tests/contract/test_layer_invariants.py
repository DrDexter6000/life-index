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
    "tools.agent_bridge",
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


def _workflow(path: str) -> dict:
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / path).read_text(encoding="utf-8"))


def _workflow_on(workflow: dict) -> dict:
    # PyYAML follows YAML 1.1 and parses the GitHub Actions "on" key as True.
    return workflow.get("on") or workflow.get(True)


def test_pr_test_gates_skip_draft_wip_pushes() -> None:
    workflow = _workflow("tests.yml")
    draft_guard = "github.event.pull_request.draft == false"

    for job_name in ("blocker", "contract", "search-eval-gate"):
        job_if = str(workflow["jobs"][job_name].get("if", ""))
        assert draft_guard in job_if, f"{job_name} must skip draft/WIP PR pushes"


def test_search_eval_gate_remains_tier1_blocking_smoke() -> None:
    workflow = _workflow("tests.yml")
    job = workflow["jobs"]["search-eval-gate"]

    assert job.get("continue-on-error") is not True
    assert "github.event.pull_request.draft == false" in str(job.get("if", ""))


def test_tier2_pr_heavy_jobs_are_post_merge_only() -> None:
    workflow = _workflow("tests.yml")

    for job_name in ("quarantine", "coverage"):
        job_if = str(workflow["jobs"][job_name].get("if", ""))
        assert "github.event_name == 'push'" in job_if
        assert "pull_request" not in job_if


def test_nightly_tier2_runs_on_schedule_manual_and_post_merge() -> None:
    workflow = _workflow("nightly.yml")
    triggers = _workflow_on(workflow)

    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers
    assert triggers["push"]["branches"] == ["main"]
    assert "full-suite" in workflow["jobs"]
    assert "package-onboarding" in workflow["jobs"]


def test_nightly_package_smoke_uses_step_scoped_runner_temp() -> None:
    workflow = _workflow("nightly.yml")
    package_job = workflow["jobs"]["package-onboarding"]

    assert "runner.temp" not in str(package_job.get("env", {}))
    assert "$RUNNER_TEMP" in str(package_job["steps"])


def test_nightly_full_suite_forces_utf8_subprocess_io() -> None:
    workflow = _workflow("nightly.yml")
    env = workflow["jobs"]["full-suite"]["env"]

    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_fast_local_tier1_gate_script_is_documented() -> None:
    script = REPO_ROOT / "scripts" / "tier1-gate.sh"
    source = script.read_text(encoding="utf-8")

    for expected in (
        "Tier 1 fast gate",
        "python -m black --check tools/",
        "python -m flake8 tools/",
        "python -m bandit -r tools/",
        "python -m mypy tools/",
        "python .github/scripts/check_doc_sync.py",
        "python -m pytest -m blocker",
    ):
        assert expected in source


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


# --- Phase A: tools/eval/ablation/ no-default-LLM invariant ---

ABLATION_ROOT = REPO_ROOT / "tools" / "eval" / "ablation"

DISALLOWED_LLM_IMPORTS = {
    "anthropic",
    "openai",
    "llm_client",
}


def _ablation_python_files() -> list[Path]:
    """Collect all .py files under tools/eval/ablation/."""
    if not ABLATION_ROOT.exists():
        return []
    return sorted(ABLATION_ROOT.rglob("*.py"))


def test_ablation_no_default_llm_imports() -> None:
    """Phase A invariant: tools/eval/ablation/ must not import LLM providers.

    The ablation eval surface is a deterministic cross-cutting tool that
    measures search quality across pipeline configurations. It must not
    depend on any LLM provider in its default code path (CHARTER §1.5).
    """
    offenders: list[str] = []
    for path in _ablation_python_files():
        imports = _imported_modules(path)
        found = imports & DISALLOWED_LLM_IMPORTS
        if found:
            rel = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{rel}: {sorted(found)}")

    assert offenders == [], f"tools/eval/ablation/ contains disallowed LLM imports: {offenders}"


# --- Phase D (gbrain #4): maintenance module invariant tests ---


MAINTENANCE_ROOT = REPO_ROOT / "tools" / "maintenance"


def _maintenance_files() -> list[Path]:
    """All .py files in the maintenance module, if it exists."""
    if not MAINTENANCE_ROOT.exists():
        return []
    return sorted(MAINTENANCE_ROOT.rglob("*.py"))


def test_maintenance_no_default_llm_imports() -> None:
    """Phase D invariant: tools/maintenance/ must not import LLM providers.

    The maintenance cycle is a dry-run/report-only command that aggregates
    six health checks via subprocess delegation. It must not depend on any
    LLM provider in its default code path (CHARTER §1.5).
    """
    offenders: list[str] = []
    for path in _maintenance_files():
        imports = _imported_modules(path)
        found = imports & DISALLOWED_LLM_IMPORTS
        if found:
            rel = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{rel}: {sorted(found)}")

    assert offenders == [], f"tools/maintenance/ contains disallowed LLM imports: {offenders}"


def test_maintenance_uses_subprocess_not_direct_import() -> None:
    """Phase D invariant: tools/maintenance/ must not import called module internals.

    The maintenance module delegates to existing CLI commands (index, entity,
    eval/ablation, backup) via subprocess. It must never import their internals
    directly — this preserves the L2/L3 subprocess boundary.
    """
    disallowed_internal_imports = {
        "tools.build_index",
        "tools.entity",
        "tools.eval.ablation",
        "tools.backup",
    }

    offenders: list[str] = []
    for path in _maintenance_files():
        imports = _imported_modules(path)
        for imported in imports:
            if any(
                imported == disallowed or imported.startswith(f"{disallowed}.")
                for disallowed in disallowed_internal_imports
            ):
                rel = path.relative_to(REPO_ROOT).as_posix()
                offenders.append(f"{rel}: {imported}")

    # Allow tools.lib.* (shared utilities) and yaml (for file parsing)
    assert offenders == [], (
        f"maintenance module directly imports called module internals "
        f"(should use subprocess): {offenders}"
    )


# --- B4.2: boost_decay echo-only invariant ---

BOOST_DECAY_FORBIDDEN_FILES = {
    REPO_ROOT / "tools" / "lib" / "search_constants.py",
    REPO_ROOT / "tools" / "search_journals" / "core.py",
    REPO_ROOT / "tools" / "search_journals" / "__main__.py",
    REPO_ROOT / "tools" / "search_journals" / "ranking.py",
    REPO_ROOT / "tools" / "eval" / "calibrate.py",
}


def _search_journals_py_files() -> list[Path]:
    search_dir = REPO_ROOT / "tools" / "search_journals"
    if not search_dir.exists():
        return []
    return sorted(search_dir.rglob("*.py"))


def test_boost_decay_not_imported_by_search_ranking() -> None:
    """B4.2 invariant: boost_decay must not be imported by search ranking/BM25/RRF/calibration.

    boost_decay is a schema placeholder for v1.2.0 Cycle 2 calibration.
    It must not be imported, read, or applied by any search ranking path
    in v1.1.1 (CHARTER + M1 PRD §6.1.2).
    """
    offenders: list[str] = []
    for path in BOOST_DECAY_FORBIDDEN_FILES:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if "boost_decay" in content:
            rel = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{rel}: contains 'boost_decay' reference")

    for path in _search_journals_py_files():
        if path in BOOST_DECAY_FORBIDDEN_FILES:
            continue
        content = path.read_text(encoding="utf-8")
        if "boost_decay" in content:
            rel = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{rel}: contains 'boost_decay' reference")

    assert (
        offenders == []
    ), f"Search ranking/BM25/RRF/calibration files must not reference boost_decay: {offenders}"


# --- RFC-2026-06-03: agent_bridge is L3 (LLM allowed) but must subprocess L2 ---

AGENT_BRIDGE_ROOT = REPO_ROOT / "tools" / "agent_bridge"


def _agent_bridge_files() -> list[Path]:
    if not AGENT_BRIDGE_ROOT.exists():
        return []
    return sorted(AGENT_BRIDGE_ROOT.rglob("*.py"))


def test_agent_bridge_does_not_import_l2_internals() -> None:
    """agent_bridge must reach L2 only via the CLI subprocess, never import L2 internals."""
    disallowed = {
        "tools.search_journals",
        "tools.write_journal",
        "tools.edit_journal",
        "tools.entity",
        "tools.build_index",
    }
    offenders: list[str] = []
    for path in _agent_bridge_files():
        for imported in _imported_modules(path):
            if any(imported == d or imported.startswith(f"{d}.") for d in disallowed):
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {imported}")
    assert offenders == [], f"agent_bridge imports L2 internals (use subprocess): {offenders}"


def test_agent_bridge_does_not_write_user_data() -> None:
    """agent_bridge must never reference the user data dir (proposals go via CLI)."""
    offenders: list[str] = []
    for path in _agent_bridge_files():
        content = path.read_text(encoding="utf-8")
        if "Documents/Life-Index" in content or "USER_DATA_DIR" in content:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == [], f"agent_bridge references user data dir: {offenders}"
