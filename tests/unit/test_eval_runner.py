#!/usr/bin/env python3

import importlib
import json
import math
import os
from importlib import import_module
from pathlib import Path

import yaml


def _load_eval_llm_module():
    return import_module("tools.eval.llm_client")


GOLDEN_QUERIES_PATH = (
    Path(__file__).resolve().parents[2] / "tools" / "eval" / "golden_queries.yaml"
)


JOURNALS = [
    {
        "filename": "life-index_2026-03-04_001.md",
        "title": "想念尿片侠",
        "date": "2026-03-04T19:43:00",
        "tags": ["亲子", "回忆", "感伤"],
        "topic": "think",
        "content": (
            "翻看女儿团团小时候的照片，那个只有2岁上下的尿片侠。"
            "突然有一种伤感——我好想再见她一面，好想再能体验一次把小肉坨坨抱在怀里的感觉。"
            "小疙瘩，爸爸想你了。"
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
        "title": "团团不认真吃饭",
        "date": "2026-03-10T18:00:00",
        "tags": ["亲子", "日常"],
        "topic": "life",
        "content": "团团最近吃饭很不认真，总是跑来跑去。不过今天她主动帮我收拾玩具，还是挺懂事的。",
    },
    {
        "filename": "life-index_2026-03-12_001.md",
        "title": "重庆过生日",
        "date": "2026-03-12T12:00:00",
        "tags": ["生日", "家庭"],
        "topic": "life",
        "content": (
            "在重庆过了一个简单的生日。妈妈做了长寿面，团团唱了生日歌。"
            "虽然简单，但很温暖。数字灵魂的概念也在脑海中酝酿。"
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
            "OpenClaw deployment is next."
        ),
    },
    {
        "filename": "life-index_2026-03-16_001.md",
        "title": "想念我的女儿",
        "date": "2026-03-16T22:00:00",
        "tags": ["思念", "亲情"],
        "topic": "think",
        "content": (
            "深夜翻看团团的照片，那种幸福中带怅然若失的复杂情绪无法用言语表达。"
            "好想把她再抱在怀里，那个让我神魂颠倒的尿片侠。"
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
            "团团说以后也要学编程。"
        ),
    },
    {
        "filename": "life-index_2026-03-20_001.md",
        "title": "读《三体》有感",
        "date": "2026-03-20T20:00:00",
        "tags": ["读书", "思考"],
        "topic": "learn",
        "content": (
            "重读《三体》，对黑暗森林法则有了新的理解。"
            "科技发展的边界在哪里？数字灵魂是否可能存在？这些问题值得深思。"
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
                "primary_name": "团团",
                "aliases": ["小疙瘩", "尿片侠"],
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
    assert 20 <= len(payload["queries"]) <= 30

    required_categories = {
        "chinese_recall",
        "entity_expansion",
        "noise_rejection",
        "english_regression",
        "cross_language",
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
        assert count >= 2, f"category {category} should have at least 2 queries"


def test_eval_runner_with_isolated_data(isolated_data_dir: Path) -> None:
    _write_eval_fixture_data(isolated_data_dir)

    from tools.eval.run_eval import run_evaluation

    result = run_evaluation(data_dir=isolated_data_dir)

    assert result["total_queries"] >= 20
    assert set(result["metrics"].keys()) == {
        "mrr_at_5",
        "recall_at_5",
        "precision_at_5",
    }
    assert "chinese_recall" in result["by_category"]
    assert result["by_category"]["chinese_recall"]["query_count"] >= 2
    assert isinstance(result["per_query"], list)
    assert result["per_query"]
    assert "python_version" in result
    assert "tokenizer_version" in result


def test_eval_baseline_save_and_compare(
    isolated_data_dir: Path, tmp_path: Path
) -> None:
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
                    "title": "想念我的女儿",
                    "date": "2026-03-16",
                    "abstract": "思念",
                    "snippet": "团团",
                },
                {
                    "title": "普通日志",
                    "date": "2026-03-17",
                    "abstract": "一般",
                    "snippet": "无关",
                },
                {
                    "title": "想念尿片侠",
                    "date": "2026-03-04",
                    "abstract": "回忆",
                    "snippet": "尿片侠",
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
                    "title": "想念我的女儿",
                    "date": "2026-03-16",
                    "abstract": "思念",
                    "snippet": "团团",
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
    assert "ndcg_at_5" not in result["metrics"]
    assert "llm_scores" not in result["per_query"][0]


def test_recall_gap_detection_with_mock(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    from tools.eval.run_eval import run_evaluation

    queries = [
        {
            "id": "Q1",
            "query": "团团",
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
                    "query": "团团",
                    "category": "family",
                    "results_found": 1,
                    "expected_min_results": 1,
                    "top_titles": ["团团不认真吃饭"],
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
        lambda: ["想念我的女儿", "重庆过生日", "团团不认真吃饭"],
    )

    result = run_evaluation(
        judge="llm",
        live=True,
        llm_client=_load_eval_llm_module().MockLLMClient(
            responses=[
                '{"expected_hits": ["想念我的女儿", "重庆过生日", "团团不认真吃饭"], "reason": "都和团团相关"}',
            ]
        ),
    )

    assert result["recall_gaps"] == [
        {
            "query_id": "Q1",
            "query": "团团",
            "expected_but_missed": ["想念我的女儿", "重庆过生日"],
            "returned": ["团团不认真吃饭"],
            "recall_ratio": 0.33,
        }
    ]


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
    monkeypatch.setattr("tools.eval.run_eval._evaluate_queries", _fake_evaluate_queries)

    result = run_evaluation(live=True)

    assert result["live_mode"] is True
    assert captured == [str(Path.home() / "Documents" / "Life-Index")]
    assert os.environ["LIFE_INDEX_DATA_DIR"] == str(fake_env_dir)


def test_recall_ratio_computation() -> None:
    from tools.eval.run_eval import _compute_recall_ratio

    assert (
        _compute_recall_ratio(
            ["想念我的女儿", "重庆过生日", "团团不认真吃饭"],
            ["团团不认真吃饭"],
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
        }

    monkeypatch.setattr(eval_main, "run_evaluation", _fake_run_evaluation)

    eval_main.main(["--live", "--judge", "llm", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert captured["live"] is True
    assert captured["judge"] == "llm"
    assert payload["success"] is True
    assert payload["data"]["judge_mode"] == "llm"


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
                        "query": "团团",
                        "pass": True,
                        "first_relevant_rank": 1,
                    }
                ],
                "recall_gaps": [
                    {"query_id": "Q1", "expected_but_missed": ["想念我的女儿"]}
                ],
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
            "per_query": [
                {"id": "Q1", "query": "团团", "pass": True, "first_relevant_rank": 1}
            ],
            "recall_gaps": [{"query_id": "Q1", "expected_but_missed": ["重庆过生日"]}],
        },
    )

    comparison = compare_against_baseline(baseline_path=baseline_path)

    assert comparison["diff"]["metric_deltas"]["ndcg_at_5"]["delta"] == 0.08
    assert comparison["diff"]["recall_gap_changes"] == [
        {
            "query_id": "Q1",
            "query": "",
            "baseline_missed": ["想念我的女儿"],
            "current_missed": ["重庆过生日"],
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
                        "query": "团团",
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
                    "query": "团团",
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
                    "query": "团团",
                    "current_missed": ["想念我的女儿", "重庆过生日"],
                    "current_expected_total": 3,
                }
            ],
        }
    )

    assert lines[0] == "═══ Search Eval Comparison ═══"
    assert "  MRR@5:        0.8500 → 0.9200  (▲ +0.0700)" in lines
    assert "  Recall@5:     0.9000 → 0.8800  (▼ -0.0200)" in lines
    assert '  GQ05 "团团": 漏检 2/3 expected (想念我的女儿, 重庆过生日)' in lines
