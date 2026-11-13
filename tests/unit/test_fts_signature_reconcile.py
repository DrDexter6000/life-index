#!/usr/bin/env python3
"""Unit tests for signature-based FTS reconciliation (R1–R5, N1).

Each case reproduces a defect where the index kept serving a wrong row:

- R1: a matching signature hid a missing FTS row (interrupted rebuild).
- R3: a queued path was skipped because its signature matched.
- R4: the row and its signature could describe different file versions.
- R5: a non-fragment path was admitted to the derived stores.
- D1: an unparsable live fragment is indexed as raw text, not dropped.
"""

import json
import os
import sqlite3
from pathlib import Path

import pytest


def _write_journal(
    data_dir: Path,
    *,
    date: str = "2026-03-04",
    sequence: int = 1,
    body: str = "body",
    title: str = "title",
) -> Path:
    year, month, _day = date.split("-")
    month_dir = data_dir / "Journals" / year / month
    month_dir.mkdir(parents=True, exist_ok=True)
    journal = month_dir / f"life-index_{date}_{sequence:03d}.md"
    journal.write_text(
        f'---\ntitle: "{title}"\ndate: "{date}"\ntopic: [life]\n---\n\n{body}\n',
        encoding="utf-8",
    )
    return journal


def _rel(journal: Path, data_dir: Path) -> str:
    return str(journal.relative_to(data_dir)).replace("\\", "/")


def _fts_conn(data_dir: Path) -> sqlite3.Connection:
    return sqlite3.connect(str(data_dir / ".index" / "journals_fts.db"))


