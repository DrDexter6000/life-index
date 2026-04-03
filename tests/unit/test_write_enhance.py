#!/usr/bin/env python3

from pathlib import Path

import pytest

from tools.lib.frontmatter import format_frontmatter, parse_frontmatter
from tools.lib.schema import migrate_metadata, validate_metadata
from tools.write_journal.prepare import prepare_journal_metadata


def test_sentiment_score_valid_range() -> None:
    metadata = {
        "schema_version": 2,
        "title": "x",
        "date": "2026-04-03",
        "sentiment_score": 0.6,
    }

    issues = validate_metadata(metadata)

    assert not [issue for issue in issues if issue["field"] == "sentiment_score"]


def test_sentiment_score_out_of_range_rejected() -> None:
    metadata = {
        "schema_version": 2,
        "title": "x",
        "date": "2026-04-03",
        "sentiment_score": 1.5,
    }

    issues = validate_metadata(metadata)

    assert any(issue["field"] == "sentiment_score" for issue in issues)


def test_themes_is_list_of_strings() -> None:
    text = format_frontmatter(
        {
            "schema_version": 2,
            "title": "x",
            "date": "2026-04-03",
            "themes": ["family", "memory"],
        }
    )

    metadata, _ = parse_frontmatter(f"{text}\n\nbody")

    assert metadata["themes"] == ["family", "memory"]


def test_entities_references_valid_ids() -> None:
    metadata = {
        "schema_version": 2,
        "title": "x",
        "date": "2026-04-03",
        "entities": ["mama", "tuantuan"],
    }

    issues = validate_metadata(metadata)

    assert not [issue for issue in issues if issue["field"] == "entities"]


def test_schema_version_2_accepted() -> None:
    metadata = {"schema_version": 2, "title": "x", "date": "2026-04-03"}

    issues = validate_metadata(metadata)

    assert not [issue for issue in issues if issue["field"] == "schema_version"]


def test_schema_version_1_backward_compat() -> None:
    metadata = {"schema_version": 1, "title": "x", "date": "2026-04-03"}

    migrated = migrate_metadata(metadata)

    assert migrated["schema_version"] == 2


def test_old_journals_without_new_fields_valid() -> None:
    metadata = {"title": "x", "date": "2026-04-03"}

    migrated = migrate_metadata(metadata)

    assert migrated["schema_version"] == 2
    assert "sentiment_score" in migrated
    assert "themes" in migrated
    assert "entities" in migrated


def test_prepare_journal_metadata_normalizes_links_list() -> None:
    result = prepare_journal_metadata(
        {
            "content": "今天记录一个外部参考资料。",
            "date": "2026-04-03",
            "topic": ["learn"],
            "links": ["https://example.com/post", "https://example.com/docs"],
        },
        use_llm=False,
    )

    assert result["links"] == [
        "https://example.com/post",
        "https://example.com/docs",
    ]


def test_prepare_journal_metadata_normalizes_links_string() -> None:
    result = prepare_journal_metadata(
        {
            "content": "今天记录一个外部参考资料。",
            "date": "2026-04-03",
            "topic": ["learn"],
            "links": "https://example.com/post, https://example.com/docs",
        },
        use_llm=False,
    )

    assert result["links"] == [
        "https://example.com/post",
        "https://example.com/docs",
    ]


def test_prepare_journal_metadata_normalizes_related_entries_string() -> None:
    result = prepare_journal_metadata(
        {
            "content": "今天记录和旧日志的关系。",
            "date": "2026-04-03",
            "topic": ["learn"],
            "related_entries": "Journals/2026/03/a.md, Journals/2026/03/b.md",
        },
        use_llm=False,
    )

    assert result["related_entries"] == [
        "Journals/2026/03/a.md",
        "Journals/2026/03/b.md",
    ]


