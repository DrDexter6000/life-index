"""Unit test marker: all tests in this directory default to blocker.

Individual tests or files that are known to be non-deterministic
(flaky, env-dependent, slow) should be explicitly marked with
`@pytest.mark.quarantine` or `@pytest.mark.slow`.
"""

import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        # Only add blocker if no other gate marker is already present
        if not any(
            marker.name in ("blocker", "quarantine", "contract", "nightly", "realdata", "semantic")
            for marker in item.iter_markers()
        ):
            item.add_marker(pytest.mark.blocker)
