#!/usr/bin/env python3
"""
Search performance regression tests — Round 8 Phase 3 Task 3.4.

Validates that Round 8 Chinese query preprocessing and jieba segmentation do not
introduce unacceptable latency on the real FTS query path.
"""

from __future__ import annotations

import importlib
import os
import time
from pathlib import Path
from typing import TypedDict

import pytest
import yaml


pytestmark = pytest.mark.benchmark


class PerfJournal(TypedDict):
    filename: str
    title: str
    date: str
    tags: list[str]
    topic: str
    content: str


def _build_perf_journals(total: int = 56) -> list[PerfJournal]:
    """Create a realistic mixed-language search corpus for perf tests."""
    journals: list[PerfJournal] = []

    for i in range(total):
        month = (i % 3) + 1
        day = (i % 28) + 1
        if i % 4 == 0:
            title = f"想念团团的第{i + 1}天"
            content = (
                "深夜翻看团团小时候的照片，想念那个让我神魂颠倒的尿片侠。"
                " 想再把她抱在怀里，也想记住这些幸福又感伤的瞬间。"
            )
            tags = ["亲子", "回忆"]
            topic = "think"
        elif i % 4 == 1:
            title = f"OpenClaw deployment note {i + 1}"
            content = (
                "Completed OpenClaw deployment optimization and reduced cold start time."
                " Search pipeline benchmarks stayed stable after the latest indexing changes."
            )
            tags = ["deployment", "benchmark"]
            topic = "work"
        elif i % 4 == 2:
            title = f"Life Index architecture review {i + 1}"
            content = (
                "Life Index dual-pipeline retrieval keeps keyword and semantic search in parallel."
                " Query normalization and ranking thresholds need to stay fast and predictable."
            )
            tags = ["architecture", "search"]
            topic = "work"
        else:
            title = f"AI算力投资策略复盘 {i + 1}"
            content = (
                "AI算力投资策略需要同时关注边缘计算、端侧部署和长期基础设施成本。"
                " 这类中英混合搜索查询需要保持召回，同时不能拖慢 FTS 路径。"
            )
            tags = ["AI", "投资"]
            topic = "learn"

        journals.append(
            {
                "filename": f"life-index_2026-{month:02d}-{day:02d}_{(i % 5) + 1:03d}.md",
                "title": title,
                "date": f"2026-{month:02d}-{day:02d}T20:00:00",
                "tags": tags,
                "topic": topic,
                "content": content,
            }
        )

    return journals


def _write_perf_corpus(tmp_dir: Path) -> int:
    """Create a complete temp Life Index corpus for search perf testing."""
    journals = _build_perf_journals()

    journals_dir = tmp_dir / "Journals" / "2026"
    (tmp_dir / "by-topic").mkdir(exist_ok=True)
    (tmp_dir / "attachments").mkdir(exist_ok=True)
    (tmp_dir / ".cache").mkdir(exist_ok=True)
    (tmp_dir / ".index").mkdir(exist_ok=True)

    entity_graph = {
        "entities": [
            {
                "id": "tuantuan",
                "type": "person",
                "primary_name": "团团",
                "aliases": ["小疙瘩", "尿片侠"],
                "attributes": {},
                "relationships": [],
            }
        ]
    }
    with (tmp_dir / "entity_graph.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(entity_graph, f, allow_unicode=True, sort_keys=False)

    for journal in journals:
        month = journal["date"][5:7]
        month_dir = journals_dir / month
        month_dir.mkdir(parents=True, exist_ok=True)
        file_path = month_dir / str(journal["filename"])
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
            str(journal["content"]),
            "",
        ]
        file_path.write_text("\n".join(frontmatter), encoding="utf-8")

    return len(journals)


