#!/usr/bin/env python3
"""Unit tests for tools.lib.chinese_tokenizer."""

from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from tools.lib.chinese_tokenizer import (
    CHINESE_STOP_WORDS,
    _process_text,
    get_dict_hash,
    is_cjk,
    load_entity_dict,
    normalize_query,
    reset_tokenizer_state,
    segment_for_fts,
)


def _tokens(value: str) -> list[str]:
    """Split a space-separated token string into tokens."""
    return [token for token in value.split() if token]


def _make_entity_graph(tmp_dir: Path, entities: list[dict]) -> Path:
    """Create a temporary entity_graph.yaml and return its path."""
    tmp_dir.mkdir(parents=True, exist_ok=True)
    graph_path = tmp_dir / "entity_graph.yaml"
    graph_path.write_text(
        yaml.dump({"entities": entities}, allow_unicode=True), encoding="utf-8"
    )
    return graph_path


class TestIsCJK:
    """Tests for is_cjk."""

    def test_chinese_char(self):
        """Chinese ideograph is recognized as CJK."""
        assert is_cjk("中") is True

    def test_english_char(self):
        """English letter is not CJK."""
        assert is_cjk("A") is False

    def test_number(self):
        """ASCII digit is not CJK."""
        assert is_cjk("1") is False

    def test_cjk_extension(self):
        """CJK Extension A ideograph is recognized."""
        assert is_cjk("㐀") is True

    def test_empty_string(self):
        """Empty string is not CJK."""
        assert is_cjk("") is False


class TestSegmentForFTS:
    """Tests for segment_for_fts."""

    def test_pure_chinese_index(self):
        """Index mode keeps precise Chinese tokens."""
        result = _tokens(segment_for_fts("想念我的女儿", mode="index"))

        assert "想念" in result
        assert "我" in result
        assert "的" in result
        assert "女儿" in result

    def test_pure_english_index(self):
        """Pure English text is preserved."""
        assert segment_for_fts("Google Stitch", mode="index") == "Google Stitch"

    def test_mixed_chinese_english_index(self):
        """Mixed text preserves English and segments Chinese."""
        result = _tokens(segment_for_fts("AI算力投资策略", mode="index"))

        assert "AI" in result
        assert "算力" in result
        assert "投资" in result
        assert "策略" in result

    def test_empty_string(self):
        """Empty input stays empty."""
        assert segment_for_fts("") == ""

    def test_pure_punctuation(self):
        """Pure punctuation is discarded."""
        assert segment_for_fts("，。！", mode="index").strip() == ""

    def test_chinese_with_punctuation(self):
        """Chinese punctuation is removed from token output."""
        result = _tokens(segment_for_fts("你好，世界！", mode="index"))

        assert "你好" in result
        assert "世界" in result
        assert all(token not in {"，", "！"} for token in result)

    def test_pure_chinese_query(self):
        """Query mode keeps content words (stopwords are filtered separately)."""
        result = _tokens(segment_for_fts("想念我的女儿", mode="query"))

        assert "想念" in result
        assert "女儿" in result
        # "我" and "的" are stopwords — filtered in query mode (see TestStopWordFiltering)

    def test_search_mode_expansion(self):
        """Query mode expands long Chinese terms for recall."""
        result = _tokens(segment_for_fts("中华人民共和国", mode="query"))

        assert "中华人民共和国" in result
        assert any(token != "中华人民共和国" for token in result)
        assert any(len(token) < len("中华人民共和国") for token in result)

    def test_index_mode_no_expansion(self):
        """Index mode avoids search-mode subword expansion."""
        result = _tokens(segment_for_fts("中华人民共和国", mode="index"))

        assert result == ["中华人民共和国"]

    def test_query_mode_more_tokens_than_index(self):
        """Query mode should return at least as many tokens as index mode."""
        index_tokens = _tokens(segment_for_fts("中华人民共和国", mode="index"))
        query_tokens = _tokens(segment_for_fts("中华人民共和国", mode="query"))

        assert len(query_tokens) >= len(index_tokens)


class TestProcessText:
    """Tests for _process_text."""

    def test_only_cjk(self):
        """Pure CJK text is segmented into Chinese tokens."""
        result = _process_text("想念我的女儿", mode="index")

        assert "想念" in result
        assert "女儿" in result

    def test_only_english(self):
        """Pure English text is preserved token-by-token."""
        assert _process_text("Google Stitch", mode="index") == ["Google", "Stitch"]

    def test_mixed_preserves_english(self):
        """English tokens survive mixed-text processing."""
        result = _process_text("AI算力 investment", mode="index")

        assert "AI" in result
        assert "investment" in result
        assert "算力" in result

    def test_mixed_preserves_numbers(self):
        """Numeric tokens survive mixed-text processing."""
        result = _process_text("2026年AI计划v2.0", mode="index")

        assert "2026" in result
        assert "AI" in result
        assert "v2.0" in result


