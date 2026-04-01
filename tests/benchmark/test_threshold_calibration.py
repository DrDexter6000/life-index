#!/usr/bin/env python3
"""Threshold calibration benchmark tests based on real journal-derived cases."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest


pytestmark = pytest.mark.benchmark


REAL_JOURNALS_DIR = Path.home() / "Documents" / "Life-Index" / "Journals"


CALIBRATION_QUERY_GROUPS: list[dict[str, Any]] = [
    {
        "query": "团团",
        "expected_hits": {
            "Journals/2026/03/life-index_2026-03-04_001.md",
            "Journals/2026/03/life-index_2026-03-20_001.md",
            "Journals/2026/03/life-index_2026-03-27_002.md",
            "Journals/2026/03/life-index_2026-03-30_001.md",
        },
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-14_002.md",
            "Journals/2026/02/life-index_2026-02-25_001.md",
        },
    },
    {
        "query": "尿片侠",
        "expected_hits": {"Journals/2026/03/life-index_2026-03-04_001.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-20_001.md",
            "Journals/2026/03/life-index_2026-03-30_001.md",
        },
    },
    {
        "query": "团团妈 第一负责人",
        "expected_hits": {"Journals/2026/03/life-index_2026-03-30_001.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-04_001.md",
            "Journals/2026/03/life-index_2026-03-14_002.md",
        },
    },
    {
        "query": "Carloha",
        "expected_hits": {
            "Journals/2026/03/life-index_2026-03-14_002.md",
            "Journals/2026/03/life-index_2026-03-16_001.md",
            "Journals/2026/03/life-index_2026-03-27_001.md",
        },
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-20_001.md",
            "Journals/2026/01/life-index_2026-01-28_002.md",
        },
    },
    {
        "query": "销售支持",
        "expected_hits": {
            "Journals/2026/03/life-index_2026-03-16_001.md",
        },
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-20_001.md",
            "Journals/2026/03/life-index_2026-03-27_001.md",
        },
    },
    {
        "query": '"Life Index 项目重构启动"',
        "expected_hits": {
            "Journals/2026/02/life-index_2026-02-25_001.md",
        },
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-11_001.md",
            "Journals/2026/03/life-index_2026-03-16_001.md",
            "Journals/2026/03/life-index_2026-03-18_001.md",
            "Journals/2026/03/life-index_2026-03-20_001.md",
            "Journals/2026/01/life-index_2026-01-28_003.md",
        },
    },
    {
        "query": '"Carloha Wiki AI Chat Bot 调试"',
        "expected_hits": {"Journals/2026/03/life-index_2026-03-27_001.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-16_001.md",
            "Journals/2026/03/life-index_2026-03-31_001.md",
        },
    },
    {
        "query": "Digital-self 项目迁移",
        "expected_hits": {"Journals/2026/02/life-index_2026-02-20_001.md"},
        "expected_misses": {
            "Journals/2026/02/life-index_2026-02-21_001.md",
            "Journals/2026/03/life-index_2026-03-31_001.md",
        },
    },
    {
        "query": '"为 Life Index 2.0 充值 Claude Code"',
        "expected_hits": {"Journals/2026/03/life-index_2026-03-31_001.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-14_001.md",
            "Journals/2026/03/life-index_2026-03-29_001.md",
        },
    },
    {
        "query": "工作待办",
        "expected_hits": {"Journals/2026/03/life-index_2026-03-14_002.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-20_001.md",
            "Journals/2026/03/life-index_2026-03-29_002.md",
        },
    },
    {
        "query": "家庭会议",
        "expected_hits": {"Journals/2026/03/life-index_2026-03-30_001.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-27_002.md",
            "Journals/2026/03/life-index_2026-03-04_001.md",
        },
    },
    {
        "query": "前端设计革命性工具",
        "expected_hits": {"Journals/2026/03/life-index_2026-03-26_001.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-22_001.md",
            "Journals/2026/03/life-index_2026-03-28_001.md",
        },
    },
    {
        "query": "Marketing Director",
        "expected_hits": {
            "Journals/2026/02/life-index_2026-02-21_002.md",
            "Journals/2026/02/life-index_2026-02-22_002.md",
        },
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-14_002.md",
            "Journals/2026/02/life-index_2026-02-21_001.md",
        },
    },
    {
        "query": "Claude Opus 4.6",
        "expected_hits": {"Journals/2026/03/life-index_2026-03-14_001.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-31_001.md",
            "Journals/2026/03/life-index_2026-03-29_001.md",
        },
    },
    {
        "query": "张雪峰 死亡",
        "expected_hits": {"Journals/2026/03/life-index_2026-03-24_001.md"},
        "expected_misses": {
            "Journals/2026/03/life-index_2026-03-11_001.md",
            "Journals/2026/03/life-index_2026-03-29_002.md",
        },
    },
]


def _copy_real_journal(relative_path: str, target_root: Path) -> None:
    source = REAL_JOURNALS_DIR / Path(relative_path).relative_to("Journals")
    destination = target_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _to_route_path(relative_path: str) -> str:
    path = str(relative_path).replace("\\", "/")
    return path[len("Journals/") :] if path.startswith("Journals/") else path


def _is_primary_journal_entry(path: str) -> bool:
    """Return whether a route/path points to a primary life-index journal entry."""
    normalized = str(path).replace("\\", "/")
    filename = Path(normalized).name
    return filename.startswith("life-index_")


@pytest.fixture
def calibration_dataset(isolated_data_dir: Path) -> list[dict[str, Any]]:
    import tools.lib.vector_index_simple as vector_index_simple
    from tools.build_index import build_all

    journals_root = isolated_data_dir / "Journals"
    all_paths = set()
    for group in CALIBRATION_QUERY_GROUPS:
        all_paths.update(group["expected_hits"])
        all_paths.update(group["expected_misses"])

    for relative_path in all_paths:
        _copy_real_journal(relative_path, isolated_data_dir)

    assert journals_root.exists()
    vector_index_simple._index_instance = None
    build_result = build_all(incremental=False)
    assert build_result["success"] is True, build_result
    return CALIBRATION_QUERY_GROUPS


def evaluate_search_quality(
    query_group: dict[str, Any],
    *,
    semantic_min_similarity: float,
    fts_min_relevance: int,
) -> dict[str, float]:
    """Evaluate search quality for one calibration query group."""
    from tools.search_journals.core import hierarchical_search
    from tools.lib.search_constants import FTS_MIN_RELEVANCE, SEMANTIC_MIN_SIMILARITY

    if semantic_min_similarity < 0:
        semantic_min_similarity = SEMANTIC_MIN_SIMILARITY
    if fts_min_relevance < 0:
        fts_min_relevance = FTS_MIN_RELEVANCE

    result = hierarchical_search(
        query=query_group["query"],
        level=3,
        semantic=True,
        semantic_min_similarity=semantic_min_similarity,
        fts_min_relevance=fts_min_relevance,
    )

    merged = result.get("merged_results", [])
    hits = {
        str(item.get("journal_route_path") or item.get("path") or "") for item in merged
    }
    hits.discard("")
    hits = {path for path in hits if _is_primary_journal_entry(path)}

    expected_hits = {_to_route_path(path) for path in query_group["expected_hits"]}
    expected_misses = {_to_route_path(path) for path in query_group["expected_misses"]}

    recall = len(hits & expected_hits) / len(expected_hits) if expected_hits else 1.0
    precision = len(hits & expected_hits) / len(hits) if hits else 1.0
    noise_rate = (
        len(hits & expected_misses) / len(expected_misses) if expected_misses else 0.0
    )

    return {
        "recall": recall,
        "precision": precision,
        "noise_rate": noise_rate,
    }


class TestThresholdCalibration:
    def test_dataset_has_at_least_10_query_groups(
        self, calibration_dataset: list[dict[str, Any]]
    ) -> None:
        assert len(calibration_dataset) >= 10

    def test_recall_above_90(self, calibration_dataset: list[dict[str, Any]]) -> None:
        for group in calibration_dataset:
            metrics = evaluate_search_quality(
                group,
                semantic_min_similarity=-1,
                fts_min_relevance=-1,
            )
            assert metrics["recall"] > 0.9, group["query"]

    def test_precision_above_70(
        self, calibration_dataset: list[dict[str, Any]]
    ) -> None:
        for group in calibration_dataset:
            metrics = evaluate_search_quality(
                group,
                semantic_min_similarity=-1,
                fts_min_relevance=-1,
            )
            assert metrics["precision"] > 0.7, group["query"]

    def test_noise_below_20(self, calibration_dataset: list[dict[str, Any]]) -> None:
        for group in calibration_dataset:
            metrics = evaluate_search_quality(
                group,
                semantic_min_similarity=-1,
                fts_min_relevance=-1,
            )
            assert metrics["noise_rate"] < 0.2, group["query"]

    def test_no_total_miss(self, calibration_dataset: list[dict[str, Any]]) -> None:
        for group in calibration_dataset:
            metrics = evaluate_search_quality(
                group,
                semantic_min_similarity=-1,
                fts_min_relevance=-1,
            )
            assert metrics["recall"] > 0.0, group["query"]
