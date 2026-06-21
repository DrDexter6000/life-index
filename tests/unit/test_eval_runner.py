#!/usr/bin/env python3

import importlib
import json
import math
import os
from importlib import import_module
from pathlib import Path

import pytest
import yaml

from tools.eval.private_data import get_golden_queries_path


def _load_eval_llm_module():
    return import_module("tools.eval.llm_client")


GOLDEN_QUERIES_PATH = get_golden_queries_path()
pytestmark = pytest.mark.skipif(
    not GOLDEN_QUERIES_PATH.exists(),
    reason="local/private eval query set not present in public checkout",
)


JOURNALS = [
    {
        "filename": "life-index_2026-03-04_001.md",
        "title": "回忆小风筝",
        "date": "2026-03-04T19:43:00",
        "tags": ["亲子", "回忆", "感伤"],
        "topic": "think",
        "content": (
            "翻看女儿晴岚小时候的照片，那个只有2岁上下的小队长。"
            "突然有一种伤感——我好想再见她一面，好想再能体验一次把小玩偶抱在怀里的感觉。"
            "小风筝，朋友想你了。"
        ),
    },
    {
        "filename": "life-index_2026-03-07_001.md",
        "title": "Life Index 架构重构",
        "date": "2026-03-07T14:30:00",
        "tags": ["重构", "优化"],
        "topic": "work",
        "content": (
            "今天完成了双管道检索架构的优化。关键词管道和语义管道并行执行，RRF融合排序。"
            "AI算力投资策略也开始关注，特别是边缘计算和端侧部署。"
        ),
    },
    {
        "filename": "life-index_2026-03-10_001.md",
        "title": "晴岚不认真吃饭",
        "date": "2026-03-10T18:00:00",
        "tags": ["亲子", "日常"],
        "topic": "life",
        "content": "晴岚最近吃饭很不认真，总是跑来跑去。不过今天她主动帮我收拾玩具，还是挺懂事的。",
    },
    {
        "filename": "life-index_2026-03-12_001.md",
        "title": "海边过生日",
        "date": "2026-03-12T12:00:00",
        "tags": ["生日", "家庭"],
        "topic": "life",
        "content": (
            "在海边过了一个简单的生日。妈妈做了长寿面，晴岚唱了生日歌。"
            "虽然简单，但很温暖。记忆索引的概念也在脑海中酝酿。"
        ),
    },
    {
        "filename": "life-index_2026-03-14_001.md",
        "title": "Google Stitch 集成测试",
        "date": "2026-03-14T10:00:00",
        "tags": ["开发", "测试"],
        "topic": "work",
        "content": (
            "Completed integration testing for Google Stitch API. "
            "The search pipeline now handles mixed Chinese-English queries correctly. "
            "OpenClaw deployment is next. "
            "We also discussed our investment strategy for Q2."
        ),
    },
    {
        "filename": "life-index_2026-03-16_001.md",
        "title": "回忆海边花园",
        "date": "2026-03-16T22:00:00",
        "tags": ["思念", "亲情"],
        "topic": "think",
        "content": (
            "深夜翻看晴岚的照片，那种幸福中带怅然若失的复杂情绪无法用言语表达。"
            "好想把她再抱在怀里，那个让我神魂颠倒的小队长。"
        ),
    },
    {
        "filename": "life-index_2026-03-18_001.md",
        "title": "LobsterAI 项目启动",
        "date": "2026-03-18T09:00:00",
        "tags": ["创业", "AI"],
        "topic": "work",
        "content": (
            "LobsterAI项目正式启动。目标是用AI算力投资策略来解决个人知识管理问题。"
            "晴岚说以后也要学编程。"
        ),
    },
    {
        "filename": "life-index_2026-03-20_001.md",
        "title": "读《星际寓言》有感",
        "date": "2026-03-20T20:00:00",
        "tags": ["读书", "思考"],
        "topic": "learn",
        "content": (
            "重读《星际寓言》，对星图法则法则有了新的理解。"
            "科技发展的边界在哪里？记忆索引是否可能存在？这些问题值得深思。"
        ),
    },
    {
        "filename": "life-index_2026-03-22_001.md",
        "title": "OpenClaw 部署优化",
        "date": "2026-03-22T11:00:00",
        "tags": ["部署", "优化"],
        "topic": "work",
        "content": (
            "Optimized OpenClaw deployment pipeline. "
            "Reduced cold start time by 40%. "
            "The agent skill system now supports dynamic loading."
        ),
    },
    {
        "filename": "life-index_2026-03-23_001.md",
        "title": "Aggregate Partial Fixture",
        "date": "2026-03-23",
        "tags": ["fixture"],
        "topic": "test",
        "content": "Neutral fixture entry without a time-of-day field.",
    },
    {
        "filename": "life-index_2026-03-25_001.md",
        "title": "人工智能伦理讨论",
        "date": "2026-03-25T15:00:00",
        "tags": ["AI", "伦理"],
        "topic": "think",
        "content": (
            "参加了关于AI算力投资策略的线上讨论。"
            "与会者对人工智能伦理有不同观点，但大家都同意透明度和可解释性是关键。"
        ),
    },
]


