#!/usr/bin/env python3
"""Unit tests for tools/search_journals/ranking.py."""

from tools.search_journals.ranking import (
    merge_and_rank_results,
)
from tools.lib.search_constants import FTS_MIN_RELEVANCE
from tools.search_journals.keyword_pipeline import run_keyword_pipeline
from unittest.mock import MagicMock, patch


def test_merge_and_rank_results_surfaces_related_entries_and_backlinked_by() -> None:
    l2_results = [
        {
            "path": "doc.md",
            "rel_path": "Journals/2026/03/doc.md",
            "title": "Doc",
            "metadata": {"related_entries": ["Journals/2026/03/other.md"]},
        }
    ]

    merged = merge_and_rank_results([], l2_results, [], query="doc", min_score=0)

    assert merged[0]["related_entries"] == ["Journals/2026/03/other.md"]
    assert "backlinked_by" in merged[0]


def test_merge_and_rank_results_reuses_single_metadata_cache_connection() -> None:
    l2_results = [
        {
            "path": "doc-a.md",
            "rel_path": "Journals/2026/03/doc-a.md",
            "title": "Doc A",
            "metadata": {},
        },
        {
            "path": "doc-b.md",
            "rel_path": "Journals/2026/03/doc-b.md",
            "title": "Doc B",
            "metadata": {},
        },
    ]

    mock_conn = MagicMock()
    with patch(
        "tools.search_journals.ranking.init_metadata_cache", return_value=mock_conn
    ) as mock_init:
        with patch("tools.search_journals.ranking.get_backlinked_by", return_value=[]):
            merge_and_rank_results([], l2_results, [], query="doc", min_score=0)

    mock_init.assert_called_once()
    mock_conn.close.assert_called_once()


def test_merge_and_rank_results_filters_low_non_rrf_scores_and_caps_results() -> None:
    l3_results = [
        {"path": f"doc-{index}.md", "relevance": 80, "title": f"Doc {index}"} for index in range(25)
    ]
    l2_results = [{"path": "weak-meta.md", "title": "Weak", "metadata": {}}]

    merged = merge_and_rank_results([], l2_results, l3_results, query="python")

    # Phase 2 (Task 3): ranking returns ALL filtered results (no internal truncation).
    # Truncation to MAX_RESULTS_DEFAULT happens in core.py (presentation layer).
    assert len(merged) == 26  # 25 L3 + 1 L2 (passes NON_RRF_MIN_SCORE threshold)
    assert all(
        item["relevance_score"] >= 25 for item in merged if item.get("source") != "metadata_search"
    )


def test_merge_and_rank_results_default_keeps_title_match_l2_result() -> None:
    merged = merge_and_rank_results(
        [],
        [{"path": "meta.md", "title": "晴岚日记", "metadata": {}}],
        [],
        query="晴岚",
    )

    assert len(merged) == 1
    assert merged[0]["path"] == "meta.md"


def test_merge_and_rank_results_dynamic_fts_threshold_tightens_high_score_cluster() -> None:
    merged = merge_and_rank_results(
        [],
        [],
        [
            {"path": "doc-1.md", "relevance": 90, "title": "Doc 1"},
            {"path": "doc-2.md", "relevance": 86, "title": "Doc 2"},
            {"path": "doc-3.md", "relevance": 82, "title": "Doc 3"},
            {"path": "doc-4.md", "relevance": 20, "title": "Doc 4"},
        ],
        query="google stitch",
    )

    assert [item["path"] for item in merged] == ["doc-1.md", "doc-2.md", "doc-3.md"]


def test_keyword_pipeline_default_uses_shared_fts_min_relevance_constant() -> None:
    assert run_keyword_pipeline.__kwdefaults__ is not None
    assert run_keyword_pipeline.__kwdefaults__["fts_min_relevance"] == FTS_MIN_RELEVANCE


def test_merge_and_rank_results_applies_entity_hint_bonus_to_people_and_tags() -> None:
    l2_results = [
        {
            "path": "with-entity.md",
            "title": "With Entity",
            "metadata": {"people": ["晴岚"], "tags": ["亲子"]},
        },
        {
            "path": "without-entity.md",
            "title": "Without Entity",
            "metadata": {"people": ["别人"], "tags": ["其他"]},
        },
    ]
    entity_hints = [
        {
            "matched_term": "我女儿",
            "entity_id": "tuantuan",
            "entity_type": "person",
            "expansion_terms": ["晴岚", "小风筝", "小队长"],
            "reason": "phrase_match",
        }
    ]

    merged = merge_and_rank_results(
        [], l2_results, [], query=None, min_score=0, entity_hints=entity_hints
    )

    assert merged[0]["path"] == "with-entity.md"
    assert merged[0]["relevance_score"] > merged[1]["relevance_score"]


