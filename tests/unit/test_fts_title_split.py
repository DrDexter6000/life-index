"""
Tests for FTS title column split (Round 10, T0.2).

Validates R11 fix: search result titles should be raw text,
not jieba-segmented tokens with spaces.

Design: title column stores raw text (for display, UNINDEXED),
title_segmented stores jieba tokens (for FTS matching, indexed).
"""

import importlib
import sqlite3
from pathlib import Path
from typing import Any

import pytest


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reload_search_index(isolated_data_dir: Path) -> None:
    """
    Reload search_index module so module-level FTS_DB_PATH
    picks up the isolated data directory from config.
    """
    import tools.lib.search_index as si_mod
    import tools.lib.fts_update as fu_mod
    import tools.lib.fts_search as fs_mod

    importlib.reload(si_mod)
    importlib.reload(fu_mod)
    importlib.reload(fs_mod)


def _get_fts_db_path() -> Path:
    """Get current FTS_DB_PATH from reloaded search_index module."""
    from tools.lib.search_index import FTS_DB_PATH

    return FTS_DB_PATH


# ── Schema verification ────────────────────────────────────────────────


class TestFTSTitleSchema:
    """Verify FTS table has both title and title_segmented columns."""

    def test_schema_has_both_title_columns(self, isolated_data_dir: Path) -> None:
        """
        After init, PRAGMA table_info(journals) must contain:
        - 'title' (raw)
        - 'title_segmented' (jieba tokens)
        """
        from tools.lib.search_index import init_fts_db

        _get_fts_db_path().parent.mkdir(parents=True, exist_ok=True)
        conn = init_fts_db()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(journals)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "title" in columns, "FTS table must have 'title' column"
        assert "title_segmented" in columns, (
            "FTS table must have 'title_segmented' column"
        )

    def test_title_is_unindexed(self, isolated_data_dir: Path) -> None:
        """
        The 'title' column should be UNINDEXED to prevent raw Chinese
        text from interfering with FTS matching.
        """
        from tools.lib.search_index import init_fts_db

        fts_db_path = _get_fts_db_path()
        fts_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = init_fts_db()
        conn.close()

        conn2 = sqlite3.connect(str(fts_db_path))
        cursor = conn2.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE name = 'journals'")
        create_sql = cursor.fetchone()[0]
        conn2.close()

        assert "title UNINDEXED" in create_sql, (
            f"'title' column should be UNINDEXED. Got: {create_sql}"
        )

    def test_title_segmented_is_indexed(self, isolated_data_dir: Path) -> None:
        """
        The 'title_segmented' column should be indexed (searchable by FTS5).
        """
        from tools.lib.search_index import init_fts_db

        fts_db_path = _get_fts_db_path()
        fts_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = init_fts_db()
        conn.close()

        conn2 = sqlite3.connect(str(fts_db_path))
        cursor = conn2.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE name = 'journals'")
        create_sql = cursor.fetchone()[0]
        conn2.close()

        assert "title_segmented UNINDEXED" not in create_sql, (
            f"'title_segmented' should be indexed. Got: {create_sql}"
        )


# ── Search result title verification ───────────────────────────────────


class TestFTSTitleDisplay:
    """Verify search results return raw title, not segmented tokens."""

    def _create_journal(
        self, data_dir: Path, title: str, content: str = "测试内容"
    ) -> Path:
        """Create a minimal journal file in the isolated data dir."""
        from datetime import datetime

        journals_dir = data_dir / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat(timespec="seconds")
        filename = f"life-index_2026-03-07_001.md"
        file_path = journals_dir / filename

        frontmatter = f"""---
title: "{title}"
date: {now}
location: "Lagos, Nigeria"
weather: "晴天 28°C"
mood: ["专注"]
tags: ["测试"]
topic: ["work"]
---

# {title}

{content}
"""
        file_path.write_text(frontmatter, encoding="utf-8")
        return file_path

    def test_title_not_segmented_in_results(self, isolated_data_dir: Path) -> None:
        """
        R11: Search result 'title' must be raw original text,
        NOT jieba-segmented tokens with spaces.

        Before fix: "计划回重庆给小朋友过生日" → "计划 回 重庆 给 小朋友 过生日"
        After fix:  "计划回重庆给小朋友过生日" → "计划回重庆给小朋友过生日"
        """
        from tools.lib.search_index import update_index, search_fts

        raw_title = "计划回重庆给小朋友过生日"
        self._create_journal(
            isolated_data_dir, raw_title, "今天很开心去给小朋友庆祝生日"
        )
        update_index(incremental=False)
        results = search_fts("生日")

        assert len(results) > 0, "Should find results for '生日'"

        # The title must be the original, not segmented
        result_title = results[0]["title"]
        assert result_title == raw_title, (
            f"Title should be raw '{raw_title}', got segmented '{result_title}'"
        )
        assert "计划 回" not in result_title
        assert "重庆 给" not in result_title

    def test_title_segmented_allows_fts_match(self, isolated_data_dir: Path) -> None:
        """
        Despite title being UNINDEXED, FTS should still match via
        title_segmented column when searching for segmented tokens.
        """
        from tools.lib.search_index import update_index, search_fts

        raw_title = "计划回重庆给小朋友过生日"
        self._create_journal(isolated_data_dir, raw_title, "一些正文内容")
        update_index(incremental=False)
        results = search_fts("小朋友")

        assert len(results) > 0, "FTS should match via title_segmented for '小朋友'"


# ── Insert verification ────────────────────────────────────────────────


class TestFTSTitleInsert:
    """Verify parse_journal produces both raw and segmented title."""

    def test_parse_journal_produces_both_titles(self, isolated_data_dir: Path) -> None:
        """
        parse_journal() must return:
        - 'title': raw original title (for display)
        - 'title_segmented': jieba segmented tokens (for FTS)
        """
        from datetime import datetime
        from tools.lib.fts_update import parse_journal

        journals_dir = isolated_data_dir / "Journals" / "2026" / "03"
        journals_dir.mkdir(parents=True, exist_ok=True)

        raw_title = "想念尿片侠"
        file_path = journals_dir / "life-index_2026-03-04_001.md"
        frontmatter = f"""---
title: "{raw_title}"
date: {datetime.now().isoformat(timespec="seconds")}
location: "Lagos, Nigeria"
tags: ["亲子"]
topic: ["think"]
---

# {raw_title}

看到团团小时候的照片。
"""
        file_path.write_text(frontmatter, encoding="utf-8")

        doc = parse_journal(file_path, journals_dir, isolated_data_dir)
        assert doc is not None, "parse_journal should succeed"

        # Raw title must be preserved
        assert doc["title"] == raw_title, (
            f"title should be raw '{raw_title}', got '{doc['title']}'"
        )

        # Segmented title must contain spaces (jieba output)
        assert " " in doc["title_segmented"], (
            f"title_segmented should have spaces from jieba, got '{doc['title_segmented']}'"
        )

        # Segmented title should contain the key token
        assert "尿片" in doc["title_segmented"] or "尿片侠" in doc["title_segmented"], (
            f"title_segmented should contain '尿片' or '尿片侠', got '{doc['title_segmented']}'"
        )