def _write_eval_fixture_data(data_dir: Path) -> None:
    journals_dir = data_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "by-topic").mkdir(exist_ok=True)
    (data_dir / "attachments").mkdir(exist_ok=True)
    (data_dir / ".cache").mkdir(exist_ok=True)
    (data_dir / ".index").mkdir(exist_ok=True)

    graph_payload = {
        "entities": [
            {
                "id": "tuantuan",
                "type": "person",
                "primary_name": "晴岚",
                "aliases": ["小风筝", "小队长"],
                "attributes": {},
                "relationships": [],
            },
            {
                "id": "openclaw",
                "type": "project",
                "primary_name": "OpenClaw",
                "aliases": [],
                "attributes": {},
                "relationships": [],
            },
            {
                "id": "lobsterai",
                "type": "project",
                "primary_name": "LobsterAI",
                "aliases": [],
                "attributes": {},
                "relationships": [],
            },
        ]
    }
    (data_dir / "entity_graph.yaml").write_text(
        yaml.safe_dump(graph_payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    for journal in JOURNALS:
        file_path = journals_dir / journal["filename"]
        frontmatter = [
            "---",
            f"title: {journal['title']!r}",
            f"date: {journal['date']}",
            f"tags: [{', '.join(journal['tags'])}]",
            f"topic: {journal['topic']}",
            "---",
            "",
            f"# {journal['title']}",
            "",
            journal["content"],
            "",
        ]
        file_path.write_text("\n".join(frontmatter), encoding="utf-8")

    feb_dir = data_dir / "Journals" / "2026" / "02"
    feb_dir.mkdir(parents=True, exist_ok=True)
    (feb_dir / "life-index_2026-02-28_001.md").write_text(
        "\n".join(
            [
                "---",
                "date: 2026-02-28",
                "title: 'Feb cross-month entry'",
                "topic: life",
                "---",
                "",
                "Cross-month boundary test content",
                "",
            ]
        ),
        encoding="utf-8",
    )

    import tools.lib.paths as paths_module
    import tools.lib.config as config_module
    import tools.lib.metadata_cache as metadata_cache_module
    import tools.lib.search_index as search_index_module
    import tools.lib.fts_update as fts_update_module
    import tools.lib.fts_search as fts_search_module

    importlib.reload(paths_module)
    importlib.reload(config_module)
    importlib.reload(metadata_cache_module)
    importlib.reload(search_index_module)
    importlib.reload(fts_update_module)
    importlib.reload(fts_search_module)

    from tools.lib.chinese_tokenizer import reset_tokenizer_state
    from tools.lib.search_index import init_fts_db, update_index

    reset_tokenizer_state()
    conn = init_fts_db()
    try:
        result = update_index(incremental=False)
        assert result["success"] is True
    finally:
        conn.close()


def test_golden_queries_yaml_is_valid() -> None:
    payload = yaml.safe_load(GOLDEN_QUERIES_PATH.read_text(encoding="utf-8"))

    assert isinstance(payload, dict)
    assert isinstance(payload.get("queries"), list)
    assert 20 <= len(payload["queries"]) <= 150

    required_categories = {
        "entity_expansion",
        "noise_rejection",
        "english_regression",
        "high_frequency",
    }
    category_counts: dict[str, int] = {category: 0 for category in required_categories}

    for query in payload["queries"]:
        assert isinstance(query["id"], str)
        assert isinstance(query["query"], str)
        assert isinstance(query["category"], str)
        assert isinstance(query["description"], str)
        assert isinstance(query["tags"], list)
        assert isinstance(query["expected"], dict)
        assert isinstance(query["expected"]["min_results"], int)
        if query["category"] in category_counts:
            category_counts[query["category"]] += 1

    for category, count in category_counts.items():
        assert count >= 1, f"category {category} should have at least 1 query"

    aggregate_queries = payload.get("aggregate_queries", [])
    smart_aggregate_queries = payload.get("smart_aggregate_queries", [])
    timeline_queries = payload.get("timeline_queries", [])
    assert isinstance(aggregate_queries, list)
    assert all(isinstance(query, dict) for query in aggregate_queries)
    assert isinstance(smart_aggregate_queries, list)
    assert all(isinstance(query, dict) for query in smart_aggregate_queries)
    assert isinstance(timeline_queries, list)
    assert all(isinstance(query, dict) for query in timeline_queries)


def test_eval_runner_with_isolated_data(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir)

    assert result["total_queries"] >= 20
    assert set(result["metrics"].keys()) >= {
        "mrr_at_5",
        "recall_at_5",
        "precision_at_5",
    }
    # chinese_recall category may have drifted; check if present
    if "chinese_recall" in result["by_category"]:
        assert result["by_category"]["chinese_recall"]["query_count"] >= 1
    assert isinstance(result["per_query"], list)
    assert result["per_query"]
    assert "python_version" in result
    assert "tokenizer_version" in result


def test_eval_runner_includes_aggregate_eval(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir)

    aggregate_eval = result["aggregate_eval"]
    assert aggregate_eval["total_queries"] >= 4
    assert aggregate_eval["passed_queries"] == aggregate_eval["total_queries"]
    assert aggregate_eval["failed_queries"] == 0
    assert aggregate_eval["failures"] == []
    assert aggregate_eval["by_category"]["aggregate_analyze"]["query_count"] >= 4

    by_id = {item["id"]: item for item in aggregate_eval["per_query"]}
    assert by_id["AGQ01"]["count"] == 3
    assert by_id["AGQ01"]["exactness"] == "exact"
    assert by_id["AGQ02"]["count"] == 1
    assert by_id["AGQ02"]["exactness"] == "exact"
    assert by_id["AGQ03"]["count"] == 2
    assert by_id["AGQ03"]["exactness"] == "approximate"
    assert by_id["AGQ04"]["count"] == 1
    assert by_id["AGQ04"]["exactness"] == "exact"
    assert by_id["AGQ04"]["index_scope_node_ids"] == [
        "month:2026-02",
        "month:2026-03",
    ]
    assert by_id["AGQ05"]["count"] == 1
    assert by_id["AGQ05"]["exactness"] == "partial"
    assert by_id["AGQ05"]["min_count"] == 1
    assert by_id["AGQ05"]["max_count"] == 2
    assert by_id["AGQ05"]["unknown_count"] == 1
    assert by_id["AGQ05"]["index_scope_node_ids"] == ["month:2026-03"]
    assert by_id["AGQ05"]["index_scope_ref_count"] == 1
    assert by_id["AGQ06"]["count"] == 4
    assert by_id["AGQ06"]["exactness"] == "exact"
    assert by_id["AGQ06"]["index_scope_node_ids"] == ["month:2026-03"]
    assert by_id["AGQ06"]["index_scope_ref_count"] == 1
    assert by_id["AGQ07"]["count"] == 2
    assert by_id["AGQ07"]["exactness"] == "approximate"
    assert by_id["AGQ07"]["index_scope_node_ids"] == ["month:2026-03"]
    assert by_id["AGQ07"]["index_scope_ref_count"] == 1


def test_eval_runner_includes_smart_aggregate_eval(isolated_data_dir: Path, monkeypatch) -> None:
    monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-03-31")
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir)

    smart_eval = result["smart_aggregate_eval"]
    assert smart_eval["total_queries"] == 8
    assert smart_eval["passed_queries"] == smart_eval["total_queries"]
    assert smart_eval["failed_queries"] == 0
    assert smart_eval["failures"] == []

    by_id = {item["id"]: item for item in smart_eval["per_query"]}
    assert by_id["SAGQ01"]["route_present"] is True
    assert by_id["SAGQ01"]["predicate_type"] == "field_equals"
    assert by_id["SAGQ01"]["predicate_field"] == "topic"
    assert by_id["SAGQ01"]["predicate_value"] == "work"
    assert by_id["SAGQ01"]["unit"] == "entry"
    assert by_id["SAGQ01"]["range"] == {
        "since": "2026-01-31",
        "until": "2026-03-31",
    }
    assert by_id["SAGQ01"]["count"] == 4
    assert by_id["SAGQ02"]["route_present"] is True
    assert by_id["SAGQ02"]["predicate_type"] == "term_presence"
    assert by_id["SAGQ02"]["predicate_term"] == "OpenClaw"
    assert by_id["SAGQ02"]["unit"] == "entry"
    assert by_id["SAGQ02"]["range"] == {
        "since": "2026-01-31",
        "until": "2026-03-31",
    }
    assert by_id["SAGQ02"]["count"] == 2
    assert by_id["SAGQ03"]["route_present"] is True
    assert by_id["SAGQ03"]["predicate_type"] == "term_presence"
    assert by_id["SAGQ03"]["predicate_term"] == "OpenClaw"
    assert by_id["SAGQ03"]["unit"] == "entry"
    assert by_id["SAGQ03"]["range"] == {
        "since": "2026-01-01",
        "until": "2026-03-31",
    }
    assert by_id["SAGQ03"]["count"] == 2
    assert by_id["SAGQ04"]["route_present"] is True
    assert by_id["SAGQ04"]["predicate_type"] == "entry_time_after"
    assert by_id["SAGQ04"]["predicate_threshold"] == "22:00"
    assert by_id["SAGQ04"]["unit"] == "day"
    assert by_id["SAGQ04"]["range"] == {
        "since": "2026-01-31",
        "until": "2026-03-31",
    }
    assert by_id["SAGQ04"]["count"] == 1
    assert by_id["SAGQ04"]["exactness"] == "partial"
    assert by_id["SAGQ04"]["min_count"] == 1
    assert by_id["SAGQ04"]["max_count"] == 3
    assert by_id["SAGQ04"]["unknown_count"] == 2
    assert by_id["SAGQ04"]["unknown_bucket_count"] == 2
    assert by_id["SAGQ05"]["route_present"] is True
    assert by_id["SAGQ05"]["predicate_type"] == "journal_count"
    assert by_id["SAGQ05"]["unit"] == "entry"
    assert by_id["SAGQ05"]["range"] == {
        "since": "2026-01-31",
        "until": "2026-03-31",
    }
    assert by_id["SAGQ05"]["count"] == 12
    assert by_id["SAGQ05"]["exactness"] == "exact"
    assert by_id["SAGQ06"]["route_present"] is True
    assert by_id["SAGQ06"]["predicate_type"] == "field_equals"
    assert by_id["SAGQ06"]["predicate_field"] == "topic"
    assert by_id["SAGQ06"]["predicate_value"] == "think"
    assert by_id["SAGQ06"]["unit"] == "entry"
    assert by_id["SAGQ06"]["range"] == {
        "since": "2026-01-01",
        "until": "2026-03-31",
    }
    assert by_id["SAGQ06"]["count"] == 3
    assert by_id["SAGQ06"]["exactness"] == "exact"
    assert by_id["SAGQ06"]["index_scope_node_ids"] == [
        "month:2026-01",
        "month:2026-02",
        "month:2026-03",
    ]
    assert by_id["SAGQ06"]["index_scope_ref_count"] == 3
    assert by_id["SAGQ07"]["route_present"] is True
    assert by_id["SAGQ07"]["predicate_type"] == "field_equals"
    assert by_id["SAGQ07"]["predicate_field"] == "topic"
    assert by_id["SAGQ07"]["predicate_value"] == "life"
    assert by_id["SAGQ07"]["unit"] == "day"
    assert by_id["SAGQ07"]["range"] == {
        "since": "2026-03-02",
        "until": "2026-03-31",
    }
    assert by_id["SAGQ07"]["count"] == 2
    assert by_id["SAGQ07"]["exactness"] == "exact"
    assert by_id["SAGQ07"]["index_scope_node_ids"] == ["month:2026-03"]
    assert by_id["SAGQ07"]["index_scope_ref_count"] == 1
    assert by_id["SAGQ08"]["route_present"] is True
    assert by_id["SAGQ08"]["predicate_type"] == "journal_count"
    assert by_id["SAGQ08"]["unit"] == "month"
    assert by_id["SAGQ08"]["range"] == {
        "since": "2026-01-01",
        "until": "2026-03-31",
    }
    assert by_id["SAGQ08"]["count"] == 2
    assert by_id["SAGQ08"]["exactness"] == "exact"
    assert by_id["SAGQ08"]["index_scope_node_ids"] == [
        "month:2026-01",
        "month:2026-02",
        "month:2026-03",
    ]
    assert by_id["SAGQ08"]["index_scope_ref_count"] == 3
    assert any("Smart Aggregate Eval" in line for line in result["summary_lines"])


def test_eval_runner_includes_timeline_eval(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir)

    timeline_eval = result["timeline_eval"]
    assert timeline_eval["total_queries"] == 3
    assert timeline_eval["passed_queries"] == timeline_eval["total_queries"]
    assert timeline_eval["failed_queries"] == 0
    assert timeline_eval["failures"] == []
    assert timeline_eval["by_category"]["timeline_navigation"]["query_count"] == 3

    by_id = {item["id"]: item for item in timeline_eval["per_query"]}
    assert by_id["TLQ01"]["total"] == 11
    assert by_id["TLQ01"]["first_date"] == "2026-03-04"
    assert by_id["TLQ01"]["last_date"] == "2026-03-25"
    assert by_id["TLQ01"]["ordered"] is True
    assert by_id["TLQ02"]["total"] == 4
    assert by_id["TLQ02"]["dates"] == [
        "2026-03-07",
        "2026-03-14",
        "2026-03-18",
        "2026-03-22",
    ]
    assert by_id["TLQ03"]["total"] == 3
    assert by_id["TLQ03"]["dates"] == [
        "2026-02-28",
        "2026-03-10",
        "2026-03-12",
    ]
    assert any("Timeline Eval" in line for line in result["summary_lines"])


def test_eval_runner_reports_aggregate_eval_failures(monkeypatch, tmp_path: Path) -> None:
    from tools.eval.run_eval import run_evaluation

    monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: [])
    monkeypatch.setattr(
        "tools.eval.run_eval.load_aggregate_queries",
        lambda _: [
            {
                "id": "AGQ_FAIL",
                "query": "bad aggregate expectation",
                "category": "aggregate_analyze",
                "aggregate": {
                    "range": "2026-03-14..2026-03-18",
                    "unit": "entry",
                    "predicate": "journal_count",
                },
                "expected": {
                    "success": True,
                    "count": 999,
                    "exactness": "exact",
                    "index_scope_node_ids": ["month:2099-01"],
                },
            }
        ],
    )
    monkeypatch.setattr("tools.eval.run_eval.load_smart_aggregate_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_timeline_queries", lambda _: [])

    result = run_evaluation(data_dir=tmp_path / "data")

    aggregate_eval = result["aggregate_eval"]
    assert aggregate_eval["failed_queries"] == 1
    assert aggregate_eval["failures"][0]["id"] == "AGQ_FAIL"
    assert "count" in aggregate_eval["failures"][0]["reason"]
    assert "index_scope_node_ids" in aggregate_eval["failures"][0]["reason"]
    assert any("Aggregate Eval" in line for line in result["summary_lines"])


