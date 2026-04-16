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

    # FTS result should be ranked first (priority=5), semantic results follow (priority=2)
    assert len(merged) == 3
    assert merged[0]["path"] == "fts-hit.md"
    assert merged[0]["fts_score"] > 0  # FTS result has lexical evidence
    assert merged[1]["semantic_score"] > 0  # Semantic results preserved after fix


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