def _row_content(data_dir: Path, journal: Path) -> str | None:
    conn = _fts_conn(data_dir)
    try:
        row = conn.execute(
            "SELECT content FROM journals WHERE path = ?", (_rel(journal, data_dir),)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _stats_row(data_dir: Path, journal: Path) -> tuple[float, int] | None:
    conn = _fts_conn(data_dir)
    try:
        row = conn.execute(
            "SELECT mtime, size FROM fts_file_stats WHERE path = ?",
            (_rel(journal, data_dir),),
        ).fetchone()
        return (row[0], row[1]) if row else None
    finally:
        conn.close()


class TestScanReconcilesRowsAndSignatures:
    def test_missing_row_with_matching_stats_is_rebuilt(self, isolated_data_dir):
        """R1: matching stats must not hide a missing FTS row."""
        from tools.lib.search_index import init_fts_db, update_index

        a = _write_journal(isolated_data_dir, date="2026-03-04", sequence=1, body="alpha r1word")
        b = _write_journal(isolated_data_dir, date="2026-03-05", sequence=2, body="beta r1word")
        assert update_index(incremental=False)["success"] is True

        # Interrupted rebuild the way the tool simulates it.
        init_fts_db(force_recreate=True).close()

        result = update_index(incremental=True)

        assert result["success"] is True
        assert _row_content(isolated_data_dir, a) is not None
        assert _row_content(isolated_data_dir, b) is not None

    def test_force_recreate_clears_signature_rows(self, isolated_data_dir):
        """Recreating the journals table invalidates every signature."""
        from tools.lib.search_index import init_fts_db, update_index

        _write_journal(isolated_data_dir)
        assert update_index(incremental=False)["success"] is True

        init_fts_db(force_recreate=True).close()

        conn = _fts_conn(isolated_data_dir)
        try:
            stats_count = conn.execute("SELECT COUNT(*) FROM fts_file_stats").fetchone()[0]
        finally:
            conn.close()
        assert stats_count == 0

    def test_pending_path_is_reread_even_when_signature_matches(self, isolated_data_dir):
        """R3: a queued path is always re-read, whatever its signature says."""
        from tools.build_index import build_all
        from tools.lib.pending_writes import get_pending, mark_pending

        journal = _write_journal(isolated_data_dir, body="oldword")
        assert build_all(incremental=False)["success"] is True
        original = journal.stat()

        # Same byte length and the very same mtime: only a forced read can see it.
        journal.write_text(
            '---\ntitle: "title"\ndate: "2026-03-04"\ntopic: [life]\n---\n\nnewword\n',
            encoding="utf-8",
        )
        assert journal.stat().st_size == original.st_size
        os.utime(journal, ns=(original.st_atime_ns, original.st_mtime_ns))
        assert journal.stat().st_mtime == original.st_mtime

        mark_pending(_rel(journal, isolated_data_dir))
        result = build_all(incremental=True)

        assert result["success"] is True
        assert _row_content(isolated_data_dir, journal) is not None
        assert "newword" in (_row_content(isolated_data_dir, journal) or "")
        assert _rel(journal, isolated_data_dir) in result["fts"]["pending_repaired"]
        assert get_pending() == []

    def test_invalid_utf8_fragment_is_indexed_as_text(self, isolated_data_dir):
        """D1: bytes that are not UTF-8 still yield a raw-text row."""
        from tools.lib.search_index import update_index

        journal = _write_journal(isolated_data_dir, body="old")
        assert update_index(incremental=False)["success"] is True

        journal.write_bytes(b"no frontmatter \xff\xfe rawbytesword\n")

        result = update_index(incremental=True)

        assert result["success"] is True
        assert result["unparsable"] == 1
        assert "rawbytesword" in (_row_content(isolated_data_dir, journal) or "")
        assert _stats_row(isolated_data_dir, journal) is not None

    def test_scalar_values_that_are_not_strings_keep_their_metadata(self, isolated_data_dir):
        """Hand-written ``title: 2024`` is a readable value, not broken frontmatter."""
        from tools.lib.search_index import update_index

        journal = _write_journal(isolated_data_dir, body="scalarword")
        journal.write_text(
            "---\ntitle: 2024\ndate: 2026-03-04\nlocation: 42\nweather: true\n"
            "project: 3.5\ntopic: [life]\n---\n\nscalarword\n",
            encoding="utf-8",
        )

        result = update_index(incremental=False)

        assert result["success"] is True
        assert result["unparsable"] == 0
        conn = _fts_conn(isolated_data_dir)
        try:
            row = conn.execute(
                "SELECT title, date, location, weather, project, topic FROM journals "
                "WHERE path = ?",
                (_rel(journal, isolated_data_dir),),
            ).fetchone()
        finally:
            conn.close()
        assert row == ("2024", "2026-03-04", "42", "True", "3.5", "life")

    def test_mapping_in_a_scalar_field_is_indexed_as_text(self, isolated_data_dir):
        """A mapping where a scalar belongs cannot be read as a value: raw-text row."""
        from tools.lib.search_index import update_index

        journal = _write_journal(isolated_data_dir, body="mappingword")
        journal.write_text(
            "---\ntitle:\n  nested: value\ndate: 2026-03-04\n---\n\nmappingword\n",
            encoding="utf-8",
        )

        result = update_index(incremental=False)

        assert result["success"] is True
        assert result["unparsable"] == 1
        assert "mappingword" in (_row_content(isolated_data_dir, journal) or "")

    def test_unparsable_source_is_indexed_as_text(self, isolated_data_dir):
        """D1: an unparsable live fragment keeps a row built from its full text."""
        from tools.lib.search_index import update_index

        journal = _write_journal(isolated_data_dir, body="n1word")
        assert update_index(incremental=False)["success"] is True
        assert _row_content(isolated_data_dir, journal) is not None

        journal.write_text("no frontmatter at all\n", encoding="utf-8")

        result = update_index(incremental=True)

        assert result["success"] is True
        assert result["unparsable"] == 1
        assert result["unparsable_paths"] == [_rel(journal, isolated_data_dir)]
        content = _row_content(isolated_data_dir, journal)
        assert content is not None and "no frontmatter at all" in content
        assert _stats_row(isolated_data_dir, journal) is not None

        conn = _fts_conn(isolated_data_dir)
        try:
            title, date = conn.execute(
                "SELECT title, date FROM journals WHERE path = ?",
                (_rel(journal, isolated_data_dir),),
            ).fetchone()
        finally:
            conn.close()
        assert title == ""
        assert date == "2026-03-04"  # filename fallback

        # Current like any other row: no per-search retry.
        again = update_index(incremental=True)
        assert again["success"] is True
        assert again["unparsable"] == 0

        # A fragment that becomes parsable again is re-read (signature change)
        # and gets a normal row on the next scan.
        journal.write_text(
            '---\ntitle: "fixed"\ndate: "2026-03-04"\n---\n\nfixedword\n',
            encoding="utf-8",
        )
        fixed = update_index(incremental=True)
        assert fixed["unparsable"] == 0
        assert "fixedword" in (_row_content(isolated_data_dir, journal) or "")
        conn = _fts_conn(isolated_data_dir)
        try:
            title = conn.execute(
                "SELECT title FROM journals WHERE path = ?",
                (_rel(journal, isolated_data_dir),),
            ).fetchone()[0]
        finally:
            conn.close()
        assert title == "fixed"


class TestReadOnceConsistency:
    """R4: row content, hash and signature must describe one file version."""

    @staticmethod
    def _flaky_reader(monkeypatch, target: Path, new_bytes: bytes):
        original = Path.read_bytes
        armed = {"value": True}

        def flaky(self):
            raw = original(self)
            if armed["value"] and Path(self) == target:
                armed["value"] = False
                target.write_bytes(new_bytes)
            return raw

        monkeypatch.setattr(Path, "read_bytes", flaky)
        return original

    def test_write_through_records_no_signature_for_a_torn_read(
        self, isolated_data_dir, monkeypatch
    ):
        from tools.lib.search_index import upsert_fts_row

        journal = _write_journal(isolated_data_dir, body="oldcontent")
        replacement = (
            b'---\ntitle: "title"\ndate: "2026-03-04"\ntopic: [life]\n---\n\nnewcontent extra\n'
        )
        original = self._flaky_reader(monkeypatch, journal, replacement)

        assert upsert_fts_row(journal) is not None
        monkeypatch.setattr(Path, "read_bytes", original)

        assert (
            _stats_row(isolated_data_dir, journal) is None
        ), "a file that changed while it was read must not get a signature row"

        # The next scan notices the missing signature and re-reads the file.
        from tools.lib.search_index import update_index

        assert update_index(incremental=True)["success"] is True
        assert "newcontent" in (_row_content(isolated_data_dir, journal) or "")
        assert _stats_row(isolated_data_dir, journal) is not None

    def test_scan_records_no_signature_for_a_torn_read(self, isolated_data_dir, monkeypatch):
        from tools.lib.search_index import update_index

        journal = _write_journal(isolated_data_dir, body="oldcontent")
        replacement = (
            b'---\ntitle: "title"\ndate: "2026-03-04"\ntopic: [life]\n---\n\nnewcontent extra\n'
        )
        original = self._flaky_reader(monkeypatch, journal, replacement)

        assert update_index(incremental=True)["success"] is True
        monkeypatch.setattr(Path, "read_bytes", original)

        assert _stats_row(isolated_data_dir, journal) is None

        assert update_index(incremental=True)["success"] is True
        assert "newcontent" in (_row_content(isolated_data_dir, journal) or "")

    def test_replaced_file_with_same_mtime_and_size_is_not_stable(
        self, isolated_data_dir, monkeypatch
    ):
        """D3: file identity (inode) is part of the stability decision."""
        from tools.lib.search_index import upsert_fts_row

        journal = _write_journal(isolated_data_dir, body="stablecontent")
        original = journal.read_bytes()
        original_stat = journal.stat()
        replacement = original[:-1] + (b"X" if original[-1:] != b"X" else b"Y")
        assert len(replacement) == len(original)

        real_read_bytes = Path.read_bytes

        def replacing_read(self):
            raw = real_read_bytes(self)
            if Path(self) == journal:
                staged = journal.with_name(journal.name + ".replacement")
                staged.write_bytes(replacement)
                os.utime(
                    staged,
                    ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
                )
                os.replace(staged, journal)
            return raw

        monkeypatch.setattr(Path, "read_bytes", replacing_read)
        row = upsert_fts_row(journal)
        monkeypatch.setattr(Path, "read_bytes", real_read_bytes)

        assert row is not None
        replaced_stat = journal.stat()
        assert replaced_stat.st_size == original_stat.st_size
        assert replaced_stat.st_mtime_ns == original_stat.st_mtime_ns
        assert replaced_stat.st_ino != original_stat.st_ino, "the test needs a new file identity"
        assert (
            _stats_row(isolated_data_dir, journal) is None
        ), "a file replaced during the read must not get a signature row"

    def test_queued_path_replaced_during_the_scan_read_gets_no_signature(
        self, isolated_data_dir, monkeypatch
    ):
        """D6: the same rule applies to a queued path read by the incremental scan.

        A queued path is force-read even though its (mtime, size) signature still
        matches, so the read is the only place the replacement can be noticed.
        The replacement keeps the same mtime and size but has a new inode, so no
        signature may be recorded and the next scan must re-read the file.
        """
        from tools.build_index import build_all
        from tools.lib.pending_writes import get_pending, mark_pending

        journal = _write_journal(isolated_data_dir, body="scanoldcontent")
        assert build_all(incremental=False)["success"] is True
        rel_path = _rel(journal, isolated_data_dir)
        original = journal.read_bytes()
        original_stat = journal.stat()
        replacement = original[:-1] + (b"Z" if original[-1:] != b"Z" else b"Q")
        assert len(replacement) == len(original)

        mark_pending(rel_path)
        real_read_bytes = Path.read_bytes

        def replacing_read(self):
            raw = real_read_bytes(self)
            if Path(self) == journal:
                staged = journal.with_name(journal.name + ".replacement")
                staged.write_bytes(replacement)
                os.utime(
                    staged,
                    ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
                )
                os.replace(staged, journal)
            return raw

        monkeypatch.setattr(Path, "read_bytes", replacing_read)
        scanned = build_all(incremental=True)
        monkeypatch.setattr(Path, "read_bytes", real_read_bytes)

        assert scanned["success"] is True
        assert rel_path in scanned["fts"]["pending_repaired"]
        assert get_pending() == []
        replaced_stat = journal.stat()
        assert replaced_stat.st_size == original_stat.st_size
        assert replaced_stat.st_mtime_ns == original_stat.st_mtime_ns
        assert replaced_stat.st_ino != original_stat.st_ino, "the test needs a new file identity"
        assert (
            _stats_row(isolated_data_dir, journal) is None
        ), "a file replaced during the scan read must not get a signature row"

        # The next scan notices the missing signature and re-reads the file.
        from tools.lib.search_index import update_index

        assert update_index(incremental=True)["success"] is True
        assert _stats_row(isolated_data_dir, journal) is not None
        assert (journal.read_bytes()) == replacement


class TestLiveFragmentAdmission:
    """R5: only live fragments may enter a derived store."""

    @pytest.mark.parametrize(
        "rel_path",
        [
            "Journals/2026/03/digest_2026-03-04.md",
            "Journals/2026/03/index_2026-03.md",
            "Journals/2026/03/monthly_2026-03.md",
            "Journals/2026/03/.revisions/life-index_2026-03-04_001_20260305_101500_000000.md",
        ],
    )
    def test_non_fragment_paths_are_rejected(self, isolated_data_dir, rel_path):
        from tools.lib.journal_files import is_live_fragment_path
        from tools.lib.metadata_cache import init_metadata_cache, upsert_journal_cache_row
        from tools.lib.search_index import upsert_fts_row

        path = isolated_data_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '---\ntitle: "derived"\ndate: "2026-03-04"\ntopic: [life]\n---\n\nbody\n',
            encoding="utf-8",
        )

        assert is_live_fragment_path(path, isolated_data_dir / "Journals") is False
        assert upsert_fts_row(path, isolated_data_dir / "Journals") is None
        assert upsert_journal_cache_row(path, isolated_data_dir / "Journals") is None

        conn = init_metadata_cache()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM metadata_cache WHERE file_path LIKE ?",
                (f"%{Path(rel_path).name}",),
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_fragment_path_is_admitted(self, isolated_data_dir):
        from tools.lib.journal_files import is_live_fragment_path

        journal = _write_journal(isolated_data_dir)
        assert is_live_fragment_path(journal, isolated_data_dir / "Journals") is True