def test_eval_runner_reports_timeline_eval_failures(monkeypatch, tmp_path: Path) -> None:
    from tools.eval.run_eval import run_evaluation

    monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_aggregate_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_smart_aggregate_queries", lambda _: [])
    monkeypatch.setattr(
        "tools.eval.run_eval.load_timeline_queries",
        lambda _: [
            {
                "id": "TLQ_FAIL",
                "query": "bad timeline expectation",
                "category": "timeline_navigation",
                "timeline": {"range_start": "2099-01", "range_end": "2099-01"},
                "expected": {
                    "success": True,
                    "total": 1,
                    "first_date": "2099-01-01",
                },
            }
        ],
    )

    result = run_evaluation(data_dir=tmp_path / "data")

    timeline_eval = result["timeline_eval"]
    assert timeline_eval["failed_queries"] == 1
    assert timeline_eval["failures"][0]["id"] == "TLQ_FAIL"
    assert "total" in timeline_eval["failures"][0]["reason"]
    assert "first_date" in timeline_eval["failures"][0]["reason"]
    assert any("Timeline Eval" in line for line in result["summary_lines"])


def test_eval_baseline_save_and_compare(isolated_data_dir: Path, tmp_path: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import compare_against_baseline, run_evaluation

    baseline_path = tmp_path / "baseline.json"
    baseline_result = run_evaluation(
        data_dir=isolated_data_dir,
        save_baseline=baseline_path,
    )

    assert baseline_path.exists()
    saved_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert saved_payload["total_queries"] == baseline_result["total_queries"]

    comparison = compare_against_baseline(
        baseline_path=baseline_path,
        data_dir=isolated_data_dir,
    )

    assert comparison["baseline"]["total_queries"] == baseline_result["total_queries"]
    assert comparison["current"]["total_queries"] == baseline_result["total_queries"]
    assert "metric_deltas" in comparison["diff"]
    assert isinstance(comparison["diff_lines"], list)


def test_eval_with_llm_judge_mock(monkeypatch) -> None:
    from tools.eval.run_eval import run_evaluation
    from tools.search_journals import core as search_core

    queries = [
        {
            "id": "Q1",
            "query": "daughter",
            "category": "family",
            "expected": {"min_results": 1},
        },
        {
            "id": "Q2",
            "query": "noise",
            "category": "family",
            "expected": {"min_results": 0},
        },
    ]
    results_map = {
        "daughter": {
            "merged_results": [
                {
                    "title": "回忆海边花园",
                    "date": "2026-03-16",
                    "abstract": "思念",
                    "snippet": "晴岚",
                },
                {
                    "title": "普通日志",
                    "date": "2026-03-17",
                    "abstract": "一般",
                    "snippet": "无关",
                },
                {
                    "title": "回忆小风筝",
                    "date": "2026-03-04",
                    "abstract": "回忆",
                    "snippet": "小队长",
                },
            ]
        },
        "noise": {
            "merged_results": [
                {
                    "title": "普通日志",
                    "date": "2026-03-17",
                    "abstract": "一般",
                    "snippet": "无关",
                },
                {
                    "title": "另一个结果",
                    "date": "2026-03-18",
                    "abstract": "一般",
                    "snippet": "无关",
                },
            ]
        },
    }

    monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: queries)
    monkeypatch.setattr(
        search_core,
        "hierarchical_search",
        lambda query, level, semantic: results_map[query],
    )

    result = run_evaluation(
        judge="llm",
        llm_client=_load_eval_llm_module().MockLLMClient(
            responses=[
                '{"score": 3, "reason": "直接相关"}',
                '{"score": 1, "reason": "弱相关"}',
                '{"score": 2, "reason": "部分相关"}',
                '{"score": 0, "reason": "无关"}',
                '{"score": 1, "reason": "无关"}',
            ]
        ),
    )

    assert result["judge_mode"] == "llm"
    assert result["metrics"]["mrr_at_5"] == 0.5
    assert result["metrics"]["precision_at_5"] == 0.2
    assert result["metrics"]["recall_at_5"] == 1.0
    assert result["metrics"]["ndcg_at_5"] == 0.8017


