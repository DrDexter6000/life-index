#!/usr/bin/env python3
"""Tests for FTS OR-query min-hits filtering (Round 10 T3.1)."""

from __future__ import annotations

from unittest.mock import patch


class TestComputeMinRequiredHits:
    def test_multi_token_query_requires_40_percent_rounded_up(self) -> None:
        from tools.search_journals.keyword_pipeline import _compute_min_required_hits

        required, non_stop = _compute_min_required_hits(
            ["量子", "计算", "机", "编程", "语言"]
        )

        assert required == 2
        assert non_stop == ["量子", "计算", "机", "编程", "语言"]

    def test_two_token_query_still_requires_two_hits(self) -> None:
        from tools.search_journals.keyword_pipeline import _compute_min_required_hits

        required, non_stop = _compute_min_required_hits(["睡眠", "不足"])

        assert required == 2
        assert non_stop == ["睡眠", "不足"]

    def test_single_token_query_skips_filter(self) -> None:
        from tools.search_journals.keyword_pipeline import _compute_min_required_hits

        required, non_stop = _compute_min_required_hits(["乐乐"])

        assert required == 0
        assert non_stop == ["乐乐"]

    def test_single_non_stopword_after_stopword_filter_skips(self) -> None:
        from tools.search_journals.keyword_pipeline import _compute_min_required_hits

        required, non_stop = _compute_min_required_hits(["今天", "最近", "有点", "累"])

        assert required == 0
        assert non_stop == ["累"]

    def test_all_stopwords_skip_filter(self) -> None:
        from tools.search_journals.keyword_pipeline import _compute_min_required_hits

        required, non_stop = _compute_min_required_hits(["的", "了", "在"])

        assert required == 0
        assert non_stop == []


class TestCountDistinctTokenHits:
    def test_all_tokens_present(self) -> None:
        from tools.search_journals.keyword_pipeline import _count_distinct_token_hits

        hits = _count_distinct_token_hits("量子计算机编程语言", ["量子", "计算", "编程"])

        assert hits == 3

    def test_partial_match(self) -> None:
        from tools.search_journals.keyword_pipeline import _count_distinct_token_hits

        hits = _count_distinct_token_hits("量子力学基本原理", ["量子", "计算", "编程"])

        assert hits == 1

    def test_no_match(self) -> None:
        from tools.search_journals.keyword_pipeline import _count_distinct_token_hits

        hits = _count_distinct_token_hits("红烧肉做法", ["量子", "计算"])

        assert hits == 0

    def test_case_insensitive_and_distinct(self) -> None:
        from tools.search_journals.keyword_pipeline import _count_distinct_token_hits

        hits = _count_distinct_token_hits(
            "Google Stitch google integration", ["google", "stitch", "google"]
        )

        assert hits == 2


class TestPipelineFTSMinHits:
    def test_segmented_fts_results_are_post_filtered_by_distinct_hits(self) -> None:
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch(
            "tools.search_journals.keyword_pipeline.search_l2_metadata"
        ) as mock_l2:
            with patch(
                "tools.search_journals.keyword_pipeline._segment_query_for_fts",
                return_value=("量子 计算 编程 语言 未来", True),
            ):
                with patch("tools.lib.search_index.search_fts") as mock_fts:
                    with patch(
                        "tools.search_journals.keyword_pipeline.search_l3_content"
                    ) as mock_l3:
                        mock_l2.return_value = {
                            "results": [],
                            "truncated": False,
                            "total_available": 0,
                        }
                        mock_fts.return_value = [
                            {
                                "path": "Journals/2026/04/weak.md",
                                "title": "量子随想",
                                "date": "2026-04-01",
                                "snippet": "只提到量子",
                                "relevance": 80,
                            },
                            {
                                "path": "Journals/2026/04/strong.md",
                                "title": "量子计算学习",
                                "date": "2026-04-02",
                                "snippet": "最近在研究编程语言",
                                "relevance": 78,
                            },
                        ]
                        mock_l3.return_value = []

                        _, _, l3_results, _, _, _ = run_keyword_pipeline(
                            query="量子计算编程语言未来", use_index=True
                        )

        assert mock_fts.call_count == 1
        assert mock_fts.call_args.args[0] == "量子 OR 计算 OR 编程 OR 语言 OR 未来"
        assert [item["title"] for item in l3_results] == ["量子计算学习"]

    def test_segmented_query_with_single_non_stopword_skips_filter(self) -> None:
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch(
            "tools.search_journals.keyword_pipeline.search_l2_metadata"
        ) as mock_l2:
            with patch(
                "tools.search_journals.keyword_pipeline._segment_query_for_fts",
                return_value=("今天 最近 有点 累", True),
            ):
                with patch("tools.lib.search_index.search_fts") as mock_fts:
                    with patch(
                        "tools.search_journals.keyword_pipeline.search_l3_content"
                    ) as mock_l3:
                        mock_l2.return_value = {
                            "results": [],
                            "truncated": False,
                            "total_available": 0,
                        }
                        mock_fts.return_value = [
                            {
                                "path": "Journals/2026/04/tired.md",
                                "title": "今天有点困",
                                "date": "2026-04-03",
                                "snippet": "最近真累",
                                "relevance": 75,
                            },
                            {
                                "path": "Journals/2026/04/other.md",
                                "title": "普通记录",
                                "date": "2026-04-04",
                                "snippet": "没有相关词",
                                "relevance": 72,
                            },
                        ]
                        mock_l3.return_value = []

                        _, _, l3_results, _, _, _ = run_keyword_pipeline(
                            query="今天最近有点累", use_index=True
                        )

        assert [item["title"] for item in l3_results] == ["今天有点困", "普通记录"]
