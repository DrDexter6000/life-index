#!/usr/bin/env python3
"""
Round 8 Phase 2 T2.5 — Relation-Aware Search Integration Tests

Verifies relation-aware queries travel through the full keyword search path:
entity expansion → keyword pipeline → ranking.
"""

import importlib
import os

import pytest
import yaml


RELATION_JOURNALS = [
    {
        "filename": "life-index_2026-03-04_001.md",
        "title": "想念小英雄",
        "date": "2026-03-04T19:43:00",
        "tags": ["亲子", "回忆", "感伤"],
        "topic": "think",
        "people": ["乐乐"],
        "content": (
            "翻看女儿乐乐小时候的照片，那个只有2岁上下的小英雄。小豆丁，爸爸想你了。"
        ),
    },
    {
        "filename": "life-index_2026-03-10_001.md",
        "title": "乐乐不认真吃饭",
        "date": "2026-03-10T18:00:00",
        "tags": ["亲子", "日常"],
        "topic": "life",
        "people": ["乐乐"],
        "content": "乐乐最近吃饭很不认真，总是跑来跑去，不过还是很可爱。",
    },
    {
        "filename": "life-index_2026-03-12_001.md",
        "title": "重庆过生日",
        "date": "2026-03-12T12:00:00",
        "tags": ["生日", "家庭"],
        "topic": "life",
        "people": ["妈妈", "乐乐"],
        "content": "在重庆过了一个简单的生日。妈妈做了长寿面，乐乐唱了生日歌。",
    },
    {
        "filename": "life-index_2026-03-16_001.md",
        "title": "想念我的女儿",
        "date": "2026-03-16T22:00:00",
        "tags": ["思念", "亲情"],
        "topic": "think",
        "people": ["乐乐"],
        "content": "深夜翻看乐乐的照片，好想再把她抱在怀里。",
    },
    {
        "filename": "life-index_2026-03-20_001.md",
        "title": "和老婆看电影",
        "date": "2026-03-20T20:00:00",
        "tags": ["家庭", "关系"],
        "topic": "life",
        "people": ["老婆"],
        "content": "周末和老婆一起去看电影，回家路上聊了很多以后的小计划。",
    },
]


SEARCH_CASES = [
    ("我女儿", "想念小英雄", "child_of reverse lookup should find tuantuan journals"),
    ("乐乐的奶奶", "重庆过生日", "grandmother relation should resolve to mama journal"),
    ("我妈妈", "重庆过生日", "parent relation should resolve to mama journal"),
    ("我老婆", "和老婆看电影", "spouse relation should resolve to spouse journal"),
]


EXPANSION_EXPECTATIONS = {
    "我女儿": ["乐乐", "小英雄"],
    "乐乐的奶奶": ["妈妈", "老妈"],
    "我妈妈": ["妈妈", "老妈"],
    "我老婆": ["老婆", "妻子"],
}


@pytest.fixture(scope="module")
def _setup_relation_search_env(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("life_index_relation_search_e2e")

    journals_dir = tmp_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "by-topic").mkdir(exist_ok=True)
    (tmp_dir / ".cache").mkdir(exist_ok=True)
    (tmp_dir / ".index").mkdir(exist_ok=True)

    entity_graph = {
        "entities": [
            {
                "id": "author-self",
                "type": "person",
                "primary_name": "我",
                "aliases": [],
                "relationships": [
                    {"target": "tuantuan", "relation": "child_of"},
                    {"target": "mama", "relation": "parent_of"},
                    {"target": "wife", "relation": "spouse_of"},
                ],
            },
            {
                "id": "tuantuan",
                "type": "person",
                "primary_name": "乐乐",
                "aliases": ["小豆丁", "小英雄"],
                "relationships": [],
            },
            {
                "id": "mama",
                "type": "person",
                "primary_name": "妈妈",
                "aliases": ["老妈"],
                "relationships": [{"target": "tuantuan", "relation": "grandmother_of"}],
            },
            {
                "id": "wife",
                "type": "person",
                "primary_name": "老婆",
                "aliases": ["妻子"],
                "relationships": [],
            },
        ]
    }
    with (tmp_dir / "entity_graph.yaml").open("w", encoding="utf-8") as file_obj:
        yaml.safe_dump(entity_graph, file_obj, allow_unicode=True, sort_keys=False)

    for journal in RELATION_JOURNALS:
        frontmatter = [
            "---",
            f"title: {journal['title']!r}",
            f"date: {journal['date']}",
            f"tags: [{', '.join(journal['tags'])}]",
            f"topic: {journal['topic']}",
            f"people: [{', '.join(journal['people'])}]",
            "---",
            "",
            f"# {journal['title']}",
            "",
            journal["content"],
            "",
        ]
        (journals_dir / journal["filename"]).write_text(
            "\n".join(frontmatter), encoding="utf-8"
        )

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
    import tools.search_journals.core as core_mod

    importlib.reload(search_index_mod)
    importlib.reload(fts_update_mod)
    importlib.reload(fts_search_mod)
    importlib.reload(core_mod)

    from tools.lib.chinese_tokenizer import reset_tokenizer_state
    from tools.lib.search_index import init_fts_db, update_index

    reset_tokenizer_state()
    conn = init_fts_db()
    result = update_index(incremental=False)
    assert result["success"], f"Index build failed: {result.get('error')}"

    yield conn, tmp_dir

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
    importlib.reload(core_mod)
    reset_tokenizer_state()


@pytest.mark.parametrize("query,expected_title_substring,note", SEARCH_CASES)
def test_expand_query_with_entity_graph_and_keyword_search(
    _setup_relation_search_env,
    query,
    expected_title_substring,
    note,
):
    from tools.search_journals.core import (
        expand_query_with_entity_graph,
        hierarchical_search,
    )

    def _normalize_text(value: str) -> str:
        return "".join(str(value).split())

    expanded_query = expand_query_with_entity_graph(query)
    for expected_term in EXPANSION_EXPECTATIONS[query]:
        assert expected_term in expanded_query, (
            f"[{note}] query={query!r} expected expanded query to contain {expected_term!r}, "
            f"got {expanded_query!r}"
        )

    result = hierarchical_search(query=query, level=3, semantic=False)
    merged_results = result.get("merged_results", [])
    merged_titles = [str(item.get("title", "")) for item in merged_results]
    normalized_expected_title = _normalize_text(expected_title_substring)
    normalized_merged_titles = [_normalize_text(title) for title in merged_titles]

    assert any(
        normalized_expected_title in normalized_title
        for normalized_title in normalized_merged_titles
    ), (
        f"[{note}] query={query!r} expected a merged result title containing "
        f"{expected_title_substring!r}, got {merged_titles}"
    )
