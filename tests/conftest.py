"""Single marker assignment hook for CI Gate segregation.

All marker decisions are based on item.path relative to tests/.
No directory-level conftest.py should add markers to avoid global pollution.
"""

from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent.resolve()

# Contract tests that are deterministic (mock-only, no external deps) -> promoted to blocker
BLOCKER_CONTRACT_FILES = frozenset(
    {
        "contract/test_error_contract.py",
        "contract/test_contract_consistency.py",
        "contract/test_r12_crash_recovery.py",
        "contract/test_r12_index_reliability.py",
        "contract/test_r12_pending_lifecycle.py",
        "contract/test_r12_search_precision.py",
        "contract/test_workflow_signals.py",
    }
)

# Eval tests are slow and non-deterministic (depend on model weights / index state)
NIGHTLY_UNIT_FILES = frozenset(
    {
        "unit/test_eval_advisory.py",
        "unit/test_eval_runner.py",
    }
)


# Suites that are deterministic and need no external dependency or real data:
# they gate every pull request. The integration, end-to-end and sanity suites
# were quarantined while search depended on model weights; it no longer does,
# and a suite that only runs after the merge lets stale tests land.
BLOCKER_DIRS = ("unit/", "search_journals/", "integration/", "e2e/", "sanity/")


def gate_markers_for(rel_path: str) -> tuple[str, ...]:
    """The CI gate markers for a test file, by its path relative to ``tests/``.

    This is the one rule that decides which gate runs a test
    (``docs/CI_HARD_CHECKS.md`` lists the gates).
    """
    # Nightly: benchmark, perf, eval
    if rel_path.startswith(("benchmark/", "perf/", "eval/")) or rel_path in NIGHTLY_UNIT_FILES:
        return ("nightly",)
    # Quarantine: tests that read the developer's real data directory
    if rel_path.startswith("dev/"):
        return ("quarantine", "realdata")
    # Contract: contract tests (except promoted blocker files)
    if rel_path.startswith("contract/"):
        return ("blocker",) if rel_path in BLOCKER_CONTRACT_FILES else ("contract",)
    if rel_path.startswith(BLOCKER_DIRS):
        return ("blocker",)
    # Default: anything else under tests/ gets quarantine to be safe
    return ("quarantine",)


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

        for marker in gate_markers_for(rel_path):
            item.add_marker(getattr(pytest.mark, marker))
