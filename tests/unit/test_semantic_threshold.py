"""Tests for semantic threshold: absolute floor + adaptive baseline."""

import sqlite3
from unittest.mock import patch

import pytest


class TestEffectiveSemanticThreshold:
    """Test get_effective_semantic_threshold() logic."""

    def test_baseline_below_floor_uses_floor(self, tmp_path):
        """baseline_p25 = 0.30 → threshold = max(0.40, 0.32) = 0.40"""
        db_path = tmp_path / "journals_fts.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO index_meta VALUES ('semantic_baseline_p25', '0.300000')")
        conn.commit()
        conn.close()

        import tools.search_journals.semantic_pipeline as semantic_pipeline

        with patch.object(semantic_pipeline, "get_fts_db_path", lambda: db_path):
            threshold = semantic_pipeline.get_effective_semantic_threshold(
                absolute_floor=0.40
            )
        assert threshold == pytest.approx(0.40, abs=0.001)

    def test_baseline_above_floor_uses_adaptive(self, tmp_path):
        """baseline_p25 = 0.42 → threshold = max(0.40, 0.44) = 0.44"""
        db_path = tmp_path / "journals_fts.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO index_meta VALUES ('semantic_baseline_p25', '0.420000')")
        conn.commit()
        conn.close()

        import tools.search_journals.semantic_pipeline as semantic_pipeline

        with patch.object(semantic_pipeline, "get_fts_db_path", lambda: db_path):
            threshold = semantic_pipeline.get_effective_semantic_threshold(
                absolute_floor=0.40
            )
        assert threshold == pytest.approx(0.44, abs=0.001)

    def test_no_baseline_falls_back_to_floor(self, tmp_path):
        """baseline_p25 not written (old index) → fallback to absolute floor 0.40"""
        db_path = tmp_path / "journals_fts.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        conn.close()

        import tools.search_journals.semantic_pipeline as semantic_pipeline

        with patch.object(semantic_pipeline, "get_fts_db_path", lambda: db_path):
            threshold = semantic_pipeline.get_effective_semantic_threshold(
                absolute_floor=0.40
            )
        assert threshold == pytest.approx(0.40, abs=0.001)

    def test_no_db_file_falls_back_to_floor(self, tmp_path):
        """FTS_DB_PATH doesn't exist → fallback to absolute floor"""
        db_path = tmp_path / "nonexistent.db"

        import tools.search_journals.semantic_pipeline as semantic_pipeline

        with patch.object(semantic_pipeline, "get_fts_db_path", lambda: db_path):
            threshold = semantic_pipeline.get_effective_semantic_threshold(
                absolute_floor=0.40
            )
        assert threshold == pytest.approx(0.40, abs=0.001)


class TestComputeSemanticBaseline:
    """Test compute_semantic_baseline() stability."""

    def test_stable_p25(self):
        """Two calls produce P25 values within 0.01 of each other."""
        import numpy as np

        from tools.lib.semantic_baseline import compute_semantic_baseline

        rng = np.random.default_rng(42)
        vectors = {}
        for i in range(100):
            vec = rng.standard_normal(32).astype(np.float32)
            vec = vec / (np.linalg.norm(vec) + 1e-8)
            vectors[f"doc_{i}.md"] = {"embedding": vec.tolist(), "date": "2026-03-01"}

        p25_a = compute_semantic_baseline(vectors, sample_size=30, seed=42)
        p25_b = compute_semantic_baseline(vectors, sample_size=30, seed=42)
        assert abs(p25_a - p25_b) < 0.01
        assert p25_a > 0.0

    def test_empty_vectors_returns_zero(self):
        """Empty vectors dict returns 0.0."""
        from tools.lib.semantic_baseline import compute_semantic_baseline

        assert compute_semantic_baseline({}) == 0.0

    def test_few_vectors_returns_zero(self):
        """Fewer than 5 vectors returns 0.0 (insufficient data)."""
        from tools.lib.semantic_baseline import compute_semantic_baseline

        vectors = {"doc.md": {"embedding": [0.1] * 32, "date": "2026-03-01"}}
        assert compute_semantic_baseline(vectors) == 0.0
