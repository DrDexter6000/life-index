#!/usr/bin/env python3

import importlib
import json
from pathlib import Path

import yaml


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
                "type": "organization",
                "primary_name": "OpenClaw",
                "aliases": [],
                "attributes": {},
                "relationships": [],
            },
            {
                "id": "lobsterai",
                "type": "organization",
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