def test_merge_and_rank_results_without_entity_hints_preserves_default_order() -> None:
    l2_results = [
        {
            "path": "first.md",
            "title": "First",
            "metadata": {},
        },
        {
            "path": "second.md",
            "title": "Second",
            "metadata": {},
        },
    ]

    merged = merge_and_rank_results([], l2_results, [], query=None, min_score=0)

    assert [item["path"] for item in merged] == ["first.md", "second.md"]


class TestDynamicThresholdRobustness:
    """B-6/B-7: dynamic threshold should not activate on small samples."""

    def test_small_sample_uses_base_threshold_not_dynamic(self) -> None:
        """With < 8 scored results, dynamic threshold must not override base."""
        from tools.search_journals.ranking import _compute_dynamic_fts_threshold

        small_sample = [
            {"score": 60},
            {"score": 55},
            {"score": 50},
        ]
        result = _compute_dynamic_fts_threshold(small_sample, base_threshold=25.0)
        # Should return the base unchanged because N < 8
        assert result == 25.0

    def test_no_plus_one_bias_in_merge(self) -> None:
        """merge_and_rank_results must NOT add a +1 bias to FTS threshold."""
        l3_results = [
            {
                "path": f"doc{i}.md",
                "title": f"Doc {i}",
                "relevance": 25,
                "source": "fts",
            }
            for i in range(3)
        ]

        merged = merge_and_rank_results(
            [], [], l3_results, query="test", min_score=FTS_MIN_RELEVANCE
        )

        # With min_score=FTS_MIN_RELEVANCE (25), all 3 docs at relevance=25
        # should pass. If +1 bias were present, threshold would be 26 and all
        # would be filtered out.
        assert len(merged) == 3


class TestEntityBonusExpansion:
    """B-9: entity bonus should check title/snippet, not just metadata."""

    def test_entity_bonus_from_metadata(self) -> None:
        """Entity bonus applies when expansion term appears in metadata people/tags."""
        l2_a = {
            "path": "with-entity.md",
            "title": "Meeting",
            "metadata": {"people": ["晴岚"], "tags": []},
        }
        l2_b = {
            "path": "without-entity.md",
            "title": "Meeting",
            "metadata": {"people": [], "tags": []},
        }
        entity_hints = [{"expansion_terms": ["晴岚", "小风筝"]}]

        merged = merge_and_rank_results(
            [],
            [l2_a, l2_b],
            [],
            query="meeting",
            min_score=0,
            entity_hints=entity_hints,
        )

        assert merged[0]["path"] == "with-entity.md"

    def test_entity_bonus_from_title(self) -> None:
        """B-9: Entity bonus applies when expansion term appears in title only."""
        l2_a = {
            "path": "title-match.md",
            "title": "想念晴岚",
            "metadata": {},
        }
        l2_b = {
            "path": "no-match.md",
            "title": "日常记录",
            "metadata": {},
        }
        entity_hints = [{"expansion_terms": ["晴岚", "小风筝"]}]

        merged = merge_and_rank_results(
            [], [l2_a, l2_b], [], query="晴岚", min_score=0, entity_hints=entity_hints
        )

        assert merged[0]["path"] == "title-match.md"

    def test_entity_bonus_from_snippet(self) -> None:
        """B-9: Entity bonus applies when expansion term appears in snippet."""
        l2_a = {
            "path": "snippet-match.md",
            "title": "Daily",
            "snippet": "今天晴岚不认真吃饭",
            "metadata": {},
        }
        l2_b = {
            "path": "no-match.md",
            "title": "Daily",
            "snippet": "普通的一天",
            "metadata": {},
        }
        entity_hints = [{"expansion_terms": ["晴岚"]}]

        merged = merge_and_rank_results(
            [], [l2_a, l2_b], [], query="吃饭", min_score=0, entity_hints=entity_hints
        )

        assert merged[0]["path"] == "snippet-match.md"


# ── T3.1: L2 weak metadata match deprioritization ──


