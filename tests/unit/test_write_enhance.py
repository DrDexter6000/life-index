#!/usr/bin/env python3

from pathlib import Path

from tools.lib.schema import migrate_metadata, validate_metadata
from tools.write_journal.prepare import prepare_journal_metadata


def test_entities_references_valid_ids() -> None:
    metadata = {
        "schema_version": 3,
        "title": "x",
        "date": "2026-04-03",
        "entities": ["mama", "tuantuan"],
    }

    issues = validate_metadata(metadata)

    assert not [issue for issue in issues if issue["field"] == "entities"]


def test_schema_version_3_accepted() -> None:
    metadata = {"schema_version": 3, "title": "x", "date": "2026-04-03"}

    issues = validate_metadata(metadata)

    assert not [issue for issue in issues if issue["field"] == "schema_version"]


def test_schema_version_1_backward_compat() -> None:
    metadata = {"schema_version": 1, "title": "x", "date": "2026-04-03"}

    migrated = migrate_metadata(metadata)

    assert migrated["schema_version"] == 3


def test_old_journals_without_new_fields_valid() -> None:
    metadata = {"title": "x", "date": "2026-04-03"}

    migrated = migrate_metadata(metadata)

    assert migrated["schema_version"] == 3
    assert "entities" in migrated
    assert "sentiment_score" not in migrated
    assert "themes" not in migrated


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


def test_write_preserves_entities_without_sentiment_or_themes(
    isolated_data_dir: Path,
) -> None:
    from tools.write_journal.core import write_journal

    result = write_journal(
        {
            "date": "2026-04-03",
            "title": "开心的一天",
            "content": "今天和家人一起吃饭，感觉非常幸福。",
        },
        dry_run=True,
    )

    assert result["success"] is True
    assert "sentiment_score" not in result["prepared_metadata"]
    assert "themes" not in result["prepared_metadata"]


def test_write_populates_entities_from_people_location(isolated_data_dir: Path) -> None:
    from tools.lib.entity_graph import save_entity_graph
    from tools.lib.paths import USER_DATA_DIR
    from tools.write_journal.core import write_journal

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


def test_write_omits_removed_placeholder_fields(isolated_data_dir: Path) -> None:
    from tools.write_journal.core import write_journal

    result = write_journal(
        {
            "date": "2026-04-03",
            "title": "普通一天",
            "content": "只是随便记一下。",
        },
        dry_run=True,
    )

    assert result["success"] is True
    assert "sentiment_score" not in result["prepared_metadata"]
    assert "themes" not in result["prepared_metadata"]
