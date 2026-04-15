#!/usr/bin/env python3
"""
Round 8 Phase 2 T2.5 — Relation-Aware Search Integration Tests
================================================================

Validates the full search chain for relation-aware retrieval:
- entity graph phrase expansion
- reverse relationship resolution
- Chinese jieba-segmented FTS lookup
- final hierarchical_search() merged_results output
"""

import importlib
import os
from pathlib import Path

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
        "content": "翻看女儿乐乐小时候的照片，那个只有2岁上下的小英雄。小豆丁，爸爸想你了。",
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
        "content": "深夜翻看乐乐的照片，好想把她再抱在怀里，那个让我神魂颠倒的小英雄。",
    },
    {
        "filename": "life-index_2026-03-20_001.md",
        "title": "给老婆的一封信",
        "date": "2026-03-20T20:00:00",
        "tags": ["家庭", "关系"],
        "topic": "relation",
        "people": ["乐乐妈"],
        "content": "写给乐乐妈的一封信。老婆这些年辛苦了，我们一起把乐乐带大。",
    },
]


RELATION_TEST_CASES = [
    (
        "我女儿",
        {"想念小英雄", "想念我的女儿"},
        {"乐乐"},
        "child reverse lookup should find tuantuan journals",
    ),
    (
        "乐乐的奶奶",
        {"重庆过生日"},
        {"妈妈", "婆婆", "老妈"},
        "grandparent phrase should resolve to mama",
    ),
    (
        "我妈妈",
        {"重庆过生日"},
        {"妈妈", "婆婆", "老妈"},
        "parent phrase should resolve to mama",
    ),
    (
        "我老婆",
        {"给老婆的一封信"},
        {"乐乐妈", "老婆"},
        "spouse phrase should resolve to wife entity",
    ),
]


@pytest.fixture(scope="module")
def _setup_relation_search_env(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("life_index_relation_e2e")

    journals_dir = tmp_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "by-topic").mkdir(exist_ok=True)
    (tmp_dir / "attachments").mkdir(exist_ok=True)
    (tmp_dir / ".cache").mkdir(exist_ok=True)
    (tmp_dir / ".index").mkdir(exist_ok=True)

    entity_graph = {
        "entities": [
            {
                "id": "author-self",
                "type": "person",
                "primary_name": "我",
                "aliases": ["作者", "自己"],
                "attributes": {},
                "relationships": [{"target": "wife-001", "relation": "spouse_of"}],
            },
            {
                "id": "wife-001",
                "type": "person",
                "primary_name": "乐乐妈",
                "aliases": ["老婆", "妻子", "王某某"],
                "attributes": {},
                "relationships": [{"target": "author-self", "relation": "spouse_of"}],
            },
            {
                "id": "mama",
                "type": "person",
                "primary_name": "妈妈",
                "aliases": ["老妈", "婆婆", "王阿姨"],
                "attributes": {},
                "relationships": [
                    {"target": "author-self", "relation": "mother_of"},
                    {"target": "tuantuan", "relation": "grandmother_of"},
                ],
            },
            {
                "id": "tuantuan",
                "type": "person",
                "primary_name": "乐乐",
                "aliases": ["小豆丁", "小英雄", "圆圆"],
                "attributes": {},
                "relationships": [{"target": "author-self", "relation": "child_of"}],
            },
        ]
    }
    graph_path = tmp_dir / "entity_graph.yaml"
    with graph_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(entity_graph, f, allow_unicode=True, sort_keys=False)

    for journal in RELATION_JOURNALS:
        file_path = journals_dir / journal["filename"]
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
        file_path.write_text("\n".join(frontmatter), encoding="utf-8")

    original_env = os.environ.get("LIFE_INDEX_DATA_DIR")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(tmp_dir)

    paths_module = importlib.import_module("tools.lib.paths")
    config_module = importlib.import_module("tools.lib.config")
    mc = importlib.import_module("tools.lib.metadata_cache")
    entity_runtime_module = importlib.import_module("tools.lib.entity_runtime")
    search_index_mod = importlib.import_module("tools.lib.search_index")
    fts_update_mod = importlib.import_module("tools.lib.fts_update")
    fts_search_mod = importlib.import_module("tools.lib.fts_search")
    core_module = importlib.import_module("tools.search_journals.core")
    keyword_pipeline_module = importlib.import_module(
        "tools.search_journals.keyword_pipeline"
    )
    semantic_pipeline_module = importlib.import_module(
        "tools.search_journals.semantic_pipeline"
    )

    importlib.reload(paths_module)
    importlib.reload(config_module)
    importlib.reload(mc)
    importlib.reload(entity_runtime_module)
    importlib.reload(search_index_mod)
    importlib.reload(fts_update_mod)
    importlib.reload(fts_search_mod)
    importlib.reload(core_module)
    importlib.reload(keyword_pipeline_module)
    importlib.reload(semantic_pipeline_module)

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
    importlib.reload(entity_runtime_module)
    importlib.reload(search_index_mod)
    importlib.reload(fts_update_mod)
    importlib.reload(fts_search_mod)
    importlib.reload(core_module)
    importlib.reload(keyword_pipeline_module)
    importlib.reload(semantic_pipeline_module)
    reset_tokenizer_state()


@pytest.mark.parametrize(
    "query,expected_titles,expected_expansion_terms,note", RELATION_TEST_CASES
)
def test_relation_aware_search_end_to_end(
    _setup_relation_search_env,
    query,
    expected_titles,
    expected_expansion_terms,
    note,
):
    from tools.search_journals import hierarchical_search

    def _normalize_title(value: str) -> str:
        return "".join(str(value).split())

    result = hierarchical_search(query=query, level=3, semantic=False)

    merged_titles = {item.get("title", "") for item in result.get("merged_results", [])}
    normalized_merged_titles = {_normalize_title(title) for title in merged_titles}
    normalized_expected_titles = {_normalize_title(title) for title in expected_titles}

    assert normalized_expected_titles & normalized_merged_titles, (
        f"[{note}] query={query!r} expected one of {sorted(expected_titles)} in merged_results, "
        f"got {sorted(merged_titles)}"
    )

    expanded_query = str(result.get("query_params", {}).get("expanded_query", ""))
    for term in expected_expansion_terms:
        assert term in expanded_query, (
            f"[{note}] query={query!r} expected expanded_query to contain {term!r}, got {expanded_query!r}"
        )