class TestFreshnessReadOnlyCost:
    def test_check_runs_one_scan_and_opens_no_journal(self, isolated_data_dir, monkeypatch):
        """The preflight check is one directory scan + DB reads, no file opens."""
        from tools.build_index import build_all
        from tools.lib import fts_update
        from tools.lib.index_freshness import check_full_freshness

        for i in range(5):
            _write_journal(
                isolated_data_dir,
                date=f"2026-03-{i + 1:02d}",
                sequence=i + 1,
                body=f"body {i}",
            )
        assert build_all(incremental=False)["success"] is True
        index_dir = isolated_data_dir / ".index"
        # Build writes a manifest; freshness should then be current.
        assert check_full_freshness(index_dir).overall_fresh is True

        reads: list[str] = []
        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes

        def counting_read_text(path, *args, **kwargs):
            reads.append(str(path))
            return original_read_text(path, *args, **kwargs)

        def counting_read_bytes(path, *args, **kwargs):
            reads.append(str(path))
            return original_read_bytes(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", counting_read_text)
        monkeypatch.setattr(Path, "read_bytes", counting_read_bytes)

        scans: list[str] = []
        original_scan = fts_update.scan_journal_files

        def counting_scan(journals_dir):
            scans.append(str(journals_dir))
            return original_scan(journals_dir)

        monkeypatch.setattr(fts_update, "scan_journal_files", counting_scan)

        report = check_full_freshness(index_dir)

        assert report.overall_fresh is True
        assert len(scans) == 1, f"expected one directory scan, got {len(scans)}"
        journal_reads = [path for path in reads if "Journals" in Path(path).parts]
        assert journal_reads == [], f"the freshness check opened journal file(s): {journal_reads}"


def test_scan_skips_unchanged_files_without_reading(isolated_data_dir, monkeypatch):
    """A second incremental scan of an unchanged archive reads no journal."""
    from tools.lib.search_index import update_index

    _write_journal(isolated_data_dir)
    assert update_index(incremental=False)["success"] is True

    reads: list[str] = []
    original = Path.read_bytes

    def counting(self):
        reads.append(str(self))
        return original(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    assert update_index(incremental=True)["success"] is True
    assert reads == []


def test_json_result_is_serializable(isolated_data_dir):
    from tools.lib.search_index import update_index

    _write_journal(isolated_data_dir)
    result = update_index(incremental=False)
    json.dumps(result)


class TestPendingAcknowledgement:
    def test_queued_path_with_nothing_to_repair_is_acknowledged(self, isolated_data_dir):
        """A queued path for a vanished file with no row/stat cannot stay forever."""
        from tools.build_index import build_all
        from tools.lib.pending_writes import get_pending, mark_pending

        _write_journal(isolated_data_dir)
        assert build_all(incremental=False)["success"] is True

        mark_pending("Journals/2026/03/life-index_2026-03-09_999.md")
        assert get_pending() != []

        result = build_all(incremental=True)

        assert result["success"] is True
        assert get_pending() == []

    def test_unparsable_queued_path_is_indexed_and_acknowledged(self, isolated_data_dir):
        """D1: an unparsable queued fragment gets a row and leaves the queue."""
        from tools.build_index import build_all
        from tools.lib.pending_writes import get_pending, mark_pending

        journal = _write_journal(isolated_data_dir, body="queued words")
        assert build_all(incremental=False)["success"] is True
        journal.write_text("no frontmatter at all\n", encoding="utf-8")
        mark_pending(_rel(journal, isolated_data_dir))

        result = build_all(incremental=True)

        assert result["success"] is True
        assert result["fts"]["unparsable"] == 1
        assert _rel(journal, isolated_data_dir) in result["fts"]["pending_repaired"]
        assert _row_content(isolated_data_dir, journal) is not None
        assert get_pending() == []

        fixed = '---\ntitle: "fixed"\ndate: "2026-03-04"\n---\n\nfixedafterrepair\n'
        journal.write_text(fixed, encoding="utf-8")
        repaired = build_all(incremental=True)
        assert repaired["fts"]["unparsable"] == 0
        assert get_pending() == []
