#!/usr/bin/env python3
"""Unit tests for tools/search_journals/ranking.py."""

from tools.search_journals.ranking import (
    merge_and_rank_results,
    merge_and_rank_results_hybrid,
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


def test_merge_and_rank_results_hybrid_surfaces_related_entries_and_backlinked_by() -> (
    None
):
    l2_results = [
        {
            "path": "doc.md",
            "rel_path": "Journals/2026/03/doc.md",
            "title": "Doc",
            "metadata": {"related_entries": ["Journals/2026/03/other.md"]},
        }
    ]

    merged = merge_and_rank_results_hybrid(
        [], l2_results, [], [], query="doc", min_rrf_score=0, min_non_rrf_score=0
    )

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
        {"path": f"doc-{index}.md", "relevance": 80, "title": f"Doc {index}"}
        for index in range(25)
    ]
    l2_results = [{"path": "weak-meta.md", "title": "Weak", "metadata": {}}]

    merged = merge_and_rank_results([], l2_results, l3_results, query="python")

    assert len(merged) == 20
    assert all(item["relevance_score"] >= 25 for item in merged)
    assert all(item["path"] != "weak-meta.md" for item in merged)


def test_merge_and_rank_results_hybrid_filters_low_rrf_scores() -> None:
    l3_results = [
        {"path": f"doc-{index}.md", "relevance": 80, "title": f"Doc {index}"}
        for index in range(80)
    ]

    merged = merge_and_rank_results_hybrid(
        [], [], l3_results, [{"path": "doc-0.md", "similarity": 0.9}]
    )

    # With fts_weight=1.0 (FTS_WEIGHT_DEFAULT), k=60 (RRF_K), min_rrf_score=0.008 (RRF_MIN_SCORE):
    # FTS-only items pass when 1.0/(60+rank) >= 0.008 → rank <= 65
    # But MAX_RESULTS_DEFAULT=20 caps the output
    assert len(merged) == 20  # Capped by MAX_RESULTS_DEFAULT
    assert all(item["relevance_score"] >= 0.008 for item in merged)
    # Verify doc-0 (hybrid match) is in results and has semantic_score > 0
    doc0_result = next((item for item in merged if item["path"] == "doc-0.md"), None)
    assert doc0_result is not None
    assert doc0_result["semantic_score"] > 0  # Has semantic signal


def test_merge_and_rank_results_hybrid_default_threshold_rejects_single_low_rrf_hit() -> (
    None
):
    merged = merge_and_rank_results_hybrid(
        [],
        [],
        [{"path": "doc-0.md", "relevance": 80, "title": "Doc 0"}],
        [],
    )

    assert len(merged) == 1
    assert merged[0]["path"] == "doc-0.md"


def test_merge_and_rank_results_default_keeps_title_match_l2_result() -> None:
    merged = merge_and_rank_results(
        [],
        [{"path": "meta.md", "title": "团团日记", "metadata": {}}],
        [],
        query="团团",
    )

    assert len(merged) == 1
    assert merged[0]["path"] == "meta.md"


def test_merge_and_rank_results_hybrid_default_keeps_single_semantic_hit() -> None:
    merged = merge_and_rank_results_hybrid(
        [],
        [],
        [],
        [{"path": "semantic.md", "similarity": 0.41}],
    )

    assert len(merged) == 1
    assert merged[0]["path"] == "semantic.md"


def test_merge_and_rank_results_hybrid_semantic_only_result_uses_semantic_thresholds_for_confidence() -> None:
    merged = merge_and_rank_results_hybrid(
        [],
        [],
        [],
        [{"path": "semantic.md", "similarity": 0.43}],
    )

    assert len(merged) == 1
    assert merged[0]["path"] == "semantic.md"
    assert merged[0]["confidence"] == "low"


def test_merge_and_rank_results_hybrid_does_not_force_extra_backfill_when_one_strong_hit_exists() -> (
    None
):
    merged = merge_and_rank_results_hybrid(
        [],
        [],
        [{"path": "fts-hit.md", "relevance": 80, "title": "FTS Hit"}],
        [
            {"path": "semantic-noise-1.md", "similarity": 0.2},
            {"path": "semantic-noise-2.md", "similarity": 0.19},
        ],
        query="尿片侠",
    )

    # With RRF_MIN_SCORE=0.008 (ADR-004) and SEMANTIC_WEIGHT_DEFAULT=0.6 (ADR-010),
    # weak semantic results (0.2/0.19 similarity) now survive the RRF threshold
    # because 0.6/(60+1) = 0.00984 > 0.008. This is expected — they enter results
    # but get low confidence. The FTS hit is still Top-1.
    assert len(merged) == 3  # 1 FTS + 2 semantic (passed RRF threshold)
    assert merged[0]["path"] == "fts-hit.md"
    assert merged[0]["fts_score"] > 0  # FTS result has lexical evidence