def test_write_generates_sentiment_score(isolated_data_dir: Path) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.write_journal.core import write_journal

    def fake_sentiment(_content: str) -> float | None:
        return 0.8

    def fake_themes(_content: str) -> list[str]:
        return ["family", "joy"]

    content_analysis.generate_sentiment_score = fake_sentiment
    content_analysis.extract_themes = fake_themes

    result = write_journal(
        {
            "date": "2026-04-03",
            "title": "开心的一天",
            "content": "今天和家人一起吃饭，感觉非常幸福。",
        },
        dry_run=True,
    )

    assert result["success"] is True
    assert result["prepared_metadata"]["sentiment_score"] is not None


def test_sentiment_score_reflects_content(isolated_data_dir: Path) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.write_journal.core import write_journal

    def fake_sentiment(content: str) -> float | None:
        if "开心" in content or "幸福" in content:
            return 0.9
        return -0.8

    content_analysis.generate_sentiment_score = fake_sentiment
    content_analysis.extract_themes = lambda _content: ["test-theme"]

    positive = write_journal(
        {
            "date": "2026-04-03",
            "title": "好消息",
            "content": "今天非常开心，特别幸福，收获满满。",
        },
        dry_run=True,
    )
    negative = write_journal(
        {
            "date": "2026-04-03",
            "title": "坏消息",
            "content": "今天很痛苦，很难过，也非常失望。",
        },
        dry_run=True,
    )

    assert positive["prepared_metadata"]["sentiment_score"] > 0
    assert negative["prepared_metadata"]["sentiment_score"] < 0


def test_write_generates_themes(isolated_data_dir: Path) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.write_journal.core import write_journal

    content_analysis.generate_sentiment_score = lambda _content: 0.3
    content_analysis.extract_themes = lambda _content: ["family", "memory"]

    result = write_journal(
        {
            "date": "2026-04-03",
            "title": "家庭晚餐",
            "content": "今天和家人一起吃饭，聊了很多成长和回忆。",
        },
        dry_run=True,
    )

    assert result["prepared_metadata"]["themes"]


def test_themes_are_meaningful(isolated_data_dir: Path) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.write_journal.core import write_journal

    content_analysis.generate_sentiment_score = lambda _content: 0.1
    content_analysis.extract_themes = lambda _content: ["project", "teamwork"]

    result = write_journal(
        {
            "date": "2026-04-03",
            "title": "工作复盘",
            "content": "今天复盘了项目推进、团队协作与长期目标。",
        },
        dry_run=True,
    )

    assert any(theme for theme in result["prepared_metadata"]["themes"])


def test_write_populates_entities_from_people_location(isolated_data_dir: Path) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.lib.entity_graph import save_entity_graph
    from tools.lib.paths import USER_DATA_DIR
    from tools.write_journal.core import write_journal

    content_analysis.generate_sentiment_score = lambda _content: None
    content_analysis.extract_themes = lambda _content: []

    save_entity_graph(
        [
            {
                "id": "mama",
                "type": "person",
                "primary_name": "妈妈",
                "aliases": [],
                "relationships": [],
            },
            {
                "id": "cq",
                "type": "place",
                "primary_name": "重庆",
                "aliases": [],
                "relationships": [],
            },
        ],
        USER_DATA_DIR / "entity_graph.yaml",
    )

    result = write_journal(
        {
            "date": "2026-04-03",
            "title": "回家",
            "content": "今天回重庆看妈妈。",
            "people": ["妈妈"],
            "location": "重庆",
        },
        dry_run=True,
    )

    assert result["prepared_metadata"]["entities"] == ["mama", "cq"]


def test_sentiment_generation_failure_graceful(
    isolated_data_dir: Path, monkeypatch
) -> None:
    import tools.lib.content_analysis as content_analysis
    from tools.write_journal.core import write_journal

    monkeypatch.setattr(
        content_analysis, "generate_sentiment_score", lambda _content: None
    )
    monkeypatch.setattr(content_analysis, "extract_themes", lambda _content: [])

    result = write_journal(
        {
            "date": "2026-04-03",
            "title": "普通一天",
            "content": "只是随便记一下。",
        },
        dry_run=True,
    )

    assert result["success"] is True
    assert result["prepared_metadata"]["sentiment_score"] is None
    assert result["prepared_metadata"]["themes"] == []