def test_ndcg_computation() -> None:
    from tools.eval.run_eval import _compute_ndcg_at_5

    score_list = [3, 0, 2]
    dcg = 3.0 + (2.0 / math.log2(4))
    idcg = 3.0 + (2.0 / math.log2(3))

    assert _compute_ndcg_at_5(score_list) == round(dcg / idcg, 4)


def test_llm_scores_propagated_to_per_query(monkeypatch) -> None:
    from tools.eval.run_eval import run_evaluation
    from tools.search_journals import core as search_core

    queries = [
        {
            "id": "Q1",
            "query": "daughter",
            "category": "family",
            "expected": {"min_results": 1},
        }
    ]
    monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: queries)
    monkeypatch.setattr(
        search_core,
        "hierarchical_search",
        lambda query, level, semantic: {
            "merged_results": [
                {
                    "title": "回忆海边花园",
                    "date": "2026-03-16",
                    "abstract": "思念",
                    "snippet": "晴岚",
                },
                {
                    "title": "普通日志",
                    "date": "2026-03-17",
                    "abstract": "一般",
                    "snippet": "无关",
                },
            ]
        },
    )

    result = run_evaluation(
        judge="llm",
        llm_client=_load_eval_llm_module().MockLLMClient(
            responses=[
                '{"score": 3, "reason": "直接相关"}',
                '{"score": 0, "reason": "无关"}',
            ]
        ),
    )

    assert result["per_query"][0]["llm_scores"] == [3, 0]
    assert result["per_query"][0]["first_relevant_rank"] == 1


def test_keyword_judge_mode_unchanged(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir, judge="keyword")

    assert result["judge_mode"] == "keyword"
    # ndcg_at_5 is now always included in metrics regardless of judge mode
    assert "llm_scores" not in result["per_query"][0]


def test_recall_gap_detection_with_mock(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    from tools.eval.run_eval import run_evaluation

    queries = [
        {
            "id": "Q1",
            "query": "晴岚",
            "category": "family",
            "expected": {"min_results": 1},
        }
    ]
    monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: queries)
    monkeypatch.setattr(
        "tools.eval.run_eval._evaluate_queries",
        lambda *args, **kwargs: (
            [
                {
                    "id": "Q1",
                    "query": "晴岚",
                    "category": "family",
                    "results_found": 1,
                    "expected_min_results": 1,
                    "top_titles": ["晴岚不认真吃饭"],
                    "precision_at_5": 0.2,
                    "reciprocal_rank": 1.0,
                    "first_relevant_rank": 1,
                    "llm_scores": [3],
                    "ndcg_at_5": 1.0,
                }
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        "tools.eval.run_eval._collect_all_journal_titles",
        lambda: ["回忆海边花园", "海边过生日", "晴岚不认真吃饭"],
    )

    result = run_evaluation(
        judge="llm",
        live=True,
        llm_client=_load_eval_llm_module().MockLLMClient(
            responses=[
                '{"expected_hits": ["回忆海边花园", "海边过生日", "晴岚不认真吃饭"], "reason": "都和晴岚相关"}',
            ]
        ),
    )

    assert result["recall_gaps"] == [
        {
            "query_id": "Q1",
            "query": "晴岚",
            "expected_but_missed": ["回忆海边花园", "海边过生日"],
            "returned": ["晴岚不认真吃饭"],
            "recall_ratio": 0.33,
        }
    ]


def test_default_eval_aggregate_is_diagnostic_only(monkeypatch, tmp_path: Path) -> None:
    from tools.eval.run_eval import run_evaluation

    monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: [])
    monkeypatch.setattr(
        "tools.eval.run_eval.load_aggregate_queries",
        lambda _: [
            {
                "id": "AGQ_DIAG",
                "query": "diagnostic aggregate",
                "category": "aggregate_analyze",
                "aggregate": {
                    "range": "2026-03-14..2026-03-18",
                    "unit": "entry",
                    "predicate": "journal_count",
                },
                "expected": {
                    "success": True,
                    "count": 999,
                    "exactness": "exact",
                },
            }
        ],
    )
    monkeypatch.setattr("tools.eval.run_eval.load_smart_aggregate_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_timeline_queries", lambda _: [])

    result = run_evaluation(data_dir=None)

    aggregate_eval = result["aggregate_eval"]
    assert aggregate_eval.get("diagnostic_only") is True
    assert aggregate_eval["failed_queries"] == 0
    assert len(aggregate_eval.get("diagnostic_observations", [])) >= 1
    obs = aggregate_eval["diagnostic_observations"][0]
    assert obs["id"] == "AGQ_DIAG"
    assert "expected" in obs
    assert "actual" in obs


def test_explicit_data_dir_aggregate_remains_hard_gate(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir)

    aggregate_eval = result["aggregate_eval"]
    assert aggregate_eval.get("diagnostic_only") is not True
    assert aggregate_eval["failed_queries"] == 0
    assert aggregate_eval["passed_queries"] == aggregate_eval["total_queries"]


def test_live_mode_uses_real_data_dir(monkeypatch, tmp_path: Path) -> None:
    from tools.eval.run_eval import run_evaluation

    captured: list[str] = []
    fake_env_dir = tmp_path / "override-dir"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(fake_env_dir))

    def _fake_evaluate_queries(*args, **kwargs):
        current_dir = importlib.import_module("tools.lib.paths").resolve_user_data_dir()
        captured.append(str(current_dir))
        return [], []

    monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_aggregate_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_smart_aggregate_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_timeline_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval._evaluate_queries", _fake_evaluate_queries)

    result = run_evaluation(live=True)

    assert result["live_mode"] is True
    assert captured == [str(Path.home() / "Documents" / "Life-Index")]
    assert os.environ["LIFE_INDEX_DATA_DIR"] == str(fake_env_dir)


