#!/usr/bin/env python3
"""Regression tests for FTS schema/query alignment."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.lib import fts_search, search_index


def _init_test_db(tmp_path: Path) -> tuple[sqlite3.Connection, Path]:
    db_path = tmp_path / "journals_fts.db"
    with (
        patch.object(search_index, "FTS_DB_PATH", db_path),
        patch.object(search_index, "INDEX_DIR", tmp_path),
    ):
        conn = search_index.init_fts_db()
    return conn, db_path


def test_new_schema_has_mood_people(tmp_path: Path) -> None:
    conn, _ = _init_test_db(tmp_path)
    try:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(journals)").fetchall()
        }
    finally:
        conn.close()

    assert "mood" in columns
    assert "people" in columns


def test_primary_query_works_with_new_schema(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    conn, db_path = _init_test_db(tmp_path)
    try:
        conn.execute(
            """
            INSERT INTO journals (
                path, title, content, date, location, weather,
                topic, project, tags, mood, people, file_hash, modified_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Journals/2026/03/life-index_2026-03-14_001.md",
                "Focused day",
                "Alice and I shipped the search fix.",
                "2026-03-14",
                "Lagos",
                "Sunny",
                '["work"]',
                "Life Index",
                '["fts"]',
                '["happy"]',
                '["Alice"]',
                "hash-001",
                "2026-03-14T10:00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with caplog.at_level("WARNING"):
        results = fts_search.search_fts(db_path, "Alice")

    assert len(results) == 1
    assert results[0]["mood"] == ["happy"]
    assert results[0]["people"] == ["Alice"]
    assert "FTS primary query failed" not in caplog.text


def test_insert_and_retrieve_mood_people(tmp_path: Path) -> None:
    journals_dir = tmp_path / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True)
    journal_path = journals_dir / "life-index_2026-03-14_001.md"
    journal_path.write_text(
        """---
title: Mood Test
date: 2026-03-14
topic: [work]
tags: [fts]
mood: [happy]
people: [Alice]
---

Alice helped fix the FTS schema mismatch.
""",
        encoding="utf-8",
    )

    with (
        patch.object(search_index, "JOURNALS_DIR", tmp_path / "Journals"),
        patch.object(search_index, "USER_DATA_DIR", tmp_path),
        patch.object(search_index, "FTS_DB_PATH", tmp_path / "journals_fts.db"),
        patch.object(search_index, "INDEX_DIR", tmp_path / ".index"),
    ):
        result = search_index.update_index(incremental=True)
        results = search_index.search_fts("schema")

    assert result["success"] is True
    assert result["added"] == 1
    assert len(results) == 1
    assert results[0]["mood"] == ["happy"]
    assert results[0]["people"] == ["Alice"]


def test_old_schema_fallback_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "old_journals_fts.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE journals USING fts5(
                path, title, content, date, location, weather, topic, project, tags,
                file_hash UNINDEXED, modified_time UNINDEXED
            )
            """
        )
        conn.execute(
            """
            INSERT INTO journals (
                path, title, content, date, location, weather,
                topic, project, tags, file_hash, modified_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Journals/2026/03/life-index_2026-03-10_001.md",
                "Old schema",
                "Legacy row still matches schema queries.",
                "2026-03-10",
                "Lagos",
                "Sunny",
                "work",
                "Life Index",
                "fts",
                "hash-old",
                "2026-03-10T10:00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with caplog.at_level("WARNING"):
        results = fts_search.search_fts(db_path, "Legacy")

    assert len(results) == 1
    assert results[0]["mood"] == []
    assert results[0]["people"] == []
    assert "FTS primary query failed" in caplog.text
