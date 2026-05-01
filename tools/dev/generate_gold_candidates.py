#!/usr/bin/env python3
"""Generate Gold Set query candidates from real journal metadata."""
from __future__ import annotations

import json
import yaml
from pathlib import Path
from collections import defaultdict


def load_existing_queries() -> set[str]:
    gold = yaml.safe_load(Path("tools/eval/golden_queries.yaml").read_text(encoding="utf-8"))
    return {q["query"] for q in gold.get("queries", [])}


def load_journals() -> list[dict]:
    data: list[dict] = json.loads(
        Path("tools/dev/journal_metadata.json").read_text(encoding="utf-8")
    )
    return data


def next_id(existing: list[dict]) -> str:
    nums = []
    for q in existing:
        try:
            nums.append(int(q["id"].replace("GQ", "")))
        except ValueError:
            pass
    return f"GQ{max(nums) + 1:03d}"


def generate_time_range(entries: list[dict], existing_queries: set[str]) -> list[dict]:
    """Generate time_range queries based on date ranges."""
    candidates = []
    # Group by month
    by_month = defaultdict(list)
    for e in entries:
        if e["date"]:
            month = e["date"][:7]  # YYYY-MM
            by_month[month].append(e)

    for month, month_entries in sorted(by_month.items()):
        if len(month_entries) < 2:
            continue
        # Query: month-level
        q_text = f"{month.replace('-', '年')}月的日志"
        if q_text not in existing_queries:
            candidates.append(
                {
                    "query": q_text,
                    "category": "time_range",
                    "expected_titles": [e["title"] for e in month_entries[:3]],
                    "min_results": 1,
                }
            )

        # Query: specific date range within month
        if len(month_entries) >= 3:
            dates = sorted(e["date"] for e in month_entries if e["date"])
            mid = dates[len(dates) // 2]
            q_text2 = f"{mid}前后的记录"
            if q_text2 not in existing_queries:
                candidates.append(
                    {
                        "query": q_text2,
                        "category": "time_range",
                        "expected_titles": [
                            e["title"] for e in month_entries if e["date"][:10] == mid
                        ][:2],
                        "min_results": 1,
                    }
                )

    # Cross-month range
    all_dates = sorted(e["date"] for e in entries if e["date"])
    if len(all_dates) >= 4:
        q_text = f"{all_dates[0][:7]}到{all_dates[-1][:7]}的记录"
        if q_text not in existing_queries:
            candidates.append(
                {
                    "query": q_text,
                    "category": "time_range",
                    "expected_titles": [entries[0]["title"], entries[-1]["title"]],
                    "min_results": 2,
                }
            )

    return candidates


def generate_complex_query(entries: list[dict], existing_queries: set[str]) -> list[dict]:
    """Generate complex_query with multi-condition combinations."""
    candidates = []

    # topic + location combinations
    for topic in ["work", "think", "life", "create"]:
        topic_entries = [e for e in entries if topic in e.get("topic", [])]
        if len(topic_entries) >= 2:
            q_text = f"{topic}相关的日志"
            if q_text not in existing_queries:
                candidates.append(
                    {
                        "query": q_text,
                        "category": "complex_query",
                        "expected_titles": [e["title"] for e in topic_entries[:3]],
                        "min_results": 1,
                    }
                )

    # topic + date combinations
    by_month_topic: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for e in entries:
        month = e["date"][:7] if e["date"] else ""
        for t in e.get("topic", []):
            by_month_topic[month][t].append(e)

    for month, topics in by_month_topic.items():
        if not month:
            continue
        for topic, topic_entries in topics.items():
            if len(topic_entries) >= 2:
                ym = month.replace("-", "年")
                q_text = f"{ym}月{topic}相关的记录"
                if q_text not in existing_queries:
                    candidates.append(
                        {
                            "query": q_text,
                            "category": "complex_query",
                            "expected_titles": [e["title"] for e in topic_entries[:2]],
                            "min_results": 1,
                        }
                    )

    return candidates


def generate_semantic_recall(entries: list[dict], existing_queries: set[str]) -> list[dict]:
    """Generate semantic_recall queries - semantically related but keyword-divergent."""
    candidates = []

    # Map themes to semantic variants
    theme_map = {
        "亲子": ["育儿", "家庭教育", "孩子成长", "父女关系"],
        "AI": ["人工智能", "机器学习", "大模型", "智能系统"],
        "工作": ["职业发展", "项目进展", "创业", "职场"],
        "投资": ["理财", "股票", "资产配置", "价值投资"],
        "家庭": ["家人", "亲情", "家庭生活", "归家"],
        "健康": ["身体", "作息", "养生", "医疗"],
        "地缘政治": ["国际关系", "中东局势", "国际新闻", "全球政治"],
        "开发": ["编程", "软件开发", "系统设计", "技术实现"],
    }

    for entry in entries:
        tags = entry.get("tags", [])
        for tag in tags:
            if tag in theme_map:
                for variant in theme_map[tag]:
                    q_text = variant
                    if q_text not in existing_queries:
                        candidates.append(
                            {
                                "query": q_text,
                                "category": "semantic_recall",
                                "expected_titles": [entry["title"]],
                                "min_results": 1,
                            }
                        )
                        break
                break

    # Deduplicate
    seen = set()
    deduped = []
    for c in candidates:
        if c["query"] not in seen:
            seen.add(c["query"])
            deduped.append(c)

    return deduped


def generate_edge_case(entries: list[dict], existing_queries: set[str]) -> list[dict]:
    """Generate edge_case queries."""
    candidates = []

    # Very short query
    for tag in ["AI", "工作", "家庭", "投资"]:
        q_text = tag
        if q_text not in existing_queries:
            matching = [e for e in entries if tag in e.get("tags", []) or tag in e.get("title", "")]
            if matching:
                candidates.append(
                    {
                        "query": q_text,
                        "category": "edge_case",
                        "expected_titles": [matching[0]["title"]],
                        "min_results": 1,
                    }
                )

    # Query with special chars
    q_text = "Life Index 2.0"
    if q_text not in existing_queries:
        matching = [e for e in entries if "Life Index" in e.get("title", "")]
        if matching:
            candidates.append(
                {
                    "query": q_text,
                    "category": "edge_case",
                    "expected_titles": [e["title"] for e in matching[:2]],
                    "min_results": 1,
                }
            )

    return candidates


def generate_noise_rejection(entries: list[dict], existing_queries: set[str]) -> list[dict]:
    """Generate noise_rejection queries - should return no results."""
    candidates = []

    noise_queries = [
        "不存在的日志标题",
        "xyz123456789",
        "完全不相关的随机内容",
    ]

    for q_text in noise_queries:
        if q_text not in existing_queries:
            candidates.append(
                {
                    "query": q_text,
                    "category": "noise_rejection",
                    "expected_titles": [],
                    "min_results": 0,
                }
            )

    return candidates


def generate_entity_expansion(entries: list[dict], existing_queries: set[str]) -> list[dict]:
    """Generate entity_expansion queries."""
    candidates = []

    # Extract entities from titles
    entities = []
    for e in entries:
        title = e["title"]
        # Known entities
        for ent in ["Carloha", "OpenClaw", "Life Index", "LobsterAI", "乐乐", "Claude", "GitHub"]:
            if ent in title and ent not in entities:
                entities.append(ent)

    for ent in entities:
        q_text = ent
        if q_text not in existing_queries:
            matching = [e for e in entries if ent in e.get("title", "")]
            if matching:
                candidates.append(
                    {
                        "query": q_text,
                        "category": "entity_expansion",
                        "expected_titles": [e["title"] for e in matching[:3]],
                        "min_results": 1,
                    }
                )

    # Deduplicate by query text
    seen = set()
    deduped = []
    for c in candidates:
        if c["query"] not in seen:
            seen.add(c["query"])
            deduped.append(c)

    return deduped


def generate_high_frequency(entries: list[dict], existing_queries: set[str]) -> list[dict]:
    """Generate high_frequency queries - common words that appear in many docs."""
    candidates = []

    # "日志" appears in almost every title or is a common search term
    common_terms = ["日志", "记录", "思考", "工作", "生活"]
    for term in common_terms:
        if term not in existing_queries:
            matching = [
                e for e in entries if term in e.get("title", "") or term in e.get("tags", [])
            ]
            if len(matching) >= 3:
                candidates.append(
                    {
                        "query": term,
                        "category": "high_frequency",
                        "expected_titles": [e["title"] for e in matching[:3]],
                        "min_results": 1,
                    }
                )

    return candidates


def main() -> None:
    existing_queries = load_existing_queries()
    entries = load_journals()

    all_candidates = []
    all_candidates.extend(generate_time_range(entries, existing_queries))
    all_candidates.extend(generate_complex_query(entries, existing_queries))
    all_candidates.extend(generate_semantic_recall(entries, existing_queries))
    all_candidates.extend(generate_edge_case(entries, existing_queries))
    all_candidates.extend(generate_noise_rejection(entries, existing_queries))
    all_candidates.extend(generate_entity_expansion(entries, existing_queries))
    all_candidates.extend(generate_high_frequency(entries, existing_queries))

    # Deduplicate
    seen = set()
    deduped = []
    for c in all_candidates:
        if c["query"] not in seen and c["query"] not in existing_queries:
            seen.add(c["query"])
            deduped.append(c)

    # Load existing to append
    gold = yaml.safe_load(Path("tools/eval/golden_queries.yaml").read_text(encoding="utf-8"))
    existing = gold.get("queries", [])
    next_num = max(int(q["id"].replace("GQ", "")) for q in existing) + 1

    # Take top candidates by category priority
    priority = {
        "time_range": 3,
        "complex_query": 3,
        "semantic_recall": 2,
        "entity_expansion": 1,
        "edge_case": 1,
        "noise_rejection": 1,
        "high_frequency": 1,
    }
    deduped.sort(key=lambda c: priority.get(c["category"], 0), reverse=True)

    # Add up to 80 new candidates
    new_queries = []
    for c in deduped[:80]:
        new_queries.append(
            {
                "id": f"GQ{next_num:03d}",
                "query": c["query"],
                "category": c["category"],
                "description": "Auto-generated from journal metadata",
                "expected": {
                    "min_results": c["min_results"],
                    "must_contain_title": c["expected_titles"][:3],
                },
                "tags": [c["category"], "auto-generated"],
            }
        )
        next_num += 1

    # Write candidate file for review
    out: dict = {"candidates": new_queries, "total": len(new_queries), "by_category": {}}
    for cat in [
        "time_range",
        "complex_query",
        "semantic_recall",
        "entity_expansion",
        "edge_case",
        "noise_rejection",
        "high_frequency",
    ]:
        out["by_category"][cat] = sum(1 for q in new_queries if q["category"] == cat)

    Path("tools/dev/gold_candidates.yaml").write_text(
        yaml.dump(out, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    print(f"Generated {len(new_queries)} candidates")
    for cat, n in out["by_category"].items():
        if n > 0:
            print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
