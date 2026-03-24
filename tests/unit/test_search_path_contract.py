#!/usr/bin/env python3
"""Regression tests for unified search path contract."""

from pathlib import Path
from unittest.mock import patch


class TestPathHelpersContract:
    def test_index_paths_normalize_to_absolute_and_dual_relative_forms(
        self, tmp_path
    ) -> None:
        from tools.lib.path_contract import build_journal_path_fields

        user_data_dir = tmp_path
        journals_dir = user_data_dir / "Journals"
        journal_file = journals_dir / "2026/03/test.md"

        fields = build_journal_path_fields(
            journal_file, journals_dir=journals_dir, user_data_dir=user_data_dir
        )

        assert fields["path"] == str(journal_file).replace("\\", "/")
        assert fields["rel_path"] == "Journals/2026/03/test.md"
        assert fields["journal_route_path"] == "2026/03/test.md"


class TestL1IndexPathContract:
    def test_search_l1_index_uses_user_data_dir_not_project_root(
        self, tmp_path
    ) -> None:
        from tools.search_journals import l1_index

        index_dir = tmp_path / "by-topic"
        index_dir.mkdir(parents=True)
        journals_dir = tmp_path / "Journals"
        journal_file = journals_dir / "2026" / "03" / "test.md"
        journal_file.parent.mkdir(parents=True)
        journal_file.write_text("x", encoding="utf-8")

        index_file = index_dir / "主题_work.md"
        index_file.write_text(
            "- [2026-03-14] [Test Journal](Journals/2026/03/test.md)",
            encoding="utf-8",
        )

        with (
            patch.object(l1_index, "BY_TOPIC_DIR", index_dir),
            patch.object(l1_index, "USER_DATA_DIR", tmp_path),
        ):
            results = l1_index.search_l1_index("topic", "work")

        assert results[0]["path"] == str(journal_file).replace("\\", "/")
        assert results[0]["rel_path"] == "Journals/2026/03/test.md"
        assert results[0]["journal_route_path"] == "2026/03/test.md"


class TestL2MetadataPathContract:
    def test_search_with_cache_exposes_normalized_path_fields(self, tmp_path) -> None:
        from tools.search_journals.l2_metadata import _search_with_cache

        user_data_dir = tmp_path
        journals_dir = user_data_dir / "Journals"
        file_path = journals_dir / "2026" / "03" / "test.md"

        cached_entries = [
            {
                "file_path": str(file_path),
                "date": "2026-03-14",
                "title": "Test Journal",
                "topic": ["work"],
                "metadata": {"title": "Test Journal"},
            }
        ]

        with (
            patch(
                "tools.search_journals.l2_metadata.get_all_cached_metadata",
                return_value=cached_entries,
            ),
            patch(
                "tools.search_journals.l2_metadata.USER_DATA_DIR",
                user_data_dir,
            ),
            patch(
                "tools.search_journals.l2_metadata.JOURNALS_DIR",
                journals_dir,
            ),
        ):
            results = _search_with_cache()

        assert results[0]["path"] == str(file_path).replace("\\", "/")
        assert results[0]["rel_path"] == "Journals/2026/03/test.md"
        assert results[0]["journal_route_path"] == "2026/03/test.md"


class TestL3ContentPathContract:
    def test_search_l3_content_with_specific_paths_exposes_route_path(
        self, tmp_path
    ) -> None:
        from tools.search_journals.l3_content import search_l3_content

        journals_dir = tmp_path / "Journals"
        journal_file = journals_dir / "2026" / "03" / "test.md"
        journal_file.parent.mkdir(parents=True)
        journal_file.write_text(
            "---\ntitle: Test\ndate: 2026-03-14\n---\n\nPython content",
            encoding="utf-8",
        )

        with (
            patch("tools.search_journals.l3_content.USER_DATA_DIR", tmp_path),
            patch("tools.search_journals.l3_content.JOURNALS_DIR", journals_dir),
        ):
            results = search_l3_content("Python", paths=[str(journal_file)])

        assert len(results) == 0

    def test_search_l3_content_with_specific_paths_exposes_route_path_for_strong_match(
        self, tmp_path
    ) -> None:
        from tools.search_journals.l3_content import search_l3_content

        journals_dir = tmp_path / "Journals"
        journal_file = journals_dir / "2026" / "03" / "test.md"
        journal_file.parent.mkdir(parents=True)
        journal_file.write_text(
            "---\ntitle: Python Test\ndate: 2026-03-14\n---\n\nPython content",
            encoding="utf-8",
        )

        with (
            patch("tools.search_journals.l3_content.USER_DATA_DIR", tmp_path),
            patch("tools.search_journals.l3_content.JOURNALS_DIR", journals_dir),
        ):
            results = search_l3_content("Python", paths=[str(journal_file)])

        assert results[0]["path"] == str(journal_file).replace("\\", "/")
        assert results[0]["rel_path"] == "Journals/2026/03/test.md"
        assert results[0]["journal_route_path"] == "2026/03/test.md"


class TestMetadataCachePathContract:
    def test_parse_and_cache_journal_returns_normalized_path_fields(
        self, tmp_path
    ) -> None:
        import tools.lib.metadata_cache as metadata_cache

        journals_dir = tmp_path / "Journals"
        journal_file = journals_dir / "2026" / "03" / "test.md"
        journal_file.parent.mkdir(parents=True)
        journal_file.write_text(
            '---\ntitle: "Test"\ndate: 2026-03-14\n---\n\nBody',
            encoding="utf-8",
        )

        with (
            patch.object(metadata_cache, "USER_DATA_DIR", tmp_path),
            patch.object(metadata_cache, "JOURNALS_DIR", journals_dir),
        ):
            conn = metadata_cache.init_metadata_cache()
            try:
                result = metadata_cache.parse_and_cache_journal(conn, journal_file)
            finally:
                conn.close()

        assert result is not None
        assert result["file_path"] == str(journal_file).replace("\\", "/")
        assert result["rel_path"] == "Journals/2026/03/test.md"
        assert result["journal_route_path"] == "2026/03/test.md"
