#!/usr/bin/env python3
"""
Tests for summary/abstract field compatibility (Round 5 Task 6).
"""

import pytest
from typing import Optional

from tools.lib.frontmatter import (
    parse_frontmatter,
    format_frontmatter,
    get_summary,
    FIELD_ORDER,
    STRING_FIELDS,
)


class TestSummaryFieldParsing:
    """summary 字段可被正常解析。"""

    def test_summary_field_parsed(self) -> None:
        """summary 字段出现在 frontmatter 中时，parse_frontmatter 正确提取。"""
        content = "---\ntitle: test\nsummary: 这是摘要\n---\n\n# test\n"
        fm, body = parse_frontmatter(content)
        assert fm["summary"] == "这是摘要"

    def test_summary_takes_priority_over_abstract(self) -> None:
        """同时存在 summary 和 abstract 时，get_summary() 返回 summary。"""
        content = "---\ntitle: test\nsummary: 新摘要\nabstract: 旧摘要\n---\n\n# test\n"
        fm, body = parse_frontmatter(content)
        effective = get_summary(fm)
        assert effective == "新摘要"

    def test_abstract_still_works_alone(self) -> None:
        """只有 abstract 时 get_summary() 仍返回其值。"""
        content = "---\ntitle: test\nabstract: 旧摘要\n---\n\n# test\n"
        fm, body = parse_frontmatter(content)
        effective = get_summary(fm)
        assert effective == "旧摘要"

    def test_neither_field_returns_none(self) -> None:
        """两个字段都不存在时，get_summary() 返回 None。"""
        content = "---\ntitle: test\n---\n\n# test\n"
        fm, body = parse_frontmatter(content)
        assert get_summary(fm) is None


class TestSummaryFieldFormatting:
    """format_frontmatter 正确输出 summary 字段。"""

    def test_new_entries_use_summary(self) -> None:
        """当数据中有 summary 时，format_frontmatter 输出 summary 字段。"""
        data = {"title": "test", "summary": "这是摘要", "date": "2026-04-07"}
        output = format_frontmatter(data)
        assert "summary:" in output
        assert "这是摘要" in output

    def test_abstract_also_formatted_when_present(self) -> None:
        """当数据中有 abstract 时，format_frontmatter 仍然输出。"""
        data = {"title": "test", "abstract": "旧摘要", "date": "2026-04-07"}
        output = format_frontmatter(data)
        assert "abstract:" in output

    def test_both_fields_formatted_when_both_present(self) -> None:
        """两个字段都有时，都输出。"""
        data = {
            "title": "test",
            "summary": "新摘要",
            "abstract": "旧摘要",
            "date": "2026-04-07",
        }
        output = format_frontmatter(data)
        assert "summary:" in output
        assert "abstract:" in output


class TestFieldOrderAndTypes:
    """summary 在 FIELD_ORDER 中排在 abstract 之前。"""

    def test_summary_in_field_order(self) -> None:
        assert "summary" in FIELD_ORDER

    def test_summary_before_abstract(self) -> None:
        """summary 排在 abstract 之前。"""
        summary_idx = FIELD_ORDER.index("summary")
        abstract_idx = FIELD_ORDER.index("abstract")
        assert summary_idx < abstract_idx

    def test_summary_in_string_fields(self) -> None:
        assert "summary" in STRING_FIELDS
