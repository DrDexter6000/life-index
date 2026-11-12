#!/usr/bin/env python3
"""Contract test: metadata cache write-time upsert and reconcile freshness.

Baseline measured on the pre-reconcile implementation (300 synthetic journals,
counting read_text/read_bytes of fragment files under Journals/):

- one write                                : 903 fragment reads (all from the
  month/year/root index + Index B refresh; the metadata cache itself read 0)
- first metadata search after that write   : 903 reads = 3 x 301
  (hash whole archive, invalidate, re-parse whole archive, hash again)
- second search                            : 301 reads (whole-archive hash)

Target behaviour pinned here:

- write/edit upsert exactly the committed journal's cache row post-commit;
- the search path decides freshness per row from (mtime, size) via a stat-only
  walk, parsing only new/changed files (reconcile), never re-reading the
  content of unchanged journals;
- full rebuild only when there is no sidecar, the recorded schema/tool version
  mismatches, or entity_graph.yaml changed;
- health --cache-audit reports valid/stale/incompatible/missing from the same
  row-versus-file comparison, dry-run (no writes).

Known accepted limit (docs/ARCHITECTURE.md): a file changed outside the tool
with identical mtime AND size is not detected until `life-index index
--rebuild`.
"""

import json
import os
from pathlib import Path

import pytest

from tools.lib.journal_files import JOURNAL_FILENAME_RE

N_JOURNALS = 40

WRITE_PAYLOAD = {
    "title": "全新写入的目标日志",
    "content": "这是契约测试中写入的新日志正文。",
    "date": "2026-04-15",
    "topic": "work",
    "tags": ["freshness-contract"],
    # A location unique to this write: it stays below the entity-candidate
    # promotion threshold, so the write does not touch entity_graph.yaml.
    # (A write that DOES promote a candidate changes the graph, which by
    # contract triggers one full rebuild at the next search.)
    "location": "唯一确认地点",
    "weather": "cloudy",
    "people": [],
}


def _is_journal_fragment(path: Path) -> bool:
    path = Path(path)
    return "Journals" in path.parts and JOURNAL_FILENAME_RE.match(path.name) is not None


