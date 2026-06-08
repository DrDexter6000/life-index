"""Contract: semantic search degrades gracefully without sentence-transformers.

When sentence-transformers is not installed, `_check_sentence_transformers`
must return a warning status (not crash) and the issue string must contain
the `[semantic]` extra install hint so users know how to opt in.
"""

import sys

import pytest


@pytest.mark.blocker
def test_health_degrades_gracefully_without_sentence_transformers(monkeypatch):
    """_check_sentence_transformers returns warning + life-index[semantic] hint."""
    from tools.__main__ import _check_sentence_transformers

    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    check, issue = _check_sentence_transformers()

    assert check["status"] == "warning"
    assert check["version"] is None
    assert "life-index[semantic]" in issue
