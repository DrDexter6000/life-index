"""Contract tests for the shared journal file kind rule (tools/lib/journal_files.py).

Charter amendment 13 gives journals two in-file kinds (fragment / digest).
Before digests exist, every tool walking Journals/ must agree on what each
Markdown file is, decided by one shared classifier. These tests pin:

1. the closed kind enumeration and the pure path classifier table;
2. enumeration helpers: default is fragments only, dot-directories such as
   .revisions/ are never live files, order is stable, and callers must ask
   for other kinds by name;
3. a source scan: no module other than the canonical one may glob ``*.md``
   in a way that can reach the journals tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.lib.journal_files import (
    JournalFileKind,
    classify_journal_path,
    count_journal_files,
    has_journal_files,
    iter_journal_files,
    iter_journal_files_of_kind,
    iter_month_journal_files,
    iter_year_journal_files,
)


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        content or f"---\ntitle: {path.stem}\ndate: 2026-03-07\n---\n", encoding="utf-8"
    )
    return path


def _mixed_month(tmp_path: Path) -> Path:
    """Month folder holding one file of every shape that occurs in real data dirs."""
    month = tmp_path / "Journals" / "2026" / "03"
    _write(month / "life-index_2026-03-07_001.md")
    _write(month / "index_2026-03.md")
    _write(month / "monthly_report_2026-03.md")
    _write(month / "digest_2026-03-07.md", "---\nkind: digest\ntitle: day digest\n---\nbody")
    _write(month / "notes.md")
    _write(
        month / ".revisions" / "life-index_2026-03-07_001_20260308_101500_000000.md",
        "---\ntitle: old revision\ndate: 2026-03-07\n---\nbody",
    )
    return tmp_path / "Journals"


class TestClassifierTable:
    """Every file shape under Journals/ maps to exactly one closed kind."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("life-index_2026-03-07_001.md", JournalFileKind.FRAGMENT),
            ("life-index_2026-01-02_12.md", JournalFileKind.FRAGMENT),
            ("digest_2026-03-07.md", JournalFileKind.DIGEST),
            ("digest_2026-03.md", JournalFileKind.DIGEST),
            ("digest_2026.md", JournalFileKind.DIGEST),
            ("index_2026-03.md", JournalFileKind.DERIVED_INDEX),
            ("index_2026.md", JournalFileKind.DERIVED_INDEX),
            ("monthly_report_2026-03.md", JournalFileKind.DERIVED_INDEX),
            ("yearly_report_2026.md", JournalFileKind.DERIVED_INDEX),
            ("notes.md", JournalFileKind.UNKNOWN),
            ("life-index_2026-03-07_001_20260308_101500_000000.md", JournalFileKind.UNKNOWN),
            ("life-index_2026-03-07.md", JournalFileKind.UNKNOWN),
            ("life-index_2026-03-07_abc.md", JournalFileKind.UNKNOWN),
            ("digest_notes.txt", JournalFileKind.UNKNOWN),
            ("README.md", JournalFileKind.UNKNOWN),
        ],
    )
    def test_name_maps_to_kind(self, name: str, expected: JournalFileKind):
        assert classify_journal_path(Path("Journals") / "2026" / "03" / name) is expected

    def test_classification_is_pure_path_logic(self, tmp_path: Path):
        # The classifier never opens the file: a non-existent path still classifies.
        missing = tmp_path / "Journals" / "2099" / "01" / "life-index_2099-01-01_001.md"
        assert not missing.exists()
        assert classify_journal_path(missing) is JournalFileKind.FRAGMENT

    def test_kind_enumeration_is_closed(self):
        assert {kind.value for kind in JournalFileKind} == {
            "fragment",
            "digest",
            "derived_index",
            "unknown",
        }

    def test_backup_derived_artifact_rule_is_shared(self):
        # tools/backup delegates its generated-artifact prefixes to the same rule.
        from tools.backup import _is_generated_journal_artifact

        for name in ("index_2026-03.md", "monthly_report_2026-03.md", "yearly_2026.md"):
            assert _is_generated_journal_artifact(Path(name))
        for name in ("life-index_2026-03-07_001.md", "digest_2026-03-07.md", "notes.md"):
            assert not _is_generated_journal_artifact(Path(name))


