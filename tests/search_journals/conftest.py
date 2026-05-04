"""Search-journals test marker: deterministic unit-level tests."""

import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        if not any(
            marker.name in ("blocker", "quarantine", "contract", "nightly", "realdata", "semantic")
            for marker in item.iter_markers()
        ):
            item.add_marker(pytest.mark.blocker)
