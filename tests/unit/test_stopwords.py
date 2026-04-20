"""Tests for Chinese and English stopword loading and filtering utilities."""

from tools.search_journals.stopwords import filter_stopwords, is_stopword, load_stopwords


class TestLoadStopwords:
    def test_zh_stopwords_not_empty(self):
        sw = load_stopwords("zh")
        assert len(sw) >= 200

    def test_zh_stopwords_are_frozenset(self):
        sw = load_stopwords("zh")
        assert isinstance(sw, frozenset)

    def test_unknown_lang_returns_empty(self):
        sw = load_stopwords("xx")
        assert len(sw) == 0

    def test_singleton_cache(self):
        """Same lang returns same object (lru_cache)."""
        sw1 = load_stopwords("zh")
        sw2 = load_stopwords("zh")
        assert sw1 is sw2


class TestIsStopword:
    def test_function_words_are_stopwords(self):
        for word in ["的", "了", "在", "是"]:
            assert is_stopword(word), f"'{word}' should be a stopword"

    def test_project_specific_are_stopwords(self):
        for word in ["最近", "今天", "感觉", "觉得"]:
            assert is_stopword(word), f"'{word}' should be a stopword"

    def test_content_words_are_not_stopwords(self):
        for word in ["睡眠", "乐乐", "重构", "工作", "边缘", "计算", "编程", "量子"]:
            assert not is_stopword(word), f"'{word}' should NOT be a stopword"


class TestFilterStopwords:
    def test_removes_function_words(self):
        result = filter_stopwords(["最近", "睡眠", "不足", "的"])
        assert result == ["睡眠", "不足"]

    def test_preserves_all_content_words(self):
        result = filter_stopwords(["量子", "计算", "编程"])
        assert result == ["量子", "计算", "编程"]

    def test_empty_input(self):
        assert filter_stopwords([]) == []

    def test_all_stopwords(self):
        result = filter_stopwords(["的", "了", "在"])
        assert result == []

    def test_preserves_order(self):
        result = filter_stopwords(["重构", "的", "搜索", "模块"])
        assert result == ["重构", "搜索", "模块"]


# ── T3.3: English stopword support ──


class TestEnglishStopwords:
    """Round 11 Phase 3 T3.3: English stopword filtering for FTS queries."""

    def test_load_en_stopwords_returns_frozenset(self) -> None:
        sw = load_stopwords("en")
        assert isinstance(sw, frozenset)

    def test_load_en_stopwords_not_empty(self) -> None:
        sw = load_stopwords("en")
        assert len(sw) >= 40

    def test_common_english_stopwords_present(self) -> None:
        sw = load_stopwords("en")
        expected = {"my", "the", "is", "a", "an", "of", "in", "to", "and", "or"}
        assert expected.issubset(sw), f"Missing: {expected - sw}"

    def test_en_stopwords_cached(self) -> None:
        sw1 = load_stopwords("en")
        sw2 = load_stopwords("en")
        assert sw1 is sw2

    def test_filter_en_removes_stopwords(self) -> None:
        result = filter_stopwords(["missing", "my", "daughter"], lang="en")
        assert result == ["missing", "daughter"]

    def test_filter_en_preserves_content_words(self) -> None:
        result = filter_stopwords(["Claude", "Opus"], lang="en")
        assert result == ["Claude", "Opus"]

    def test_filter_zh_not_regressed_by_en(self) -> None:
        """Chinese stopword filtering must still work after adding English."""
        result = filter_stopwords(["乐乐"], lang="zh")
        assert result == ["乐乐"]

    def test_is_stopword_en(self) -> None:
        assert is_stopword("the", lang="en")
        assert is_stopword("my", lang="en")
        assert not is_stopword("daughter", lang="en")

    def test_filter_en_mixed_case(self) -> None:
        """Stopword matching should be case-insensitive for English."""
        result = filter_stopwords(["Missing", "My", "Daughter"], lang="en")
        assert result == ["Missing", "Daughter"]

    def test_filter_en_empty_input(self) -> None:
        assert filter_stopwords([], lang="en") == []


class TestEnglishStopwordsInFTS:
    """T3.3: Verify English stopword integration in FTS query building."""

    def test_build_fts_queries_filters_english_stopwords(self) -> None:
        from tools.search_journals.keyword_pipeline import _build_fts_queries

        primary, fallback = _build_fts_queries("missing my daughter")
        assert "my" not in primary
        assert "missing" in primary
        assert "daughter" in primary

    def test_build_fts_queries_preserves_quoted_phrases(self) -> None:
        from tools.search_journals.keyword_pipeline import _build_fts_queries

        primary, fallback = _build_fts_queries('"my daughter"')
        # Quoted queries pass through unchanged
        assert primary == '"my daughter"'
        assert fallback is None

    def test_build_fts_queries_chinese_not_affected(self) -> None:
        from tools.search_journals.keyword_pipeline import _build_fts_queries

        # Chinese queries should not have English stopword filtering applied
        primary, fallback = _build_fts_queries("乐乐", was_segmented=True)
        assert "乐乐" in primary