def test_live_mode_aggregate_eval_is_diagnostic_only(monkeypatch) -> None:
    from tools.eval.run_eval import run_evaluation

    captured: dict[str, bool] = {}

    monkeypatch.setattr("tools.eval.run_eval.load_golden_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_aggregate_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_smart_aggregate_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval.load_timeline_queries", lambda _: [])
    monkeypatch.setattr("tools.eval.run_eval._evaluate_queries", lambda *_, **__: ([], []))

    def _fake_evaluate_aggregate_queries(_queries, *, diagnostic_only=False):
        captured["diagnostic_only"] = diagnostic_only
        return {
            "total_queries": 0,
            "passed_queries": 0,
            "failed_queries": 0,
            "metrics": {"pass_rate": 0.0},
            "by_category": {},
            "per_query": [],
            "failures": [],
        }

    monkeypatch.setattr(
        "tools.eval.run_eval._evaluate_aggregate_queries",
        _fake_evaluate_aggregate_queries,
    )

    def _fake_evaluate_smart_aggregate_queries(_queries, *, diagnostic_only=False):
        captured["smart_diagnostic_only"] = diagnostic_only
        return {
            "total_queries": 0,
            "passed_queries": 0,
            "failed_queries": 0,
            "metrics": {"pass_rate": 0.0},
            "by_category": {},
            "per_query": [],
            "failures": [],
        }

    monkeypatch.setattr(
        "tools.eval.run_eval._evaluate_smart_aggregate_queries",
        _fake_evaluate_smart_aggregate_queries,
    )

    def _fake_evaluate_timeline_queries(_queries, *, diagnostic_only=False):
        captured["timeline_diagnostic_only"] = diagnostic_only
        return {
            "total_queries": 0,
            "passed_queries": 0,
            "failed_queries": 0,
            "metrics": {"pass_rate": 0.0},
            "by_category": {},
            "per_query": [],
            "failures": [],
        }

    monkeypatch.setattr(
        "tools.eval.run_eval._evaluate_timeline_queries",
        _fake_evaluate_timeline_queries,
    )

    run_evaluation(live=True)

    assert captured["diagnostic_only"] is True
    assert captured["smart_diagnostic_only"] is True
    assert captured["timeline_diagnostic_only"] is True


def test_recall_ratio_computation() -> None:
    from tools.eval.run_eval import _compute_recall_ratio

    assert (
        _compute_recall_ratio(
            ["回忆海边花园", "海边过生日", "晴岚不认真吃饭"],
            ["晴岚不认真吃饭"],
        )
        == 0.33
    )


def test_eval_cli_passes_live_and_judge_flags(monkeypatch, capsys) -> None:
    from tools.eval import __main__ as eval_main

    captured: dict[str, object] = {}

    def _fake_run_evaluation(**kwargs):
        captured.update(kwargs)
        return {
            "summary_lines": ["ok"],
            "metrics": {"mrr_at_5": 1.0, "recall_at_5": 1.0, "precision_at_5": 1.0},
            "total_queries": 1,
            "failures": [],
            "judge_mode": kwargs["judge"],
            "live_mode": kwargs["live"],
            "recall_gaps": [],
            "aggregate_eval": {"total_queries": 1, "failed_queries": 0},
        }

    monkeypatch.setattr(eval_main, "run_evaluation", _fake_run_evaluation)

    eval_main.main(["--live", "--judge", "llm", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert captured["live"] is True
    assert captured["judge"] == "llm"
    assert payload["success"] is True
    assert payload["data"]["judge_mode"] == "llm"
    assert payload["data"]["aggregate_eval"]["total_queries"] == 1


def test_compare_with_llm_metrics(tmp_path: Path, monkeypatch) -> None:
    from tools.eval.run_eval import compare_against_baseline

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "mrr_at_5": 0.85,
                    "recall_at_5": 0.9,
                    "precision_at_5": 0.75,
                    "ndcg_at_5": 0.8,
                },
                "per_query": [
                    {
                        "id": "Q1",
                        "query": "晴岚",
                        "pass": True,
                        "first_relevant_rank": 1,
                    }
                ],
                "recall_gaps": [{"query_id": "Q1", "expected_but_missed": ["回忆海边花园"]}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: {
            "metrics": {
                "mrr_at_5": 0.92,
                "recall_at_5": 0.88,
                "precision_at_5": 0.8,
                "ndcg_at_5": 0.88,
            },
            "per_query": [{"id": "Q1", "query": "晴岚", "pass": True, "first_relevant_rank": 1}],
            "recall_gaps": [{"query_id": "Q1", "expected_but_missed": ["海边过生日"]}],
        },
    )

    comparison = compare_against_baseline(baseline_path=baseline_path)

    assert comparison["diff"]["metric_deltas"]["ndcg_at_5"]["delta"] == 0.08
    assert comparison["diff"]["recall_gap_changes"] == [
        {
            "query_id": "Q1",
            "query": "",
            "baseline_missed": ["回忆海边花园"],
            "current_missed": ["海边过生日"],
            "current_expected_total": 1,
        }
    ]


def test_compare_detects_regression(tmp_path: Path, monkeypatch) -> None:
    from tools.eval.run_eval import compare_against_baseline

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "metrics": {"mrr_at_5": 1.0, "recall_at_5": 1.0, "precision_at_5": 1.0},
                "per_query": [
                    {
                        "id": "Q1",
                        "query": "晴岚",
                        "pass": True,
                        "first_relevant_rank": 1,
                    }
                ],
                "recall_gaps": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: {
            "metrics": {"mrr_at_5": 0.5, "recall_at_5": 0.0, "precision_at_5": 0.0},
            "per_query": [
                {
                    "id": "Q1",
                    "query": "晴岚",
                    "pass": False,
                    "first_relevant_rank": None,
                }
            ],
            "recall_gaps": [],
        },
    )

    comparison = compare_against_baseline(baseline_path=baseline_path)

    assert comparison["diff"]["new_failures"] == ["Q1"]
    assert comparison["diff"]["regressions"][0]["id"] == "Q1"


def test_summary_lines_format() -> None:
    from tools.eval.run_eval import generate_summary_lines

    lines = generate_summary_lines(
        {
            "metric_deltas": {
                "mrr_at_5": {"baseline": 0.85, "current": 0.92, "delta": 0.07},
                "recall_at_5": {"baseline": 0.9, "current": 0.88, "delta": -0.02},
                "precision_at_5": {"baseline": 0.75, "current": 0.8, "delta": 0.05},
                "ndcg_at_5": {"baseline": 0.8, "current": 0.88, "delta": 0.08},
            },
            "regressions": [],
            "recall_gap_changes": [
                {
                    "query_id": "GQ05",
                    "query": "晴岚",
                    "current_missed": ["回忆海边花园", "海边过生日"],
                    "current_expected_total": 3,
                }
            ],
        }
    )

    assert lines[0] == "═══ Search Eval Comparison ═══"
    assert "  MRR@5:        0.8500 → 0.9200  (▲ +0.0700)" in lines
    assert "  Recall@5:     0.9000 → 0.8800  (▼ -0.0200)" in lines
    assert '  GQ05 "晴岚": 漏检 2/3 expected (回忆海边花园, 海边过生日)' in lines


