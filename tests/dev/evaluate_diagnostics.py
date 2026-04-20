#!/usr/bin/env python3
"""Evaluate R12 diagnostic results — quality scoring."""
import json
import sys

results = json.load(open("tests/dev/r12_diagnostic_results.json", encoding="utf-8"))

# Quality criteria per query
EXPECTED = {
    "KW01": {"min_found": 5, "relevant_top": ["工作", "Carloha", "LobsterAI"]},
    "KW02": {"min_found": 3, "relevant_top": ["乐乐", "小英雄"]},
    "KW03": {"min_found": 3, "relevant_top": ["Life Index", "LifeIndex"]},
    "KW04": {"min_found": 1, "relevant_top": ["重构"]},
    "KW05": {"min_found": 1, "relevant_top": ["旅行", "归家", "重庆"]},
    "KW06": {"min_found": 1, "relevant_top": ["健康", "41岁"]},
    "KW07": {"min_found": 1, "relevant_top": ["部署", "OpenClaw"]},
    "KW08": {"min_found": 2, "relevant_top": ["学习", "GitHub"]},
    "KW09": {"min_found": 0, "relevant_top": []},  # No quantum computing journals
    "KW10": {"min_found": 1, "relevant_top": ["爸爸", "小英雄"]},
    "NL01": {"min_found": 1, "relevant_top": ["健康"]},
    "NL02": {"min_found": 1, "relevant_top": []},  # Sleep time - no specific data
    "NL03": {"min_found": 1, "relevant_top": ["乐乐"]},
    "NL04": {"min_found": 1, "relevant_top": ["daughter", "乐乐", "小英雄", "想念"]},
    "NL05": {"min_found": 3, "relevant_top": ["工作", "Life Index"]},
    "NL06": {"min_found": 1, "relevant_top": ["心情", "吵架", "恐惧"]},
    "NL07": {"min_found": 1, "relevant_top": ["拉各斯", "归家"]},
    "NL08": {"min_found": 3, "relevant_top": ["Life Index", "想法", "重构"]},
    "NL09": {"min_found": 1, "relevant_top": ["学习"]},
    "NL10": {"min_found": 1, "relevant_top": ["开心", "Star", "乐乐"]},
}

total_score = 0
max_score = 0

for r in results:
    rid = r["id"]
    exp = EXPECTED.get(rid, {})
    score = 0
    max_per = 10
    max_score += max_per

    found = r.get("total_found", 0)
    no_match = r.get("no_confident_match", False)
    top5 = r.get("top5", [])

    # 1. Found results (3 pts)
    min_found = exp.get("min_found", 0)
    if found >= min_found:
        score += 3
    elif found > 0:
        score += 1

    # 2. High confidence in top results (3 pts)
    if top5 and top5[0].get("confidence") == "high":
        score += 3
    elif top5 and top5[0].get("confidence") == "medium":
        score += 2
    elif top5:
        score += 1

    # 3. Relevant content in top-5 (4 pts)
    relevant = exp.get("relevant_top", [])
    if relevant:
        top_titles = " ".join(t.get("title", "") for t in top5)
        matched = sum(1 for kw in relevant if kw in top_titles)
        if matched > 0:
            score += min(4, 2 * matched)
    else:
        # KW09: no relevant journals expected
        if found == 0 or no_match:
            score += 4  # Correctly found nothing
        else:
            score += 2  # Found something but shouldn't

    pct = score / max_per * 100
    top_title = top5[0]["title"] if top5 else "NONE"
    conf = top5[0]["confidence"] if top5 else "none"
    print(f"{rid} | {score:2d}/{max_per} | found={found:3d} | conf={conf:6s} | {top_title}")

overall = total_score / max_score * 10 if max_score > 0 else 0
print(f"\nOverall: {total_score}/{max_score} = {overall:.1f}/10")
