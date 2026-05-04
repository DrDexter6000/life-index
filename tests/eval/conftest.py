"""Eval test marker: golden-set / eval-gate tests."""

import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "blocker" not in [m.name for m in item.iter_markers()]:
            item.add_marker(pytest.mark.nightly)
