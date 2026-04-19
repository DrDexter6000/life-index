"""
Phase 0 Integration Test — CLI encoding + FTS schema migration (Round 10).

End-to-end verification that T0.1–T0.3 work together:
1. CLI subprocess with Chinese query returns valid JSON (T0.1)
2. Search result titles are raw text, not segmented (T0.2)
3. Old v1 schema auto-migrates to v2 on search (T0.3)
"""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _setup_isolation(isolated_data_dir: Path) -> None:
    """Set up isolated data directory for all Phase 0 integration tests."""
    self_data_dir = isolated_data_dir
    journals_dir = isolated_data_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True, exist_ok=True)

    # Create a test journal with Chinese title
    journal_content = """---
title: "想念尿片侠"
date: 2026-03-04T19:43:02
location: "Chongqing, China"
weather: "晴天（浮云、阵雨）"
mood: ["思念", "温暖"]
people: ["团团"]
tags: ["亲子", "回忆"]
project: "LifeIndex"
topic: ["think", "create"]
abstract: "翻看女儿团团小时候的照片。"
---

# 想念尿片侠

看到团团小时候的照片，那个只有2岁上下的尿片侠。
突然有一种伤感——我好想这个小娃娃。
"""
    journal_path = journals_dir / "life-index_2026-03-04_001.md"
    journal_path.write_text(journal_content, encoding="utf-8")


class TestPhase0Integration:
    """Phase 0 E2E: encoding + title split + schema migration."""

    @pytest.mark.integration
    def test_subprocess_search_returns_valid_json_with_raw_title(
        self, isolated_data_dir: Path
    ) -> None:
        """
        Full E2E: build index → CLI search → verify JSON + raw title.

        Validates:
        - CLI subprocess doesn't crash (R10 fix)
        - JSON output is valid
        - Title is raw "想念尿片侠", not "想念 尿片 侠" (R11 fix)
        """
        # First, build the index via Python API
        import importlib
        import tools.lib.search_index as si_mod

        importlib.reload(si_mod)
        from tools.lib.search_index import update_index

        result = update_index(incremental=False)
        assert result["success"], f"Index build failed: {result}"

        # Now call CLI as subprocess (the real R10 test)
        env = os.environ.copy()
        env["LIFE_INDEX_DATA_DIR"] = str(isolated_data_dir)

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.search_journals",
                "--query",
                "团团",
                "--no-semantic",
            ],
            capture_output=True,
            encoding="utf-8",
            env=env,
            timeout=60,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        # Must not crash (R10)
        assert proc.returncode == 0, f"CLI failed. stderr: {proc.stderr}"

        # Must produce valid JSON
        output = json.loads(proc.stdout)
        assert output["success"] is True

        # Title must be raw (R11)
        results = output.get("merged_results", [])
        if results:
            title = results[0]["title"]
            assert "想念 尿片" not in title, (
                f"Title should be raw, not segmented: '{title}'"
            )
            assert title == "想念尿片侠", f"Expected raw title, got: '{title}'"

    @pytest.mark.integration
    def test_old_schema_auto_migrates_on_index_open(
        self, isolated_data_dir: Path
    ) -> None:
        """
        Simulate a v1.x user upgrading: old schema DB auto-migrates.

        Steps:
        1. Create v1 schema DB (no title_segmented)
        2. Call update_index() which triggers ensure_fts_schema()
        3. Verify schema is now v2 and titles are raw
        """
        import importlib
        import tools.lib.search_index as si_mod

        importlib.reload(si_mod)
        from tools.lib.search_index import (
            FTS_DB_PATH,
            ensure_fts_schema,
            search_fts,
        )

        # Create v1 schema DB
        FTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(FTS_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE VIRTUAL TABLE journals USING fts5(
                path, title, content, date, location, weather,
                topic, project, tags, mood, people,
                file_hash UNINDEXED, modified_time UNINDEXED
            )
        """)
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        cursor.execute(
            "INSERT OR REPLACE INTO index_meta VALUES (?, ?)",
            ("schema_version", "1"),
        )
        conn.commit()
        conn.close()

        # Migration should happen automatically
        migration_result = ensure_fts_schema()
        assert migration_result["migrated"] is True

        # Verify v2 schema
        conn2 = sqlite3.connect(str(FTS_DB_PATH))
        c2 = conn2.cursor()
        c2.execute("PRAGMA table_info(journals)")
        columns = {row[1] for row in c2.fetchall()}
        conn2.close()

        assert "title_segmented" in columns

        # Verify search works with raw titles
        results = search_fts("团团")
        if results:
            assert results[0]["title"] == "想念尿片侠"

    @pytest.mark.integration
    def test_rebuild_produces_v2_schema_with_raw_titles(
        self, isolated_data_dir: Path
    ) -> None:
        """
        Fresh `life-index index --rebuild` should produce v2 schema
        with raw titles and segmented title_segmented column.
        """
        import importlib
        import tools.lib.search_index as si_mod
        import tools.lib.fts_update as fu_mod

        importlib.reload(si_mod)
        importlib.reload(fu_mod)

        from tools.lib.search_index import (
            FTS_DB_PATH,
            update_index,
            search_fts,
        )
        from tools.lib.search_constants import TOKENIZER_VERSION

        result = update_index(incremental=False)
        assert result["success"]
        assert result["total"] == 1

        # Check schema version
        conn = sqlite3.connect(str(FTS_DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM index_meta WHERE key = 'schema_version'")
        schema_row = cursor.fetchone()

        cursor.execute("SELECT title, title_segmented FROM journals")
        data_row = cursor.fetchone()
        conn.close()

        assert schema_row is not None
        assert int(schema_row[0]) == 2, "Schema should be v2"

        assert data_row is not None
        title, title_segmented = data_row

        # Title is raw
        assert title == "想念尿片侠"
        # Title_segmented has spaces from jieba
        assert " " in title_segmented
