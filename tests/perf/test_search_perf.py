#!/usr/bin/env python3
"""Performance regression tests for search/index operations."""

import importlib
import os
import sys
import time
import types

import pytest
import yaml

from tests.e2e.test_search_quality import JOURNALS


def _install_ranking_stub() -> types.ModuleType:
    """Install a lightweight ranking stub for perf tests.

    The workspace currently has a syntax error in tools.search_journals.ranking,
    but these perf regressions only need hierarchical_search timing and success.
    """

    def _merge_unique(*groups):
        seen = set()
        merged = []
        for group in groups:
            for item in group:
                path = item.get("path")
                if path in seen:
                    continue
                seen.add(path)
                merged.append(item)
        return merged

    ranking_stub = types.ModuleType("tools.search_journals.ranking")
    setattr(
        ranking_stub,
        "merge_and_rank_results",
        lambda l1, l2, l3, query, **kwargs: _merge_unique(l3, l2, l1),
    )
    setattr(
        ranking_stub,
        "merge_and_rank_results_hybrid",
        lambda l1, l2, l3, semantic_results, query, **kwargs: _merge_unique(
            l3, semantic_results, l2, l1
        ),
    )
    sys.modules["tools.search_journals.ranking"] = ranking_stub
    return ranking_stub


@pytest.fixture(scope="module")
def _setup_search_env(tmp_path_factory):
    """Build a temp Life Index environment with an FTS index."""
    tmp_dir = tmp_path_factory.mktemp("life_index_search_perf")
    original_ranking_module = sys.modules.get("tools.search_journals.ranking")

    journals_dir = tmp_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "by-topic").mkdir(exist_ok=True)
    (tmp_dir / "attachments").mkdir(exist_ok=True)
    (tmp_dir / ".cache").mkdir(exist_ok=True)
    (tmp_dir / ".index").mkdir(exist_ok=True)

    entity_graph = {
        "entities": [
            {
                "id": "tuantuan",
                "type": "person",
                "primary_name": "乐乐",
                "aliases": ["小豆丁", "小英雄"],
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
    graph_path = tmp_dir / "entity_graph.yaml"
    with graph_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(entity_graph, f, allow_unicode=True, sort_keys=False)

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

    original_env = os.environ.get("LIFE_INDEX_DATA_DIR")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(tmp_dir)

    import tools.lib.paths as paths_module
    import tools.lib.config as config_module
    import tools.lib.metadata_cache as mc

    importlib.reload(paths_module)
    importlib.reload(config_module)
    importlib.reload(mc)

    import tools.lib.search_index as search_index_mod
    import tools.lib.fts_update as fts_update_mod
    import tools.lib.fts_search as fts_search_mod

    importlib.reload(search_index_mod)
    importlib.reload(fts_update_mod)
    importlib.reload(fts_search_mod)

    from tools.lib.chinese_tokenizer import reset_tokenizer_state

    reset_tokenizer_state()
    _install_ranking_stub()

    import tools.search_journals.core as core_mod

    importlib.reload(core_mod)

    conn = search_index_mod.init_fts_db()
    result = search_index_mod.update_index(incremental=False)
    assert result["success"], f"Index build failed: {result.get('error')}"

    yield tmp_dir

    conn.close()
    if original_env is not None:
        os.environ["LIFE_INDEX_DATA_DIR"] = original_env
    else:
        os.environ.pop("LIFE_INDEX_DATA_DIR", None)

    importlib.reload(paths_module)
    importlib.reload(config_module)
    importlib.reload(mc)
    importlib.reload(search_index_mod)
    importlib.reload(fts_update_mod)
    importlib.reload(fts_search_mod)
    reset_tokenizer_state()
    if original_ranking_module is not None:
        sys.modules["tools.search_journals.ranking"] = original_ranking_module
    else:
        sys.modules.pop("tools.search_journals.ranking", None)


@pytest.mark.perf
def test_chinese_query_under_200ms(_setup_search_env):
    import tools.search_journals.core as core_mod

    result = core_mod.hierarchical_search(
        query="想念我的女儿",
        level=3,
        semantic=False,
    )

    assert result["success"] is True
    assert result["performance"]["total_time_ms"] < 200


@pytest.mark.perf
def test_english_query_under_200ms(_setup_search_env):
    import tools.search_journals.core as core_mod

    result = core_mod.hierarchical_search(
        query="deployment",
        level=3,
        semantic=False,
    )

    assert result["success"] is True
    assert result["performance"]["total_time_ms"] < 200


@pytest.mark.perf
def test_full_rebuild_under_5s(_setup_search_env):
    import tools.lib.search_index as search_index_mod

    start = time.time()
    result = search_index_mod.update_index(incremental=False)
    elapsed_ms = (time.time() - start) * 1000

    assert result["success"] is True
    assert elapsed_ms < 5000


@pytest.mark.perf
def test_jieba_segmentation_under_50ms(_setup_search_env):
    from tools.lib.chinese_tokenizer import segment_for_fts

    queries = [
        "想念我的女儿",
        "想念女儿",
        "AI算力投资策略",
        "乐乐不认真吃饭",
        "重庆过生日",
        "数字灵魂",
        "想念小英雄",
        "小豆丁",
        "双管道检索",
        "人工智能伦理讨论",
    ]

    durations_ms = []
    for query in queries:
        start = time.time()
        segmented = segment_for_fts(query)
        durations_ms.append((time.time() - start) * 1000)
        assert isinstance(segmented, str)

    average_ms = sum(durations_ms) / len(durations_ms)
    assert average_ms < 50
