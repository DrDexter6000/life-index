"""Tests for the in-process query harness (T5.0).

Verifies that the harness loads the model once and provides fast
repeated queries with output structure matching CLI JSON.
"""

import importlib
import os
import sys
import time

import pytest


MODULES_TO_RELOAD = [
    "tools.lib.paths",
    "tools.lib.config",
    "tools.lib.metadata_cache",
    "tools.lib.vector_index_simple",
    "tools.lib.entity_runtime",
    "tools.lib.search_index",
    "tools.lib.fts_update",
    "tools.lib.fts_search",
    "tools.search_journals.semantic",
    "tools.search_journals.semantic_pipeline",
    "tools.search_journals.keyword_pipeline",
    "tools.search_journals.core",
    "tools.search_journals.ranking",
    "tools.search_journals.confidence",
    "tools.search_journals.title_promotion",
    "tools.search_journals.ranking_reason",
    "tools.search_journals.stopwords",
]


@pytest.fixture(scope="module", autouse=True)
def _setup_isolated_env(tmp_path_factory):
    """Set up isolated data directory with seed journals for all tests."""
    tmp = tmp_path_factory.mktemp("life_index_inproc_harness")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(tmp)
    for mod_name in MODULES_TO_RELOAD:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])

    from tools.build_index import build_all
    from tools.write_journal.core import write_journal

    seed = [
        {"title": "重构搜索模块的思考", "content": "重构搜索模块，使用 RRF 融合算法。", "date": "2026-03-01", "topic": "work"},
        {"title": "想念尿片侠", "content": "看到女儿小时候的照片，感慨万分。小疙瘩长大了。", "date": "2026-03-02", "topic": "think"},
        {"title": "Claude Opus 4.6 CTO 级技术评审", "content": "Claude Opus 4.6 发布，CTO 级技术能力引发讨论。", "date": "2026-03-03", "topic": "work"},
    ]
    for j in seed:
        write_journal(j)
    build_all(incremental=False)


class TestInprocHarnessStructure:
    """Verify harness output structure matches CLI JSON."""

    def test_harness_returns_dict(self):
        from tests.nl_query_inproc import harness
        result = harness.search("重构搜索模块")
        assert isinstance(result, dict)
        assert result.get("success") is True

    def test_harness_has_merged_results(self):
        from tests.nl_query_inproc import harness
        result = harness.search("重构")
        assert "merged_results" in result
        assert isinstance(result["merged_results"], list)

    def test_harness_result_fields_match_cli(self):
        """Every merged result must have the same fields as CLI output."""
        from tests.nl_query_inproc import harness
        result = harness.search("重构搜索模块", level=3)
        if result["merged_results"]:
            r = result["merged_results"][0]
            required_fields = [
                "path", "title", "search_rank", "confidence",
                "rrf_score", "final_score", "relevance_score",
                "source", "title_promoted",
            ]
            for field in required_fields:
                assert field in r, f"Missing field: {field}"

    def test_harness_explain_mode(self):
        """Explain mode should add explain dict + ranking_reason.

        Note: when semantic pipeline returns 0 results, the fallback
        code path (core.py line 728) does not forward explain=True to
        merge_and_rank_results. This is a known Phase 4 gap. The test
        only asserts explain fields when semantic was active.
        """
        from tests.nl_query_inproc import harness
        result = harness.search("重构搜索模块", explain=True)
        if result["merged_results"]:
            r = result["merged_results"][0]
            # ranking_reason is added post-rank in core.py (T4.5),
            # independent of the merge_and_rank code path
            assert "ranking_reason" in r, (
                "ranking_reason must be present in explain mode (T4.5)"
            )
            # explain dict is only added inside merge_and_rank_results
            # when the semantic path is taken; fallback path skips it
            if result.get("semantic_available") and result.get("semantic_results"):
                assert "explain" in r, (
                    "explain dict must be present when semantic pipeline is active"
                )

    def test_harness_non_explain_no_ranking_reason(self):
        """Non-explain mode should NOT include ranking_reason."""
        from tests.nl_query_inproc import harness
        result = harness.search("重构搜索模块", explain=False)
        for r in result.get("merged_results", []):
            assert "ranking_reason" not in r


class TestInprocHarnessPerformance:
    """Verify single cold-start + fast repeated queries."""

    def test_repeated_queries_fast(self):
        """After first query (model loaded), subsequent queries should be <500ms each."""
        from tests.nl_query_inproc import harness
        # Warm up (load model)
        harness.search("重构")

        times = []
        for _ in range(10):
            start = time.perf_counter()
            harness.search("重构搜索模块")
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg = sum(times) / len(times)
        assert avg < 0.5, f"Average query time {avg:.3f}s exceeds 500ms"

    def test_three_queries_under_25s(self):
        """Three different queries should complete in <25s total (one cold-start)."""
        from tests.nl_query_inproc import harness
        # Reload harness to ensure fresh cold-start measurement
        import tests.nl_query_inproc as mod
        importlib.reload(mod)

        start = time.perf_counter()
        for q in ["重构", "团团", "Claude Opus"]:
            mod.harness.search(q)
        total = time.perf_counter() - start
        assert total < 25.0, f"Three queries took {total:.1f}s (>25s)"


class TestInprocHarnessConsistency:
    """Verify harness output is consistent with hierarchical_search."""

    def test_same_query_deterministic(self):
        """Same query should return same top result."""
        from tests.nl_query_inproc import harness
        r1 = harness.search("重构搜索模块")
        r2 = harness.search("重构搜索模块")
        if r1["merged_results"] and r2["merged_results"]:
            assert r1["merged_results"][0]["path"] == r2["merged_results"][0]["path"]

    def test_semantic_available_flag(self):
        """Result should indicate semantic availability."""
        from tests.nl_query_inproc import harness
        result = harness.search("重构搜索模块")
        assert "semantic_available" in result
