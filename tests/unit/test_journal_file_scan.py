"""Tests for the one-pass journal fragment stat scan (tools/lib/journal_files.py)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from tools.lib.journal_files import iter_journal_files, scan_journal_files


def _write(path: Path, body: str = "body") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {path.stem}\ndate: 2026-03-07\n---\n{body}", encoding="utf-8")
    return path


class TestFragmentStatScan:
    def test_returns_path_mtime_and_size_for_every_fragment(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        created = [
            _write(journals / "2026" / "03" / "life-index_2026-03-07_001.md"),
            _write(journals / "2026" / "03" / "life-index_2026-03-08_002.md"),
            _write(journals / "2025" / "12" / "life-index_2025-12-31_001.md"),
        ]
        # Give each file a distinguishable mtime/size.
        for index, path in enumerate(created):
            stamp = 1_700_000_000.25 + index
            os.utime(path, (stamp, stamp))

        stats = scan_journal_files(journals)

        assert [item.path for item in stats] == list(iter_journal_files(journals))
        for item in stats:
            stat = item.path.stat()
            assert item.mtime == stat.st_mtime
            assert item.size == stat.st_size

    def test_mtime_equals_path_stat_mtime_for_every_file(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        paths = []
        for day in range(1, 16):
            paths.append(
                _write(
                    journals / "2026" / "03" / f"life-index_2026-03-{day:02d}_{day:03d}.md",
                    body="x" * day,
                )
            )
        # Include a pre-1970-style/fractional stamp to exercise float conversion.
        for index, path in enumerate(paths):
            stamp = time.time() - index * 12345.678
            os.utime(path, (stamp, stamp))

        stats = scan_journal_files(journals)

        assert len(stats) == len(paths)
        for item in stats:
            assert item.mtime == item.path.stat().st_mtime, item.path
            assert item.size == item.path.stat().st_size, item.path

    def test_uses_the_same_kind_and_dot_directory_rules(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        month = journals / "2026" / "03"
        fragment = _write(month / "life-index_2026-03-07_001.md")
        _write(month / "index_2026-03.md")
        _write(month / "monthly_report_2026-03.md")
        _write(month / "digest_2026-03-07.md")
        _write(month / "notes.md")
        _write(month / ".revisions" / "life-index_2026-03-07_001_20260308_101500_000000.md")

        assert [item.path for item in scan_journal_files(journals)] == [fragment]

    def test_is_stable_and_sorted_across_calls(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        for seq in (1, 2, 3):
            _write(journals / "2025" / "12" / f"life-index_2025-12-31_{seq:03d}.md")
            _write(journals / "2026" / "03" / f"life-index_2026-03-07_{seq:03d}.md")

        first = scan_journal_files(journals)
        second = scan_journal_files(journals)

        assert [item.path for item in first] == [item.path for item in second]
        assert [item.path for item in first] == sorted(item.path for item in first)
        assert first[0].path.name.startswith("life-index_2025-12-31")
        assert first[-1].path.name.startswith("life-index_2026-03-07")

    def test_missing_directory_yields_nothing(self, tmp_path: Path):
        assert scan_journal_files(tmp_path / "does-not-exist") == []

    def test_walks_each_directory_once(self, tmp_path: Path, monkeypatch):
        journals = tmp_path / "Journals"
        _write(journals / "2025" / "12" / "life-index_2025-12-31_001.md")
        _write(journals / "2026" / "03" / "life-index_2026-03-07_001.md")
        _write(journals / "2026" / "04" / "life-index_2026-04-07_001.md")

        import tools.lib.journal_files as journal_files

        calls: list[str] = []
        original = journal_files.os.scandir

        def counting_scandir(path="."):
            calls.append(str(path))
            return original(path)

        monkeypatch.setattr(journal_files.os, "scandir", counting_scandir)
        scan_journal_files(journals)

        journals_abs = os.path.normcase(os.path.abspath(journals))
        under = [
            call
            for call in calls
            if os.path.normcase(os.path.abspath(call)) == journals_abs
            or os.path.normcase(os.path.abspath(call)).startswith(journals_abs + os.sep)
        ]
        # root + 2 year dirs + 3 month dirs, each visited exactly once.
        assert len(under) == 6
        assert len(set(under)) == 6
