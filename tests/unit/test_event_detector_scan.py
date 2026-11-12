"""Event detector behaviour: shared per-call scan and unchanged detector results."""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tools.lib.entity_graph import save_entity_graph

_FIXED_GRAPH = [
    {
        "id": "actor-alice",
        "type": "actor",
        "primary_name": "Alice",
        "aliases": [],
        "attributes": {"kind": "human"},
        "relationships": [],
        "source": "user",
        "status": "confirmed",
    }
]


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _current_schema_journal(path: Path, date: str = "2026-03-07") -> Path:
    return _write(
        path,
        "---\n" "schema_version: 3\n" f'date: "{date}"\n' "title: current\n" "---\n\nbody\n",
    )


def _old_schema_journal(path: Path, date: str = "2026-03-07") -> Path:
    return _write(
        path,
        "---\n" "schema_version: 1\n" f'date: "{date}"\n' "title: old\n" "---\n\nbody\n",
    )


def _detect_all(context: dict) -> list:
    from tools.lib.event_detectors import register_all_detectors
    from tools.lib.events import detect_events

    register_all_detectors()
    return detect_events(context=context, timeout_ms=10_000)


class TestOneWalkPerDetectionCall:
    def test_registers_are_shared_and_scan_happens_once(self, tmp_path: Path, monkeypatch):
        journals = tmp_path / "Journals"
        for day in range(1, 5):
            _current_schema_journal(
                journals / "2025" / "12" / f"life-index_2025-12-{day:02d}_001.md"
            )
            _current_schema_journal(
                journals / "2026" / "03" / f"life-index_2026-03-{day:02d}_001.md"
            )

        import tools.lib.event_detectors as event_detectors

        calls: list[str] = []
        original = event_detectors.scan_journal_files

        def counting_scan(journals_dir: Path):
            calls.append(str(journals_dir))
            return original(journals_dir)

        monkeypatch.setattr(event_detectors, "scan_journal_files", counting_scan)

        context = {"journals_dir": journals, "data_dir": tmp_path}
        _detect_all(context)

        assert len(calls) == 1
        # The scan is per call: it must not leak back into the caller's context.
        assert "_journal_file_stat_scan" not in context

        _detect_all(context)
        assert len(calls) == 2

    def test_directories_are_scanned_once_not_once_per_detector(self, tmp_path: Path, monkeypatch):
        journals = tmp_path / "Journals"
        _current_schema_journal(journals / "2025" / "12" / "life-index_2025-12-31_001.md")
        _current_schema_journal(journals / "2026" / "03" / "life-index_2026-03-07_001.md")
        _current_schema_journal(journals / "2026" / "04" / "life-index_2026-04-07_001.md")

        import tools.lib.journal_files as journal_files

        calls: list[str] = []
        original = journal_files.os.scandir

        def counting_scandir(path="."):
            calls.append(str(path))
            return original(path)

        monkeypatch.setattr(journal_files.os, "scandir", counting_scandir)
        _detect_all({"journals_dir": journals, "data_dir": tmp_path})

        journals_abs = os.path.normcase(os.path.abspath(journals))
        under = [
            call
            for call in calls
            if os.path.normcase(os.path.abspath(call)) == journals_abs
            or os.path.normcase(os.path.abspath(call)).startswith(journals_abs + os.sep)
        ]
        # root + 2 year dirs + 3 month dirs, not 3 full walks.
        assert len(under) == 6
        assert len(set(under)) == 6