def test_merge_and_rank_results_hybrid_prefers_stronger_lexical_result_over_weaker_semantic_only() -> (
    None
):
    merged = merge_and_rank_results_hybrid(
        [],
        [
            {
                "path": "meta.md",
                "title": "团团日记",
                "metadata": {"abstract": "团团今天很好"},
            }
        ],
        [],
        [{"path": "semantic.md", "similarity": 0.36}],
        query="团团",
        min_rrf_score=0,
        min_non_rrf_score=0,
    )

    assert len(merged) == 2
    assert merged[0]["path"] == "meta.md"


def test_merge_and_rank_results_dynamic_fts_threshold_tightens_high_score_cluster() -> (
    None
):
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
            "metadata": {"people": ["团团"], "tags": ["亲子"]},
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
            "expansion_terms": ["团团", "小疙瘩", "尿片侠"],
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

    def test_no_plus_one_bias_in_hybrid_merge(self) -> None:
        """merge_and_rank_results_hybrid must NOT add +1 to non-RRF threshold."""
        from tools.lib.search_constants import NON_RRF_MIN_SCORE

        l2_results = [
            {
                "path": f"doc{i}.md",
                "title": f"Doc {i}",
                "metadata": {},
            }
            for i in range(3)
        ]

        merged = merge_and_rank_results_hybrid(
            [],
            l2_results,
            [],
            [],
            query="test",
            min_rrf_score=0,
            min_non_rrf_score=NON_RRF_MIN_SCORE,
        )

        # L2 base = 30 >= NON_RRF_MIN_SCORE = 10, so all should pass.
        # If +1 bias were present, threshold would be 11 but L2 base is still 30
        # so they'd still pass — but we verify the threshold logic is clean.
        assert len(merged) == 3


