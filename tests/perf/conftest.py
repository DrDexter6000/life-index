"""Performance test marker: performance regression tests."""

import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.nightly)
