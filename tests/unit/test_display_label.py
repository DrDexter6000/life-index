#!/usr/bin/env python3
"""Unit tests for the one display-label rule (tools.lib.journal_files)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.lib.journal_files import display_label

PATH = Path("Journals/2026/03/life-index_2026-03-04_001.md")


class TestTitleWins:
    def test_title_returned_stripped_and_unchanged(self) -> None:
        assert display_label("  标题  ", "正文第一行", PATH) == "标题"

    def test_title_beats_body_and_file_name(self) -> None:
        assert display_label("标题", "完全不同的正文", PATH) == "标题"

    def test_whitespace_only_title_falls_through_to_body(self) -> None:
        assert display_label("   \n\t ", "第一行内容", PATH) == "第一行内容"


class TestBodyFirstLine:
    @pytest.mark.parametrize("terminator", ["。", "！", "？", "!", "?"])
    def test_each_terminator_cuts_and_is_kept(self, terminator: str) -> None:
        body = f"前面的话{terminator}后面还有一句"
        assert display_label("", body, PATH) == f"前面的话{terminator}"

    def test_first_non_blank_line_wins_over_later_lines(self) -> None:
        body = "\n\n   \n第一行。\n第二行。"
        assert display_label("", body, PATH) == "第一行。"

    def test_heading_markers_removed(self) -> None:
        assert display_label("", "### 一个标题行", PATH) == "一个标题行"

    def test_marker_only_lines_carry_no_text_and_are_skipped(self) -> None:
        assert display_label("", "###\n#\n实际内容", PATH) == "实际内容"

    def test_cjk_text_cut_at_30_characters_with_ellipsis(self) -> None:
        text = "这" * 40
        assert display_label("", text, PATH) == "这" * 30 + "…"

    def test_exactly_30_characters_gets_no_ellipsis(self) -> None:
        text = "这" * 30
        assert display_label("", text, PATH) == text

    def test_terminator_beyond_30_characters_loses_to_the_length_cut(self) -> None:
        text = "这" * 40 + "。尾"
        assert display_label("", text, PATH) == "这" * 30 + "…"

    def test_terminator_as_the_30th_character_is_kept_without_ellipsis(self) -> None:
        text = "这" * 29 + "。" + "尾部"
        assert display_label("", text, PATH) == "这" * 29 + "。"

    def test_ascii_text_uses_the_same_30_character_cut(self) -> None:
        text = "a" * 33
        assert display_label("", text, PATH) == "a" * 30 + "…"


class TestFileNameFallback:
    def test_blank_body_falls_back_to_file_name_without_extension(self) -> None:
        assert display_label("", "", PATH) == "life-index_2026-03-04_001"

    def test_whitespace_body_falls_back_to_file_name(self) -> None:
        assert display_label(" ", " \n \t ", PATH) == "life-index_2026-03-04_001"

    def test_marker_only_body_falls_back_to_file_name(self) -> None:
        assert display_label("", "#\n###", PATH) == "life-index_2026-03-04_001"
