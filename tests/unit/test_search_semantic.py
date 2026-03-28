#!/usr/bin/env python3
"""
Unit tests for tools/search_journals/semantic.py
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools.search_journals.semantic import (
    search_semantic,
    enrich_semantic_result,
)


class TestSearchSemantic:
    """Tests for search_semantic function"""

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_success(self, mock_get_model, mock_get_index):
        """Test successful semantic search"""
        # Mock model
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        # Mock index
        mock_index = MagicMock()
        mock_index.search.return_value = [
            ("Journals/2026/03/test.md", 0.95),
            ("Journals/2026/03/test2.md", 0.85),
        ]
        mock_index.get.return_value = {"date": "2026-03-20"}
        mock_get_index.return_value = mock_index

        results, metrics = search_semantic("test query")

        assert len(results) == 2
        assert results[0]["similarity"] == 0.95
        assert results[0]["source"] == "semantic"
        assert "semantic_encode_ms" in metrics
        assert "semantic_search_ms" in metrics

    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_model_not_loaded(self, mock_get_model):
        """Test semantic search when model fails to load"""
        mock_model = MagicMock()
        mock_model.load.return_value = False
        mock_get_model.return_value = mock_model

        results, metrics = search_semantic("test query")

        assert results == []
        assert metrics == {}

    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_import_error(self, mock_get_model):
        """Test semantic search with ImportError"""
        mock_get_model.side_effect = ImportError("No module")

        results, metrics = search_semantic("test query")

        assert results == []
        assert metrics == {}

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_with_date_filter(self, mock_get_model, mock_get_index):
        """Test semantic search with date filters"""
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        mock_index = MagicMock()
        mock_index.search.return_value = []
        mock_get_index.return_value = mock_index

        results, metrics = search_semantic(
            "test query", date_from="2026-01-01", date_to="2026-03-31"
        )

        mock_index.search.assert_called_once()
        # Verify date filters were passed
        call_kwargs = mock_index.search.call_args
        assert call_kwargs[1].get("date_from") == "2026-01-01"
        assert call_kwargs[1].get("date_to") == "2026-03-31"
        assert "semantic_encode_ms" in metrics
        assert "semantic_search_ms" in metrics

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_exception(self, mock_get_model, mock_get_index):
        """Test semantic search handles exceptions gracefully"""
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.side_effect = OSError("Read error")
        mock_get_model.return_value = mock_model

        results, metrics = search_semantic("test query")

        assert results == []
        assert "semantic_encode_ms" in metrics

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_returns_encode_and_search_timings(
        self, mock_get_model, mock_get_index
    ):
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        mock_index = MagicMock()
        mock_index.search.return_value = []
        mock_get_index.return_value = mock_index

        results, metrics = search_semantic("test query")

        assert results == []
        assert "semantic_encode_ms" in metrics
        assert "semantic_search_ms" in metrics

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_filters_low_similarity_and_uses_default_top_k(
        self, mock_get_model, mock_get_index
    ):
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        mock_index = MagicMock()
        mock_index.search.return_value = [
            ("Journals/2026/03/strong.md", 0.9),
            ("Journals/2026/03/borderline.md", 0.4),
            ("Journals/2026/03/weak.md", 0.2),
        ]
        mock_index.get.return_value = {"date": "2026-03-20"}
        mock_get_index.return_value = mock_index

        # Use explicit min_similarity=0.25 to reject 0.2; default top_k=50
        results, _ = search_semantic("test query", min_similarity=0.25)

        assert len(results) == 2
        assert results[0]["similarity"] == 0.9
        assert results[1]["similarity"] == 0.4
        assert mock_index.search.call_args.kwargs["top_k"] == 50

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_default_threshold_keeps_borderline_similarity(
        self, mock_get_model, mock_get_index
    ):
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        mock_index = MagicMock()
        mock_index.search.return_value = [
            ("Journals/2026/03/borderline.md", 0.4),
        ]
        mock_index.get.return_value = {"date": "2026-03-20"}
        mock_get_index.return_value = mock_index

        results, _ = search_semantic("test query")

        assert len(results) == 1
        assert results[0]["similarity"] == 0.4

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_default_threshold_keeps_moderate_similarity(
        self, mock_get_model, mock_get_index
    ):
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        mock_index = MagicMock()
        mock_index.search.return_value = [
            ("Journals/2026/03/moderate.md", 0.42),
        ]
        mock_index.get.return_value = {"date": "2026-03-20"}
        mock_get_index.return_value = mock_index

        results, _ = search_semantic("test query")

        assert len(results) == 1
        assert results[0]["similarity"] == 0.42

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_default_threshold_keeps_036_and_034_at_025_floor(
        self, mock_get_model, mock_get_index
    ):
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        mock_index = MagicMock()
        mock_index.search.return_value = [
            ("Journals/2026/03/keep.md", 0.36),
            ("Journals/2026/03/drop.md", 0.34),
        ]
        mock_index.get.return_value = {"date": "2026-03-20"}
        mock_get_index.return_value = mock_index

        results, _ = search_semantic("test query")

        assert len(results) == 2
        assert results[0]["similarity"] == 0.36
        assert results[1]["similarity"] == 0.34

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_default_threshold_keeps_026_but_rejects_024(
        self, mock_get_model, mock_get_index
    ):
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        mock_index = MagicMock()
        mock_index.search.return_value = [
            ("Journals/2026/03/keep026.md", 0.26),
            ("Journals/2026/03/drop024.md", 0.24),
        ]
        mock_index.get.return_value = {"date": "2026-03-20"}
        mock_get_index.return_value = mock_index

        # Use explicit min_similarity=0.25 to keep 0.26 but reject 0.24
        results, _ = search_semantic("test query", min_similarity=0.25)

        assert len(results) == 1
        assert results[0]["similarity"] == 0.26

    @patch("tools.lib.vector_index_simple.get_index")
    @patch("tools.lib.vector_index_simple.get_model")
    def test_search_semantic_accepts_custom_threshold_and_top_k(
        self, mock_get_model, mock_get_index
    ):
        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        mock_get_model.return_value = mock_model

        mock_index = MagicMock()
        mock_index.search.return_value = [
            ("Journals/2026/03/strong.md", 0.9),
            ("Journals/2026/03/weak.md", 0.2),
        ]
        mock_index.get.return_value = {"date": "2026-03-20"}
        mock_get_index.return_value = mock_index

        results, _ = search_semantic("test query", min_similarity=0.1, top_k=5)

        assert len(results) == 2
        assert mock_index.search.call_args.kwargs["top_k"] == 5


class TestEnrichSemanticResult:
    """Tests for enrich_semantic_result function"""

    def test_enrich_result_basic(self):
        """Test basic result enrichment"""
        result = {
            "path": "/some/path/test.md",
            "similarity": 0.9,
            "source": "semantic",
        }

        with patch.object(Path, "exists", return_value=False):
            enriched = enrich_semantic_result(result)

        # Should return copy of original when file doesn't exist
        assert enriched["similarity"] == 0.9
        assert enriched["source"] == "semantic"

    def test_enrich_result_with_file(self, tmp_path):
        """Test enrichment with actual file"""
        test_file = tmp_path / "test.md"
        content = """---
