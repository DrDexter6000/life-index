"""Contract test marker.

Most contract tests run under the Contract gate (TEMPORARY continue-on-error).
A few contract tests that are deterministic and mock-only are promoted to blocker.
"""

import pytest

# Contract tests that are deterministic (mock-only, no external deps)
BLOCKER_CONTRACT_FILES = frozenset(
    {
        "test_error_contract.py",
        "test_contract_consistency.py",
        "test_r12_crash_recovery.py",
        "test_r12_index_reliability.py",
        "test_r12_pending_lifecycle.py",
        "test_r12_search_precision.py",
        "test_workflow_signals.py",
    }
)


def pytest_collection_modifyitems(config, items):
    for item in items:
        fname = item.path.name
        # Respect explicit markers from source code
        existing = {m.name for m in item.iter_markers()}
        if existing & {"blocker", "quarantine", "contract", "nightly"}:
            continue
        if fname in BLOCKER_CONTRACT_FILES:
            item.add_marker(pytest.mark.blocker)
        else:
            item.add_marker(pytest.mark.contract)
