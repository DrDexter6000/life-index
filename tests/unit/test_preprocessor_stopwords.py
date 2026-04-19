#!/usr/bin/env python3
"""Task 4.4 RED: Preprocessor keywords stopwords filtering.

Tests that English stopwords are filtered from preprocessor keywords output.
Only pure ASCII tokens should be filtered — Chinese queries should be unaffected.

Run BEFORE implementation to verify RED phase.
"""

import pytest

from tools.search_journals.query_preprocessor import extract_keywords, build_search_plan


# ── Test 1: "missing my daughter" → no "my" in keywords ────────────────


def test_missing_my_daughter_filters_my() -> None:
    ""'"missing my daughter" should not contain "my" in keywords.'''
    keywords = extract_keywords("missing my daughter")
    assert "my" not in [k.lower() for k in keywords]


# ── Test 2: "what did I do yesterday" → no "what", "did", "I" ──────────


def test_what_did_i_do_filters_stopwords() -> None:
    ""'"what did I do yesterday" should not contain "what", "did", "I".'''
    keywords = extract_keywords("what did I do yesterday")
    lower_keywords = [k.lower() for k in keywords]
    assert "what" not in lower_keywords
    assert "did" not in lower_keywords
    assert "i" not in lower_keywords


# ── Test 3: "AI development" → keeps "AI", "development" ───────────────


def test_ai_development_keeps_real_words() -> None:
    ""'"AI development" should keep both "AI" and "development".'''
    keywords = extract_keywords("AI development")
    lower_keywords = [k.lower() for k in keywords]
    assert "ai" in lower_keywords
    assert "development" in lower_keywords


# ── Test 4: Chinese queries unaffected ──────────────────────────────────


def test_chinese_queries_unaffected() -> None:
    """Chinese query should not lose tokens to English stopword filtering."""
    keywords = extract_keywords("我想念我的女儿")
    # Should still have meaningful tokens
    assert len(keywords) >= 1
    # "我的" is a Chinese word, not an English stopword
    # The tokenizer may split it differently but it should NOT be filtered by English stopwords


# ── Test 5: Mixed English+Chinese preserves both ────────────────────────


def test_mixed_english_chinese() -> None:
    """Mixed English+Chinese should filter English stopwords but keep Chinese."""
    keywords = extract_keywords("the 健康检查")
    lower_keywords = [k.lower() for k in keywords]
    assert "the" not in lower_keywords
    # Chinese characters should remain
    has_chinese = any(any('\u4e00' <= c <= '\u9fff' for c in k) for k in keywords)
    assert has_chinese


# ── Test 6: build_search_plan also filters stopwords from keywords ──────


def test_build_search_plan_filters_stopwords() -> None:
    """build_search_plan should also filter stopwords from its keywords field."""
    plan = build_search_plan("what did I do yesterday")
    lower_kw = [k.lower() for k in plan.keywords]
    assert "what" not in lower_kw
    assert "did" not in lower_kw
    assert "i" not in lower_kw


# ── Test 7: Common stopword list coverage ───────────────────────────────


def test_common_stopwords_filtered() -> None:
    """Verify common English stopwords are filtered."""
    for word in ["my", "the", "a", "an", "is", "was", "are", "have", "has", "do", "does"]:
        keywords = extract_keywords(f"{word} testing")
        lower_kw = [k.lower() for k in keywords]
        assert word.lower() not in lower_kw, f"Stopword '{word}' should be filtered"


# ── Round 13 Phase 3: Chinese stopword filtering ─────────────────────


class TestChineseStopwordFiltering:
    """Tests for Chinese function word and punctuation stopword filtering."""

    def test_zh_stopword_filters_punctuation(self) -> None:
        """Chinese punctuation marks should be in zh stopword set."""
        from tools.search_journals.stopwords import load_stopwords

        zh_sw = load_stopwords("zh")
        assert "？" in zh_sw
        assert "！" in zh_sw
        assert "。" in zh_sw

    def test_zh_stopword_filters_function_words(self) -> None:
        """High-frequency function words should be in zh stopword set."""
        from tools.search_journals.stopwords import load_stopwords

        zh_sw = load_stopwords("zh")
        # "有" is already in the file but verify it stays
        assert "有" in zh_sw
        # New additions
        assert "得" in zh_sw

    def test_extract_keywords_filters_stopwords(self) -> None:
        """extract_keywords should filter out zh stopwords."""
        keywords = extract_keywords("我有多久没有关心过健康了？")
        # Should not contain these stopwords
        for w in ["有", "没有", "过", "？"]:
            assert w not in keywords, f"Stopword '{w}' should be filtered out"

    def test_extract_keywords_preserves_content(self) -> None:
        """extract_keywords should preserve content words after filtering."""
        keywords = extract_keywords("我有多久没有关心过健康了？")
        # Should contain content words
        keyword_text = "".join(keywords)
        assert "关心" in keyword_text or "健康" in keyword_text

    def test_zh_stopword_comma(self) -> None:
        """Chinese comma should be in zh stopword set."""
        from tools.search_journals.stopwords import load_stopwords

        zh_sw = load_stopwords("zh")
        assert "，" in zh_sw

    def test_zh_stopword_semicolon(self) -> None:
        """Chinese semicolon should be in zh stopword set."""
        from tools.search_journals.stopwords import load_stopwords

        zh_sw = load_stopwords("zh")
        assert "；" in zh_sw