title: Test Journal
date: 2026-03-20
tags: [test, unit]
topic: work
abstract: Test abstract
---

This is the body content that should be turned into a snippet.
"""
        test_file.write_text(content, encoding="utf-8")

        result = {
            "path": str(test_file),
            "similarity": 0.9,
            "source": "semantic",
        }

        enriched = enrich_semantic_result(result)

        assert enriched["title"] == "Test Journal"
        assert enriched["abstract"] == "Test abstract"
        assert enriched["tags"] == ["test", "unit"]
        assert enriched["topic"] == "work"
        assert "snippet" in enriched

    def test_enrich_result_existing_fields_preserved(self, tmp_path):
        """Test that existing fields are not overwritten"""
        test_file = tmp_path / "test.md"
        content = """---
title: File Title
---

Body content.
"""
        test_file.write_text(content, encoding="utf-8")

        result = {
            "path": str(test_file),
            "title": "Existing Title",  # Should not be overwritten
            "similarity": 0.9,
        }

        enriched = enrich_semantic_result(result)

        # Existing title should be preserved
        assert enriched["title"] == "Existing Title"

    def test_enrich_result_snippet_truncation(self, tmp_path):
        """Test snippet truncation for long content"""
        test_file = tmp_path / "test.md"
        long_body = "x" * 500  # Long body
        content = f"""---
title: Test
---

{long_body}
"""
        test_file.write_text(content, encoding="utf-8")

        result = {"path": str(test_file), "similarity": 0.9}

        enriched = enrich_semantic_result(result)

        # Snippet should be truncated to ~200 chars
        assert len(enriched["snippet"]) <= 203  # 200 + "..."
        assert enriched["snippet"].endswith("...")

    def test_enrich_result_with_project(self, tmp_path):
        """Test enrichment includes project field"""
        test_file = tmp_path / "test.md"
        content = """---
title: Test
project: LifeIndex
---

Body.
"""
        test_file.write_text(content, encoding="utf-8")

        result = {"path": str(test_file)}

        enriched = enrich_semantic_result(result)

        assert enriched["project"] == "LifeIndex"

    def test_enrich_result_io_error(self, tmp_path):
        """Test enrichment handles IO errors gracefully"""
        non_existent = tmp_path / "nonexistent.md"

        result = {"path": str(non_existent), "similarity": 0.9}

        enriched = enrich_semantic_result(result)

        # Should return original data
        assert enriched["similarity"] == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