class TestDetectorResultsUnchanged:
    """Characterization cases: these pass before and after the shared scan."""

    def test_no_journals(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        journals.mkdir()
        assert _detect_all({"journals_dir": journals, "data_dir": tmp_path}) == []

    def test_newest_journal_ten_days_old(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        journal = _current_schema_journal(journals / "2020" / "01" / "life-index_2020-01-01_001.md")
        ten_days_ago = time.time() - 10 * 86400
        os.utime(journal, (ten_days_ago, ten_days_ago))

        events = _detect_all({"journals_dir": journals, "data_dir": tmp_path})

        assert [event.type for event in events] == ["no_journal_streak"]
        assert events[0].data["days"] == 10
        assert events[0].message == f"已连续{events[0].data['days']}天未记日志"

    def test_journal_newer_than_fts_database(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        _current_schema_journal(journals / "2020" / "01" / "life-index_2020-01-01_001.md")
        index_dir = tmp_path / ".index"
        index_dir.mkdir(parents=True)
        fts_db = index_dir / "journals_fts.db"
        fts_db.write_bytes(b"")
        old = time.time() - 3600
        os.utime(fts_db, (old, old))

        events = _detect_all({"journals_dir": journals, "data_dir": tmp_path})

        stale = [event for event in events if event.type == "index_stale"]
        assert len(stale) == 1
        assert stale[0].data == {
            "reason": "newer_journals",
            "suggested_command": "life-index index",
            "side_effect": "write",
            "side_effect_note": (
                "Writes derived index artifacts only; source journals are not modified."
            ),
        }
        assert stale[0].message == "索引可能已过时，建议运行 life-index index"

    def test_fewer_than_ten_journals_are_all_checked(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        for day in range(1, 4):
            _old_schema_journal(journals / "2020" / "01" / f"life-index_2020-01-{day:02d}_001.md")

        events = _detect_all({"journals_dir": journals, "data_dir": tmp_path})

        schema_events = [event for event in events if event.type == "schema_migration_available"]
        assert len(schema_events) == 1
        assert schema_events[0].data == {"outdated_count": 3}
        assert schema_events[0].message == "发现 3 篇旧格式日志，可运行 life-index migrate --apply"

    def test_schema_check_reads_only_the_newest_ten(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        for day in range(1, 13):
            _old_schema_journal(journals / "2020" / "01" / f"life-index_2020-01-{day:02d}_001.md")

        events = _detect_all({"journals_dir": journals, "data_dir": tmp_path})

        schema_events = [event for event in events if event.type == "schema_migration_available"]
        assert len(schema_events) == 1
        assert schema_events[0].data == {"outdated_count": 10}

    def test_month_with_only_non_fragments_does_not_trigger_review(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        check_date = datetime.now() - timedelta(days=30)
        month_dir = journals / f"{check_date.year}" / f"{check_date.month:02d}"
        _write(month_dir / f"index_{check_date.year}-{check_date.month:02d}.md", "# index")
        _write(month_dir / "notes.md", "notes")
        _write(
            month_dir / ".revisions" / "life-index_2020-01-01_001_20200102_101500_000000.md",
            "---\ntitle: revision\n---\n",
        )

        events = _detect_all({"journals_dir": journals, "data_dir": tmp_path})

        assert [event.type for event in events] == []

    def test_entity_detectors_still_work_with_shared_scan(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        journals.mkdir()
        save_entity_graph(_FIXED_GRAPH, tmp_path / "entity_graph.yaml")
        # Old graph mtime -> audit hint; missing profiles -> stale hint.
        old = time.time() - 40 * 86400
        os.utime(tmp_path / "entity_graph.yaml", (old, old))

        events = _detect_all({"journals_dir": journals, "data_dir": tmp_path})
        types = [event.type for event in events]

        assert types.count("entity_audit_due") == 1
        assert types.count("entity_profiles_stale") == 1
        assert (
            "entity_graph.yaml"
            in next(event for event in events if event.type == "entity_profiles_stale").data[
                "side_effect_note"
            ]
        )

    def test_index_version_mismatch_still_reported(self, tmp_path: Path):
        from tools.lib.search_constants import TOKENIZER_VERSION

        journals = tmp_path / "Journals"
        journal = _current_schema_journal(journals / "2020" / "01" / "life-index_2020-01-01_001.md")
        index_dir = tmp_path / ".index"
        index_dir.mkdir(parents=True)
        fts_db = index_dir / "journals_fts.db"
        conn = sqlite3.connect(str(fts_db))
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS journals USING fts5(path, title, content)")
        conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("tokenizer_version", str(TOKENIZER_VERSION - 1)),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("schema_version", "1"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("dict_hash", "dummy_hash"),
        )
        conn.commit()
        conn.close()
        os.utime(fts_db, None)
        old = time.time() - 3600
        os.utime(journal, (old, old))

        events = _detect_all({"journals_dir": journals, "data_dir": tmp_path})

        stale = [event for event in events if event.type == "index_stale"]
        assert len(stale) == 1
        assert stale[0].data["reason"] == "version_mismatch"
        assert stale[0].message == "索引 schema/分词器已变更，建议运行 life-index index --rebuild"


@pytest.mark.parametrize("detector_name", ["check_no_journal_streak", "check_index_stale"])
def test_detectors_accept_a_context_without_a_precomputed_scan(tmp_path: Path, detector_name: str):
    """A detector called directly still computes its own scan."""
    import tools.lib.event_detectors as event_detectors

    journals = tmp_path / "Journals"
    journals.mkdir()
    detector = getattr(event_detectors, detector_name)
    assert detector({"journals_dir": journals, "data_dir": tmp_path}) == []