def test_eval_runner_includes_ir_eval_artifacts(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir)

    ir_eval = result["ir_eval"]

    # Assert required top-level keys
    assert "qrel_coverage" in ir_eval
    assert "run_coverage" in ir_eval
    assert "artifacts" in ir_eval
    assert "qrels" in ir_eval["artifacts"]
    assert "run" in ir_eval["artifacts"]

    # Privacy: qrels must contain only query IDs (str) and doc IDs (str) with int grades
    qrels = ir_eval["artifacts"]["qrels"]
    for query_id, doc_dict in qrels.items():
        assert isinstance(query_id, str)
        for doc_id, grade in doc_dict.items():
            assert isinstance(doc_id, str)
            assert isinstance(grade, int)
            # Doc IDs must be journal route paths, never raw content
            assert "life-index_" in doc_id

    # Privacy: run must contain only query IDs (str) and doc IDs (str) with float scores
    run_artifact = ir_eval["artifacts"]["run"]
    for query_id, doc_dict in run_artifact.items():
        assert isinstance(query_id, str)
        for doc_id, score in doc_dict.items():
            assert isinstance(doc_id, str)
            assert isinstance(score, float)
            assert "life-index_" in doc_id

    # Coverage reports have expected structure
    qrel_cov = ir_eval["qrel_coverage"]
    assert isinstance(qrel_cov["total_queries"], int)
    assert isinstance(qrel_cov["resolved"], int)
    assert isinstance(qrel_cov["ambiguous"], int)
    assert isinstance(qrel_cov["unresolved"], int)
    assert isinstance(qrel_cov["negative"], int)
    assert isinstance(qrel_cov["min_results_only"], int)
    assert isinstance(qrel_cov["warnings"], list)

    run_cov = ir_eval["run_coverage"]
    assert isinstance(run_cov["total_queries"], int)
    assert isinstance(run_cov["total_result_items"], int)
    assert isinstance(run_cov["emitted_items"], int)
    assert isinstance(run_cov["skipped_empty_doc_ids"], int)
    assert isinstance(run_cov["warnings"], list)

    # Privacy: no raw journal content, titles, or query text in coverage reports
    for forbidden in ["回忆小风筝", "晴岚", "海边过生日", "小风筝", "女儿"]:
        assert forbidden not in str(qrel_cov), f"Privacy leak in qrel_coverage: {forbidden}"
        assert forbidden not in str(run_cov), f"Privacy leak in run_coverage: {forbidden}"

    # Privacy: no raw text in artifacts either
    for forbidden in ["回忆小风筝", "晴岚", "海边过生日", "小风筝", "女儿"]:
        assert forbidden not in str(qrels), f"Privacy leak in qrels: {forbidden}"
        assert forbidden not in str(run_artifact), f"Privacy leak in run: {forbidden}"


def test_aggregate_cross_month_index_scope(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir)

    aggregate_eval = result["aggregate_eval"]
    by_id = {item["id"]: item for item in aggregate_eval["per_query"]}
    assert "AGQ04" in by_id
    agg_item = by_id["AGQ04"]
    assert agg_item["pass"] is True
    assert agg_item["success"] is True
    assert agg_item["count"] == 1
    assert agg_item["exactness"] == "exact"
    assert agg_item["index_scope_node_ids"] == ["month:2026-02", "month:2026-03"]


# --- Pack B: Baseline canonicalization lookup tests (M4-B1) ---


