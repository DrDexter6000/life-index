"""Tests for canonical Life Index journal file enumeration."""

from __future__ import annotations

from pathlib import Path


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ntitle: t\ndate: 2026-01-01\n---\nbody", encoding="utf-8")
    return path


def _mixed_journal_dir(tmp_path: Path) -> tuple[Path, Path, Path]:
    data_dir = tmp_path / "Life-Index"
    journals_dir = data_dir / "Journals"
    month_dir = journals_dir / "2026" / "01"
    valid = _write(month_dir / "life-index_2026-01-01_001.md")
    _write(month_dir / "life-index_2026-01-02.md")
    _write(month_dir / "life-index_2026-01-03_abc.md")
    _write(month_dir / "notes_2026-01-04_001.md")
    _write(month_dir / "README.md")
    return data_dir, journals_dir, valid


class TestJournalFiles:
    def test_canonical_counter_uses_strict_journal_filename_contract(self, tmp_path):
        from tools.lib.journal_files import (
            count_journal_files,
            is_journal_file,
            iter_journal_files,
        )

        _data_dir, journals_dir, valid = _mixed_journal_dir(tmp_path)

        assert is_journal_file(valid)
        assert not is_journal_file(journals_dir / "2026" / "01" / "README.md")
        assert not is_journal_file(journals_dir / "2026" / "01" / "life-index_2026-01-02.md")
        assert [path.name for path in iter_journal_files(journals_dir)] == [valid.name]
        assert count_journal_files(journals_dir) == 1

    def test_bootstrap_migrate_and_health_share_same_journal_count(self, tmp_path, monkeypatch):
        import tools.__main__ as main_cli
        from tools.bootstrap import detect_data_state
        from tools.migrate import scan_journals

        data_dir, journals_dir, _valid = _mixed_journal_dir(tmp_path)
        monkeypatch.setattr(main_cli, "get_user_data_dir", lambda: data_dir)
        monkeypatch.setattr(main_cli, "get_journals_dir", lambda: journals_dir)

        state = detect_data_state(data_dir=str(data_dir))
        report = scan_journals(journals_dir)
        health_check, _issue = main_cli._check_data_dir()

        assert state["journal_count"] == 1
        assert report["total_scanned"] == 1
        assert health_check["journal_count"] == 1
