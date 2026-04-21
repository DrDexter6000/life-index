#!/usr/bin/env python3
"""
Unit tests for extracted sub-functions from merge_and_rank_results_hybrid.

Each test covers one private sub-function with minimal mock data.
These tests verify the refactored sub-functions produce correct results
independently of the full search pipeline.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestBuildHybridCandidates:
    """Tests for _build_hybrid_candidates."""

    def test_empty_inputs_return_empty(self):
        from tools.search_journals.ranking import _build_hybrid_candidates

        scored, fts_paths, sem_paths = _build_hybrid_candidates([], [])
        assert scored == {}
        assert fts_paths == []
        assert sem_paths == []

    def test_fts_results_populate_candidates(self):
        from tools.search_journals.ranking import _build_hybrid_candidates

        l3 = [
            {"path": "/a.md", "title": "Alpha", "relevance": 80},
            {"path": "/b.md", "title": "Beta", "relevance": 50},
        ]
        with patch("tools.search_journals.ranking.enrich_semantic_result") as mock:
            mock.side_effect = lambda r: {"path": r["path"], "title": r["title"]}
            scored, fts_paths, sem_paths = _build_hybrid_candidates(l3, [])

        assert len(scored) == 2
        assert scored["/a.md"]["fts_score"] == 80.0
        assert scored["/b.md"]["fts_score"] == 50.0
        assert len(fts_paths) == 2
        # Higher relevance first
        assert fts_paths[0] == "/a.md"
        assert sem_paths == []

    def test_fts_title_match_bonus(self):
        from tools.search_journals.ranking import _build_hybrid_candidates
        from tools.lib.search_constants import SCORE_TITLE_MATCH_BONUS

        l3 = [{"path": "/a.md", "title": "A", "relevance": 60, "title_match": True}]
        with patch("tools.search_journals.ranking.enrich_semantic_result") as mock:
            mock.return_value = {"path": "/a.md", "title": "A"}
            scored, _, _ = _build_hybrid_candidates(l3, [])

        assert scored["/a.md"]["fts_score"] == 60.0 + SCORE_TITLE_MATCH_BONUS

    def test_semantic_results_populate_candidates(self):
        from tools.search_journals.ranking import _build_hybrid_candidates

        sem = [
            {"path": "/x.md", "similarity": 0.9},
            {"path": "/y.md", "similarity": 0.7},
        ]
        with patch("tools.search_journals.ranking.enrich_semantic_result") as mock:
            mock.side_effect = lambda r: {"path": r["path"]}
            scored, fts_paths, sem_paths = _build_hybrid_candidates([], sem)

        assert len(scored) == 2
        assert scored["/x.md"]["semantic_score"] == 90.0
        assert scored["/x.md"]["tier"] == 4
        assert len(sem_paths) == 2
        assert sem_paths[0] == "/x.md"

    def test_overlap_deduplication_merges_scores(self):
        from tools.search_journals.ranking import _build_hybrid_candidates

        l3 = [{"path": "/shared.md", "title": "S", "relevance": 70}]
        sem = [{"path": "/shared.md", "similarity": 0.8}]
        with patch("tools.search_journals.ranking.enrich_semantic_result") as mock:
            mock.return_value = {"path": "/shared.md", "title": "S"}
            scored, _, _ = _build_hybrid_candidates(l3, sem)

        assert len(scored) == 1
        assert scored["/shared.md"]["fts_score"] == 70.0
        assert scored["/shared.md"]["semantic_score"] == 80.0
        assert scored["/shared.md"]["tier"] == 3  # FTS tier preserved


class TestComputeWeightedRRFScores:
    """Tests for _compute_weighted_rrf_scores."""

    def test_empty_paths_return_empty(self):
        from tools.search_journals.ranking import _compute_weighted_rrf_scores

        scores, event = _compute_weighted_rrf_scores([], [], fts_weight=1.0, semantic_weight=0.6)
        assert scores == {}
        assert event is None

    def test_fts_only_scoring(self):
        from tools.search_journals.ranking import _compute_weighted_rrf_scores
        from tools.lib.search_constants import RRF_K

        fts_paths = ["/a.md", "/b.md"]
        scores, event = _compute_weighted_rrf_scores(
            fts_paths,
            [],
            fts_weight=1.0,
            semantic_weight=0.6,
        )

        assert len(scores) == 2
        assert scores["/a.md"] == pytest.approx(1.0 / (RRF_K + 1))
        assert scores["/b.md"] == pytest.approx(1.0 / (RRF_K + 2))

    def test_semantic_only_scoring(self):
        from tools.search_journals.ranking import _compute_weighted_rrf_scores
        from tools.lib.search_constants import RRF_K

        sem_paths = ["/x.md"]
        scores, event = _compute_weighted_rrf_scores(
            [],
            sem_paths,
            fts_weight=1.0,
            semantic_weight=0.6,
        )

        assert scores["/x.md"] == pytest.approx(0.6 / (RRF_K + 1))

    def test_combined_scores_additive(self):
        from tools.search_journals.ranking import _compute_weighted_rrf_scores
        from tools.lib.search_constants import RRF_K

        # Same path appears in both lists at rank 1
        fts_paths = ["/shared.md"]
        sem_paths = ["/shared.md"]
        scores, _ = _compute_weighted_rrf_scores(
            fts_paths,
            sem_paths,
            fts_weight=1.0,
            semantic_weight=0.6,
        )

        expected = 1.0 / (RRF_K + 1) + 0.6 / (RRF_K + 1)
        assert scores["/shared.md"] == pytest.approx(expected)

    def test_small_n_triggers_event(self):
        from tools.search_journals.ranking import _compute_weighted_rrf_scores

        # 3 results < threshold 8
        fts_paths = ["/a.md", "/b.md", "/c.md"]
        scores, event = _compute_weighted_rrf_scores(
            fts_paths,
            [],
            fts_weight=1.0,
            semantic_weight=0.6,
        )

        assert event is not None
        assert event["event"] == "rrf_small_n_fallback"
        assert event["n"] == 3
        assert event["fallback_threshold"] == 8

    def test_large_n_no_event(self):
        from tools.search_journals.ranking import _compute_weighted_rrf_scores

        fts_paths = [f"/{i}.md" for i in range(10)]
        scores, event = _compute_weighted_rrf_scores(
            fts_paths,
            [],
            fts_weight=1.0,
            semantic_weight=0.6,
        )

        assert event is None


class TestAddNonRRFCandidates:
    """Tests for _add_non_rrf_candidates."""

    def test_rrf_scores_applied(self):
        from tools.search_journals.ranking import _add_non_rrf_candidates

        scored = {
            "/a.md": {
                "data": {"path": "/a.md"},
                "fts_score": 80.0,
                "semantic_score": 0.0,
                "final_score": 0.0,
                "rrf_score": 0.0,
                "tier": 3,
                "has_rrf": False,
            }
        }
        rrf_scores = {"/a.md": 0.0164}
        _add_non_rrf_candidates(scored, [], [], rrf_scores, None, None, None)

        assert scored["/a.md"]["final_score"] == 0.0164
        assert scored["/a.md"]["rrf_score"] == 0.0164
        assert scored["/a.md"]["has_rrf"] is True

    def test_l2_candidates_added(self):
        from tools.search_journals.ranking import _add_non_rrf_candidates
        from tools.lib.search_constants import SCORE_L2_BASE

        scored = {}
        l2 = [{"path": "/l2.md", "title": "L2 Doc", "metadata": {}}]
        _add_non_rrf_candidates(scored, [], l2, {}, None, None, None)

        assert "/l2.md" in scored
        assert scored["/l2.md"]["final_score"] == float(SCORE_L2_BASE)
        assert scored["/l2.md"]["tier"] == 2
        assert scored["/l2.md"]["has_rrf"] is False

    def test_l1_candidates_added(self):
        from tools.search_journals.ranking import _add_non_rrf_candidates
        from tools.lib.search_constants import SCORE_L1_BASE

        scored = {}
        l1 = [{"path": "/l1.md", "date": "2026-03-14"}]
        _add_non_rrf_candidates(scored, l1, [], {}, None, None, None)

        assert "/l1.md" in scored
        assert scored["/l1.md"]["final_score"] == float(SCORE_L1_BASE)
        assert scored["/l1.md"]["tier"] == 1

    def test_l2_deduplicated_when_already_in_scored(self):
        from tools.search_journals.ranking import _add_non_rrf_candidates

        scored = {
            "/shared.md": {
                "data": {"path": "/shared.md"},
                "fts_score": 70.0,
                "semantic_score": 0.0,
                "final_score": 0.0,
                "rrf_score": 0.0,
                "tier": 3,
                "has_rrf": False,
            }
        }
        l2 = [{"path": "/shared.md", "title": "Shared", "metadata": {}}]
        _add_non_rrf_candidates(scored, [], l2, {}, None, None, None)

        # L2 should NOT overwrite existing entry
        assert scored["/shared.md"]["fts_score"] == 70.0

    def test_topic_boost_applied(self):
        from tools.search_journals.ranking import _add_non_rrf_candidates
        from tools.lib.search_constants import TOPIC_HINT_BOOST

        scored = {
            "/a.md": {
                "data": {"path": "/a.md", "topic": "work"},
                "fts_score": 50.0,
                "semantic_score": 0.0,
                "final_score": 0.01,
                "rrf_score": 0.0,
                "tier": 3,
                "has_rrf": False,
            }
        }
        _add_non_rrf_candidates(scored, [], [], {}, None, None, ["work"])

        assert scored["/a.md"]["final_score"] == pytest.approx(0.01 * TOPIC_HINT_BOOST)

    def test_no_topic_boost_when_not_matching(self):
        from tools.search_journals.ranking import _add_non_rrf_candidates

        scored = {
            "/a.md": {
                "data": {"path": "/a.md", "topic": "life"},
                "fts_score": 50.0,
                "semantic_score": 0.0,
                "final_score": 0.01,
                "rrf_score": 0.0,
                "tier": 3,
                "has_rrf": False,
            }
        }
        _add_non_rrf_candidates(scored, [], [], {}, None, None, ["work"])

        assert scored["/a.md"]["final_score"] == 0.01


class TestApplyHybridThresholds:
    """Tests for _apply_hybrid_thresholds."""

    def _make_entry(
        self,
        path: str,
        *,
        has_rrf: bool = True,
        final_score: float = 0.02,
        fts_score: float = 0.0,
        semantic_score: float = 0.0,
        tier: int = 3,
    ) -> dict:
        return {
            "data": {"path": path},
            "fts_score": fts_score,
            "semantic_score": semantic_score,
            "final_score": final_score,
            "rrf_score": final_score if has_rrf else 0.0,
            "tier": tier,
            "has_rrf": has_rrf,
        }

    def test_all_pass_with_low_thresholds(self):
        from tools.search_journals.ranking import _apply_hybrid_thresholds

        scored = {
            "/a.md": self._make_entry("/a.md", final_score=0.03),
            "/b.md": self._make_entry("/b.md", final_score=0.02),
        }
        result = _apply_hybrid_thresholds(
            scored,
            min_rrf_score=0.0,
            min_non_rrf_score=0.0,
            max_results=10,
        )
        assert len(result) == 2

    def test_high_threshold_filters_all(self):
        from tools.search_journals.ranking import _apply_hybrid_thresholds

        scored = {
            "/a.md": self._make_entry("/a.md", final_score=0.01),
        }
        result = _apply_hybrid_thresholds(
            scored,
            min_rrf_score=0.99,
            min_non_rrf_score=0.99,
            max_results=10,
        )
        assert len(result) == 0

    def test_max_results_limits_output(self):
        from tools.search_journals.ranking import _apply_hybrid_thresholds

        scored = {f"/{i}.md": self._make_entry(f"/{i}.md", final_score=0.03) for i in range(10)}
        result = _apply_hybrid_thresholds(
            scored,
            min_rrf_score=0.0,
            min_non_rrf_score=0.0,
            max_results=3,
        )
        assert len(result) == 3

    def test_backfill_on_empty_thresholded(self):
        from tools.search_journals.ranking import _apply_hybrid_thresholds

        # Has retrieval signal but all filtered by threshold
        scored = {
            "/a.md": self._make_entry("/a.md", final_score=0.001, fts_score=50.0),
        }
        result = _apply_hybrid_thresholds(
            scored,
            min_rrf_score=0.99,
            min_non_rrf_score=0.99,
            max_results=10,
        )
        # Backfill should return 1 result
        assert len(result) == 1
        assert result[0]["data"]["path"] == "/a.md"

    def test_no_backfill_without_retrieval_signal(self):
        from tools.search_journals.ranking import _apply_hybrid_thresholds

        # No fts_score or semantic_score => no retrieval signal => no backfill
        scored = {
            "/a.md": self._make_entry(
                "/a.md",
                final_score=0.001,
                has_rrf=False,
                tier=1,
            ),
        }
        result = _apply_hybrid_thresholds(
            scored,
            min_rrf_score=0.99,
            min_non_rrf_score=0.99,
            max_results=10,
        )
        assert len(result) == 0


class TestFinalizeHybridResults:
    """Tests for _finalize_hybrid_results."""

    def _make_item(
        self,
        path: str,
        *,
        has_rrf: bool = True,
        final_score: float = 0.02,
        fts_score: float = 80.0,
        semantic_score: float = 0.0,
    ) -> dict:
        return {
            "data": {"path": path, "title": "Test"},
            "fts_score": fts_score,
            "semantic_score": semantic_score,
            "final_score": final_score,
            "rrf_score": final_score if has_rrf else 0.0,
            "tier": 3,
            "has_rrf": has_rrf,
        }

    def test_empty_input_returns_empty(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        with patch("tools.search_journals.ranking.init_metadata_cache"):
            result = _finalize_hybrid_results([], explain=False, rrf_small_n_event=None)
        assert result == []

    def test_search_rank_assigned(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        items = [self._make_item("/a.md"), self._make_item("/b.md")]
        with patch("tools.search_journals.ranking.init_metadata_cache") as mock_init:
            mock_conn = MagicMock()
            mock_init.return_value = mock_conn
            result = _finalize_hybrid_results(items, explain=False, rrf_small_n_event=None)

        assert result[0]["search_rank"] == 1
        assert result[1]["search_rank"] == 2

    def test_score_fields_populated(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        items = [self._make_item("/a.md", fts_score=80.0, semantic_score=90.0)]
        with patch("tools.search_journals.ranking.init_metadata_cache") as mock_init:
            mock_conn = MagicMock()
            mock_init.return_value = mock_conn
            result = _finalize_hybrid_results(items, explain=False, rrf_small_n_event=None)

        assert result[0]["fts_score"] == 80.0
        assert result[0]["semantic_score"] == 90.0
        assert "final_score" in result[0]
        assert "rrf_score" in result[0]

    def test_source_field_fts_and_semantic(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        items = [self._make_item("/a.md", fts_score=80.0, semantic_score=90.0)]
        with patch("tools.search_journals.ranking.init_metadata_cache") as mock_init:
            mock_conn = MagicMock()
            mock_init.return_value = mock_conn
            result = _finalize_hybrid_results(items, explain=False, rrf_small_n_event=None)

        assert result[0]["source"] == "fts,semantic"

    def test_source_field_none(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        items = [self._make_item("/a.md", fts_score=0.0, semantic_score=0.0)]
        with patch("tools.search_journals.ranking.init_metadata_cache") as mock_init:
            mock_conn = MagicMock()
            mock_init.return_value = mock_conn
            result = _finalize_hybrid_results(items, explain=False, rrf_small_n_event=None)

        assert result[0]["source"] == "none"

    def test_explain_field_when_requested(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        items = [self._make_item("/a.md", fts_score=80.0, semantic_score=90.0)]
        with patch("tools.search_journals.ranking.init_metadata_cache") as mock_init:
            mock_conn = MagicMock()
            mock_init.return_value = mock_conn
            result = _finalize_hybrid_results(items, explain=True, rrf_small_n_event=None)

        assert "explain" in result[0]
        assert result[0]["explain"]["keyword_pipeline"]["has_fts_match"] is True
        assert result[0]["explain"]["semantic_pipeline"]["has_semantic_match"] is True

    def test_no_explain_field_by_default(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        items = [self._make_item("/a.md")]
        with patch("tools.search_journals.ranking.init_metadata_cache") as mock_init:
            mock_conn = MagicMock()
            mock_init.return_value = mock_conn
            result = _finalize_hybrid_results(items, explain=False, rrf_small_n_event=None)

        assert "explain" not in result[0]

    def test_rrf_small_n_event_attached(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        event = {"event": "rrf_small_n_fallback", "n": 3}
        items = [self._make_item("/a.md")]
        with patch("tools.search_journals.ranking.init_metadata_cache") as mock_init:
            mock_conn = MagicMock()
            mock_init.return_value = mock_conn
            result = _finalize_hybrid_results(items, explain=False, rrf_small_n_event=event)

        assert "events" in result[0]
        assert len(result[0]["events"]) == 1
        assert result[0]["events"][0]["n"] == 3

    def test_metadata_conn_closed(self):
        from tools.search_journals.ranking import _finalize_hybrid_results

        items = [self._make_item("/a.md")]
        with patch("tools.search_journals.ranking.init_metadata_cache") as mock_init:
            mock_conn = MagicMock()
            mock_init.return_value = mock_conn
            _finalize_hybrid_results(items, explain=False, rrf_small_n_event=None)
            mock_conn.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