class TestStopWordFiltering:
    """Tests for stop word filtering (T1.6)."""

    def test_query_mode_filters_stopwords(self):
        """Query mode removes stop words like '的'."""
        result = _tokens(segment_for_fts("想念我的女儿", mode="query"))

        # "的" should be filtered in query mode
        assert "的" not in result
        # Content words should remain
        assert "想念" in result
        assert "女儿" in result

    def test_query_mode_filters_bu(self):
        """Query mode filters '不' to prevent precision bomb (Metis Risk #2)."""
        result = _tokens(segment_for_fts("乐乐不认真吃饭", mode="query"))

        assert "不" not in result
        assert "乐乐" in result
        assert "认真" in result
        assert "吃饭" in result

    def test_index_mode_no_stopword_filtering(self):
        """Index mode preserves all tokens including stop words."""
        result = _tokens(segment_for_fts("想念我的女儿", mode="index"))

        assert "的" in result

    def test_content_words_not_filtered(self):
        """Important content words are never filtered."""
        for word in ["想念", "女儿", "乐乐", "投资", "策略"]:
            assert word not in CHINESE_STOP_WORDS

    def test_stopword_list_size(self):
        """Stop word list contains at least 40 common words."""
        assert len(CHINESE_STOP_WORDS) >= 40


class TestNormalizeQuery:
    """Tests for query normalization (Round 8 Phase 3 T3.2)."""

    def test_strips_terminal_punctuation(self):
        assert normalize_query("AI算力投资策略！") == "AI算力投资策略"

    def test_strips_book_title_marks(self):
        assert normalize_query("「乐乐」") == "乐乐"

    def test_converts_fullwidth_space(self):
        assert normalize_query("Life　Index") == "Life Index"

    def test_collapses_multiple_spaces(self):
        assert normalize_query("想 念   我 的 女 儿") == "想 念 我 的 女 儿"


class TestEntityDictionary:
    """Tests for entity dictionary loading (T1.5)."""

    def setup_method(self) -> None:
        """Reset tokenizer state before each test."""
        reset_tokenizer_state()

    def test_entity_name_not_split(self):
        """Entity name '乐乐' stays as single token after dict loading."""
        with TemporaryDirectory() as tmp:
            graph_path = _make_entity_graph(
                Path(tmp),
                [
                    {
                        "id": "tuantuan",
                        "type": "person",
                        "primary_name": "乐乐",
                        "aliases": ["小豆丁"],
                        "attributes": {},
                        "relationships": [],
                    }
                ],
            )
            load_entity_dict(graph_path)

        result = _tokens(segment_for_fts("乐乐哭了", mode="index"))
        assert "乐乐" in result

    def test_multi_char_entity_alias(self):
        """Multi-character alias like '小豆丁' stays intact."""
        with TemporaryDirectory() as tmp:
            graph_path = _make_entity_graph(
                Path(tmp),
                [
                    {
                        "id": "tuantuan",
                        "type": "person",
                        "primary_name": "圆圆",
                        "aliases": ["乐乐", "小豆丁", "小英雄"],
                        "attributes": {},
                        "relationships": [],
                    }
                ],
            )
            load_entity_dict(graph_path)

        result = _tokens(segment_for_fts("想念小英雄", mode="index"))
        assert "小英雄" in result

    def test_english_entity_name_ignored(self):
        """English entity names are not loaded into jieba dict."""
        with TemporaryDirectory() as tmp:
            graph_path = _make_entity_graph(
                Path(tmp),
                [
                    {
                        "id": "li",
                        "type": "project",
                        "primary_name": "Life Index",
                        "aliases": [],
                        "attributes": {},
                        "relationships": [],
                    }
                ],
            )
            load_entity_dict(graph_path)

        # Should not error — English names are simply skipped
        result = segment_for_fts("Life Index project", mode="index")
        assert "Life" in result
        assert "Index" in result

    def test_missing_entity_graph_no_error(self):
        """Missing entity_graph.yaml does not cause errors."""
        reset_tokenizer_state()
        graph_path = Path("/nonexistent/entity_graph.yaml")
        load_entity_dict(graph_path)

        # Should still work with default jieba dictionary
        result = segment_for_fts("想念我的女儿", mode="index")
        assert "想念" in result

    def test_dict_hash_consistency(self):
        """Dict hash is consistent for same entity graph."""
        with TemporaryDirectory() as tmp:
            graph_path = _make_entity_graph(
                Path(tmp),
                [
                    {
                        "id": "tuantuan",
                        "type": "person",
                        "primary_name": "乐乐",
                        "aliases": [],
                        "attributes": {},
                        "relationships": [],
                    }
                ],
            )
            reset_tokenizer_state()
            load_entity_dict(graph_path)
            hash1 = get_dict_hash()

            reset_tokenizer_state()
            load_entity_dict(graph_path)
            hash2 = get_dict_hash()

        assert hash1 == hash2
        assert len(hash1) > 0

    def test_dict_hash_changes_with_content(self):
        """Dict hash changes when entity names change."""
        with TemporaryDirectory() as tmp:
            graph_a = _make_entity_graph(
                Path(tmp) / "a",
                [
                    {
                        "id": "a",
                        "type": "person",
                        "primary_name": "乐乐",
                        "aliases": [],
                        "attributes": {},
                        "relationships": [],
                    }
                ],
            )
            graph_b = _make_entity_graph(
                Path(tmp) / "b",
                [
                    {
                        "id": "b",
                        "type": "person",
                        "primary_name": "豆豆",
                        "aliases": [],
                        "attributes": {},
                        "relationships": [],
                    }
                ],
            )

            reset_tokenizer_state()
            load_entity_dict(graph_a)
            hash_a = get_dict_hash()

            reset_tokenizer_state()
            load_entity_dict(graph_b)
            hash_b = get_dict_hash()

        assert hash_a != hash_b
