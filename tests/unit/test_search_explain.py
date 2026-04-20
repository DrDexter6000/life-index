#!/usr/bin/env python3
"""Runtime behavior tests for search explain output."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.search_journals.ranking import (
    merge_and_rank_results,
    merge_and_rank_results_hybrid,
)


@pytest.fixture
def relation_patches(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyConn:
        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "tools.search_journals.ranking.init_metadata_cache", lambda: DummyConn()
    )
    monkeypatch.setattr(
        "tools.search_journals.ranking.get_backlinked_by",
        lambda conn, rel_path: [],
    )


def _result(
    path: str, *, relevance: float = 88.0, similarity: float = 0.82
) -> tuple[list[dict], list[dict]]:
    l3_results = [
        {
            "path": path,
            "rel_path": "Journals/2026/04/entry.md",
            "title": "Entry",
            "relevance": relevance,
            "title_match": True,
            "metadata": {"topic": ["work"]},
        }
    ]
    semantic_results = [
        {
            "path": path,
            "rel_path": "Journals/2026/04/entry.md",
            "title": "Entry",
            "similarity": similarity,
            "metadata": {"topic": ["work"]},
        }
    ]
    return l3_results, semantic_results


class TestSearchExplain:
    def test_explain_result_has_explain_field(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "entry.md")
        l3_results, semantic_results = _result(path)

        results = merge_and_rank_results_hybrid(
            [], [], l3_results, semantic_results, query="entry", explain=True
        )

        assert "explain" in results[0]

    def test_explain_contains_keyword_pipeline(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "entry.md")
        l3_results, semantic_results = _result(path)

        results = merge_and_rank_results_hybrid(
            [], [], l3_results, semantic_results, query="entry", explain=True
        )

        assert isinstance(results[0]["explain"]["keyword_pipeline"]["fts_score"], float)

    def test_explain_contains_semantic_pipeline(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "entry.md")
        l3_results, semantic_results = _result(path, similarity=0.83)

        results = merge_and_rank_results_hybrid(
            [], [], l3_results, semantic_results, query="entry", explain=True
        )

        assert results[0]["explain"]["semantic_pipeline"][
            "cosine_similarity"
        ] == pytest.approx(0.83, abs=0.0001)

    def test_explain_contains_fusion(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "entry.md")
        l3_results, semantic_results = _result(path)

        results = merge_and_rank_results_hybrid(
            [], [], l3_results, semantic_results, query="entry", explain=True
        )

        assert isinstance(results[0]["explain"]["fusion"]["rrf_score"], float)

    def test_no_explain_by_default(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "entry.md")
        l3_results, semantic_results = _result(path)

        results = merge_and_rank_results_hybrid(
            [], [], l3_results, semantic_results, query="entry", explain=False
        )

        assert "explain" not in results[0]


# ── T3.4: Explain fallback gap fix (non-hybrid path) ──


class TestExplainNonHybridFallback:
    """Round 11 Phase 3 T3.4: Non-hybrid ranking path must support explain."""

    def test_non_hybrid_explain_includes_keyword_pipeline(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "entry.md")
        l3_results = [
            {
                "path": path,
                "title": "乐乐日记",
                "relevance": 85,
                "metadata": {},
            }
        ]

        results = merge_and_rank_results(
            [], [], l3_results, query="乐乐", min_score=0, explain=True
        )

        assert len(results) == 1
        assert "explain" in results[0]
        assert "keyword_pipeline" in results[0]["explain"]

    def test_non_hybrid_explain_shows_fts_score(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "entry.md")
        l3_results = [
            {
                "path": path,
                "title": "Entry",
                "relevance": 85,
                "metadata": {},
            }
        ]

        results = merge_and_rank_results(
            [], [], l3_results, query="entry", min_score=0, explain=True
        )

        assert results[0]["explain"]["keyword_pipeline"]["fts_score"] > 0
        assert results[0]["explain"]["keyword_pipeline"]["has_fts_match"] is True

    def test_non_hybrid_explain_no_semantic_pipeline(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        """Non-hybrid path has no semantic pipeline — should show zero."""
        path = str(tmp_path / "entry.md")
        l3_results = [
            {
                "path": path,
                "title": "Entry",
                "relevance": 85,
                "metadata": {},
            }
        ]

        results = merge_and_rank_results(
            [], [], l3_results, query="entry", min_score=0, explain=True
        )

        sem = results[0]["explain"]["semantic_pipeline"]
        assert sem["cosine_similarity"] == 0.0
        assert sem["has_semantic_match"] is False

    def test_non_hybrid_no_explain_by_default(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        path = str(tmp_path / "entry.md")
        l3_results = [
            {
                "path": path,
                "title": "Entry",
                "relevance": 85,
                "metadata": {},
            }
        ]

        results = merge_and_rank_results(
            [], [], l3_results, query="entry", min_score=0, explain=False
        )

        assert "explain" not in results[0]

    def test_hybrid_explain_not_regressed(
        self, relation_patches: None, tmp_path: Path
    ) -> None:
        """Hybrid explain must still work after T3.4 changes."""
        path = str(tmp_path / "entry.md")
        l3_results, semantic_results = _result(path)

        results = merge_and_rank_results_hybrid(
            [], [], l3_results, semantic_results, query="entry", explain=True
        )

        assert "explain" in results[0]
        assert results[0]["explain"]["keyword_pipeline"]["has_fts_match"] is True
        assert results[0]["explain"]["semantic_pipeline"]["has_semantic_match"] is True
