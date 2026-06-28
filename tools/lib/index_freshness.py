"""Index freshness — unified freshness detection for the FTS index.

Round 12 Phase 3 Task 3.1: Checks manifest counts against actual index counts
and pending queue status to determine whether indexes are up-to-date.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .index_manifest import read_manifest
from .pending_writes import has_pending
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class FreshnessReport:
    """Comprehensive freshness status of the FTS index.

    ``vector_fresh`` is retained as a legacy output field for callers that
    already consume it. Vector indexes are no longer built or required.
    """

    fts_fresh: bool
    vector_fresh: bool
    overall_fresh: bool
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fts_fresh": self.fts_fresh,
            "vector_fresh": self.vector_fresh,
            "overall_fresh": self.overall_fresh,
            "issues": self.issues,
        }


def get_fts_count(index_dir: Path) -> int:
    """Get FTS document count from the FTS database."""
    fts_db = index_dir / "journals_fts.db"
    if not fts_db.exists():
        return 0
    try:
        import sqlite3

        conn = sqlite3.connect(str(fts_db))
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM journals")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()
    except Exception:
        return 0


def get_vector_count(index_dir: Path) -> int:
    """Legacy compatibility helper; vector indexes are no longer required."""

    return 0


def check_full_freshness(index_dir: Path) -> FreshnessReport:
    """Check freshness of the FTS index.

    Compares actual FTS counts against manifest records and checks for pending writes.

    Args:
        index_dir: Path to the .index directory.

    Returns:
        FreshnessReport with legacy vector_fresh=True.
    """
    issues: List[str] = []

    # Check manifest exists
    manifest = read_manifest(index_dir)
    if manifest is None:
        return FreshnessReport(
            fts_fresh=False,
            vector_fresh=True,
            overall_fresh=False,
            issues=["no_manifest: No index manifest found, run 'life-index index'"],
        )

    # Check partial build
    if manifest.partial:
        issues.append("partial_build: Last index build was incomplete")

    actual_fts = get_fts_count(index_dir)

    fts_fresh = actual_fts == manifest.fts_count
    vector_fresh = True

    if not fts_fresh:
        issues.append(
            f"fts_stale: FTS has {actual_fts} docs, manifest expects {manifest.fts_count}"
        )

    # Check pending queue
    if has_pending():
        issues.append("pending_writes: There are pending writes not yet indexed")

    overall_fresh = fts_fresh and len(issues) == 0

    return FreshnessReport(
        fts_fresh=fts_fresh,
        vector_fresh=vector_fresh,
        overall_fresh=overall_fresh,
        issues=issues,
    )
