"""Guard test: perf tests must run real ranking, not stubs.

Round 16 A.2 — if this test fails, someone re-introduced a stub
that masks real ranking behavior in perf tests.
"""

import inspect
from tools.search_journals import ranking


def test_merge_and_rank_is_real_implementation():
    """merge_and_rank_results_hybrid must be the real implementation."""
    src = inspect.getsource(ranking.merge_and_rank_results_hybrid)
    assert (
        "RRF_K" in src or "rrf" in src.lower()
    ), "merge_and_rank_results_hybrid appears stubbed — see Round 16 A.2"
    assert (
        src.count("\n") > 30
    ), "merge_and_rank_results_hybrid is suspiciously short — may be a stub"