@pytest.fixture
def perf_search_env(tmp_path: Path):
    """Create a temporary indexed search environment with 56 journals."""
    total_journals = _write_perf_corpus(tmp_path)

    original_env = os.environ.get("LIFE_INDEX_DATA_DIR")
    os.environ["LIFE_INDEX_DATA_DIR"] = str(tmp_path)

    import tools.lib.paths as paths_module
    import tools.lib.config as config_module
    import tools.lib.metadata_cache as metadata_cache_module
    import tools.lib.search_index as search_index_module
    import tools.lib.fts_update as fts_update_module
    import tools.lib.fts_search as fts_search_module

    importlib.reload(paths_module)
    importlib.reload(config_module)
    importlib.reload(metadata_cache_module)

    from tools.lib.chinese_tokenizer import reset_tokenizer_state

    reset_tokenizer_state()
    importlib.reload(search_index_module)
    importlib.reload(fts_update_module)
    importlib.reload(fts_search_module)

    yield tmp_path, total_journals

    if original_env is not None:
        os.environ["LIFE_INDEX_DATA_DIR"] = original_env
    else:
        os.environ.pop("LIFE_INDEX_DATA_DIR", None)

    importlib.reload(paths_module)
    importlib.reload(config_module)
    importlib.reload(metadata_cache_module)
    importlib.reload(search_index_module)
    importlib.reload(fts_update_module)
    importlib.reload(fts_search_module)
    reset_tokenizer_state()


def _run_production_fts_query(query: str) -> list[dict[str, object]]:
    """Execute the real normalize → segment → FTS query flow used in production."""
    import tools.lib.chinese_tokenizer as chinese_tokenizer
    from tools.lib.search_index import search_fts
    from tools.search_journals.keyword_pipeline import (
        _build_fts_queries,
        _segment_query_for_fts,
    )

    normalize_query = getattr(chinese_tokenizer, "normalize_query")
    normalized = normalize_query(query)
    segmented = _segment_query_for_fts(normalized)
    fts_query, fallback_query = _build_fts_queries(segmented)

    results = search_fts(fts_query)
    if fallback_query and len(results) < 3:
        results = results + [
            item
            for item in search_fts(fallback_query)
            if item["path"] not in {existing["path"] for existing in results}
        ]
    return results


class TestSearchPerformanceRegression:
    """Threshold-based performance regression tests for Round 8 search."""

    def test_full_rebuild_56_journals_under_5s(self, perf_search_env) -> None:
        """Full FTS rebuild for the perf corpus should stay comfortably under 5s."""
        _, total_journals = perf_search_env
        from tools.lib.search_index import update_index

        start = time.perf_counter()
        result = update_index(incremental=False)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n[56 journals] Full rebuild: {elapsed_ms:.2f}ms")
        assert result["success"] is True
        assert result["total"] == total_journals
        assert elapsed_ms < 5000, f"Full rebuild took {elapsed_ms:.2f}ms"

    def test_chinese_query_path_under_200ms(self, perf_search_env) -> None:
        """Chinese query normalization + segmentation + FTS should stay under 200ms."""
        from tools.lib.search_index import update_index

        update_index(incremental=False)

        warmup_results = _run_production_fts_query("想念 团团")
        assert warmup_results, "Chinese warmup query should return results"

        start = time.perf_counter()
        results = _run_production_fts_query("想念团团")
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\nChinese query path: {elapsed_ms:.2f}ms")
        assert results, "Chinese query should return results"
        assert elapsed_ms < 200, f"Chinese query path took {elapsed_ms:.2f}ms"

    def test_english_query_path_has_no_material_regression(
        self, perf_search_env
    ) -> None:
        """English FTS queries should remain fast after jieba integration."""
        from tools.lib.search_index import update_index

        update_index(incremental=False)

        _run_production_fts_query("想念团团")
        _run_production_fts_query("OpenClaw deployment")

        chinese_start = time.perf_counter()
        chinese_results = _run_production_fts_query("想念团团")
        chinese_elapsed_ms = (time.perf_counter() - chinese_start) * 1000

        english_start = time.perf_counter()
        english_results = _run_production_fts_query("OpenClaw deployment")
        english_elapsed_ms = (time.perf_counter() - english_start) * 1000

        print(
            f"\nChinese query: {chinese_elapsed_ms:.2f}ms | "
            f"English query: {english_elapsed_ms:.2f}ms"
        )
        assert chinese_results, "Chinese comparison query should return results"
        assert english_results, "English query should return results"
        assert english_elapsed_ms < 200, (
            f"English query path took {english_elapsed_ms:.2f}ms"
        )
        assert english_elapsed_ms <= chinese_elapsed_ms + 50, (
            "English query path regressed materially after jieba integration: "
            f"english={english_elapsed_ms:.2f}ms chinese={chinese_elapsed_ms:.2f}ms"
        )
