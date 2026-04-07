#!/usr/bin/env python3
"""Unit tests for tools.generate_index."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.generate_index import (
    collect_month_journals,
    collect_year_journals,
    generate_monthly_abstract,
    generate_monthly_index,
    generate_monthly_index_content,
    generate_root_index,
    generate_root_index_content,
    generate_yearly_abstract,
    generate_yearly_index,
    generate_yearly_index_content,
    parse_frontmatter,
)


def _write_journal(
    file_path: Path,
    *,
    title: str,
    date: str,
    topic: str,
    mood: str = "[]",
    location: str = '"Lagos"',
    people: str = "[]",
    tags: str = "[]",
) -> None:
    file_path.write_text(
        "\n".join(
            [
                "---",
                f'title: "{title}"',
                f"date: {date}",
                f"topic: {topic}",
                f"mood: {mood}",
                f"location: {location}",
                f"people: {people}",
                f"tags: {tags}",
                "---",
                "",
                f"# {title}",
                "",
                "正文",
            ]
        ),
        encoding="utf-8",
    )


class TestParseFrontmatter:
    def test_parse_valid_journal_returns_metadata(self, tmp_path: Path) -> None:
        journal = tmp_path / "test.md"
        journal.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n# Content\n",
            encoding="utf-8",
        )

        result = parse_frontmatter(journal)

        assert result["title"] == "Test"
        assert result["date"] == "2026-03-14"

    def test_parse_invalid_journal_returns_empty_dict(self, tmp_path: Path) -> None:
        journal = tmp_path / "broken.md"
        journal.write_bytes(b"\xff\xfe Invalid UTF-8 \x00\x00")

        result = parse_frontmatter(journal)

        assert result == {}


class TestCollectJournals:
    def test_collect_month_journals_includes_new_metadata_fields(
        self, tmp_path: Path
    ) -> None:
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)
        _write_journal(
            month_dir / "life-index_2026-03-04_001.md",
            title="想念尿片侠",
            date="2026-03-04T19:43:02",
            topic='["think", "life"]',
            mood='["思念", "温暖"]',
            people='["团团"]',
            tags='["亲子", "回忆"]',
        )

        with patch("tools.generate_index.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_month_journals(2026, 3)

        assert len(result) == 1
        assert result[0]["location"] == "Lagos"
        assert result[0]["people"] == ["团团"]
        assert result[0]["tags"] == ["亲子", "回忆"]

    def test_collect_year_journals_reads_multiple_months(self, tmp_path: Path) -> None:
        for month in ("01", "02"):
            month_dir = tmp_path / "Journals" / "2026" / month
            month_dir.mkdir(parents=True)
            _write_journal(
                month_dir / f"life-index_2026-{month}-15_001.md",
                title=f"Month {month}",
                date=f"2026-{month}-15T10:00:00",
                topic='["work"]',
            )

        with patch("tools.generate_index.JOURNALS_DIR", tmp_path / "Journals"):
            result = collect_year_journals(2026)

        assert len(result) == 2
        assert {item["month"] for item in result} == {"01", "02"}


class TestRenamedExportsAndMonthlyIndex:
    def test_backward_compatible_aliases_are_preserved(self) -> None:
        assert generate_monthly_abstract is generate_monthly_index
        assert generate_yearly_abstract is generate_yearly_index

    def test_generate_monthly_index_content_uses_new_index_format(self) -> None:
        journals = [
            {
                "file": "life-index_2026-03-04_001.md",
                "path": "./life-index_2026-03-04_001.md",
                "date": "2026-03-04T19:43:02",
                "title": "想念尿片侠",
                "tags": ["亲子", "女儿"],
                "project": "",
                "topic": ["think", "life"],
                "mood": ["思念", "温暖"],
                "people": ["团团"],
                "location": "Lagos",
                "abstract": "翻看女儿照片",
            },
            {
                "file": "life-index_2026-03-07_001.md",
                "path": "./life-index_2026-03-07_001.md",
                "date": "2026-03-07T11:00:00",
                "title": "架构重构初稿",
                "tags": ["重构", "语义搜索"],
                "project": "",
                "topic": ["work", "create"],
                "mood": ["专注"],
                "people": ["Karpathy"],
                "location": "Chongqing",
                "abstract": "开始重构",
            },
        ]

        with patch("tools.generate_index.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2026-03-31"
            content = generate_monthly_index_content(2026, 3, journals)

        assert content.startswith("---\nyear: 2026\nmonth: 3\nentries: 2\n")
        assert 'date_range: "2026-03-01 — 2026-03-31"' in content
        assert "# 2026-03 月度索引" in content
        assert "## 条目列表" in content
        assert "| 日期 | 标题 | 主题 | 情绪 | 地点 | 人物 |" in content
        assert (
            "| 03-04 | [想念尿片侠](life-index_2026-03-04_001.md) | think, life | 思念, 温暖 | Lagos | 团团 |"
            in content
        )
        assert (
            "| 03-07 | [架构重构初稿](life-index_2026-03-07_001.md) | work, create | 专注 | Chongqing | Karpathy |"
            in content
        )
        assert "> *(由月度报告填写——`generate_index` 不生成此段)*" in content
        assert "*Total: 2 entries · Last updated: 2026-03-31*" in content
        assert "## 标签统计" not in content
        assert "## 项目统计" not in content
        assert "## 主题统计" not in content

    def test_generate_monthly_index_writes_new_filename_and_output_path(
        self, tmp_path: Path
    ) -> None:
        month_dir = tmp_path / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True)
        _write_journal(
            month_dir / "life-index_2026-03-04_001.md",
            title="想念尿片侠",
            date="2026-03-04T19:43:02",
            topic='["think", "life"]',
            mood='["思念"]',
            people='["团团"]',
            tags='["亲子"]',
        )

        with patch("tools.generate_index.JOURNALS_DIR", tmp_path / "Journals"):
            result = generate_monthly_index(2026, 3)

        output_path = month_dir / "index_2026-03.md"
        assert result["success"] is True
        assert result["output_path"] == str(output_path)
        assert result["journal_count"] == 1
        assert output_path.exists()
        assert "# 2026-03 月度索引" in output_path.read_text(encoding="utf-8")


class TestYearlyIndex:
    def test_generate_yearly_index_content_renders_month_overview(self) -> None:
        monthly_summaries = [
            {
                "month": "01",
                "entries": 12,
                "moods": ["专注", "幸福"],
                "locations": ["Shenzhen", "Chongqing"],
                "notable_tags": ["新年", "重构"],
                "relative_path": "01/index_2026-01.md",
            },
            {
                "month": "02",
                "entries": 8,
                "moods": ["焦虑", "疲惫"],
                "locations": ["Lagos"],
                "notable_tags": ["出差", "Life Index v1.5"],
                "relative_path": "02/index_2026-02.md",
            },
        ]
        journals = [
            {
                "topic": ["work", "create"],
                "mood": ["专注"],
                "location": "Shenzhen",
                "people": ["团团"],
                "tags": ["重构"],
            },
            {
                "topic": ["life"],
                "mood": ["幸福", "焦虑"],
                "location": "Lagos",
                "people": ["张三"],
                "tags": ["出差"],
            },
        ]

        content = generate_yearly_index_content(2026, journals, monthly_summaries)

        assert content.startswith("---\nyear: 2026\nentries: 2\n")
        assert "# 2026 年度索引" in content
        assert "## 月度总览" in content
        assert (
            "| [01](01/index_2026-01.md) | 12 | 专注, 幸福 | Shenzhen, Chongqing | 新年, 重构 |"
            in content
        )
        assert (
            "| [02](02/index_2026-02.md) | 8 | 焦虑, 疲惫 | Lagos | 出差, Life Index v1.5 |"
            in content
        )
        assert "> *(由年度报告填写——`generate_index` 不生成此段)*" in content
        assert "*Total: 2 entries*" in content

    def test_generate_yearly_index_uses_monthly_index_and_fallback_scan(
        self, tmp_path: Path
    ) -> None:
        year_dir = tmp_path / "Journals" / "2026"
        jan_dir = year_dir / "01"
        feb_dir = year_dir / "02"
        jan_dir.mkdir(parents=True)
        feb_dir.mkdir(parents=True)

        (jan_dir / "index_2026-01.md").write_text(
            "\n".join(
                [
                    "---",
                    "year: 2026",
                    "month: 1",
                    "entries: 3",
                    "topics: {work: 2, life: 1}",
                    "moods: {专注: 2, 幸福: 1}",
                    "locations: [Shenzhen, Chongqing]",
                    "people: [团团]",
                    "notable_tags: [重构, 假期]",
                    'date_range: "2026-01-01 — 2026-01-31"',
                    "---",
                    "",
                    "# 2026-01 月度索引",
                ]
            ),
            encoding="utf-8",
        )
        _write_journal(
            feb_dir / "life-index_2026-02-15_001.md",
            title="二月记录",
            date="2026-02-15T09:00:00",
            topic='["create"]',
            mood='["疲惫"]',
            location='"Lagos"',
            people='["Karpathy"]',
            tags='["迁移"]',
        )

        with patch("tools.generate_index.JOURNALS_DIR", tmp_path / "Journals"):
            result = generate_yearly_index(2026)

        output_path = year_dir / "index_2026.md"
        output = output_path.read_text(encoding="utf-8")
        assert result["success"] is True
        assert result["output_path"] == str(output_path)
        assert result["journal_count"] == 4
        assert (
            "| [01](01/index_2026-01.md) | 3 | 专注, 幸福 | Shenzhen, Chongqing | 重构, 假期 |"
            in output
        )
        assert "| [02](02/index_2026-02.md) | 1 | 疲惫 | Lagos | 迁移 |" in output
        assert "Karpathy" in output


class TestRootIndex:
    def test_generate_root_index_content_keeps_output_compact(self) -> None:
        yearly_summaries = [
            {
                "year": 2026,
                "entries": 89,
                "locations": ["Lagos", "Shenzhen", "Chongqing"],
                "topics": ["work", "create", "think", "life"],
                "relative_path": "Journals/2026/index_2026.md",
            },
            {
                "year": 2025,
                "entries": 276,
                "locations": ["Lagos", "Chongqing", "Beijing"],
                "topics": ["life", "relation", "work", "health"],
                "relative_path": "Journals/2025/index_2025.md",
            },
        ]
        topic_summaries = [
            {
                "name": "work",
                "file": "主题_work.md",
                "count": 120,
            },
            {
                "name": "life",
                "file": "主题_life.md",
                "count": 98,
            },
        ]

        with patch("tools.generate_index.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2026-03-31"
            content = generate_root_index_content(
                yearly_summaries=yearly_summaries,
                topic_summaries=topic_summaries,
                total_entries=365,
                date_range="2025-01 — 2026-03",
            )

        assert content.startswith(
            '---\ntotal_entries: 365\ndate_range: "2025-01 — 2026-03"\n---'
        )
        assert (
            "| [2026](Journals/2026/index_2026.md) | 89 | Lagos, Shenzhen, Chongqing | work, create, think, life |"
            in content
        )
        assert "- [主题_work.md](by-topic/主题_work.md) · work · (120)" in content
        assert "*Last updated: 2026-03-31 · Total entries: 365*" in content
        assert len(content.encode("utf-8")) < 2048

    def test_generate_root_index_reads_yearly_indexes_and_topic_files(
        self, tmp_path: Path
    ) -> None:
        user_data_dir = tmp_path / "Life-Index"
        journals_dir = user_data_dir / "Journals"
        by_topic_dir = user_data_dir / "by-topic"
        (journals_dir / "2026").mkdir(parents=True)
        (journals_dir / "2025").mkdir(parents=True)
        by_topic_dir.mkdir(parents=True)

        (journals_dir / "2026" / "index_2026.md").write_text(
            "\n".join(
                [
                    "---",
                    "year: 2026",
                    "entries: 89",
                    "topics: {work: 32, create: 18, think: 12, life: 15}",
                    "moods: {专注: 28}",
                    "locations: [Lagos, Shenzhen, Chongqing]",
                    "people: [团团]",
                    "notable_tags: [重构] ",
                    "---",
                    "",
                    "# 2026 年度索引",
                ]
            ),
            encoding="utf-8",
        )
        (journals_dir / "2025" / "index_2025.md").write_text(
            "\n".join(
                [
                    "---",
                    "year: 2025",
                    "entries: 276",
                    "topics: {life: 120, relation: 40, work: 35, health: 22}",
                    "moods: {幸福: 40}",
                    "locations: [Lagos, Chongqing, Beijing]",
                    "people: [张三]",
                    "notable_tags: [迁移]",
                    "---",
                    "",
                    "# 2025 年度索引",
                ]
            ),
            encoding="utf-8",
        )
        (by_topic_dir / "主题_work.md").write_text("# work\n", encoding="utf-8")
        (by_topic_dir / "主题_life.md").write_text("# life\n", encoding="utf-8")

        with (
            patch("tools.generate_index.USER_DATA_DIR", user_data_dir),
            patch("tools.generate_index.JOURNALS_DIR", journals_dir),
        ):
            result = generate_root_index()

        output_path = user_data_dir / "INDEX.md"
        output = output_path.read_text(encoding="utf-8")
        assert result["success"] is True
        assert result["output_path"] == str(output_path)
        assert result["journal_count"] == 365
        assert "[2026](Journals/2026/index_2026.md)" in output
        assert "[2025](Journals/2025/index_2025.md)" in output
        assert "[主题_work.md](by-topic/主题_work.md)" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
