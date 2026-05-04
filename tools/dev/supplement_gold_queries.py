#!/usr/bin/env python3
"""Supplement additional Gold Set queries to reach 150+."""

from __future__ import annotations

import yaml
from pathlib import Path


def main() -> None:
    gold_path = Path("tools/eval/golden_queries.yaml")
    gold = yaml.safe_load(gold_path.read_text(encoding="utf-8"))
    existing = gold.get("queries", [])
    existing_queries = {q["query"] for q in existing}
    next_id = max(int(q["id"].replace("GQ", "")) for q in existing) + 1

    supplements = [
        # chinese_recall (+6)
        {
            "id": f"GQ{next_id:03d}",
            "query": "小英雄",
            "category": "chinese_recall",
            "description": "Chinese nickname recall",
            "expected": {"min_results": 1, "must_contain_title": ["想念小英雄"]},
            "tags": ["chinese", "recall"],
        },
        {
            "id": f"GQ{next_id+1:03d}",
            "query": "GitHub仓库",
            "category": "chinese_recall",
            "description": "Chinese query with English entity",
            "expected": {"min_results": 1, "must_contain_title": ["中年人的第一个GitHub仓库"]},
            "tags": ["chinese", "recall"],
        },
        {
            "id": f"GQ{next_id+2:03d}",
            "query": "Carloha工作",
            "category": "chinese_recall",
            "description": "Chinese + brand name mixed query",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["Carloha Wiki诞生记：AI赋能的一天"],
            },
            "tags": ["chinese", "recall"],
        },
        {
            "id": f"GQ{next_id+3:03d}",
            "query": "乐乐教育",
            "category": "chinese_recall",
            "description": "Chinese family topic query",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["家庭会议：确立乐乐教育第一责任人原则"],
            },
            "tags": ["chinese", "recall"],
        },
        {
            "id": f"GQ{next_id+4:03d}",
            "query": "LobsterAI项目",
            "category": "chinese_recall",
            "description": "Chinese + English brand recall",
            "expected": {"min_results": 1, "must_contain_title": ["LobsterAI Journal 臃肿危机"]},
            "tags": ["chinese", "recall"],
        },
        {
            "id": f"GQ{next_id+5:03d}",
            "query": "Life Index开发",
            "category": "chinese_recall",
            "description": "Chinese query about product development",
            "expected": {"min_results": 1, "must_contain_title": ["Life Index 搜索功能优化"]},
            "tags": ["chinese", "recall"],
        },
        # edge_case (+4)
        {
            "id": f"GQ{next_id+6:03d}",
            "query": "团",
            "category": "edge_case",
            "description": "Single Chinese character query",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["家庭会议：确立乐乐教育第一责任人原则"],
            },
            "tags": ["edge_case", "short"],
        },
        {
            "id": f"GQ{next_id+7:03d}",
            "query": "AI",
            "category": "edge_case",
            "description": "Very short English acronym",
            "expected": {"min_results": 1, "must_contain_title": ["人类 vs AI"]},
            "tags": ["edge_case", "short"],
        },
        {
            "id": f"GQ{next_id+8:03d}",
            "query": "2.0",
            "category": "edge_case",
            "description": "Version number query",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["Life Index Web GUI 功能开发完成"],
            },
            "tags": ["edge_case", "version"],
        },
        {
            "id": f"GQ{next_id+9:03d}",
            "query": "特朗普病危与美国衰败的思考",
            "category": "edge_case",
            "description": "Long exact title match",
            "expected": {"min_results": 1, "must_contain_title": ["特朗普病危与美国衰败的思考"]},
            "tags": ["edge_case", "exact_match"],
        },
        # entity_expansion (+4)
        {
            "id": f"GQ{next_id+10:03d}",
            "query": "Claude",
            "category": "entity_expansion",
            "description": "Brand entity recall",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["Claude Opus 4.6 对 Life Index 的 CTO 级别技术评审"],
            },
            "tags": ["entity", "brand"],
        },
        {
            "id": f"GQ{next_id+11:03d}",
            "query": "OpenCode",
            "category": "entity_expansion",
            "description": "Product entity recall",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["OpenCode浏览器自动化故障解决记录"],
            },
            "tags": ["entity", "product"],
        },
        {
            "id": f"GQ{next_id+12:03d}",
            "query": "算力",
            "category": "entity_expansion",
            "description": "Chinese concept entity",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["智算中心迈入兆瓦级时代——算力投资思考"],
            },
            "tags": ["entity", "concept"],
        },
        {
            "id": f"GQ{next_id+13:03d}",
            "query": "投资",
            "category": "entity_expansion",
            "description": "Chinese topic entity",
            "expected": {
                "min_results": 1,
                "must_contain_title": ["AI算力国资股长线投资研究（Kimi辅助）"],
            },
            "tags": ["entity", "topic"],
        },
        # high_frequency (+1)
        {
            "id": f"GQ{next_id+14:03d}",
            "query": "思考",
            "category": "high_frequency",
            "description": "High frequency Chinese word",
            "expected": {"min_results": 1, "must_contain_title": ["特朗普病危与美国衰败的思考"]},
            "tags": ["high_frequency", "chinese"],
        },
    ]

    # Filter out duplicates
    added = []
    for s in supplements:
        if s["query"] not in existing_queries:
            added.append(s)
            existing_queries.add(s["query"])

    merged = existing + added
    gold["queries"] = merged
    gold_path.write_text(yaml.dump(gold, allow_unicode=True, sort_keys=False), encoding="utf-8")

    print(f"Added: {len(added)}")
    print(f"Total: {len(merged)}")


if __name__ == "__main__":
    main()
