"""Index consistency diagnostics — measure FTS index health without fixing anything.

Read-only diagnostic tools that compare FTS count and actual journal file count,
reporting discrepancies. Vector fields are retained as legacy empty fields.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set

from ..lib.path_contract import safe_relative_path


@dataclass
class IndexHealthReport:
    """Structured result of an index health check."""

    fts_count: int = 0
    vector_count: int = 0
    file_count: int = 0
    fts_orphans: Set[str] = field(default_factory=set)  # in FTS but not on disk
    fts_missing: Set[str] = field(default_factory=set)  # on disk but not in FTS
    vec_orphans: Set[str] = field(default_factory=set)  # in vectors but not on disk
    vec_missing: Set[str] = field(default_factory=set)  # on disk but not in vectors
    issues: list[str] = field(default_factory=list)

    @property
    def fts_ok(self) -> bool:
        return not self.fts_orphans and not self.fts_missing

    @property
    def vector_ok(self) -> bool:
        return True

    @property
    def consistency_ok(self) -> bool:
        return self.fts_ok


def _scan_actual_journals(data_dir: Path) -> Set[str]:
    """Scan Journals/ directory for life-index_*.md files, return relative paths.

    Paths are returned relative to *data_dir* (the Life-Index/ root),
    matching the convention used by FTS and vector indexes.
    """
    journals_dir = data_dir / "Journals"
    actual: Set[str] = set()
    if not journals_dir.exists():
        return actual
    for journal_file in journals_dir.rglob("life-index_*.md"):
        # Skip .revisions directories
        if ".revisions" in journal_file.parts:
            continue
        actual.add(safe_relative_path(journal_file, data_dir))
    return actual


def _read_fts_paths(index_dir: Path) -> Set[str]:
    """Read all indexed paths from FTS database."""
    paths: Set[str] = set()
    db_path = index_dir / "journals_fts.db"
    if not db_path.exists():
        return paths
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT path FROM journals")
        for row in cur.fetchall():
            paths.add(row[0])
        conn.close()
    except Exception:
        pass
    return paths


def _read_vector_paths(index_dir: Path) -> Set[str]:
    """Legacy compatibility helper; vector indexes are no longer required."""

    return set()


def check_index_health(data_dir: Path) -> IndexHealthReport:
    """Check index consistency: compare FTS and actual file counts.

    This is a read-only operation — it never modifies any index or data file.
    """
    index_dir = data_dir / ".index"

    actual_paths = _scan_actual_journals(data_dir)
    fts_paths = _read_fts_paths(index_dir)
    vec_paths = _read_vector_paths(index_dir)

    fts_orphans = fts_paths - actual_paths
    fts_missing = actual_paths - fts_paths
    vec_orphans: Set[str] = set()
    vec_missing: Set[str] = set()

    issues: list[str] = []
    if fts_orphans:
        issues.append(
            f"FTS has {len(fts_orphans)} orphan(s): entries indexed but file missing on disk"
        )
    if fts_missing:
        issues.append(f"FTS missing {len(fts_missing)} file(s): on disk but not indexed")
    if not fts_orphans and not fts_missing and actual_paths:
        issues.append("FTS index consistent with actual files")

    return IndexHealthReport(
        fts_count=len(fts_paths),
        vector_count=len(vec_paths),
        file_count=len(actual_paths),
        fts_orphans=fts_orphans,
        fts_missing=fts_missing,
        vec_orphans=vec_orphans,
        vec_missing=vec_missing,
        issues=issues,
    )
