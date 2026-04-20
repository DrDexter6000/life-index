#!/usr/bin/env python3
"""Batch search quality diagnostic — 20 queries (10 keyword + 10 NL semantic).

Runs against REAL user data (~/Documents/Life-Index/) via in-process harness.
Outputs structured JSON results for analysis.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

# Ensure we're using real user data (no LIFE_INDEX_DATA_DIR override)
import os

if "LIFE_INDEX_DATA_DIR" in os.environ:
    del os.environ["LIFE_INDEX_DATA_DIR"]

from tools.search_journals.core import hierarchical_search

KEYWORD_QUERIES = [
    {"id": "KW01", "query": "团团", "type": "keyword", "intent": "实体搜索 - 找到关于女儿团团的所有日志"},
    {"id": "KW02", "query": "Claude Opus", "type": "keyword", "intent": "英文关键词 - 找到与 Claude Opus 互动的记录"},
    {"id": "KW03", "query": "重构搜索模块", "type": "keyword", "intent": "精确技术主题 - 找到搜索重构相关条目"},
    {"id": "KW04", "query": "生日 重庆", "type": "keyword", "intent": "地点+事件组合 - 找到重庆过生日"},
    {"id": "KW05", "query": "焦虑", "type": "keyword", "intent": "情绪词 - 找到焦虑相关条目"},
    {"id": "KW06", "query": "OpenClaw 部署", "type": "keyword", "intent": "项目+动作组合"},
    {"id": "KW07", "query": "尿片侠", "type": "keyword", "intent": "实体别名搜索"},
    {"id": "KW08", "query": "Life Index 架构", "type": "keyword", "intent": "项目名+技术领域"},
    {"id": "KW09", "query": "投资 算力", "type": "keyword", "intent": "双关键词组合"},
    {"id": "KW10", "query": "量子计算机编程", "type": "keyword", "intent": "完全不相关查询 - 应返回0结果或无置信匹配"},
]

NL_QUERIES = [
    {"id": "NL01", "query": "我有多久没有关心过健康了？", "type": "nl", "intent": "隐式主题搜索 - 应找到健康/身体相关日志"},
    {"id": "NL02", "query": "过去60天我有多少次晚于10点睡觉？", "type": "nl", "intent": "时间量化查询 - 系统不应负责量化，但应返回相关条目"},
    {"id": "NL03", "query": "最近有什么让我开心的事？", "type": "nl", "intent": "情绪相关搜索"},
    {"id": "NL04", "query": "我和女儿之间有哪些珍贵的回忆？", "type": "nl", "intent": "关系+情感搜索 - 应找到团团相关"},
    {"id": "NL05", "query": "上个月在工作中取得了什么进展？", "type": "nl", "intent": "时间+工作维度搜索"},
    {"id": "NL06", "query": "missing my daughter", "type": "nl", "intent": "跨语言搜索 - 应找到想念尿片侠"},
    {"id": "NL07", "query": "我对AI发展有哪些思考？", "type": "nl", "intent": "主题+思考维度"},
    {"id": "NL08", "query": "最近和家人的关系怎么样？", "type": "nl", "intent": "关系维度搜索"},
    {"id": "NL09", "query": "在尼日利亚的生活有什么值得记录的？", "type": "nl", "intent": "地点+生活维度"},
    {"id": "NL10", "query": "我对Life Index这个项目有什么规划和期望？", "type": "nl", "intent": "项目规划搜索"},
]


def run_query(item: dict) -> dict:
    """Run a single query and collect structured results."""
    start = time.perf_counter()
    result = hierarchical_search(query=item["query"], level=3, explain=True)
    elapsed = time.perf_counter() - start

    merged = result.get("merged_results", [])
    top5 = []
    for r in merged[:5]:
        entry = {
            "title": r.get("title", ""),
            "date": r.get("date", ""),
            "confidence": r.get("confidence", ""),
            "source": r.get("source", ""),
            "rrf_score": r.get("rrf_score", 0),
            "final_score": r.get("final_score", 0),
            "ranking_reason": r.get("ranking_reason", ""),
        }
        top5.append(entry)

    return {
        "id": item["id"],
        "query": item["query"],
        "type": item["type"],
        "intent": item["intent"],
        "elapsed_s": round(elapsed, 2),
        "total_results": len(merged),
        "no_confident_match": result.get("no_confident_match", False),
        "semantic_available": result.get("semantic_available", False),
        "top5": top5,
        "mix": result.get("performance", {}).get("result_mix", "unknown"),
    }


def main() -> None:
    all_queries = KEYWORD_QUERIES + NL_QUERIES
    results = []

    print(f"Running {len(all_queries)} queries against real user data...")
    print(f"Data dir: {Path.home() / 'Documents' / 'Life-Index'}")
    print()

    for i, q in enumerate(all_queries):
        print(f"  [{i+1:2d}/{len(all_queries)}] {q['id']}: {q['query'][:40]}...")
        r = run_query(q)
        results.append(r)

    output_path = Path(__file__).parent.parent / "tests" / "search_diagnostic_results.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_path}")
    print(f"\n{'='*80}")

    # Print summary table
    print(f"\n{'ID':<6} {'Type':<9} {'Results':>7} {'ConfMatch':>10} {'Elapsed':>8} {'Top1 Title'}")
    print("-" * 90)
    for r in results:
        top1 = r["top5"][0]["title"][:35] if r["top5"] else "(无结果)"
        conf = "YES" if r["no_confident_match"] else "no"
        print(f"{r['id']:<6} {r['type']:<9} {r['total_results']:>7} {conf:>10} {r['elapsed_s']:>7.1f}s {top1}")

    print(f"\n{'='*80}")
    print("DIAGNOSTIC COMPLETE")


if __name__ == "__main__":
    main()
