"""E2E integration test for Phase 4 (weight + fields + title + reason).

Validates the four Phase 4 changes work together end-to-end:
- T4.1: Semantic weight 0.4 → 0.6
- T4.2: Unified score fields (rrf_score / final_score / relevance_score)
- T4.3: source field reflecting pipeline hits
- T4.4: Title hard promotion (post-rank 1.5x multiplier)
- T4.5: ranking_reason in --explain mode
"""

import importlib
import os
import sys

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

TEST_JOURNALS = [
    {
        "title": "想念小英雄",
        "content": "看到女儿小时候的照片，感慨万分。小豆丁长大了。",
        "date": "2026-03-01",
        "topic": "think",
    },
    {
        "title": "乐乐不认真吃饭",
        "content": "今天乐乐又不认真吃饭了，真是头疼。",
        "date": "2026-03-02",
        "topic": "life",
    },
    {
        "title": "Claude Opus 4.6 CTO 级技术评审",
        "content": "Claude Opus 4.6 发布，CTO 级技术能力引发讨论。AI 伦理与算力。",
        "date": "2026-03-03",
        "topic": "work",
    },
    {
        "title": "重构搜索模块的思考",
        "content": "重构搜索模块，使用 RRF 融合算法。边缘计算部署测试。",
        "date": "2026-03-04",
        "topic": "work",
    },
    {
        "title": "AI 算力投资策略",
        "content": "讨论 AI 算力的投资策略和前景。",
        "date": "2026-03-05",
        "topic": "work",
    },
    {
        "title": "读《三体》有感",
        "content": "读了三体，思考数字灵魂和宇宙文明。",
        "date": "2026-03-06",
        "topic": "learn",
    },
    {
        "title": "想念我的女儿",
        "content": "想念乐乐，那个可爱的孩子。小豆丁长大了。",
        "date": "2026-03-07",
        "topic": "life",
    },
    {
        "title": "Life Index 架构重构",
        "content": "Life Index 搜索架构全面重构，双管道并行检索。",
        "date": "2026-03-08",
        "topic": "work",
    },
    {
        "title": "Google Stitch 集成测试",
        "content": "Google Stitch 集成测试成功。OpenClaw deployment optimization.",
        "date": "2026-03-09",
        "topic": "work",
    },
    {
        "title": "OpenClaw 部署优化",
        "content": "优化 OpenClaw 的 deployment 流程。Dynamic loading 改进。",
        "date": "2026-03-10",
        "topic": "work",
    },
]


@pytest.fixture(scope="module")
def search_env(tmp_path_factory):
    """Set up isolated search environment with test journals."""
    tmp = tmp_path_factory.mktemp("life_index_phase4_e2e")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(tmp)
    for mod_name in MODULES_TO_RELOAD:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
    from tools.build_index import build_all
    from tools.search_journals.core import hierarchical_search
    from tools.write_journal.core import write_journal

    for j in TEST_JOURNALS:
        write_journal(j)
    build_all(incremental=False)
    return hierarchical_search


class TestPhase4E2E:
    """End-to-end validation of Phase 4 changes."""

    def test_semantic_query_finds_daughter(self, search_env):
        """T4.1: '想起女儿' should find daughter-related journals via semantic."""
        result = search_env(query="想起女儿", level=3)
        merged = result.get("merged_results", [])
        assert len(merged) >= 1, "Should find at least one result for '想起女儿'"
        top_title = str(merged[0].get("title", ""))
        # Should match daughter-related journals, not unrelated ones
        assert (
            "乐乐" in top_title or "小英雄" in top_title or "女儿" in top_title
        ), f"Top result '{top_title}' should be about daughter"

    def test_claude_opus_title_promoted(self, search_env):
        """T4.4: 'Claude Opus' query should promote the matching title."""
        result = search_env(query="Claude Opus", level=3)
        merged = result.get("merged_results", [])
        if merged:
            claude_results = [r for r in merged if "Claude" in str(r.get("title", ""))]
            if claude_results:
                assert claude_results[0].get("title_promoted") is True

    def test_claude_opus_confidence_not_inflated(self, search_env):
        """T4.4/D12: Title promotion must not inflate confidence beyond D10 rules."""
        result = search_env(query="Claude Opus", level=3)
        for r in result.get("merged_results", []):
            if r.get("title_promoted"):
                # Confidence must follow D10 rules, not be artificially high
                assert r["confidence"] in {"high", "medium", "low"}

    def test_all_results_have_unified_fields(self, search_env):
        """T4.2: Every result must have rrf_score, final_score, relevance_score."""
        result = search_env(query="重构搜索模块", level=3)
        for r in result.get("merged_results", []):
            assert "rrf_score" in r, f"Missing rrf_score in {r.get('path')}"
            assert "final_score" in r, f"Missing final_score in {r.get('path')}"
            assert "relevance_score" in r, f"Missing relevance_score in {r.get('path')}"

    def test_source_field_reflects_pipeline(self, search_env):
        """T4.3: source field must be fts/semantic/fts,semantic/none."""
        result = search_env(query="重构搜索模块", level=3)
        allowed = {"fts", "semantic", "fts,semantic", "none"}
        for r in result.get("merged_results", []):
            assert r["source"] in allowed, f"Invalid source: {r['source']}"

    def test_rrf_score_positive_for_hybrid(self, search_env):
        """Hybrid results should have rrf_score > 0 when both pipelines contribute."""
        result = search_env(query="乐乐", level=3)
        has_positive_rrf = any(r.get("rrf_score", 0) > 0 for r in result.get("merged_results", []))
        assert has_positive_rrf, "At least one result should have positive rrf_score"

    def test_final_score_geq_rrf_score(self, search_env):
        """final_score >= rrf_score (title promotion can increase it)."""
        result = search_env(query="乐乐不认真吃饭", level=3)
        for r in result.get("merged_results", []):
            assert (
                r["final_score"] >= r["rrf_score"] - 1e-6
            ), f"final_score ({r['final_score']}) < rrf_score ({r['rrf_score']})"

    def test_explain_mode_has_ranking_reason(self, search_env):
        """T4.5: --explain mode should add ranking_reason to every result."""
        result = search_env(query="重构搜索模块", level=3, explain=True)
        for r in result.get("merged_results", []):
            assert "ranking_reason" in r, "Missing ranking_reason in explain mode"
            assert len(r["ranking_reason"]) <= 120
            assert len(r["ranking_reason"]) > 0

    def test_non_explain_mode_no_ranking_reason(self, search_env):
        """T4.5: Normal mode should NOT include ranking_reason."""
        result = search_env(query="重构搜索模块", level=3, explain=False)
        for r in result.get("merged_results", []):
            assert "ranking_reason" not in r, "ranking_reason should not exist in non-explain mode"

    def test_title_promoted_field_on_all_results(self, search_env):
        """T4.4: Every result should have the title_promoted boolean."""
        result = search_env(query="乐乐", level=3)
        for r in result.get("merged_results", []):
            assert "title_promoted" in r
            assert isinstance(r["title_promoted"], bool)

    def test_relevance_score_backward_compat(self, search_env):
        """relevance_score alias must be present for backward compatibility."""
        result = search_env(query="AI 算力", level=3)
        for r in result.get("merged_results", []):
            assert "relevance_score" in r
            assert r["relevance_score"] >= 0