class TestEnumeration:
    def test_default_enumeration_returns_only_the_fragment(self, tmp_path: Path):
        journals = _mixed_month(tmp_path)
        names = [path.name for path in iter_journal_files(journals)]
        assert names == ["life-index_2026-03-07_001.md"]
        assert count_journal_files(journals) == 1

    def test_dot_directories_are_never_live_files_of_any_kind(self, tmp_path: Path):
        journals = _mixed_month(tmp_path)
        everything = list(iter_journal_files_of_kind(journals, tuple(JournalFileKind)))
        assert not any(".revisions" in path.parts for path in everything)
        assert "life-index_2026-03-07_001_20260308_101500_000000.md" not in {
            path.name for path in everything
        }

    def test_callers_must_ask_for_other_kinds_by_name(self, tmp_path: Path):
        journals = _mixed_month(tmp_path)
        digests = list(iter_journal_files_of_kind(journals, (JournalFileKind.DIGEST,)))
        assert [path.name for path in digests] == ["digest_2026-03-07.md"]

        derived = list(iter_journal_files_of_kind(journals, (JournalFileKind.DERIVED_INDEX,)))
        assert [path.name for path in derived] == ["index_2026-03.md", "monthly_report_2026-03.md"]

        unknown = list(iter_journal_files_of_kind(journals, (JournalFileKind.UNKNOWN,)))
        assert [path.name for path in unknown] == ["notes.md"]

    def test_month_and_year_helpers_cover_one_scope(self, tmp_path: Path):
        journals = _mixed_month(tmp_path)
        month = journals / "2026" / "03"
        assert [path.name for path in iter_month_journal_files(month)] == [
            "life-index_2026-03-07_001.md"
        ]
        assert [path.name for path in iter_year_journal_files(journals / "2026")] == [
            "life-index_2026-03-07_001.md"
        ]

    def test_month_helpers_skip_month_index_and_revisions(self, tmp_path: Path):
        journals = _mixed_month(tmp_path)
        month = journals / "2026" / "03"
        everything = list(iter_month_journal_files(month, tuple(JournalFileKind)))
        assert [path.name for path in everything] == [
            "digest_2026-03-07.md",
            "index_2026-03.md",
            "life-index_2026-03-07_001.md",
            "monthly_report_2026-03.md",
            "notes.md",
        ]

    def test_has_journal_files_ignores_derived_and_revisions(self, tmp_path: Path):
        journals = _mixed_month(tmp_path)
        assert has_journal_files(journals / "2026" / "03")
        # A month holding only a derived index / stray note has no journal.
        bare = tmp_path / "bare" / "Journals" / "2026" / "04"
        _write(bare / "index_2026-04.md")
        _write(bare / "notes.md")
        _write(bare / ".revisions" / "life-index_2026-04-01_001_20260402_101500_000000.md")
        assert not has_journal_files(bare)

    def test_order_is_stable_across_calls(self, tmp_path: Path):
        journals = tmp_path / "Journals"
        for seq in (1, 2, 3):
            _write(journals / "2025" / "12" / f"life-index_2025-12-31_{seq:03d}.md")
            _write(journals / "2026" / "03" / f"life-index_2026-03-07_{seq:03d}.md")
        first = [p.name for p in iter_journal_files(journals)]
        second = [p.name for p in iter_journal_files(journals)]
        assert first == second == sorted(first)
        assert first[0].startswith("life-index_2025-12-31")
        assert first[-1].startswith("life-index_2026-03-07")

    def test_missing_directory_yields_nothing(self, tmp_path: Path):
        assert list(iter_journal_files(tmp_path / "does-not-exist")) == []
        assert not has_journal_files(tmp_path / "does-not-exist")

    def test_existing_public_names_keep_fragment_meaning(self, tmp_path: Path):
        from tools.lib.journal_files import is_journal_file

        journals = _mixed_month(tmp_path)
        month = journals / "2026" / "03"
        assert is_journal_file(month / "life-index_2026-03-07_001.md")
        assert not is_journal_file(month / "index_2026-03.md")
        assert not is_journal_file(month / "digest_2026-03-07.md")
        assert not is_journal_file(month / "notes.md")
        revision = month / ".revisions" / "life-index_2026-03-07_001_20260308_101500_000000.md"
        assert not is_journal_file(revision)