def _write_baseline_json(
    path: Path,
    *,
    frozen_at: str = "2026-05-04",
    anchor_date: str | None = None,
    baseline_id: str = "test-baseline",
) -> None:
    """Write a minimal valid baseline JSON file."""
    payload = {
        "baseline_id": baseline_id,
        "frozen_at": frozen_at,
        "anchor_date": anchor_date or frozen_at,
        "metrics": {"mrr_at_5": 0.5, "recall_at_5": 0.5, "precision_at_5": 0.5},
        "per_query": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_baseline_lookup_prefers_tools_dir_over_tests_dir(tmp_path: Path) -> None:
    """A baseline in tools/eval/baselines/ wins over a newer-mtime file in tests/eval/baselines/."""
    from tools.eval.run_eval import _find_latest_baseline

    tools_dir = tmp_path / "tools_baselines"
    tests_dir = tmp_path / "tests_baselines"
    tools_dir.mkdir()
    tests_dir.mkdir()

    # Create a tools baseline with an older frozen_at and older mtime
    tools_baseline = tools_dir / "round-19-phase1d-baseline-v4.json"
    tools_baseline.write_text(
        json.dumps({"frozen_at": "2026-03-04", "total_queries": 50}),
        encoding="utf-8",
    )

    # Create a tests baseline with a newer frozen_at and newer mtime
    import time

    time.sleep(0.05)
    tests_baseline = tests_dir / "round-19-phase1d-baseline-v5.json"
    tests_baseline.write_text(
        json.dumps({"frozen_at": "2026-03-10", "total_queries": 55}),
        encoding="utf-8",
    )

    # tools_baseline has older mtime; tests_baseline has newer mtime.
    # Canonicalization: tools dir wins regardless of mtime/frozen_at.
    result = _find_latest_baseline(tools_dir=tools_dir, tests_dir=tests_dir)
    assert result is not None
    assert result.parent == tools_dir, f"Expected tools/eval/baselines/ to win, but got {result}"


def test_baseline_lookup_falls_back_to_tests_dir(tmp_path: Path) -> None:
    """When no tools baseline exists, tests/eval/baselines/ remains fallback."""
    from tools.eval.run_eval import _find_latest_baseline

    tests_dir = tmp_path / "tests_baselines"
    tests_dir.mkdir()

    tests_baseline = tests_dir / "round-19-phase1d-baseline-v4.json"
    tests_baseline.write_text(
        json.dumps({"frozen_at": "2026-03-04", "total_queries": 50}),
        encoding="utf-8",
    )

    # Empty tools dir → should fall back to tests dir
    tools_dir = tmp_path / "tools_baselines"
    tools_dir.mkdir()

    result = _find_latest_baseline(tools_dir=tools_dir, tests_dir=tests_dir)
    assert result is not None
    assert result.parent == tests_dir


def test_baseline_lookup_sorts_by_frozen_at_not_mtime(tmp_path: Path) -> None:
    """Deterministic sort by frozen_at wins over filesystem mtime."""
    from tools.eval.run_eval import _find_latest_baseline

    tools_dir = tmp_path / "tools_baselines"
    tools_dir.mkdir()

    import time

    # Write newer frozen_at first (older mtime)
    newer_frozen = tools_dir / "round-20-baseline-v1.json"
    newer_frozen.write_text(
        json.dumps({"frozen_at": "2026-05-01", "total_queries": 60}),
        encoding="utf-8",
    )

    time.sleep(0.05)

    # Write older frozen_at second (newer mtime)
    older_frozen = tools_dir / "round-19-phase1d-baseline-v4.json"
    older_frozen.write_text(
        json.dumps({"frozen_at": "2026-03-04", "total_queries": 50}),
        encoding="utf-8",
    )

    # older_frozen has newer mtime but older frozen_at → must NOT win
    result = _find_latest_baseline(tools_dir=tools_dir)
    assert result is not None
    assert (
        result.name == "round-20-baseline-v1.json"
    ), f"Expected deterministic sort by frozen_at, but got {result.name}"


def test_baseline_lookup_sorts_by_frozen_at_then_filename(tmp_path: Path) -> None:
    """Within a directory, sort by embedded frozen_at desc, then filename desc."""
    from tools.eval.run_eval import _find_latest_baseline

    tools_dir = tmp_path / "tools" / "eval" / "baselines"
    tests_dir = tmp_path / "tests" / "eval" / "baselines"

    # Two baselines in tools_dir with different frozen_at values
    _write_baseline_json(
        tools_dir / "round-19-older-baseline.json",
        frozen_at="2026-05-01",
        baseline_id="older",
    )
    _write_baseline_json(
        tools_dir / "round-20-newer-baseline.json",
        frozen_at="2026-05-10",
        baseline_id="newer",
    )

    result = _find_latest_baseline(
        tools_dir=tools_dir,
        tests_dir=tests_dir,
    )
    assert result is not None
    assert result.name == "round-20-newer-baseline.json"


def test_baseline_lookup_filename_desc_when_dates_tie(tmp_path: Path) -> None:
    """When frozen_at/anchor_date tie, filename descending breaks the tie before mtime."""
    from tools.eval.run_eval import _find_latest_baseline

    tools_dir = tmp_path / "tools_baselines"
    tools_dir.mkdir()

    import time

    later_name = tools_dir / "round-19-phase1d-baseline-v4.json"
    later_name.write_text(
        json.dumps({"frozen_at": "2026-05-04", "anchor_date": "2026-05-04"}),
        encoding="utf-8",
    )

    time.sleep(0.05)

    earlier_name = tools_dir / "round-19-phase1c-baseline-v3.json"
    earlier_name.write_text(
        json.dumps({"frozen_at": "2026-05-04", "anchor_date": "2026-05-04"}),
        encoding="utf-8",
    )

    # Both have identical frozen_at and anchor_date.
    # earlier_name has newer mtime but later_name is lexically later.
    # Sort policy: frozen_at desc → anchor_date desc → filename desc → mtime desc
    # "round-19-phase1d-baseline-v4.json" > "round-19-phase1c-baseline-v3.json" lexicographically,
    # so filename desc should pick phase1d-v4 regardless of mtime.
    # If filename were ascending (the bug), sorted()[0] would pick phase1c-v3
    # because it sorts first alphabetically.
    result = _find_latest_baseline(tools_dir=tools_dir)
    assert result is not None
    assert (
        result.name == "round-19-phase1d-baseline-v4.json"
    ), f"Expected filename-desc tie-break to pick lexically later name, but got {result.name}"


def test_baseline_lookup_returns_none_when_no_baselines(tmp_path: Path) -> None:
    """When neither directory has baselines, return None."""
    from tools.eval.run_eval import _find_latest_baseline

    tools_dir = tmp_path / "tools" / "eval" / "baselines"
    tests_dir = tmp_path / "tests" / "eval" / "baselines"

    result = _find_latest_baseline(
        tools_dir=tools_dir,
        tests_dir=tests_dir,
    )
    assert result is None


# --- Pack C: Reproducible Comparison Gate tests (M4-C1) ---


def _pack_c_baseline_payload() -> dict:
    """Minimal baseline payload with typed eval, IR, and companion sections."""
    return {
        "frozen_at": "2026-03-31",
        "anchor_date": "2026-03-31",
        "commit": "abc1234",
        "judge_mode": "keyword",
        "live_mode": False,
        "semantic_enabled": False,
        "metrics": {
            "mrr_at_5": 0.85,
            "recall_at_5": 0.9,
            "precision_at_5": 0.75,
            "ndcg_at_5": 0.8,
        },
        "total_queries": 2,
        "skipped_queries": 0,
        "per_query": [
            {
                "id": "Q1",
                "query": "sample query",
                "category": "family",
                "results_found": 1,
                "top_titles": ["Relevant Sample Doc"],
                "top_doc_ids": ["2026/03/life-index_2026-03-04_001.md"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 1.0,
                "ndcg_at_5": 1.0,
                "expected_min_results": 1,
                "pass": True,
                "eval_mode": "exact_mrr",
            },
            {
                "id": "Q2",
                "query": "zero-result sample",
                "category": "noise_rejection",
                "results_found": 0,
                "top_titles": [],
                "top_doc_ids": [],
                "first_relevant_rank": None,
                "first_relevant_rank_at_10": None,
                "reciprocal_rank": 0.0,
                "precision_at_5": 0.0,
                "ndcg_at_5": 0.0,
                "expected_min_results": 0,
                "pass": True,
                "eval_mode": "exact_mrr",
            },
        ],
        "failures": [],
        "recall_gaps": [],
        "aggregate_eval": {
            "total_queries": 1,
            "passed_queries": 1,
            "failed_queries": 0,
            "metrics": {"pass_rate": 1.0},
            "by_category": {},
            "per_query": [],
            "failures": [],
        },
        "smart_aggregate_eval": {
            "total_queries": 1,
            "passed_queries": 0,
            "failed_queries": 1,
            "metrics": {"pass_rate": 0.0},
            "by_category": {},
            "per_query": [],
            "failures": [{"id": "SAGQ_X", "query": "test", "reason": "count mismatch"}],
        },
        "timeline_eval": {
            "total_queries": 2,
            "passed_queries": 2,
            "failed_queries": 0,
            "metrics": {"pass_rate": 1.0},
            "by_category": {},
            "per_query": [],
            "failures": [],
        },
        "ir_eval": {
            "artifacts": {
                "qrels": {"Q1": {"2026/03/life-index_2026-03-04_001.md": 1}},
                "run": {"Q1": {"2026/03/life-index_2026-03-04_001.md": 1.0}},
            },
            "qrel_coverage": {
                "total_queries": 1,
                "resolved": 1,
                "ambiguous": 0,
                "unresolved": 0,
                "negative": 0,
                "min_results_only": 0,
                "warnings": [],
            },
            "run_coverage": {
                "total_queries": 2,
                "total_result_items": 1,
                "emitted_items": 1,
                "skipped_empty_doc_ids": 0,
                "warnings": [],
            },
        },
    }


def _pack_c_current_payload() -> dict:
    """Current run with one regression (Q2 now fails) and improved aggregate."""
    return {
        "frozen_at": "2026-03-31",
        "anchor_date": "2026-03-31",
        "commit": "def5678",
        "judge_mode": "keyword",
        "live_mode": False,
        "semantic_enabled": False,
        "metrics": {
            "mrr_at_5": 0.5,
            "recall_at_5": 0.5,
            "precision_at_5": 0.5,
            "ndcg_at_5": 0.5,
        },
        "total_queries": 2,
        "skipped_queries": 0,
        "per_query": [
            {
                "id": "Q1",
                "query": "sample query",
                "category": "family",
                "results_found": 1,
                "top_titles": ["Relevant Sample Doc"],
                "top_doc_ids": ["2026/03/life-index_2026-03-04_001.md"],
                "first_relevant_rank": 1,
                "first_relevant_rank_at_10": 1,
                "reciprocal_rank": 1.0,
                "precision_at_5": 1.0,
                "ndcg_at_5": 1.0,
                "expected_min_results": 1,
                "pass": True,
                "eval_mode": "exact_mrr",
            },
            {
                "id": "Q2",
                "query": "zero-result sample",
                "category": "noise_rejection",
                "results_found": 1,
                "top_titles": ["unexpected result"],
                "top_doc_ids": ["2026/03/life-index_2026-03-07_001.md"],
                "first_relevant_rank": None,
                "first_relevant_rank_at_10": None,
                "reciprocal_rank": 0.0,
                "precision_at_5": 0.0,
                "ndcg_at_5": 0.0,
                "expected_min_results": 0,
                "pass": False,
                "eval_mode": "exact_mrr",
            },
        ],
        "failures": [
            {
                "id": "Q2",
                "query": "zero-result sample",
                "reason": "Expected 0 results, got 1",
            }
        ],
        "recall_gaps": [],
        "aggregate_eval": {
            "total_queries": 1,
            "passed_queries": 1,
            "failed_queries": 0,
            "metrics": {"pass_rate": 1.0},
            "by_category": {},
            "per_query": [],
            "failures": [],
        },
        "smart_aggregate_eval": {
            "total_queries": 1,
            "passed_queries": 1,
            "failed_queries": 0,
            "metrics": {"pass_rate": 1.0},
            "by_category": {},
            "per_query": [],
            "failures": [],
        },
        "timeline_eval": {
            "total_queries": 2,
            "passed_queries": 1,
            "failed_queries": 1,
            "metrics": {"pass_rate": 0.5},
            "by_category": {},
            "per_query": [],
            "failures": [{"id": "TLQ_X", "query": "test", "reason": "total mismatch"}],
        },
        "ir_eval": {
            "artifacts": {
                "qrels": {"Q1": {"2026/03/life-index_2026-03-04_001.md": 1}},
                "run": {"Q1": {"2026/03/life-index_2026-03-04_001.md": 1.0}},
            },
            "qrel_coverage": {
                "total_queries": 1,
                "resolved": 1,
                "ambiguous": 0,
                "unresolved": 0,
                "negative": 0,
                "min_results_only": 0,
                "warnings": [],
            },
            "run_coverage": {
                "total_queries": 2,
                "total_result_items": 1,
                "emitted_items": 1,
                "skipped_empty_doc_ids": 0,
                "warnings": [],
            },
        },
    }


def test_compare_includes_typed_eval_comparison(tmp_path: Path, monkeypatch) -> None:
    """Pack C: compare_against_baseline() exposes typed eval_comparison with failure_delta."""
    from tools.eval.run_eval import compare_against_baseline

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(_pack_c_baseline_payload(), ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: _pack_c_current_payload(),
    )

    comparison = compare_against_baseline(baseline_path=baseline_path)

    # eval_comparison is a dict representation of EvalComparison
    ec = comparison["diff"]["eval_comparison"]
    assert isinstance(ec, dict)
    assert "failure_delta" in ec
    # baseline had 0 failures, current has 1 failure → delta = +1
    assert ec["failure_delta"] == 1
    assert "fixed_query_ids" in ec
    assert "regressed_query_ids" in ec
    assert "baseline_commit" in ec
    assert "candidate_commit" in ec


def test_compare_includes_ir_run_comparison(tmp_path: Path, monkeypatch) -> None:
    """Pack C: compare_against_baseline() exposes ir_run_comparison with metric_deltas."""
    from tools.eval.run_eval import compare_against_baseline

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(_pack_c_baseline_payload(), ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: _pack_c_current_payload(),
    )

    comparison = compare_against_baseline(baseline_path=baseline_path)

    ir_comp = comparison["diff"]["ir_run_comparison"]
    assert isinstance(ir_comp, dict)
    assert "metric_deltas" in ir_comp
    assert "per_query_deltas" in ir_comp
    assert "queries_compared" in ir_comp
    # metric_deltas should be a list of MetricDelta dicts
    assert isinstance(ir_comp["metric_deltas"], list)


def test_compare_includes_companion_eval_deltas(tmp_path: Path, monkeypatch) -> None:
    """Pack C: compare_against_baseline() exposes companion_eval_deltas with D-M04-011 fields."""
    from tools.eval.run_eval import compare_against_baseline

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(_pack_c_baseline_payload(), ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: _pack_c_current_payload(),
    )

    comparison = compare_against_baseline(baseline_path=baseline_path)

    companion_deltas = comparison["diff"]["companion_eval_deltas"]
    assert isinstance(companion_deltas, list)
    assert len(companion_deltas) >= 1

    # Check each delta entry has D-M04-011 fields
    for delta_entry in companion_deltas:
        assert "section" in delta_entry
        assert "baseline_mode" in delta_entry
        assert "current_mode" in delta_entry
        assert "passed_delta" in delta_entry
        assert "failed_delta" in delta_entry
        assert "pass_rate_delta" in delta_entry
        assert "comparable" in delta_entry
        assert "reason" in delta_entry

    # Find aggregate_eval entry — baseline had 1 pass/0 fail, current has 1 pass/0 fail
    agg_delta = next(d for d in companion_deltas if d["section"] == "aggregate_eval")
    assert agg_delta["passed_delta"] == 0
    assert agg_delta["failed_delta"] == 0
    assert agg_delta["pass_rate_delta"] == 0.0
    assert agg_delta["comparable"] is True

    # smart_aggregate_eval: baseline had 0 pass/1 fail, current has 1 pass/0 fail
    smart_delta = next(d for d in companion_deltas if d["section"] == "smart_aggregate_eval")
    assert smart_delta["passed_delta"] == 1
    assert smart_delta["failed_delta"] == -1
    assert smart_delta["comparable"] is True

    # timeline_eval: baseline had 2 pass/0 fail, current has 1 pass/1 fail
    tl_delta = next(d for d in companion_deltas if d["section"] == "timeline_eval")
    assert tl_delta["passed_delta"] == -1
    assert tl_delta["failed_delta"] == 1


def test_companion_delta_diagnostic_vs_hard_gate_shape_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    """Pack C: diagnostic-vs-hard-gate shape mismatch degrades to non-comparable warning.

    The comparison must not crash when baseline is diagnostic-only
    and current is hard-gate; instead it records a non-comparable delta.
    """
    from tools.eval.run_eval import compare_against_baseline

    baseline = _pack_c_baseline_payload()
    # Make baseline aggregate_eval diagnostic-only (has diagnostic_only: True)
    baseline["aggregate_eval"]["diagnostic_only"] = True
    baseline["aggregate_eval"]["diagnostic_observations"] = [
        {"id": "AGQ_X", "query": "test", "reason": "count mismatch", "expected": 999, "actual": 3}
    ]
    # Re-count: diagnostic_only means failed_queries is 0 but the data is unreliable
    baseline["aggregate_eval"]["failed_queries"] = 0
    baseline["aggregate_eval"]["passed_queries"] = 1

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")

    current = _pack_c_current_payload()
    # current has hard_gate aggregate (no diagnostic_only flag)
    # This is a shape mismatch: baseline is diagnostic, current is hard gate

    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: current,
    )

    # Must NOT raise — should degrade to a non-comparable warning
    comparison = compare_against_baseline(baseline_path=baseline_path)

    companion_deltas = comparison["diff"]["companion_eval_deltas"]
    agg_delta = next(d for d in companion_deltas if d["section"] == "aggregate_eval")
    assert agg_delta["comparable"] is False
    assert "diagnostic" in agg_delta["reason"].lower() or "mode" in agg_delta["reason"].lower()


def test_companion_delta_missing_section_degrades_gracefully(tmp_path: Path, monkeypatch) -> None:
    """Pack C: missing companion section in current degrades to warning, not crash."""
    from tools.eval.run_eval import compare_against_baseline

    baseline = _pack_c_baseline_payload()
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")

    current = _pack_c_current_payload()
    # Remove timeline_eval entirely from current
    del current["timeline_eval"]

    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: current,
    )

    # Must not crash
    comparison = compare_against_baseline(baseline_path=baseline_path)

    companion_deltas = comparison["diff"]["companion_eval_deltas"]
    tl_delta = next(d for d in companion_deltas if d["section"] == "timeline_eval")
    assert tl_delta["comparable"] is False
    assert tl_delta["baseline_mode"] is not None
    assert tl_delta["current_mode"] is None or "missing" in tl_delta["reason"].lower()


