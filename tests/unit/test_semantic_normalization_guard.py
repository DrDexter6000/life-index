#!/usr/bin/env python3
"""
Unit tests for vector normalization guard (E0605).

Tests cover:
- `_assert_normalized_sample` directly: catches unnormalized vectors
- `_assert_normalized_sample` directly: passes for normalized vectors
- `search_semantic` integration: unnormalized index vectors trigger E0605 error
- `search_semantic` integration: normalized vectors pass without error
"""

import logging

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from tools.lib.vector_guards import (
    VectorNotNormalizedError,
    _assert_normalized_sample,
    check_vector_index_normalized,
)


# ---------------------------------------------------------------------------
# Helper: build a list of unit-normalized random vectors
# ---------------------------------------------------------------------------


def _make_normalized_vectors(count: int, dim: int = 8) -> list[list[float]]:
    """Return *count* random unit-normalized vectors of dimension *dim*."""
    vecs = []
    for _ in range(count):
        v = np.random.randn(dim).astype(np.float64)
        v /= np.linalg.norm(v)
        vecs.append(v.tolist())
    return vecs


def _make_unnormalized_vectors(
    count: int, dim: int = 8, norm_target: float = 2.5
) -> list[list[float]]:
    """Return vectors whose norms equal *norm_target* instead of 1.0."""
    vecs = []
    for _ in range(count):
        v = np.random.randn(dim).astype(np.float64)
        v = v / np.linalg.norm(v) * norm_target
        vecs.append(v.tolist())
    return vecs


# ===================================================================
# Direct guard tests
# ===================================================================


class TestAssertNormalizedSampleDirect:
    """Tests for _assert_normalized_sample in isolation."""

    def test_normalized_vectors_pass(self) -> None:
        """Normal unit vectors must not raise."""
        vecs = _make_normalized_vectors(10)
        # Should not raise
        _assert_normalized_sample(vecs)

    def test_unnormalized_vectors_raise(self) -> None:
        """Vectors with norm != 1.0 must raise VectorNotNormalizedError."""
        vecs = _make_unnormalized_vectors(10, norm_target=2.5)
        with pytest.raises(VectorNotNormalizedError) as exc_info:
            _assert_normalized_sample(vecs)
        assert exc_info.value.details
        assert exc_info.value.details[0]["norm"] != pytest.approx(1.0, abs=1e-6)

    def test_empty_vectors_pass(self) -> None:
        """Empty vector list must not raise."""
        _assert_normalized_sample([])

    def test_single_normalized_vector_passes(self) -> None:
        """Single normalized vector must not raise."""
        vecs = _make_normalized_vectors(1)
        _assert_normalized_sample(vecs)

    def test_single_unnormalized_vector_raises(self) -> None:
        """Single unnormalized vector must raise."""
        vecs = _make_unnormalized_vectors(1, norm_target=3.0)
        with pytest.raises(VectorNotNormalizedError):
            _assert_normalized_sample(vecs)

    def test_mixed_vectors_raise(self) -> None:
        """If at least one sampled vector is bad, raise."""
        normalized = _make_normalized_vectors(3)
        # Corrupt the first vector
        normalized[0] = [x * 2.5 for x in normalized[0]]
        with pytest.raises(VectorNotNormalizedError):
            _assert_normalized_sample(normalized)

    def test_error_logged_at_error_level(self, caplog: pytest.LogCaptureFixture) -> None:
        """On failure, must log at ERROR level."""
        vecs = _make_unnormalized_vectors(5, norm_target=2.5)
        with caplog.at_level(logging.ERROR, logger="tools.lib.vector_guards"):
            with pytest.raises(VectorNotNormalizedError):
                _assert_normalized_sample(vecs)
        assert any("E0605" in r.message for r in caplog.records)


# ===================================================================
# check_vector_index_normalized integration tests
# ===================================================================


class TestCheckVectorIndexNormalized:
    """Tests for check_vector_index_normalized wrapper."""

    def test_passes_with_valid_index(self) -> None:
        idx_vectors = {
            f"path_{i}.md": {"embedding": v, "date": "2026-01-01", "hash": "abc"}
            for i, v in enumerate(_make_normalized_vectors(5))
        }
        # Should not raise
        check_vector_index_normalized(idx_vectors)

    def test_raises_with_bad_vectors(self) -> None:
        idx_vectors = {
            f"path_{i}.md": {"embedding": v, "date": "2026-01-01", "hash": "abc"}
            for i, v in enumerate(_make_unnormalized_vectors(5, norm_target=2.5))
        }
        with pytest.raises(VectorNotNormalizedError):
            check_vector_index_normalized(idx_vectors)

    def test_empty_index_passes(self) -> None:
        check_vector_index_normalized({})


