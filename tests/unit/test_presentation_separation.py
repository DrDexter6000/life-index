"""Verify ranking layer returns full results, truncation only in presentation layer.

Per CHARTER §1.11: retrieval/ranking layer returns complete candidate set.
Truncation lives only in the presentation layer (tools/search_journals/__main__.py).
- ranking.py must return ALL results (no internal truncation)
- core.py must NOT truncate — no MAX_RESULTS_DEFAULT in retrieval path
- CLI presentation layer must support --offset + has_more + total_matches
"""

from pathlib import Path
import sys

# Ensure tools is importable
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def test_non_hybrid_ranking_returns_full_set():
    """merge_and_rank_results should return ALL results, not truncated."""
    from tools.search_journals.ranking import merge_and_rank_results

    # Create 30 L3 results — more than MAX_RESULTS_DEFAULT (20)
    l3 = [
        {
            "path": f"journal_{i:03d}.md",
            "relevance": 100 - i,
            "title_match": False,
            "source": "content_search",
            "title": f"Test {i}",
            "date": "2026-01-01",
        }
        for i in range(30)
    ]
    result = merge_and_rank_results(
        l1_results=[],
        l2_results=[],
        l3_results=l3,
        query="test",
        max_results=20,
    )
    # After refactor: should return 30 (no internal truncation)
    # Before refactor: returns 20 (truncated internally)
    assert len(result) == 30, (
        f"ranking should return all 30 results, got {len(result)}. "
        "Internal truncation violates R/P separation."
    )


def test_no_truncation_in_ranking():
    """grep check: ranking.py must not contain [:max_results] truncation."""
    ranking_file = REPO_ROOT / "tools" / "search_journals" / "ranking.py"
    text = ranking_file.read_text(encoding="utf-8")
    assert (
        "[:max_results]" not in text
    ), "ranking.py still contains [:max_results] internal truncation"


def test_core_no_truncation_to_default():
    """core.py must NOT use MAX_RESULTS_DEFAULT for retrieval truncation.

    Per CHARTER §1.11 rule #2: retrieval/ranking layer returns complete
    ranked candidate set; truncation lives only in the presentation layer
    (tools/search_journals/__main__.py). The old model had core.py
    hard-truncate to MAX_RESULTS_DEFAULT — that is now a violation.
    """
    core_file = REPO_ROOT / "tools" / "search_journals" / "core.py"
    text = core_file.read_text(encoding="utf-8")
    assert "MAX_RESULTS_DEFAULT" not in text, (
        "core.py must not reference MAX_RESULTS_DEFAULT — "
        "truncation lives in presentation layer only"
    )


def test_cli_has_offset_param():
    """CLI must support --offset parameter."""
    main_file = REPO_ROOT / "tools" / "search_journals" / "__main__.py"
    text = main_file.read_text(encoding="utf-8")
    assert "--offset" in text, "CLI must have --offset parameter"