class JournalReadCounter:
    """Count journal fragment content reads (Path.read_text / Path.read_bytes)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.reads: list[str] = []
        orig_read_text = Path.read_text
        orig_read_bytes = Path.read_bytes
        counter = self

        def _counting_read_text(path, *args, **kwargs):
            if _is_journal_fragment(path):
                counter.reads.append(str(path))
            return orig_read_text(path, *args, **kwargs)

        def _counting_read_bytes(path, *args, **kwargs):
            if _is_journal_fragment(path):
                counter.reads.append(str(path))
            return orig_read_bytes(path, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", _counting_read_text)
        monkeypatch.setattr(Path, "read_bytes", _counting_read_bytes)

    @property
    def total(self) -> int:
        return len(self.reads)

    @property
    def distinct(self) -> int:
        return len(set(self.reads))

    def reset(self) -> None:
        self.reads.clear()


@pytest.fixture
def journal_reads(monkeypatch: pytest.MonkeyPatch) -> JournalReadCounter:
    return JournalReadCounter(monkeypatch)


def _make_synthetic_journals(data_dir: Path, n: int) -> list[Path]:
    """Create n synthetic fragment journals across three months."""
    per_date: dict[str, int] = {}
    created: list[Path] = []
    for i in range(n):
        month = (i % 3) + 1
        day = (i % 28) + 1
        date_str = f"2026-{month:02d}-{day:02d}"
        per_date[date_str] = per_date.get(date_str, 0) + 1
        seq = per_date[date_str]
        month_dir = data_dir / "Journals" / "2026" / f"{month:02d}"
        month_dir.mkdir(parents=True, exist_ok=True)
        journal = month_dir / f"life-index_{date_str}_{seq:03d}.md"
        journal.write_text(
            "---\n"
            "schema_version: 2.1.0\n"
            f'date: "{date_str}"\n'
            f"title: 第{i + 1}篇合成日志\n"
            "topic: life\n"
            "tags:\n  - freshness-contract\n"
            "location: 测试城市\n"
            "weather: sunny\n"
            "mood:\n  - calm\n"
            "people: []\n"
            "---\n\n"
            f"# 第{i + 1}篇合成日志\n\n"
            f"这是第{i + 1}篇合成日志的正文内容。\n",
            encoding="utf-8",
        )
        created.append(journal)
    return created


def _warm_cache_to_steady_state() -> None:
    """Populate cache rows and the version sidecar (established-installation state)."""
    from tools.lib.metadata_cache import ensure_cache_version_current

    ensure_cache_version_current()


def _metadata_search(query: str = "合成") -> dict:
    from tools.search_journals.l2_metadata import search_l2_metadata

    return search_l2_metadata(query=query)


def _write_one_journal(payload: dict | None = None) -> dict:
    from tools.write_journal.core import write_journal

    return write_journal(dict(payload or WRITE_PAYLOAD))


def _dump_cache_rows() -> list[dict]:
    from tools.lib.metadata_cache import init_metadata_cache

    conn = init_metadata_cache()
    try:
        cursor = conn.execute("SELECT * FROM metadata_cache ORDER BY file_path")
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def _cache_row_for(journal: Path) -> dict | None:
    from tools.lib.metadata_cache import init_metadata_cache

    conn = init_metadata_cache()
    try:
        cursor = conn.execute("SELECT * FROM metadata_cache ORDER BY file_path")
        columns = [description[0] for description in cursor.description]
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            if Path(row_dict["file_path"]).name == journal.name:
                return row_dict
        return None
    finally:
        conn.close()


def _sidecar_path(data_dir: Path) -> Path:
    return data_dir / ".life-index" / "cache" / "_version.json"


# ============================================================
# Search-path freshness: reconcile, never re-read unchanged journals
# ============================================================


class TestSearchReconcileFreshness:
    def test_first_search_after_write_reads_no_journal_files(
        self, isolated_data_dir, journal_reads
    ):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")

        journal_reads.reset()
        response = _metadata_search(query="目标日志")

        assert journal_reads.total == 0, (
            f"first metadata search after a write re-read {journal_reads.total} "
            "journal files; expected 0"
        )
        # The cache must actually be current: the new journal is searchable.
        titles = [entry.get("title", "") for entry in response["results"]]
        assert any("全新写入的目标日志" in title for title in titles)

    def test_second_search_reads_no_journal_files(self, isolated_data_dir, journal_reads):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()
        _write_one_journal()

        _metadata_search()

        journal_reads.reset()
        _metadata_search()

        assert journal_reads.total == 0, (
            f"steady-state metadata search re-read {journal_reads.total} journal "
            "files; expected 0"
        )

    def test_outside_edited_journal_reparsed_only_that_file(self, isolated_data_dir, journal_reads):
        journals = _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        edited = journals[7]
        stat = edited.stat()
        edited.write_text(
            edited.read_text(encoding="utf-8") + "\n\n外部编辑追加的正文，改变了文件大小。\n",
            encoding="utf-8",
        )
        os.utime(edited, (stat.st_mtime + 10, stat.st_mtime + 10))

        journal_reads.reset()
        _metadata_search()

        assert journal_reads.total == 1, (
            f"expected exactly the edited file to be re-parsed, got " f"{journal_reads.total} reads"
        )
        assert journal_reads.reads == [str(edited)]

    def test_outside_deleted_journal_loses_its_row(self, isolated_data_dir, journal_reads):
        journals = _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        deleted = journals[3]
        deleted_key = _cache_row_for(deleted)["file_path"]
        deleted.unlink()

        journal_reads.reset()
        _metadata_search()

        rows = _dump_cache_rows()
        assert all(row["file_path"] != deleted_key for row in rows)
        assert len(rows) == N_JOURNALS - 1

    def test_missing_sidecar_triggers_full_rebuild(self, isolated_data_dir, journal_reads):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()
        _sidecar_path(isolated_data_dir).unlink()

        journal_reads.reset()
        _metadata_search()

        assert journal_reads.total == N_JOURNALS, (
            f"full rebuild must parse each journal exactly once, got " f"{journal_reads.total}"
        )
        assert len(_dump_cache_rows()) == N_JOURNALS

    def test_schema_version_mismatch_triggers_full_rebuild(self, isolated_data_dir, journal_reads):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        from tools.lib.metadata_cache import CACHE_VERSION_SCHEMA_VERSION

        sidecar_path = _sidecar_path(isolated_data_dir)
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["schema_version"] = "v0.0.1-not-current"
        sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

        journal_reads.reset()
        _metadata_search()

        assert journal_reads.total == N_JOURNALS, (
            f"schema-version mismatch must trigger a full rebuild parsing each "
            f"journal exactly once, got {journal_reads.total}"
        )
        refreshed = json.loads(_sidecar_path(isolated_data_dir).read_text(encoding="utf-8"))
        assert refreshed["schema_version"] == CACHE_VERSION_SCHEMA_VERSION

    def test_entity_graph_change_triggers_full_rebuild(self, isolated_data_dir, journal_reads):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        # No entity_graph.yaml existed during warm-up; creating one changes the
        # graph dependency recorded in the sidecar.
        (isolated_data_dir / "entity_graph.yaml").write_text(
            "entities:\n  - id: TEST-ENTITY-001\n    type: person\n    primary_name: 测试人物\n"
            "    aliases: []\n    relationships: []\n",
            encoding="utf-8",
        )

        journal_reads.reset()
        _metadata_search()

        assert journal_reads.total == N_JOURNALS, (
            f"entity graph change must trigger a full rebuild parsing each "
            f"journal exactly once, got {journal_reads.total}"
        )
        assert len(_dump_cache_rows()) == N_JOURNALS


# ============================================================
# Write/edit-time upsert
# ============================================================


class TestWriteTimeUpsert:
    def test_write_upserts_cache_row_before_any_search(self, isolated_data_dir):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")
        written = Path(result["journal_path"])

        from tools.lib.metadata_cache import get_cached_metadata, init_metadata_cache

        conn = init_metadata_cache()
        try:
            row = get_cached_metadata(conn, written)
        finally:
            conn.close()
        assert row is not None, "write must upsert the new journal's cache row"
        assert row["title"] == WRITE_PAYLOAD["title"]

    def test_write_records_metadata_cache_row_side_effect(self, isolated_data_dir):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")

        records = [r for r in result["side_effects"] if r["name"] == "metadata_cache_row"]
        assert len(records) == 1
        assert records[0]["phase"] == "post_commit"
        assert records[0]["status"] == "complete"
        assert records[0]["blocking"] is False

    def test_edit_upserts_cache_row_before_any_search(self, isolated_data_dir):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        result = _write_one_journal()
        written = Path(result["journal_path"])

        from tools.edit_journal import edit_journal
        from tools.lib.metadata_cache import get_cached_metadata, init_metadata_cache

        edit_result = edit_journal(
            journal_path=written,
            frontmatter_updates={"weather": "rainy"},
        )
        assert edit_result.get("success") is True, edit_result.get("error")

        conn = init_metadata_cache()
        try:
            row = get_cached_metadata(conn, written)
        finally:
            conn.close()
        assert row is not None, "edit must upsert the edited journal's cache row"
        assert row["weather"] == "rainy"

    def test_upserted_rows_match_full_rebuild_rows(self, isolated_data_dir):
        """N single-row upserts must equal one full rebuild, field by field.

        ``cached_at`` legitimately differs (it is the INSERT OR REPLACE
        timestamp); every stored content field must be identical.
        """
        journals = _make_synthetic_journals(isolated_data_dir, N_JOURNALS)

        from tools.lib.metadata_cache import (
            init_metadata_cache,
            invalidate_cache,
            parse_and_cache_journal,
            update_cache_for_all_journals,
        )

        conn = init_metadata_cache()
        try:
            for journal in journals:
                assert parse_and_cache_journal(conn, journal) is not None
        finally:
            conn.close()
        upserted_rows = _dump_cache_rows()

        invalidate_cache()
        update_cache_for_all_journals()
        rebuilt_rows = _dump_cache_rows()

        assert len(upserted_rows) == len(rebuilt_rows) == N_JOURNALS

        def _comparable(rows: list[dict]) -> list[dict]:
            return [
                {key: value for key, value in row.items() if key != "cached_at"} for row in rows
            ]

        assert _comparable(upserted_rows) == _comparable(rebuilt_rows)


# ============================================================
# health --cache-audit: row-versus-file status, dry-run
# ============================================================


class TestCacheAuditRowComparison:
    def _audit(self) -> dict:
        from tools.lib.metadata_cache import run_cache_audit

        return run_cache_audit()["cache_audit"]

    def test_audit_valid_after_write(self, isolated_data_dir):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        result = _write_one_journal()
        assert result.get("journal_path"), result.get("error")

        assert self._audit()["status"] == "valid"

    def test_audit_stale_after_outside_edit(self, isolated_data_dir):
        journals = _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        edited = journals[5]
        stat = edited.stat()
        edited.write_text(edited.read_text(encoding="utf-8") + "\n\n外部编辑。\n", encoding="utf-8")
        os.utime(edited, (stat.st_mtime + 10, stat.st_mtime + 10))

        assert self._audit()["status"] == "stale"

    def test_audit_incompatible_on_schema_mismatch(self, isolated_data_dir):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        sidecar_path = _sidecar_path(isolated_data_dir)
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        sidecar["schema_version"] = "v0.0.1-not-current"
        sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

        audit = self._audit()
        assert audit["version_exists"] is True
        assert audit["status"] == "incompatible"

    def test_audit_missing_without_sidecar(self, isolated_data_dir):
        _make_synthetic_journals(isolated_data_dir, N_JOURNALS)

        audit = self._audit()
        assert audit["version_exists"] is False
        assert audit["status"] == "missing"

    def test_audit_is_dry_run(self, isolated_data_dir):
        journals = _make_synthetic_journals(isolated_data_dir, N_JOURNALS)
        _warm_cache_to_steady_state()

        sidecar_path = _sidecar_path(isolated_data_dir)
        sidecar_bytes = sidecar_path.read_bytes()
        rows_before = _dump_cache_rows()

        # An outside edit makes the cache stale; the audit must observe this
        # without repairing anything.
        edited = journals[9]
        stat = edited.stat()
        edited.write_text(edited.read_text(encoding="utf-8") + "\n\n外部编辑。\n", encoding="utf-8")
        os.utime(edited, (stat.st_mtime + 10, stat.st_mtime + 10))

        assert self._audit()["status"] == "stale"
        assert sidecar_path.read_bytes() == sidecar_bytes
        assert _dump_cache_rows() == rows_before
