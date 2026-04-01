#!/usr/bin/env python3
"""Refactor tests for shared embedding model and normalization SSOT."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestSharedEmbeddingModelRefactor:
    def test_semantic_and_simple_import_same_shared_model_class(self) -> None:
        from tools.lib.embedding_backends import SharedEmbeddingModel
        from tools.lib.semantic_search import EmbeddingModel as SemanticEmbeddingModel
        from tools.lib.vector_index_simple import EmbeddingModel as SimpleEmbeddingModel

        assert SemanticEmbeddingModel is SharedEmbeddingModel
        assert SimpleEmbeddingModel is SharedEmbeddingModel

    def test_encode_normalizes_at_shared_entrypoint(self) -> None:
        from tools.lib.embedding_backends import SharedEmbeddingModel

        SharedEmbeddingModel._instance = None
        SharedEmbeddingModel._model = MagicMock()
        SharedEmbeddingModel._backend = "sentence-transformers"
        SharedEmbeddingModel._model.encode.return_value = [[3.0, 4.0]]

        model = SharedEmbeddingModel()
        encoded = model.encode(["hello"])

        assert encoded == [[0.6, 0.8]]

    def test_simple_vector_index_add_keeps_pre_normalized_embedding(self) -> None:
        from tools.lib.vector_index_simple import SimpleVectorIndex

        index = SimpleVectorIndex()
        index.vectors = {}
        embedding = [0.6, 0.8]

        index.add("Journals/2026/04/test.md", embedding, "2026-04-01", "hash123")

        stored = index.vectors["Journals/2026/04/test.md"]
        assert stored["embedding"] == embedding
        assert stored["normalized"] is True
