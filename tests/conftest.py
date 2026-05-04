"""Single marker assignment hook for CI Gate segregation.

All marker decisions are based on item.path relative to tests/.
No directory-level conftest.py should add markers to avoid global pollution.
"""

from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent.resolve()

# Contract tests that are deterministic (mock-only, no external deps) -> promoted to blocker
BLOCKER_CONTRACT_FILES = frozenset({
    "contract/test_error_contract.py",
    "contract/test_contract_consistency.py",
    "contract/test_r12_crash_recovery.py",
    "contract/test_r12_index_reliability.py",
    "contract/test_r12_pending_lifecycle.py",
    "contract/test_r12_search_precision.py",
    "contract/test_workflow_signals.py",
})

# Eval tests are slow and non-deterministic (depend on model weights / index state)
NIGHTLY_UNIT_FILES = frozenset({
    "unit/test_eval_gate.py",
    "unit/test_eval_runner.py",
    "unit/test_eval_llm.py",
})


def pytest_collection_modifyitems(config, items):
    for item in items:
        # Skip if already explicitly marked in source code
        existing = {m.name for m in item.iter_markers()}
        if existing & {"blocker", "quarantine", "contract", "nightly", "realdata", "semantic"}:
            continue

        # Get path relative to tests/ directory
        try:
            rel_path = item.path.relative_to(TESTS_DIR).as_posix()
        except ValueError:
            # item not under tests/ (e.g. from external plugins)
            continue

        # Nightly: benchmark, perf, eval
        if rel_path.startswith(("benchmark/", "perf/", "eval/")):
            item.add_marker(pytest.mark.nightly)
            continue
        if rel_path in NIGHTLY_UNIT_FILES:
            item.add_marker(pytest.mark.nightly)
            continue

        # Quarantine: dev, e2e, integration, sanity
        if rel_path.startswith(("dev/", "e2e/", "integration/", "sanity/")):
            item.add_marker(pytest.mark.quarantine)
            if rel_path.startswith("dev/"):
                item.add_marker(pytest.mark.realdata)
            if rel_path.startswith(("e2e/", "integration/")):
                item.add_marker(pytest.mark.semantic)
            continue

        # Contract: contract tests (except promoted blocker files)
        if rel_path.startswith("contract/"):
            if rel_path in BLOCKER_CONTRACT_FILES:
                item.add_marker(pytest.mark.blocker)
            else:
                item.add_marker(pytest.mark.contract)
            continue

        # Blocker: unit tests (except nightly eval files) + search_journals
        if rel_path.startswith(("unit/", "search_journals/")):
            item.add_marker(pytest.mark.blocker)
            continue

        # Default: anything else under tests/ gets quarantine to be safe
        item.add_marker(pytest.mark.quarantine)
