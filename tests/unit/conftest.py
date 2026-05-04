"""Unit test marker: all tests in this directory default to blocker.

Individual tests or files that are known to be non-deterministic
(flaky, env-dependent, slow) should be explicitly marked with
`@pytest.mark.quarantine` or `@pytest.mark.slow`.
"""

import pytest

# Eval tests are slow and non-deterministic (depend on model weights / index state)
NIGHTLY_UNIT_FILES = frozenset({
    "test_eval_gate.py",
    "test_eval_runner.py",
    "test_eval_llm.py",
})


def pytest_collection_modifyitems(config, items):
    for item in items:
        fname = item.path.name
        # Respect explicit markers from source code
        existing = {m.name for m in item.iter_markers()}
        if existing & {"blocker", "quarantine", "contract", "nightly", "realdata", "semantic"}:
            continue
        if fname in NIGHTLY_UNIT_FILES:
            item.add_marker(pytest.mark.nightly)
        else:
            item.add_marker(pytest.mark.blocker)
