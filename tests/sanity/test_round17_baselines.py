"""Round 17 Phase 0 baseline verification.

These tests verify the CURRENT state of the codebase before Round 17 execution.
All tests should PASS — we are confirming baselines, not asserting changes.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_charter_exists_and_signed():
    charter = REPO_ROOT / "CHARTER.md"
    assert charter.exists(), "CHARTER.md must exist"
    text = charter.read_text(encoding="utf-8")
    assert "v1.1.0" in text, "CHARTER must be v1.1.0+ (updated Phase 6-B)"
    assert "2026-04-23" in text, "CHARTER must be signed (批准日期)"


def test_search_constants_exports():
    """Verify search_constants.py has exports."""
    const = REPO_ROOT / "tools" / "lib" / "search_constants.py"
    assert const.exists()
    text = const.read_text(encoding="utf-8")
    assert "__all__" in text


def test_golden_queries_count():
    """Verify golden queries file exists and has entries."""
    gq = REPO_ROOT / "tools" / "eval" / "golden_queries.yaml"
    assert gq.exists(), "golden_queries.yaml must exist"
    text = gq.read_text(encoding="utf-8")
    # Count entries by id pattern
    ids = re.findall(r'- id: "GQ\d+"', text)
    assert len(ids) >= 20, f"Expected >=20 golden queries, got {len(ids)}"


def test_scattered_constants_eliminated():
    """Verify scattered constants have been eliminated per CHARTER §4.3.

    After Phase 1-A migration, confidence.py should use named constants
    imported from search_constants, not bare numeric literals.
    """
    conf = REPO_ROOT / "tools" / "search_journals" / "confidence.py"
    text = conf.read_text(encoding="utf-8")
    # These bare literals should NO LONGER exist after migration
    for bare_val in [">= 70", ">= 55", ">= 0.018", ">= 50", ">= 45", ">= 0.010"]:
        assert (
            bare_val not in text
        ), f"Bare threshold '{bare_val}' still in confidence.py after Phase 1-A migration"
    # Named constants should be imported instead
    assert "CONFIDENCE_HIGH_FTS" in text, "confidence.py must import CONFIDENCE_HIGH_FTS"