# ===================================================================
# search_semantic integration tests (mocked)
# ===================================================================


class TestSearchSemanticNormalizationGuard:
    """Integration tests: guard wired into search_semantic."""

    @pytest.fixture(autouse=True)
    def _reset_singletons(self) -> None:
        """Reset SharedEmbeddingModel singleton between tests."""
        from tools.lib.embedding_backends import SharedEmbeddingModel

        SharedEmbeddingModel._instance = None
        SharedEmbeddingModel._model = None
        SharedEmbeddingModel._backend = None
        SharedEmbeddingModel._model_verified = False

    def test_unnormalized_vector_triggers_error(self) -> None:
        """When index contains unnormalized vectors, search returns E0605 error."""
        from tools.search_journals.semantic import search_semantic

        dim = 8
        bad_vec = np.random.randn(dim).astype(np.float64)
        bad_vec = bad_vec / np.linalg.norm(bad_vec) * 2.5  # norm=2.5
        query_vec = np.random.randn(dim).astype(np.float64)
        query_vec /= np.linalg.norm(query_vec)

        mock_index = MagicMock()
        mock_index.vectors = {
            "test/path.md": {
                "embedding": bad_vec.tolist(),
                "date": "2026-01-01",
                "hash": "abc",
            }
        }

        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [query_vec.tolist()]

        with (
            patch("tools.lib.vector_index_simple.get_model", return_value=mock_model),
            patch("tools.lib.vector_index_simple.get_index", return_value=mock_index),
        ):
            results, perf = search_semantic("test query")

        # Should return exactly one element: the error dict
        assert len(results) == 1
        error_result = results[0]
        assert error_result["success"] is False
        assert error_result["error"]["code"] == "E0605"

    def test_normalized_vectors_pass(self) -> None:
        """When index contains normalized vectors, search completes normally."""
        from tools.search_journals.semantic import search_semantic

        dim = 8
        good_vec = np.random.randn(dim).astype(np.float64)
        good_vec /= np.linalg.norm(good_vec)
        query_vec = np.random.randn(dim).astype(np.float64)
        query_vec /= np.linalg.norm(query_vec)

        mock_index = MagicMock()
        mock_index.vectors = {
            "test/path.md": {
                "embedding": good_vec.tolist(),
                "date": "2026-01-01",
                "hash": "abc",
            }
        }
        mock_index.search.return_value = [("test/path.md", 0.95)]
        mock_index.get.return_value = {
            "embedding": good_vec.tolist(),
            "date": "2026-01-01",
            "hash": "abc",
        }

        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [query_vec.tolist()]

        with (
            patch("tools.lib.vector_index_simple.get_model", return_value=mock_model),
            patch("tools.lib.vector_index_simple.get_index", return_value=mock_index),
            patch(
                "tools.search_journals.semantic.enrich_semantic_result",
                side_effect=lambda x, **kw: x,
            ),
            patch(
                "tools.search_journals.semantic.merge_journal_path_fields",
                side_effect=lambda d, *a, **kw: d,
            ),
        ):
            results, perf = search_semantic("test query")

        # Should return search results, not an error
        assert len(results) >= 1
        if results:
            assert "success" not in results[0] or results[0].get("success") is not False

    def test_error_response_has_recovery_strategy(self) -> None:
        """E0605 error response must include recovery_strategy."""
        from tools.search_journals.semantic import search_semantic

        dim = 8
        bad_vec = np.random.randn(dim).astype(np.float64)
        bad_vec = bad_vec / np.linalg.norm(bad_vec) * 2.5
        query_vec = np.random.randn(dim).astype(np.float64)
        query_vec /= np.linalg.norm(query_vec)

        mock_index = MagicMock()
        mock_index.vectors = {
            "test/path.md": {
                "embedding": bad_vec.tolist(),
                "date": "2026-01-01",
                "hash": "abc",
            }
        }

        mock_model = MagicMock()
        mock_model.load.return_value = True
        mock_model.encode.return_value = [query_vec.tolist()]

        with (
            patch("tools.lib.vector_index_simple.get_model", return_value=mock_model),
            patch("tools.lib.vector_index_simple.get_index", return_value=mock_index),
        ):
            results, perf = search_semantic("test query")

        error_resp = results[0]
        assert error_resp["error"]["recovery_strategy"] == "fail"
        assert "index --rebuild" in error_resp["error"]["suggestion"]
