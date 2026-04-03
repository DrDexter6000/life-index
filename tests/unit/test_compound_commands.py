#!/usr/bin/env python3
"""Runtime behavior tests for compound commands."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.search_journals.__main__ import main as search_main
from tools.write_journal.__main__ import _cmd_write


def _write_args(data: str, *, auto_index: bool) -> argparse.Namespace:
    return argparse.Namespace(
        data=data,
        dry_run=False,
        auto_index=auto_index,
        verbose=False,
    )


def _build_search_result(path: str) -> dict:
    return {
        "success": True,
        "merged_results": [
            {
                "path": path,
                "title": "Entry",
                "relevance_score": 88,
            }
        ],
        "total_found": 1,
    }


class TestWriteAutoIndex:
    def test_write_auto_index_triggers_build(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_mock = MagicMock(return_value={"success": True})
        monkeypatch.setattr("tools.write_journal.__main__.ensure_dirs", lambda: None)
        monkeypatch.setattr(
            "tools.write_journal.__main__.write_journal",
            lambda data, dry_run=False: {"success": True, "journal_path": "x.md"},
        )
        monkeypatch.setattr("tools.build_index.build_all", build_mock)

        exit_code = _cmd_write(
            _write_args('{"date":"2026-04-03","content":"body"}', auto_index=True)
        )

        assert exit_code == 0
        build_mock.assert_called_once_with(incremental=True, fts_only=False)

    def test_write_auto_index_result_contains_index_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        emitted: list[dict] = []
        monkeypatch.setattr("tools.write_journal.__main__.ensure_dirs", lambda: None)
        monkeypatch.setattr(
            "tools.write_journal.__main__.write_journal",
            lambda data, dry_run=False: {"success": True, "journal_path": "x.md"},
        )
        monkeypatch.setattr(
            "tools.build_index.build_all",
            lambda incremental=True, fts_only=False: {"success": True, "added": 1},
        )
        monkeypatch.setattr("tools.write_journal.__main__._emit_json", emitted.append)

        exit_code = _cmd_write(
            _write_args('{"date":"2026-04-03","content":"body"}', auto_index=True)
        )

        assert exit_code == 0
        assert emitted[0]["index_result"]["success"] is True
        assert emitted[0]["index_result"]["added"] == 1

    def test_write_auto_index_failure_preserves_write_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        emitted: list[dict] = []
        monkeypatch.setattr("tools.write_journal.__main__.ensure_dirs", lambda: None)
        monkeypatch.setattr(
            "tools.write_journal.__main__.write_journal",
            lambda data, dry_run=False: {"success": True, "journal_path": "x.md"},
        )

        def raising_build_all(
            *, incremental: bool = True, fts_only: bool = False
        ) -> dict:
            raise RuntimeError("boom")

        monkeypatch.setattr("tools.build_index.build_all", raising_build_all)
        monkeypatch.setattr("tools.write_journal.__main__._emit_json", emitted.append)

        exit_code = _cmd_write(
            _write_args('{"date":"2026-04-03","content":"body"}', auto_index=True)
        )

        assert exit_code == 0
        assert emitted[0]["success"] is True
        assert emitted[0]["index_warning"] == "boom"

    def test_write_without_auto_index_does_not_call_build(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        build_mock = MagicMock(return_value={"success": True})
        monkeypatch.setattr("tools.write_journal.__main__.ensure_dirs", lambda: None)
        monkeypatch.setattr(
            "tools.write_journal.__main__.write_journal",
            lambda data, dry_run=False: {"success": True, "journal_path": "x.md"},
        )
        monkeypatch.setattr("tools.build_index.build_all", build_mock)

        exit_code = _cmd_write(
            _write_args('{"date":"2026-04-03","content":"body"}', auto_index=False)
        )

        assert exit_code == 0
        build_mock.assert_not_called()


class TestSearchReadTop:
    def test_search_read_top_returns_full_content(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        journal = tmp_path / "entry.md"
        journal.write_text(
            '---\ntitle: "Title"\ndate: 2026-04-03\n---\n\n# Title\n\nBody text',
            encoding="utf-8",
        )
        monkeypatch.setattr("tools.search_journals.__main__.ensure_dirs", lambda: None)
        monkeypatch.setattr(
            "tools.search_journals.__main__.hierarchical_search",
            lambda **kwargs: {
                "success": True,
                "merged_results": [
                    {"path": str(journal), "title": "Entry 1"},
                    {"path": str(journal), "title": "Entry 2"},
                ],
                "total_found": 2,
            },
        )
        monkeypatch.setattr(
            "sys.argv",
            ["search_journals", "--query", "body", "--read-top", "2"],
        )

        with pytest.raises(SystemExit) as exc_info:
            search_main()

        payload = capsys.readouterr().out
        assert exc_info.value.code == 0
        assert '"full_content": "# Title\\n\\nBody text"' in payload

    def test_search_read_top_strips_frontmatter(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        journal = tmp_path / "entry.md"
        journal.write_text(
            '---\ntitle: "Title"\ndate: 2026-04-03\n---\n\nBody only', encoding="utf-8"
        )
        monkeypatch.setattr("tools.search_journals.__main__.ensure_dirs", lambda: None)
        monkeypatch.setattr(
            "tools.search_journals.__main__.hierarchical_search",
            lambda **kwargs: _build_search_result(str(journal)),
        )
        monkeypatch.setattr(
            "sys.argv",
            ["search_journals", "--query", "body", "--read-top", "1"],
        )

        with pytest.raises(SystemExit):
            search_main()

        payload = capsys.readouterr().out
        assert 'title: "Title"' not in payload
        assert '"full_content": "Body only"' in payload

    def test_search_read_top_missing_file_returns_null(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        missing_path = "Z:/missing/entry.md"
        monkeypatch.setattr("tools.search_journals.__main__.ensure_dirs", lambda: None)
        monkeypatch.setattr(
            "tools.search_journals.__main__.hierarchical_search",
            lambda **kwargs: _build_search_result(missing_path),
        )
        monkeypatch.setattr(
            "sys.argv",
            ["search_journals", "--query", "body", "--read-top", "1"],
        )

        with pytest.raises(SystemExit):
            search_main()

        payload = capsys.readouterr().out
        assert '"full_content": null' in payload
