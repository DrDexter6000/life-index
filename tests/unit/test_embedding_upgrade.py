#!/usr/bin/env python3
"""Embedding upgrade RED tests for Phase 1 / Batch 1.

These tests define the expected state after upgrading the semantic-search
embedding stack away from MiniLM-L12-v2 toward a long-context model.
"""

from __future__ import annotations

import importlib
from pathlib import Path


def _reload_search_modules() -> tuple[object, object, object]:
    import tools.lib.search_config as search_config
    import tools.lib.semantic_search as semantic_search
    import tools.lib.vector_index_simple as vector_index_simple

    return (
        importlib.reload(search_config),
        importlib.reload(semantic_search),
        importlib.reload(vector_index_simple),
    )


class TestEmbeddingUpgrade:
    def test_long_content_searchable(self, isolated_data_dir: Path) -> None:
        """长日志后半部分内容不应在向量化前被截断。"""
        _, semantic_search, vector_index_simple = _reload_search_modules()

        journal_dir = isolated_data_dir / "Journals" / "2026" / "04"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal_path = journal_dir / "life-index_2026-04-01_001.md"

        tail_keyword = "银河尽头的紫色雨"
        body = ("前文填充。" * 900) + f" 关键尾部信息：{tail_keyword}"
        journal_path.write_text(
            "---\n"
            'title: "Long Journal"\n'
            "date: 2026-04-01T10:00:00\n"
            "tags: [upgrade]\n"
            "topic: [learn]\n"
            "---\n\n"
            f"{body}\n",
            encoding="utf-8",
        )

        sqlite_parsed = semantic_search.parse_journal_for_vec(journal_path)

        captured_texts: list[str] = []

        def capture_encode(texts: list[str]) -> list[list[float]]:
            captured_texts.extend(texts)
            return [[0.0] * vector_index_simple.EMBEDDING_DIM for _ in texts]

        vector_index_simple._index_instance = None
        vector_index_simple.update_vector_index_simple(capture_encode, incremental=True)

        assert sqlite_parsed is not None
        assert captured_texts, "simple backend should send at least one journal text for embedding"
        assert tail_keyword in sqlite_parsed[1]
        assert tail_keyword in captured_texts[0]

    def test_chinese_semantic_quality(self) -> None:
        """升级后的模型配置应明确保持中英文多语种能力。"""
        search_config, _, _ = _reload_search_modules()

        model = search_config.EMBEDDING_MODEL
        assert model["name"] == "BAAI/bge-m3"
        assert "zh" in str(model["metadata"].get("supported_languages", "")).lower()

    def test_english_semantic_quality(self) -> None:
        """升级后的模型配置应明确保持英文语义能力。"""
        search_config, _, _ = _reload_search_modules()

        model = search_config.EMBEDDING_MODEL
        assert model["name"] == "BAAI/bge-m3"
        assert "en" in str(model["metadata"].get("supported_languages", "")).lower()

    def test_cross_language_search(self) -> None:
        """目标模型应具备跨语言/多语言检索定位。"""
        search_config, _, _ = _reload_search_modules()

        model = search_config.EMBEDDING_MODEL
        supported = str(model["metadata"].get("supported_languages", "")).lower()
        assert model["name"] == "BAAI/bge-m3"
        assert "zh" in supported and "en" in supported

    def test_embedding_dimension(self) -> None:
        """两个向量后端必须共享同一模型配置与维度。"""
        search_config, semantic_search, vector_index_simple = _reload_search_modules()

        expected_dimension = search_config.EMBEDDING_MODEL["dimension"]

        assert search_config.EMBEDDING_MODEL["name"] == "BAAI/bge-m3"
        assert expected_dimension == semantic_search.EMBEDDING_DIM
        assert expected_dimension == vector_index_simple.EMBEDDING_DIM

    def test_model_loads_offline(self) -> None:
        """目标模型配置必须声明长上下文能力，支撑离线缓存加载。"""
        search_config, _, _ = _reload_search_modules()

        model = search_config.EMBEDDING_MODEL
        assert model["name"] == "BAAI/bge-m3"
        assert int(model["metadata"].get("max_seq_length", 0)) >= 8192
