"""Round 11 Representative Query Set (PRD §8.1).

This is the minimum verification set for Round 11. Every query here
must pass signal-level assertions by Phase 5 completion.
"""

from __future__ import annotations

R11_REPRESENTATIVE_QUERIES: list[dict] = [
    {
        "id": "R11-Q01",
        "query": "过去60天我有多少次晚于10点睡觉？",
        "type": "time_aggregation",
        "expect": {
            "search_plan_date_range_not_null": True,
            "intent_type": "count",
            "ambiguity_includes": "aggregation_requires_agent_judgement",
        },
    },
    {
        "id": "R11-Q02",
        "query": "上个月在工作中取得了什么进展？",
        "type": "time_work_summary",
        "expect": {
            "search_plan_date_range_not_null": True,
            "topic_hints_includes": "work",
            "ambiguity_may_include": "time_range_interpretation",
        },
    },
    {
        "id": "R11-Q03",
        "query": "我有多久没有关心过健康了？",
        "type": "topic_time_awareness",
        "expect": {
            "topic_hints_includes": "health",
            "search_plan_not_null": True,
        },
    },
    {
        "id": "R11-Q04",
        "query": "我和女儿之间有哪些珍贵的回忆？",
        "type": "entity_relation",
        "expect": {
            "search_plan_not_null": True,
            "entity_hints_may_resolve": ["团团", "尿片侠"],
        },
    },
    {
        "id": "R11-Q05",
        "query": "missing my daughter",
        "type": "cross_language_entity",
        "expect": {
            "search_plan_not_null": True,
            "no_silent_failure": True,
        },
    },
    {
        "id": "R11-Q06",
        "query": "量子计算机编程",
        "type": "rejection_irrelevant",
        "expect": {
            "no_confident_match": True,
            "low_or_no_results": True,
        },
    },
    {
        "id": "R11-Q07",
        "query": "团团",
        "type": "entity_keyword",
        "expect": {
            "search_plan_not_null": True,
            "no_regression_entity_ranking": True,
        },
    },
    {
        "id": "R11-Q08",
        "query": "Claude Opus",
        "type": "tech_keyword",
        "expect": {
            "search_plan_not_null": True,
            "no_regression_title_promotion": True,
        },
    },
]
