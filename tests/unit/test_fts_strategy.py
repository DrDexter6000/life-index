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


# ---------------------------------------------------------------------------
# R2-A3: FTS Entity Boundary Tests
# ---------------------------------------------------------------------------


class TestFTSEntityBoundary:
    """R2-A3: Entity-expanded queries must be properly segmented for FTS5.

    The bug: expand_query_with_entity_graph() injects AND/OR operators into
    the query string.  _has_explicit_fts_operator() detects these and bypasses
    Chinese segmentation entirely.  Unsegmented Chinese text then cannot match
    jieba-tokenized FTS index content.

    The fix: propagate an entity_expanded flag so that _segment_query_for_fts()
    can segment the non-operator Chinese portions while preserving AND/OR/parens.
    _segment_entity_expanded_query() must return was_segmented=False so that
    _build_fts_queries() uses the operator-passthrough path instead of OR-joining
    all tokens and producing malformed output like "AND OR ... OR OR OR ...".
    """

    # Unicode escape constants — avoid terminal-rendered Chinese (Windows cp936)
    _ZAI = "在"  # 在
    _CQ = "重庆"  # 重庆
    _SC = "山城"  # 山城
    _FSXGDS = "发生过的事"  # 发生过的事
    _TD = "团队"  # 团队
    _JS = "建设"  # 建设
    _BJ = "北京"  # 北京
    _SH = "上海"  # 上海

    @staticmethod
    def _assert_no_malformed_operators(fts_query: str) -> None:
        """Assert FTS query does not contain adjacent-operator garbage."""
        assert "AND OR" not in fts_query, f"Malformed 'AND OR' in: {fts_query!r}"
        assert "OR AND" not in fts_query, f"Malformed 'OR AND' in: {fts_query!r}"
        assert "OR OR" not in fts_query, f"Malformed 'OR OR' in: {fts_query!r}"
        assert not fts_query.startswith("AND "), f"Leading AND in: {fts_query!r}"
        assert not fts_query.startswith("OR "), f"Leading OR in: {fts_query!r}"
        assert not fts_query.endswith(" AND"), f"Trailing AND in: {fts_query!r}"
        assert not fts_query.endswith(" OR"), f"Trailing OR in: {fts_query!r}"

    # -- Test 1: user-typed explicit operators still pass through unchanged --

    def test_user_typed_or_bypasses_segmentation(self) -> None:
        """A user-typed query with OR must reach FTS as-is."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        q = f"{self._TD} OR {self._JS}"
        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query=q, use_index=True, entity_expanded=False)

        assert mock_fts.call_count == 1
        assert mock_fts.call_args.args[0] == q

    def test_user_typed_and_bypasses_segmentation(self) -> None:
        """A user-typed query with AND must reach FTS as-is."""
        from tools.search_journals.keyword_pipeline import run_keyword_pipeline

        q = f"{self._BJ} AND {self._SH}"
        with patch("tools.search_journals.keyword_pipeline.search_l2_metadata") as mock_l2:
            with patch("tools.lib.search_index.search_fts") as mock_fts:
                mock_l2.return_value = {
                    "results": [],
                    "truncated": False,
                    "total_available": 0,
                }
                mock_fts.return_value = []

                run_keyword_pipeline(query=q, use_index=True, entity_expanded=False)

        assert mock_fts.call_count == 1
        assert mock_fts.call_args.args[0] == q

    # -- Test 2: entity-expanded query does NOT bypass segmentation --

    def test_entity_expanded_query_gets_segmented(self) -> None:
        """Entity-expanded query with AND/OR must NOT bypass segmentation."""
        from tools.search_journals.keyword_pipeline import (
            _segment_query_for_fts,
        )

        expanded = f"{self._ZAI} AND ({self._CQ} OR Chongqing OR {self._SC}) AND {self._FSXGDS}"
        result, was_segmented = _segment_query_for_fts(expanded, entity_expanded=True)

        # Must NOT be identical bypass
        assert result != expanded, "Entity-expanded query bypassed segmentation entirely"
        # was_segmented MUST be False — operators are explicit, passthrough path needed
        assert (
            was_segmented is False
        ), "was_segmented=True would cause _build_fts_queries to OR-join everything"

    # -- Test 3: final FTS query preserves AND/OR/parens structure --

    def test_entity_expanded_preserves_operators(self) -> None:
        """After segmentation, AND/OR operators and parentheses must be preserved."""
        from tools.search_journals.keyword_pipeline import (
            _segment_query_for_fts,
        )

        expanded = f"{self._ZAI} AND ({self._CQ} OR Chongqing OR {self._SC}) AND {self._FSXGDS}"
        result, was_segmented = _segment_query_for_fts(expanded, entity_expanded=True)

        assert "AND" in result
        assert "OR" in result
        assert "(" in result
        assert ")" in result
        assert "Chongqing" in result
        assert was_segmented is False

    def test_entity_expanded_builds_correct_fts_query(self) -> None:
        """Full pipeline: entity-expanded query produces valid FTS without malformed operators."""
        from tools.search_journals.keyword_pipeline import (
            _build_fts_queries,
            _segment_query_for_fts,
        )

        expanded = f"{self._ZAI} AND ({self._CQ} OR Chongqing OR {self._SC}) AND {self._FSXGDS}"
        segmented, was_segmented = _segment_query_for_fts(expanded, entity_expanded=True)
        fts_query, fallback = _build_fts_queries(segmented, was_segmented=was_segmented)

        # No fallback — operator passthrough path returns None
        assert fallback is None
        # Must preserve AND/OR structure
        assert "AND" in fts_query
        assert "OR" in fts_query
        # Must NOT contain malformed adjacent operators
        self._assert_no_malformed_operators(fts_query)
        # Must preserve parenthesized group structure
        assert f"({self._CQ} OR Chongqing OR {self._SC})" in fts_query
        assert ") AND" in fts_query

    # -- Test 4: hyphenated date tokens remain safe --

    def test_entity_expanded_date_token_safe(self) -> None:
        """Hyphenated date tokens must be quoted to avoid FTS 'no such column' errors."""
        from tools.search_journals.keyword_pipeline import (
            _build_fts_queries,
            _segment_query_for_fts,
        )

        expanded = f"{self._ZAI} AND ({self._CQ} OR Chongqing) AND 2026-01-15"
        segmented, was_segmented = _segment_query_for_fts(expanded, entity_expanded=True)
        fts_query, _ = _build_fts_queries(segmented, was_segmented=was_segmented)

        # Date must be quoted to prevent FTS interpreting '-' as NOT
        assert '"2026-01-15"' in fts_query, f"Date token not quoted in: {fts_query!r}"
        # Must NOT contain malformed adjacent operators
        self._assert_no_malformed_operators(fts_query)

    # -- Test 5: common no-entity path unchanged --

    def test_no_entity_path_unchanged(self) -> None:
        """When entity_expanded=False (default), behavior is unchanged."""
        from tools.search_journals.keyword_pipeline import _segment_query_for_fts

        # Plain Chinese query — no operators, normal path
        result, was_segmented = _segment_query_for_fts("想念我的女儿")
        assert isinstance(result, str)
        assert isinstance(was_segmented, bool)

        # Query with operators and entity_expanded=False — must bypass
        result2, was_segmented2 = _segment_query_for_fts(
            f"{self._TD} OR {self._JS}", entity_expanded=False
        )
        assert result2 == f"{self._TD} OR {self._JS}"
        assert was_segmented2 is False
