#!/usr/bin/env python3
"""Unit tests for tools/search_journals/ranking.py."""

from tools.search_journals.ranking import (
    merge_and_rank_results,
    merge_and_rank_results_hybrid,
)


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
        [{"path": "meta.md", "title": "乐乐日记", "metadata": {}}],
        [],
        query="乐乐",
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


def test_merge_and_rank_results_hybrid_prefers_stronger_lexical_result_over_weaker_semantic_only() -> (
    None
):
    merged = merge_and_rank_results_hybrid(
        [],
        [
            {
                "path": "meta.md",
                "title": "乐乐日记",
                "metadata": {"abstract": "乐乐今天很好"},
            }
        ],
        [],
        [{"path": "semantic.md", "similarity": 0.36}],
        query="乐乐",
        min_non_rrf_score=0,
    )

    assert len(merged) == 2
    assert merged[0]["path"] == "meta.md"