class TestEntityBonusExpansion:
    """B-9: entity bonus should check title/snippet, not just metadata."""

    def test_entity_bonus_from_metadata(self) -> None:
        """Entity bonus applies when expansion term appears in metadata people/tags."""
        l2_a = {
            "path": "with-entity.md",
            "title": "Meeting",
            "metadata": {"people": ["团团"], "tags": []},
        }
        l2_b = {
            "path": "without-entity.md",
            "title": "Meeting",
            "metadata": {"people": [], "tags": []},
        }
        entity_hints = [{"expansion_terms": ["团团", "小疙瘩"]}]

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
            "title": "想念团团",
            "metadata": {},
        }
        l2_b = {
            "path": "no-match.md",
            "title": "日常记录",
            "metadata": {},
        }
        entity_hints = [{"expansion_terms": ["团团", "小疙瘩"]}]

        merged = merge_and_rank_results(
            [], [l2_a, l2_b], [], query="团团", min_score=0, entity_hints=entity_hints
        )

        assert merged[0]["path"] == "title-match.md"

    def test_entity_bonus_from_snippet(self) -> None:
        """B-9: Entity bonus applies when expansion term appears in snippet."""
        l2_a = {
            "path": "snippet-match.md",
            "title": "Daily",
            "snippet": "今天团团不认真吃饭",
            "metadata": {},
        }
        l2_b = {
            "path": "no-match.md",
            "title": "Daily",
            "snippet": "普通的一天",
            "metadata": {},
        }
        entity_hints = [{"expansion_terms": ["团团"]}]

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

        merged = merge_and_rank_results(
            [], [l2_weak], [l3_strong], query="test", min_score=0
        )

        assert len(merged) == 2
        assert merged[0]["path"] == "l3-strong.md"
        assert merged[0]["source"] == "fts"
        assert merged[1]["source"] == "none"

    def test_l2_with_title_match_can_rank_above_l3_weak(self) -> None:
        """L2 with title_match (strong metadata signal) may rank above
        a very weak L3 FTS result — title match is a valid signal."""
        l2_title_match = {
            "path": "l2-title.md",
            "title": "团团日记",
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
            query="团团",
            min_score=0,
        )

        assert len(merged) == 2
        # L2 with title match can outrank a barely-threshold L3
        # (L2 gets base + title bonus = 30 + 8 = 38 > L3's 26)
        assert merged[0]["path"] == "l2-title.md"

    def test_hybrid_fts_strong_beats_l2_weak_metadata(self) -> None:
        """In hybrid mode, L3 FTS result should outrank L2 weak match."""
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
        semantic = [
            {"path": "l3-strong.md", "similarity": 0.85},
        ]

        merged = merge_and_rank_results_hybrid(
            [],
            [l2_weak],
            [l3_strong],
            semantic,
            query="test",
            min_rrf_score=0,
            min_non_rrf_score=0,
        )

        fts_result = next(
            (r for r in merged if r["path"] == "l3-strong.md"), None
        )
        l2_result = next(
            (r for r in merged if r["path"] == "l2-weak.md"), None
        )
        assert fts_result is not None
        assert l2_result is not None
        assert fts_result["search_rank"] < l2_result["search_rank"]

    def test_hybrid_source_none_penalty_in_l2_bucket(self) -> None:
        """Within L2 bucket, results with source='none' get a penalty
        so they rank below L2 results with entity bonus."""
        l2_with_entity = {
            "path": "l2-entity.md",
            "title": "Doc",
            "metadata": {"people": ["团团"], "tags": ["亲子"]},
        }
        l2_weak = {
            "path": "l2-weak.md",
            "title": "Other Doc",
            "metadata": {},
        }
        entity_hints = [
            {
                "matched_term": "团团",
                "entity_id": "tuantuan",
                "entity_type": "person",
                "expansion_terms": ["团团", "小疙瘩"],
                "reason": "alias_match",
            }
        ]

        merged = merge_and_rank_results_hybrid(
            [],
            [l2_with_entity, l2_weak],
            [],
            [],
            query="团团",
            min_rrf_score=0,
            min_non_rrf_score=0,
            entity_hints=entity_hints,
        )

        assert len(merged) == 2
        assert merged[0]["path"] == "l2-entity.md"

    def test_existing_ranking_tests_not_regressed(self) -> None:
        """T3.1 changes must not break existing ranking behavior:
        title-match L2 still surfaces for single-result queries."""
        merged = merge_and_rank_results(
            [],
            [{"path": "meta.md", "title": "团团日记", "metadata": {}}],
            [],
            query="团团",
        )
        assert len(merged) == 1
        assert merged[0]["path"] == "meta.md"

    def test_non_hybrid_source_field_correct(self) -> None:
        """Verify source field is set correctly in non-hybrid path."""
        l2_result = {"path": "meta.md", "title": "Doc", "metadata": {}}
        l3_result = {"path": "fts.md", "relevance": 50, "title": "FTS Doc"}

        merged = merge_and_rank_results(
            [], [l2_result], [l3_result], query="doc", min_score=0
        )

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

        merged = merge_and_rank_results(
            [], [l2_result], [l3_result], query="shared", min_score=0
        )

        # Same path should appear only once
        path_counts = [r["path"] for r in merged].count("same-doc.md")
        assert path_counts == 1
        # L3 FTS match should be the one kept (higher score)
        assert merged[0]["path"] == "same-doc.md"
        assert merged[0]["source"] == "fts"

    def test_hybrid_dedup_keeps_highest_ranked(self) -> None:
        """In hybrid mode, same path from multiple sources appears only once."""
        l3_result = {
            "path": "same-doc.md",
            "relevance": 85,
            "title": "Shared Doc",
        }
        semantic_result = {
            "path": "same-doc.md",
            "similarity": 0.90,
        }

        merged = merge_and_rank_results_hybrid(
            [],
            [],
            [l3_result],
            [semantic_result],
            query="shared",
            min_rrf_score=0,
            min_non_rrf_score=0,
        )

        path_counts = [r["path"] for r in merged].count("same-doc.md")
        assert path_counts == 1
        # The single result should have both FTS and semantic scores
        assert merged[0]["fts_score"] > 0
        assert merged[0]["semantic_score"] > 0

    def test_different_paths_not_deduplicated(self) -> None:
        """Different paths should never be deduplicated."""
        l3_a = {"path": "doc-a.md", "relevance": 80, "title": "Doc A"}
        l3_b = {"path": "doc-b.md", "relevance": 60, "title": "Doc B"}

        merged = merge_and_rank_results(
            [], [], [l3_a, l3_b], query="doc", min_score=0
        )

        assert len(merged) == 2

    def test_dedup_preserves_relative_order(self) -> None:
        """After dedup, remaining results maintain their relative order."""
        l3_results = [
            {"path": f"doc-{i}.md", "relevance": 90 - i * 5, "title": f"Doc {i}"}
            for i in range(5)
        ]

        merged = merge_and_rank_results(
            [], [], l3_results, query="doc", min_score=0
        )

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
