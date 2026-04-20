"""Batch search runner for Round 11 final review — 20 simulated user queries."""
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
sys.stderr.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]

from tools.search_journals.core import hierarchical_search

QUERIES = [
    # === Keyword searches (10) ===
    ("KW01", "乐乐"),
    ("KW02", "Claude Opus"),
    ("KW03", "重构搜索模块"),
    ("KW04", "生日 重庆"),
    ("KW05", "焦虑"),
    ("KW06", "OpenClaw 部署"),
    ("KW07", "小英雄"),
    ("KW08", "投资 算力"),
    ("KW09", "量子计算机编程"),
    ("KW10", "Life Index 架构"),
    # === Natural language searches (10) ===
    ("NL01", "过去60天我有多少次晚于10点睡觉？"),
    ("NL02", "上个月在工作中取得了什么进展？"),
    ("NL03", "我有多久没有关心过健康了？"),
    ("NL04", "我和女儿之间有哪些珍贵的回忆？"),
    ("NL05", "missing my daughter"),
    ("NL06", "最近有什么让我开心的事？"),
    ("NL07", "我对AI发展有哪些思考？"),
    ("NL08", "最近和家人的关系怎么样？"),
    ("NL09", "在尼日利亚的生活有什么值得记录的？"),
    ("NL10", "我对Life Index这个项目有什么规划和期望？"),
]


def run_search(qid: str, query: str) -> dict:
    """Run a single search and return structured result."""
    try:
        result = hierarchical_search(query=query, level=3, semantic=True)
        data = result.get("data", result)

        sp = data.get("search_plan") or {}
        amb = data.get("ambiguity") or {}
        hints = data.get("hints") or []
        results = data.get("merged_results") or data.get("results") or []
        total = data.get("total_found", 0)
        ncm = data.get("no_confident_match", False)
        warnings = data.get("warnings", [])

        # Debug: if no results, check what keys exist
        if not results and total > 0:
            # Maybe results are under a different key
            alt_keys = [k for k in data.keys() if k not in ("search_plan", "ambiguity", "hints", "warnings", "events")]
            print(f"[DEBUG {qid}] total_found={total} but results=[] | keys={list(data.keys())[:15]}", file=sys.stderr)

        top5 = []
        for i, r in enumerate(results[:5]):
            top5.append({
                "rank": i + 1,
                "title": (r.get("title") or "?")[:60],
                "confidence": r.get("confidence", "?"),
                "score": round(r.get("score", 0), 3),
                "date": str(r.get("date", "?"))[:10],
                "path_tail": (r.get("path") or "?")[-50:],
            })

        return {
            "id": qid,
            "query": query,
            "intent": sp.get("intent_type", "N/A"),
            "date_range": sp.get("date_range"),
            "topic_hints": sp.get("topic_hints", []),
            "keywords": sp.get("keywords", []),
            "ambiguity_detected": amb.get("detected", False),
            "ambiguity_types": [a.get("type") for a in amb.get("items", [])],
            "hints_count": len(hints),
            "hint_types": [h.get("type") for h in hints[:5]],
            "total_found": total,
            "no_confident_match": ncm,
            "warnings": warnings,
            "top5": top5,
        }
    except Exception as e:
        import traceback
        return {"id": qid, "query": query, "error": str(e), "traceback": traceback.format_exc()}


def main():
    all_results = []
    for qid, query in QUERIES:
        print(f"--- Running {qid}: {query} ---", file=sys.stderr)
        r = run_search(qid, query)
        all_results.append(r)

    # Save to file (avoids PowerShell encoding issues)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search_results_r11.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"Results saved to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