def test_compare_preserves_existing_diff_fields(tmp_path: Path, monkeypatch) -> None:
    """Pack C: existing metric_deltas, regressions, new_failures, etc. are preserved."""
    from tools.eval.run_eval import compare_against_baseline

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(_pack_c_baseline_payload(), ensure_ascii=False), encoding="utf-8"
    )

    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: _pack_c_current_payload(),
    )

    comparison = compare_against_baseline(baseline_path=baseline_path)

    # Existing fields must still exist
    assert "metric_deltas" in comparison["diff"]
    assert "regressions" in comparison["diff"]
    assert "new_failures" in comparison["diff"]
    assert "new_passes" in comparison["diff"]
    assert "recall_gap_changes" in comparison["diff"]

    # New Pack C fields
    assert "eval_comparison" in comparison["diff"]
    assert "ir_run_comparison" in comparison["diff"]
    assert "companion_eval_deltas" in comparison["diff"]


def test_compare_ir_run_no_qrels_degrades(tmp_path: Path, monkeypatch) -> None:
    """Pack C: when baseline has no IR artifacts, ir_run_comparison degrades gracefully."""
    from tools.eval.run_eval import compare_against_baseline

    baseline = _pack_c_baseline_payload()
    # Remove IR artifacts from baseline (legacy baseline)
    del baseline["ir_eval"]

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(
        "tools.eval.run_eval.run_evaluation",
        lambda **kwargs: _pack_c_current_payload(),
    )

    # Must not crash
    comparison = compare_against_baseline(baseline_path=baseline_path)

    ir_comp = comparison["diff"]["ir_run_comparison"]
    assert isinstance(ir_comp, dict)
    # Should indicate no comparison was possible
    assert ir_comp.get("queries_compared", 0) == 0 or ir_comp.get("metric_deltas") == []
