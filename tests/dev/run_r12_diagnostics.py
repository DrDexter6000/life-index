#!/usr/bin/env python3
"""Round 12 Diagnostic — 20 simulated user searches (10 KW + 10 NL)."""

import json
import sys
import time

# Ensure project root is on path
sys.path.insert(0, ".")

from tools.search_journals.core import hierarchical_search

QUERIES = [
    # ── 10 Keyword Searches ──
    {"id": "KW01", "query": "工作", "type": "keyword"},
    {"id": "KW02", "query": "团团", "type": "keyword"},
    {"id": "KW03", "query": "LifeIndex", "type": "keyword"},
    {"id": "KW04", "query": "重构", "type": "keyword"},
    {"id": "KW05", "query": "旅行", "type": "keyword"},
    {"id": "KW06", "query": "健康", "type": "keyword"},
    {"id": "KW07", "query": "部署", "type": "keyword"},
    {"id": "KW08", "query": "学习", "type": "keyword"},
    {"id": "KW09", "query": "量子计算机编程", "type": "keyword"},
    {"id": "KW10", "query": "爸爸", "type": "keyword"},
    # ── 10 Natural Language Searches ──
    {"id": "NL01", "query": "我有多久没有关心过健康了？", "type": "nl"},
    {"id": "NL02", "query": "过去60天我有多少次晚于10点睡觉？", "type": "nl"},
    {"id": "NL03", "query": "最近一次提到团团是什么时候？", "type": "nl"},
    {"id": "NL04", "query": "missing my daughter", "type": "nl"},
    {"id": "NL05", "query": "今年我在工作上的主要进展是什么？", "type": "nl"},
    {"id": "NL06", "query": "最近心情怎么样？", "type": "nl"},
    {"id": "NL07", "query": "上次去拉各斯的感觉如何？", "type": "nl"},
    {"id": "NL08", "query": "我对Life Index项目有什么新的想法？", "type": "nl"},
    {"id": "NL09", "query": "过去一个月学到了什么？", "type": "nl"},
    {"id": "NL10", "query": "最近有什么让我开心的事？", "type": "nl"},
]


def run_search(q: dict) -> dict:
    start = time.time()
    result = hierarchical_search(query=q["query"], level=3)
    elapsed = time.time() - start

    merged = result.get("merged_results", [])
    top5 = []
    for r in merged[:5]:
        top5.append({
            "title": r.get("title", "?"),
            "date": r.get("date", "?"),
            "confidence": r.get("confidence", "?"),
            "score": round(r.get("final_score", r.get("relevance_score", 0)), 2),
            "source": r.get("source", "?"),
        })

    plan = result.get("search_plan") or {}
    return {
        "id": q["id"],
        "query": q["query"],
        "type": q["type"],
        "total_found": result.get("total_found", 0),
        "no_confident_match": result.get("no_confident_match", False),
        "elapsed_s": round(elapsed, 1),
        "intent": plan.get("intent_type", "?"),
        "date_range": plan.get("date_range"),
        "topic_hints": plan.get("topic_hints", []),
        "keywords": plan.get("keywords", []),
        "ambiguity": result.get("ambiguity", {}).get("has_ambiguity", False),
        "warnings": result.get("warnings", []),
        "top5": top5,
    }


def main():
    import os
    results = []
    for i, q in enumerate(QUERIES):
        sys.stderr.write(f"[{i+1}/20] {q['id']}: {q['query']}\n")
        sys.stderr.flush()
        try:
            r = run_search(q)
        except Exception as e:
            r = {"id": q["id"], "query": q["query"], "type": q["type"], "error": str(e)}
        results.append(r)

    out_path = os.path.join(os.path.dirname(__file__), "r12_diagnostic_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"\nDone. Results written to {out_path}\n")
    sys.stderr.flush()


if __name__ == "__main__":
    main()
