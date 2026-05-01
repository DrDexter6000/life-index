"""Verify ranking layer returns full results, truncation only in presentation layer.

Phase 2 (Task 3): Separation of ranking and presentation concerns.
- ranking.py must return ALL results (no internal truncation)
- core.py must truncate to MAX_RESULTS_DEFAULT for backward compat
- CLI must support --offset + has_more + total_available
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


def test_hybrid_ranking_returns_full_set():
    """merge_and_rank_results_hybrid should return ALL results, not truncated."""
    from tools.search_journals.ranking import merge_and_rank_results_hybrid

    # Create 30 L3 results and 30 semantic results
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
    semantic = [
        {
            "path": f"journal_{i:03d}.md",
            "similarity": 0.9 - i * 0.01,
            "source": "semantic_search",
            "title": f"Test {i}",
            "date": "2026-01-01",
        }
        for i in range(30)
    ]
    result = merge_and_rank_results_hybrid(
        l1_results=[],
        l2_results=[],
        l3_results=l3,
        semantic_results=semantic,
        query="test",
        max_results=20,
    )
    # After refactor: should return all results (no internal truncation)
    assert len(result) > 20, (
        f"hybrid ranking should return >20 results, got {len(result)}. "
        "Internal truncation violates R/P separation."
    )


def test_no_truncation_in_ranking():
    """grep check: ranking.py must not contain [:max_results] truncation."""
    ranking_file = REPO_ROOT / "tools" / "search_journals" / "ranking.py"
    text = ranking_file.read_text(encoding="utf-8")
    assert (
        "[:max_results]" not in text
    ), "ranking.py still contains [:max_results] internal truncation"


def test_core_truncates_to_default():
    """core.py must truncate results to MAX_RESULTS_DEFAULT for backward compat."""
    core_file = REPO_ROOT / "tools" / "search_journals" / "core.py"
    text = core_file.read_text(encoding="utf-8")
    # After refactor, core.py should have a truncation line
    assert (
        "MAX_RESULTS_DEFAULT" in text
    ), "core.py must reference MAX_RESULTS_DEFAULT for backward-compat truncation"


def test_cli_has_offset_param():
    """CLI must support --offset parameter."""
    main_file = REPO_ROOT / "tools" / "search_journals" / "__main__.py"
    text = main_file.read_text(encoding="utf-8")
    assert "--offset" in text, "CLI must have --offset parameter"
