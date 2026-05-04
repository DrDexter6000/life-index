#!/usr/bin/env python3
"""FTS query strategy verification tests for Batch 2."""

from __future__ import annotations

from unittest.mock import patch


class TestFTSStrategy:
    def test_whitespace_query_skips_l3_search(self) -> None:
        """纯空白查询应在进入 FTS/L3 前直接短路为空结果。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                with patch("tools.search_journals.keyword_pipeline.search_l3_content") as mock_l3:
                    mock_l2.return_value = {
                        "results": [],
                        "truncated": False,
                        "total_available": 0,
                    }

                    _, _, l3_results, _, _, _ = run_keyword_pipeline(query="   ", use_index=True)

        assert mock_fts.call_count == 0
        assert mock_l3.call_count == 0
        assert l3_results == []

    def test_punctuation_only_query_skips_l3_search(self) -> None:
        """纯标点查询应视为无有效 query，而不是回退成全文扫描。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                with patch("tools.search_journals.keyword_pipeline.search_l3_content") as mock_l3:
                    mock_l2.return_value = {
                        "results": [],
                        "truncated": False,
                        "total_available": 0,
                    }

                    _, _, l3_results, _, _, _ = run_keyword_pipeline(query="！！！", use_index=True)

        assert mock_fts.call_count == 0
        assert mock_l3.call_count == 0
        assert l3_results == []

    def test_query_normalization_applies_before_segmentation(self) -> None:
        """查询进入 FTS 前应先做标准化。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query="「乐乐」！", use_index=True)

        assert mock_fts.call_count == 1
        assert mock_fts.call_args.args[0] == "乐乐"

    def test_multi_word_and_first(self) -> None:
        """多词查询应优先使用 AND：'团队 建设' 先走 AND 查询。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = [
                    {
                        "path": "Journals/2026/04/team.md",
                        "title": "Team Build",
                        "date": "2026-04-01",
                        "snippet": "团队建设",
                        "relevance": 80,
                    }
                ]

                run_keyword_pipeline(query="团队 建设", use_index=True)

        assert mock_fts.call_count >= 1
        assert mock_fts.call_args_list[0].args[0] == "团队 AND 建设"

    def test_and_fallback_to_or(self) -> None:
        """AND 结果过少（<3）时，自动降级为 OR。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.side_effect = [
                    [
                        {
                            "path": "Journals/2026/04/team.md",
                            "title": "Team Build",
                            "date": "2026-04-01",
                            "snippet": "团队建设",
                            "relevance": 80,
                        }
                    ],
                    [
                        {
                            "path": "Journals/2026/04/team.md",
                            "title": "Team Build",
                            "date": "2026-04-01",
                            "snippet": "团队建设",
                            "relevance": 80,
                        },
                        {
                            "path": "Journals/2026/04/travel.md",
                            "title": "Travel",
                            "date": "2026-04-02",
                            "snippet": "团队旅行",
                            "relevance": 60,
                        },
                    ],
                ]

                _, _, l3_results, _, _, _ = run_keyword_pipeline(query="团队 建设", use_index=True)

        assert mock_fts.call_count == 2
        assert mock_fts.call_args_list[0].args[0] == "团队 AND 建设"
        assert mock_fts.call_args_list[1].args[0] == "团队 OR 建设"
        assert len(l3_results) == 2

    def test_single_word_unchanged(self) -> None:
        """单词查询行为不变。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query="团队", use_index=True)

        assert mock_fts.call_count == 1
        assert mock_fts.call_args.args[0] == "团队"

    def test_chinese_multi_word(self) -> None:
        """中文多词查询：'春节 旅行' AND 优先。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query="春节 旅行", use_index=True)

        assert mock_fts.call_count >= 1
        assert mock_fts.call_args_list[0].args[0] == "春节 AND 旅行"

    def test_explicit_or_respected(self) -> None:
        """用户显式使用 OR 时，不覆盖为 AND。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query="团队 OR 建设", use_index=True)

        assert mock_fts.call_count == 1
        assert mock_fts.call_args.args[0] == "团队 OR 建设"

    def test_quoted_phrase_exact(self) -> None:
        """引号内的短语应做精确匹配。"""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query='"团队建设"', use_index=True)

        assert mock_fts.call_count == 1
        assert mock_fts.call_args.args[0] == '"团队建设"'

    def test_lowercase_and_not_treated_as_operator(self) -> None:
        """Natural-language 'and'/'or'/'not' must NOT be treated as FTS operators (B-2)."""
        from tools.search_journals.keyword_pipeline import _has_explicit_fts_operator

        assert _has_explicit_fts_operator("how and why") is False
        assert _has_explicit_fts_operator("this or that") is False
        assert _has_explicit_fts_operator("not available") is False

    def test_uppercase_and_or_not_still_operators(self) -> None:
        """Upper-case AND/OR/NOT must still be treated as FTS operators."""
        from tools.search_journals.keyword_pipeline import _has_explicit_fts_operator

        assert _has_explicit_fts_operator("team AND project") is True
        assert _has_explicit_fts_operator("team OR project") is True
        assert _has_explicit_fts_operator("team NOT project") is True

    def test_natural_language_query_gets_segmented(self) -> None:
        """'how and why' should not be treated as FTS AND; stopwords are filtered."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query="how and why", use_index=True)

        # T3.3: English stopwords ('how', 'and') are filtered, leaving 'why'.
        # The key invariant is that lowercase 'and' is NOT misinterpreted as
        # the FTS AND operator (which would produce "how AND and AND why").
        assert mock_fts.call_count >= 1
        fts_query = mock_fts.call_args_list[0].args[0]
        assert fts_query == "why"

    def test_no_segmented_sentinel_in_fts_query(self) -> None:
        """B-3: The __SEGMENTED__ sentinel must never appear in FTS queries."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query="想念我的女儿", use_index=True)

        assert mock_fts.call_count >= 1
        for call in mock_fts.call_args_list:
            fts_query = call.args[0]
            assert (
                "__SEGMENTED__" not in fts_query
            ), f"B-3: sentinel leaked into FTS query: {fts_query}"