class TestL2WeakMetadataDeprioritization:
    """Round 11 Phase 3 T3.1: L2 weak metadata matches (source='none')
    must not outrank L3 FTS strong matches.

    The ranking should apply a source-aware penalty so that within each
    priority bucket, results with source='none' (pure metadata, no FTS)
    are ranked below results with actual content matches.
    """

    def test_fts_strong_beats_l2_weak_metadata(self) -> None:
        """L2 weak match (score=30, source='none') should not beat
        L3 FTS strong match (score=80)."""
        l2_weak = {
            "path": "l2-weak.md",
            "title": "Some Doc",
            "metadata": {},
        }
        l3_strong = {
            "path": "l3-strong.md",
            "relevance": 80,
            "title": "Strong FTS Match",
        }

        merged = merge_and_rank_results([], [l2_weak], [l3_strong], query="test", min_score=0)

        assert len(merged) == 2
        assert merged[0]["path"] == "l3-strong.md"
        assert merged[0]["source"] == "fts"
        assert merged[1]["source"] == "none"

    def test_l2_with_title_match_can_rank_above_l3_weak(self) -> None:
        """L2 with title_match (strong metadata signal) may rank above
        a very weak L3 FTS result — title match is a valid signal."""
        l2_title_match = {
            "path": "l2-title.md",
            "title": "晴岚日记",
            "metadata": {},
        }
        l3_weak = {
            "path": "l3-weak.md",
            "relevance": 26,
            "title": "Unrelated",
        }

        merged = merge_and_rank_results(
            [],
            [l2_title_match],
            [l3_weak],
            query="晴岚",
            min_score=0,
        )

        assert len(merged) == 2
        # L2 with title match can outrank a barely-threshold L3
        # (L2 gets base + title bonus = 30 + 8 = 38 > L3's 26)
        assert merged[0]["path"] == "l2-title.md"

    def test_existing_ranking_tests_not_regressed(self) -> None:
        """T3.1 changes must not break existing ranking behavior:
        title-match L2 still surfaces for single-result queries."""
        merged = merge_and_rank_results(
            [],
            [{"path": "meta.md", "title": "晴岚日记", "metadata": {}}],
            [],
            query="晴岚",
        )
        assert len(merged) == 1
        assert merged[0]["path"] == "meta.md"

    def test_non_hybrid_source_field_correct(self) -> None:
        """Verify source field is set correctly in non-hybrid path."""
        l2_result = {"path": "meta.md", "title": "Doc", "metadata": {}}
        l3_result = {"path": "fts.md", "relevance": 50, "title": "FTS Doc"}

        merged = merge_and_rank_results([], [l2_result], [l3_result], query="doc", min_score=0)

        fts_entry = next(r for r in merged if r["path"] == "fts.md")
        meta_entry = next(r for r in merged if r["path"] == "meta.md")
        assert fts_entry["source"] == "fts"
        assert meta_entry["source"] == "none"


# ── T3.2: Same-path deduplication ──


class TestSamePathDeduplication:
    """Round 11 Phase 3 T3.2: Same journal should not appear multiple times
    in merged results due to multi-segment matches."""

    def test_non_hybrid_dedup_keeps_higher_score(self) -> None:
        """When same path appears in both L2 and L3, keep only the higher-ranked."""
        l2_result = {
            "path": "same-doc.md",
            "title": "Shared Doc",
            "metadata": {},
        }
        l3_result = {
            "path": "same-doc.md",
            "relevance": 85,
            "title": "Shared Doc",
        }

        merged = merge_and_rank_results([], [l2_result], [l3_result], query="shared", min_score=0)

        # Same path should appear only once
        path_counts = [r["path"] for r in merged].count("same-doc.md")
        assert path_counts == 1
        # L3 FTS match should be the one kept (higher score)
        assert merged[0]["path"] == "same-doc.md"
        assert merged[0]["source"] == "fts"

    def test_different_paths_not_deduplicated(self) -> None:
        """Different paths should never be deduplicated."""
        l3_a = {"path": "doc-a.md", "relevance": 80, "title": "Doc A"}
        l3_b = {"path": "doc-b.md", "relevance": 60, "title": "Doc B"}

        merged = merge_and_rank_results([], [], [l3_a, l3_b], query="doc", min_score=0)

        assert len(merged) == 2

    def test_dedup_preserves_relative_order(self) -> None:
        """After dedup, remaining results maintain their relative order."""
        l3_results = [
            {"path": f"doc-{i}.md", "relevance": 90 - i * 5, "title": f"Doc {i}"} for i in range(5)
        ]

        merged = merge_and_rank_results([], [], l3_results, query="doc", min_score=0)

        paths = [r["path"] for r in merged]
        assert paths == sorted(paths, key=lambda p: int(p.split("-")[1].split(".")[0]))

    def test_total_found_counts_unique_paths(self) -> None:
        """total_found should reflect unique results, not raw count."""
        l2_result = {"path": "overlap.md", "title": "Overlap", "metadata": {}}
        l3_result = {"path": "overlap.md", "relevance": 80, "title": "Overlap"}
        l3_unique = {"path": "unique.md", "relevance": 60, "title": "Unique"}

        merged = merge_and_rank_results(
            [], [l2_result], [l3_result, l3_unique], query="test", min_score=0
        )

        assert len(merged) == 2  # overlap.md deduped + unique.md
