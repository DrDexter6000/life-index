#!/usr/bin/env python3
"""Integration test: golden rejection queries must produce no/low-confidence results."""

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
]


@pytest.fixture(scope="module")
def rejection_queries() -> list[dict]:
    path = Path(__file__).parent.parent / "golden_rejection_queries.yaml"
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data["queries"]


@pytest.fixture(scope="module")
def search_func(tmp_path_factory: pytest.TempPathFactory):
    """Set up isolated data dir with test journals and return search function."""
    tmp = tmp_path_factory.mktemp("life_index_rejection")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(tmp)

    for module_name in MODULES_TO_RELOAD:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])

    from tools.build_index import build_all
    from tools.search_journals.core import hierarchical_search
    from tools.write_journal.core import write_journal

    test_journals = [
        {
            "title": "Life Index 架构重构",
            "content": "重构搜索模块，使用 RRF 融合算法。边缘计算部署测试。AI 算力优化。",
            "date": "2026-03-01",
            "topic": "work",
        },
        {
            "title": "想念我的女儿",
            "content": "想念团团，那个可爱的孩子。",
            "date": "2026-03-02",
            "topic": "life",
        },
        {
            "title": "想念尿片侠",
            "content": "看到女儿小时候的照片，感慨万分。小疙瘩长大了。",
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
            "title": "团团不认真吃饭",
            "content": "今天团团又不认真吃饭了，真是头疼。",
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

    for journal in test_journals:
        write_journal(
            {
                "title": journal["title"],
                "content": journal["content"],
                "date": journal["date"],
                "topic": journal["topic"],
            }
        )

    build_all(incremental=False)
    return hierarchical_search


def test_rejection_pass_rate(rejection_queries: list[dict], search_func) -> None:
    """At least 90% of rejection queries must pass (no/low confidence results)."""
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
                }
            )

    total = len(rejection_queries)
    rate = passed / total if total else 0.0

    assert rate >= 0.90, (
        f"Rejection pass-rate {rate:.1%} ({passed}/{total}) < 90% threshold.\n"
        f"Failed queries:\n"
        + "\n".join(
            f"  {item['id']}: '{item['query']}' → {item['results']} results, "
            f"no_confident_match={item['no_confident_match']}"
            for item in failed
        )
    )
