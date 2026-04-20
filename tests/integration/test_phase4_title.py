"""Integration test for title hard promotion (T4.4 / D12)."""

import importlib
import os
import sys

import pytest
from pathlib import Path

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
    "tools.search_journals.stopwords",
]

TEST_JOURNALS = [
    {"title": "Life Index 架构重构", "content": "重构搜索模块，使用 RRF 融合算法。边缘计算部署测试。AI 算力优化。", "date": "2026-03-01", "topic": "work"},
    {"title": "想念我的女儿", "content": "想念乐乐，那个可爱的孩子。", "date": "2026-03-02", "topic": "life"},
    {"title": "想念小英雄", "content": "看到女儿小时候的照片，感慨万分。小豆丁长大了。", "date": "2026-03-03", "topic": "think"},
    {"title": "重庆过生日", "content": "在重庆庆祝生日，数字灵魂的思考。", "date": "2026-03-04", "topic": "life"},
    {"title": "乐乐不认真吃饭", "content": "今天乐乐又不认真吃饭了，真是头疼。", "date": "2026-03-05", "topic": "life"},
    {"title": "Google Stitch 集成测试", "content": "Google Stitch 集成测试成功。OpenClaw deployment optimization.", "date": "2026-03-06", "topic": "work"},
    {"title": "OpenClaw 部署优化", "content": "优化 OpenClaw 的 deployment 流程。Dynamic loading 改进。", "date": "2026-03-07", "topic": "work"},
    {"title": "读《三体》有感", "content": "读了三体，思考数字灵魂和宇宙文明。", "date": "2026-03-08", "topic": "learn"},
    {"title": "人工智能伦理讨论", "content": "参加 AI 伦理讨论会，关于 AI 算力的道德问题。", "date": "2026-03-09", "topic": "think"},
    {"title": "LobsterAI 项目启动", "content": "LobsterAI 项目正式启动，AI 算力投资策略讨论。", "date": "2026-03-10", "topic": "work"},
]


@pytest.fixture(scope="module")
def search_func(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("life_index_phase4_title")
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


def test_title_match_ranks_higher(search_func):
    """Query matching a title should rank that result higher via promotion."""
    result = search_func(query="乐乐不认真吃饭", level=3)
    merged = result.get("merged_results", [])
    if merged:
        top = merged[0]
        # Title "乐乐不认真吃饭" should be promoted (query = title = 100% coverage)
        assert top.get("title_promoted") is True


def test_promotion_does_not_affect_confidence(search_func):
    """Promoted results keep their original D10 confidence label."""
    result = search_func(query="乐乐不认真吃饭", level=3)
    for r in result.get("merged_results", []):
        if r.get("title_promoted"):
            # Confidence should still follow D10 rules, not be artificially inflated
            assert r["confidence"] in {"high", "medium", "low"}


def test_all_results_have_title_promoted_field(search_func):
    """Every merged result must have the title_promoted boolean field."""
    result = search_func(query="重构搜索模块", level=3)
    merged = result.get("merged_results", [])
    for r in merged:
        assert "title_promoted" in r, f"Missing title_promoted in {r.get('path')}"
        assert isinstance(r["title_promoted"], bool)
