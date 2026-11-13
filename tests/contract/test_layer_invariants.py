"""Contract tests for Foundation Freeze layer invariants.

These tests are intentionally static and dependency-light.  They guard the
project structure that keeps L2 deterministic while allowing explicit L3 /
developer-only LLM entry points. They also pin the shape of the local gate
and the online backstop (docs/CI_HARD_CHECKS.md).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_RUNNER = REPO_ROOT / "scripts" / "gate.py"
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"

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
    REPO_ROOT
    / "tools"
    / "search_journals"
    / "orchestrator.py",
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


def _workflow(path: str) -> dict:
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / path).read_text(encoding="utf-8"))


def _workflow_on(workflow: dict) -> dict:
    # PyYAML follows YAML 1.1 and parses the GitHub Actions "on" key as True.
    return workflow.get("on") or workflow.get(True)


def _gate_markers_for(rel_path: str) -> tuple[str, ...]:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "life_index_tests_conftest", REPO_ROOT / "tests" / "conftest.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.gate_markers_for(rel_path))


@pytest.mark.parametrize("suite", ["unit", "search_journals", "integration", "e2e", "sanity"])
def test_deterministic_suites_gate_pull_requests(suite: str) -> None:
    """A suite that only runs after the merge lets stale tests land."""
    assert _gate_markers_for(f"{suite}/test_anything.py") == ("blocker",)


def test_only_real_data_and_unclassified_tests_are_quarantined() -> None:
    assert _gate_markers_for("dev/test_anything.py") == ("quarantine", "realdata")
    assert _gate_markers_for("a_new_directory/test_anything.py") == ("quarantine",)
    assert _gate_markers_for("test_at_the_top.py") == ("quarantine",)


def test_slow_suites_stay_out_of_the_pull_request_gates() -> None:
    for suite in ("benchmark", "perf", "eval"):
        assert _gate_markers_for(f"{suite}/test_anything.py") == ("nightly",)
    assert _gate_markers_for("unit/test_eval_runner.py") == ("nightly",)


def test_contract_suite_is_split_between_the_contract_and_blocker_gates() -> None:
    assert _gate_markers_for("contract/test_anything.py") == ("contract",)
    assert _gate_markers_for("contract/test_error_contract.py") == ("blocker",)


def test_one_local_gate_runner_owns_the_check_inventory() -> None:
    """scripts/gate.py is the single runner; the old gate scripts are gone."""
    assert GATE_RUNNER.is_file()
    for retired in (
        "scripts/pre-push-gate.sh",
        "scripts/tier1-gate.sh",
        "scripts/run_coverage_gate.sh",
        ".github/workflows/tests.yml",
        ".github/workflows/quality.yml",
        ".github/workflows/nightly.yml",
    ):
        assert not (REPO_ROOT / retired).exists(), f"{retired} was replaced by the gate"
    for kept in ("scripts/run_eval_gate.sh", "scripts/run_eval_advisory.sh"):
        assert (REPO_ROOT / kept).is_file(), f"{kept} is a maintenance tool and stays"


def test_pre_push_gate_is_a_native_hook_installed_by_the_gate() -> None:
    """pre-commit owns commit-time hooks only; the push gate is a native Git
    pre-push hook written by the gate itself (it must see every pushed ref)."""
    config_text = PRE_COMMIT_CONFIG.read_text(encoding="utf-8")
    config = yaml.safe_load(config_text)
    assert "default_install_hook_types" not in config
    local_hooks = [
        hook for repo in config["repos"] if repo["repo"] == "local" for hook in repo["hooks"]
    ]
    assert local_hooks == [], "no pre-commit hook may run the gate"
    assert "pre-push" not in {stage for hook in local_hooks for stage in hook.get("stages", [])}

    runner = GATE_RUNNER.read_text(encoding="utf-8")
    assert "install_hook" in runner and "HOOK_TEMPLATE" in runner
    assert '--from-hook "$@"' in runner  # the native hook forwards Git's stdin records
    assert "check_hook" in runner  # --check-hook verifies the hook by content


def test_backstop_is_one_non_blocking_ubuntu_py311_job() -> None:
    workflow = _workflow("backstop.yml")
    triggers = _workflow_on(workflow)

    assert set(triggers) == {"push", "pull_request", "workflow_dispatch"}
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["pull_request"]["branches"] == ["main"]

    assert list(workflow["jobs"]) == ["backstop"], "one job, no matrix of required checks"
    job = workflow["jobs"]["backstop"]
    assert job["runs-on"] == "ubuntu-latest"

    text = (REPO_ROOT / ".github" / "workflows" / "backstop.yml").read_text(encoding="utf-8")
    assert "draft" not in text, "the backstop has no draft/required-check gating logic"
    assert "continue-on-error" not in text

    steps = job["steps"]
    python_step = next(
        step for step in steps if step.get("uses", "").startswith("actions/setup-python")
    )
    assert python_step["with"]["python-version"] == "3.11"

    env = job["env"]
    assert env["LIFE_INDEX_INDEX_FTS_ONLY"] == "1"
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"

    runs = "\n".join(str(step.get("run", "")) for step in steps)
    # The static inventory is listed in one place: the gate itself runs it.
    assert "scripts/gate.py --fast --base" in runs
    # The sentinel, the full suite and the package smoke run even after an
    # earlier step failed, so a red fast pass cannot hide the rest.
    if_clauses = [str(step.get("if", "")) for step in steps if step.get("if")]
    assert len(if_clauses) >= 4 and all("!cancelled()" in clause for clause in if_clauses)
    assert "pytest tests" in runs and "--timeout=600" in runs
    assert "run_public_core_assertions.py" in runs
    assert "github.event.before" in runs and "github.event.pull_request.base.sha" in runs
    assert "0000000000000000000000000000000000000000" in runs  # zero-SHA handling is explicit
    assert 'rev-parse "${HEAD}^"' in runs  # fallback base is the head's first parent
    assert "life-index bootstrap --json" in runs  # clean-wheel smoke the gate cannot do


def test_benchmark_workflow_is_manual_and_weekly_only() -> None:
    triggers = _workflow_on(_workflow("benchmark.yml"))

    assert set(triggers) == {"workflow_dispatch", "schedule"}
    assert "push" not in triggers


def test_ci_doc_describes_gate_and_backstop_and_keeps_the_ssot_block() -> None:
    doc = (REPO_ROOT / "docs" / "CI_HARD_CHECKS.md").read_text(encoding="utf-8")

    assert "scripts/gate.py" in doc
    assert "backstop.yml" in doc
    assert "--install-hook" in doc  # the native hook's install command is documented
    assert "every outgoing commit" in doc  # the per-commit scan rule is stated
    assert "--no-verify" in doc  # the documented not-covered list names it
    assert "PLATFORM-SSOT:PUBLIC-BLOCKER-EXECUTION:START" in doc
    assert "PLATFORM-SSOT:PUBLIC-BLOCKER-EXECUTION:END" in doc
    assert "| 1 | blocker gate |" not in doc  # the inventory table is gone
    assert "gate --list" in doc or "gate.py --list" in doc
    assert "- v2.1-public" in doc  # version history records the change


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


# --- recall compatibility wrapper invariant tests ---


RECALL_ROOT = REPO_ROOT / "tools" / "recall"


def _recall_files() -> list[Path]:
    """All .py files in the recall module, if it exists."""
    if not RECALL_ROOT.exists():
        return []
    return sorted(RECALL_ROOT.rglob("*.py"))


def test_recall_module_does_not_import_llm_providers() -> None:
    """tools/recall/ must not import anthropic/openai anywhere.

    The recall wrapper is retained only for compatibility and delegates to
    search via subprocess. It must never import LLM providers directly.
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

    The compatibility wrapper invokes search via subprocess (like on_this_day),
    never importing L2 internals.
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
