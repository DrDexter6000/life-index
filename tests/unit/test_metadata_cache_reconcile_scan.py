"""Metadata cache reconcile uses the one-pass fragment stat scan."""

from __future__ import annotations

import os
from pathlib import Path

from tools.lib.metadata_cache import (
    _scan_row_file_freshness,
    ensure_cache_version_current,
    reconcile_cache_with_files,
)


def _write_journal(path: Path, title: str = "journal") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nschema_version: 3\ntitle: {title}\ndate: 2026-03-07\ntopic: [life]\n---\n\nbody\n",
        encoding="utf-8",
    )
    return path


def _warm_cache(isolated_data_dir: Path, count: int = 5) -> list[Path]:
    journals = isolated_data_dir / "Journals" / "2026" / "03"
    created = [
        _write_journal(journals / f"life-index_2026-03-{day:02d}_{day:03d}.md", f"journal {day}")
        for day in range(1, count + 1)
    ]
    assert ensure_cache_version_current()["rebuilt"] is True
    return created


def _patch_scan_counter(monkeypatch, metadata_cache_module) -> list[int]:
    calls = [0]
    original = metadata_cache_module.scan_journal_files

    def counting_scan(journals_dir: Path):
        calls[0] += 1
        return original(journals_dir)

    monkeypatch.setattr(metadata_cache_module, "scan_journal_files", counting_scan)
    return calls


def _patch_fragment_stat_counter(monkeypatch) -> list[str]:
    statted: list[str] = []
    original = Path.stat

    def counting_stat(self: Path, *args, **kwargs):
        statted.append(str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", counting_stat)
    return statted


class TestReconcileUsesScan:
    def test_reconcile_uses_one_scan_and_no_per_file_stat(self, isolated_data_dir, monkeypatch):
        import tools.lib.metadata_cache as metadata_cache

        _warm_cache(isolated_data_dir)
        scans = _patch_scan_counter(monkeypatch, metadata_cache)
        statted = _patch_fragment_stat_counter(monkeypatch)

        result = reconcile_cache_with_files()

        assert result == {"updated": 0, "skipped": 5, "removed": 0, "errors": 0}
        assert scans[0] == 1
        journals_abs = os.path.normcase(os.path.abspath(isolated_data_dir / "Journals"))
        fragment_stats = [
            path
            for path in statted
            if os.path.normcase(os.path.abspath(path)).startswith(journals_abs + os.sep)
            and path.endswith(".md")
        ]
        assert fragment_stats == []

    def test_freshness_scan_uses_one_scan_and_matching_counts(self, isolated_data_dir, monkeypatch):
        import tools.lib.metadata_cache as metadata_cache

        journals = _warm_cache(isolated_data_dir)
        scans = _patch_scan_counter(monkeypatch, metadata_cache)
        _patch_fragment_stat_counter(monkeypatch)

        first = _scan_row_file_freshness()

        assert first == {
            "total_rows": 5,
            "up_to_date_rows": 5,
            "stale_rows": 0,
            "untracked_files": 0,
        }
        assert scans[0] == 1

        # Outside edit: same dry-run comparison still sees exactly one stale row.
        edited = journals[2]
        stat = edited.stat()
        edited.write_text(edited.read_text(encoding="utf-8") + "\noutside edit\n", encoding="utf-8")
        os.utime(edited, (stat.st_mtime + 10, stat.st_mtime + 10))

        second = _scan_row_file_freshness()

        assert second == {
            "total_rows": 5,
            "up_to_date_rows": 4,
            "stale_rows": 1,
            "untracked_files": 0,
        }
        assert scans[0] == 2


class TestListingThatDisagreesWithTheFileStat:
    """A directory listing may lag or round differently from the file's own stat.

    Rows are written from the file's own stat, so a listing that disagrees must
    not make unchanged files look stale on every search.
    """

    def _patch_skewed_scan(self, monkeypatch, metadata_cache_module) -> None:
        from tools.lib.journal_files import JournalFileStat

        original = metadata_cache_module.scan_journal_files

        def skewed_scan(journals_dir: Path):
            return [
                JournalFileStat(path=item.path, mtime=item.mtime + 2.0, size=item.size)
                for item in original(journals_dir)
            ]

        monkeypatch.setattr(metadata_cache_module, "scan_journal_files", skewed_scan)

    def test_reconcile_does_not_reparse_unchanged_files(self, isolated_data_dir, monkeypatch):
        import tools.lib.metadata_cache as metadata_cache

        _warm_cache(isolated_data_dir)
        self._patch_skewed_scan(monkeypatch, metadata_cache)
        parsed: list[Path] = []
        original_parse = metadata_cache.parse_and_cache_journal

        def counting_parse(conn, file_path):
            parsed.append(file_path)
            return original_parse(conn, file_path)

        monkeypatch.setattr(metadata_cache, "parse_and_cache_journal", counting_parse)

        result = reconcile_cache_with_files()

        assert parsed == []
        assert result == {"updated": 0, "skipped": 5, "removed": 0, "errors": 0}

    def test_audit_counts_unchanged_files_as_up_to_date(self, isolated_data_dir, monkeypatch):
        import tools.lib.metadata_cache as metadata_cache

        _warm_cache(isolated_data_dir)
        self._patch_skewed_scan(monkeypatch, metadata_cache)

        detail = _scan_row_file_freshness()

        assert detail["up_to_date_rows"] == 5
        assert detail["stale_rows"] == 0

    def test_a_really_changed_file_is_still_reparsed(self, isolated_data_dir, monkeypatch):
        import tools.lib.metadata_cache as metadata_cache

        created = _warm_cache(isolated_data_dir)
        _write_journal(created[2], "changed title that is longer")
        self._patch_skewed_scan(monkeypatch, metadata_cache)

        result = reconcile_cache_with_files()

        assert result["updated"] == 1
        assert result["skipped"] == 4