class TestSourceScan:
    """No ad-hoc catch-all ``*.md`` glob may reach the journals tree.

    The scan flags two static shapes in every module under ``tools/``:

    - the bare catch-all strings ``"*.md"`` / ``"**/*.md"`` (wherever they
      appear, including as helper arguments), because such a pattern can match
      any file name and therefore any digest, derived index, stray note, or
      old revision;
    - ``.glob(f"...")`` / ``.rglob(f"...")`` calls, because a dynamic pattern
      cannot be statically verified and must be reviewed by hand.

    Known blind spots (accepted): variable-pattern calls such as
    ``.glob(pattern)``, and name-suffix walks such as ``os.scandir`` +
    ``endswith(".md")`` in tools/lib/fs_consistency.py (deliberate "any
    markdown write" freshness signal).

    Everything found must be either in tools/lib/journal_files.py (the
    canonical module) or on the exact (file, pattern) allowlist below. The
    allowlist is per finding, never a blanket file exemption, and stale
    entries fail too so the list cannot rot.
    """

    TOOLS_ROOT = Path(__file__).resolve().parents[2] / "tools"
    CANONICAL_MODULE = "lib/journal_files.py"

    # (repo-relative path under tools/) -> set of finding patterns authorised
    # for exactly that file. Every entry carries the reason its directory can
    # never be mistaken for live journals.
    ALLOWLIST: dict[str, set[str]] = {
        # by-topic/ legacy topic indexes: a sibling directory, never Journals/.
        "search_journals/l1_index.py": {'"*.md"'},
        # by-topic/ index freshness verification: sibling directory.
        "verify/core.py": {'"*.md"'},
        # Entities/ derived entity profiles: sibling directory.
        "generate_index/entity_profiles.py": {'"*.md"'},
        # Whole-data-dir file audits (encoding / links / portability / privacy):
        # they inspect every Markdown file as a file, with no journal semantics.
        "maintenance/audit.py": {'"*.md"'},
        # Canonical .revisions/ listing: dot-directory contents are never live
        # journal files of any kind, and only this module reads them on purpose.
        "lib/revisions.py": {"f-glob"},
        # Skill sync scans installed skill directories, never user data.
        "sync_skill/__init__.py": {"f-glob"},
    }

    BARE_MD_STRING_RE = re.compile(r'"(\*\*/)?\*\.md"')
    FSTRING_GLOB_RE = re.compile(r'\.(?:rglob|glob)\(\s*f"')

    def _findings_by_file(self) -> dict[str, set[str]]:
        findings: dict[str, set[str]] = {}
        for py_file in sorted(self.TOOLS_ROOT.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            rel = py_file.relative_to(self.TOOLS_ROOT).as_posix()
            if rel == self.CANONICAL_MODULE:
                continue
            text = py_file.read_text(encoding="utf-8")
            marks: set[str] = set()
            if self.BARE_MD_STRING_RE.search(text):
                # Both "*.md" and "**/*.md" normalize to one catch-all mark.
                marks.add('"*.md"')
            if self.FSTRING_GLOB_RE.search(text):
                marks.add("f-glob")
            if marks:
                findings[rel] = marks
        return findings

    def test_no_adhoc_md_glob_reaches_the_journals_tree(self):
        findings = self._findings_by_file()
        violations: list[str] = []
        for rel, marks in findings.items():
            allowed = self.ALLOWLIST.get(rel, set())
            for mark in sorted(marks - allowed):
                violations.append(f"{rel}: {mark}")
        assert not violations, (
            "Catch-all *.md glob or dynamic f-string glob outside the shared "
            "journal_files helpers (migrate to tools/lib/journal_files.py or "
            "add an exact allowlist entry with a reason):\n  " + "\n  ".join(violations)
        )

    def test_allowlist_entries_are_exact_and_not_stale(self):
        findings = self._findings_by_file()
        stale: list[str] = []
        for rel, marks in self.ALLOWLIST.items():
            for mark in sorted(marks):
                if mark not in findings.get(rel, set()):
                    stale.append(f"{rel}: {mark}")
        assert not stale, (
            "Stale allowlist entries (pattern no longer present in the file — "
            "remove them so the allowlist stays exact):\n  " + "\n  ".join(stale)
        )


class TestConsumersSeeOnlyFragments:
    """End-to-end: non-fragment Markdown is never searched or cached as a journal.

    Every file in the month carries the same search word in title and body, so
    a consumer that still read digests, derived indexes, stray notes, or old
    revisions as journals would return or cache them.
    """

    WORD = "zebrafinch"
    FRAGMENT = "life-index_2026-03-07_001.md"

    def _populate(self, data_dir: Path) -> None:
        month = data_dir / "Journals" / "2026" / "03"
        for name in (
            self.FRAGMENT,
            "index_2026-03.md",
            "monthly_report_2026-03.md",
            "digest_2026-03-07.md",
            "notes.md",
            ".revisions/life-index_2026-03-07_001_20260308_101500_000000.md",
        ):
            _write(
                month / name,
                f"---\ntitle: {self.WORD} {name}\ndate: 2026-03-07\ntopic: [life]\n---\n\n"
                f"{self.WORD} {self.WORD} {self.WORD}\n",
            )

    def test_content_search_fallback_returns_only_the_fragment(self, isolated_data_dir: Path):
        from tools.search_journals.l3_content import search_l3_content

        self._populate(isolated_data_dir)
        hits = search_l3_content(self.WORD)
        assert sorted(Path(hit["path"]).name for hit in hits) == [self.FRAGMENT]

    def test_metadata_cache_rebuild_caches_only_the_fragment(self, isolated_data_dir: Path):
        from tools.lib import metadata_cache

        self._populate(isolated_data_dir)
        metadata_cache.update_cache_for_all_journals()
        conn = metadata_cache.init_metadata_cache()
        try:
            rows = conn.execute("SELECT file_path FROM metadata_cache").fetchall()
        finally:
            conn.close()
        assert sorted(Path(row[0]).name for row in rows) == [self.FRAGMENT]
