#!/usr/bin/env python3
"""Phase 3 end-to-end assertions for noise control and recall preservation."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
import yaml


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
    "tools.search_journals.stopwords",
]

TEST_JOURNALS = [
    {
        "title": "Life Index 架构重构",
        "content": "重构搜索模块，使用 RRF 融合算法。边缘计算部署测试。AI 算力优化。",
        "date": "2026-03-01",
        "topic": "work",
    },
    {
        "title": "想念我的女儿",
        "content": "想念乐乐，那个可爱的孩子。",
        "date": "2026-03-02",
        "topic": "life",
    },
    {
        "title": "想念小英雄",
        "content": "看到女儿小时候的照片，感慨万分。小豆丁长大了。",
        "date": "2026-03-03",
        "topic": "think",
    },
    {
        "title": "重庆过生日",
        "content": "在重庆庆祝生日，数字灵魂的思考。",
        "date": "2026-03-04",
        "topic": "life",
    },
    {
        "title": "乐乐不认真吃饭",
        "content": "今天乐乐又不认真吃饭了，真是头疼。",
        "date": "2026-03-05",
        "topic": "life",
    },
    {
        "title": "Google Stitch 集成测试",
        "content": "Google Stitch 集成测试成功。OpenClaw deployment optimization.",
        "date": "2026-03-06",
        "topic": "work",
    },
    {
        "title": "OpenClaw 部署优化",
        "content": "优化 OpenClaw 的 deployment 流程。Dynamic loading 改进。",
        "date": "2026-03-07",
        "topic": "work",
    },
    {
        "title": "读《三体》有感",
        "content": "读了三体，思考数字灵魂和宇宙文明。",
        "date": "2026-03-08",
        "topic": "learn",
    },
    {
        "title": "人工智能伦理讨论",
        "content": "参加 AI 伦理讨论会，关于 AI 算力的道德问题。",
        "date": "2026-03-09",
        "topic": "think",
    },
    {
        "title": "LobsterAI 项目启动",
        "content": "LobsterAI 项目正式启动，AI 算力投资策略讨论。",
        "date": "2026-03-10",
        "topic": "work",
    },
]


@pytest.fixture(scope="module")
def rejection_queries() -> list[dict]:
    path = Path(__file__).parent.parent / "golden_rejection_queries.yaml"
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data["queries"]


@pytest.fixture(scope="module")
def search_func(tmp_path_factory: pytest.TempPathFactory):
    """Build isolated corpus and return hierarchical_search."""
    tmp = tmp_path_factory.mktemp("life_index_phase3_e2e")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(tmp)

    for module_name in MODULES_TO_RELOAD:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])

    from tools.build_index import build_all
    from tools.search_journals.core import hierarchical_search
    from tools.write_journal.core import write_journal

    for journal in TEST_JOURNALS:
        write_journal(journal)

    build_all(incremental=False)
    return hierarchical_search


def _titles_and_confidence(results: list[dict]) -> list[str]:
    return [
        f"{item.get('title', '<untitled>')} ({item.get('confidence', 'missing')})"
        for item in results
    ]


@pytest.mark.parametrize(
    "query",
    ["量子计算机编程", "马达加斯加首都风景"],
)
def test_irrelevant_queries_produce_no_confident_results(query: str, search_func) -> None:
    result = search_func(query=query, level=3)
    merged = result.get("merged_results", [])

    assert result.get("no_confident_match", False) or len(merged) == 0, (
        f"Irrelevant query '{query}' should be rejected, got "
        f"no_confident_match={result.get('no_confident_match')} and "
        f"results={_titles_and_confidence(merged)}"
    )


def test_ai_compute_query_retains_recall(search_func) -> None:
    result = search_func(query="AI 算力", level=3)
    merged = result.get("merged_results", [])

    assert len(merged) >= 3, (
        "Expected >=3 hits for 'AI 算力', got "
        f"{len(merged)}: {_titles_and_confidence(merged)}"
    )
    assert merged[0].get("confidence") in {"high", "medium"}, (
        "Top-1 confidence for 'AI 算力' should stay usable, got "
        f"{merged[0].get('confidence')} with {merged[0].get('title')}"
    )


def test_tuantuan_query_retains_family_recall(search_func) -> None:
    result = search_func(query="乐乐", level=3)
    merged = result.get("merged_results", [])

    assert len(merged) >= 2, (
        "Expected >=2 hits for '乐乐', got "
        f"{len(merged)}: {_titles_and_confidence(merged)}"
    )
    assert "乐乐" in str(merged[0].get("title", "")), (
        "Top-1 title for '乐乐' should explicitly contain 乐乐, got "
        f"{merged[0].get('title')}"
    )


def test_edge_computing_query_keeps_expected_top1(search_func) -> None:
    result = search_func(query="边缘计算", level=3)
    merged = result.get("merged_results", [])

    assert len(merged) >= 1, "Expected at least one result for '边缘计算'"
    assert merged[0].get("title") == "Life Index 架构重构", (
        "Top-1 for '边缘计算' regressed: "
        f"{_titles_and_confidence(merged)}"
    )


def test_golden_rejection_queries_pass_rate_stays_at_or_above_90_percent(
    rejection_queries: list[dict], search_func
) -> None:
    passed = 0
    failed: list[dict[str, object]] = []

    for item in rejection_queries:
        result = search_func(query=item["query"], level=3)
        merged = result.get("merged_results", [])
        expected = item["expected"]

        ok = True
        if "max_results" in expected and len(merged) > expected["max_results"]:
            ok = False
        if expected.get("require_no_confident_match") and not result.get(
            "no_confident_match", False
        ):
            ok = False

        if ok:
            passed += 1
        else:
            failed.append(
                {
                    "id": item["id"],
                    "query": item["query"],
                    "results": len(merged),
                    "no_confident_match": result.get("no_confident_match"),
                    "titles": _titles_and_confidence(merged),
                }
            )

    total = len(rejection_queries)
    rate = passed / total if total else 0.0

    assert rate >= 0.90, (
        f"Rejection pass-rate {rate:.1%} ({passed}/{total}) < 90%.\n"
        + "\n".join(
            f"  {item['id']}: '{item['query']}' → {item['results']} results, "
            f"no_confident_match={item['no_confident_match']}, titles={item['titles']}"
            for item in failed
        )
    )


def test_english_cross_language_query_not_overfiltered_by_stopwords() -> None:
    from tools.search_journals.stopwords import filter_stopwords, is_stopword

    filtered = filter_stopwords(["missing", "my", "daughter"])

    assert not is_stopword("missing")
    assert not is_stopword("daughter")
    assert "missing" in filtered and "daughter" in filtered, (
        f"Core English content words were filtered out: {filtered}"
    )
