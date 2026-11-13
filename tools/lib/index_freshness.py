"""Index freshness — unified freshness detection for the FTS index.

Round 12 Phase 3 Task 3.1 started this as manifest-count comparison. Since
the FTS write-through landed, freshness is decided the same way the metadata
cache decides it: by comparing every live fragment's ``(mtime, size)``
signature with ``fts_file_stats`` and requiring an FTS row for the path. The
manifest still says whether the last archive scan completed, but its row
count is no longer a freshness signal.

The check itself is read-only: one ``scan_journal_files()`` pass plus indexed
reads of the FTS database (the journals paths and the signature rows). It
never opens a journal file.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List

from .index_manifest import read_manifest
from .pending_writes import has_pending
from .logger import get_logger

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from .fts_update import FtsSignatureReport

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
    # True only when this report came from the real signature check (not a
    # test double); the search preflight forwards the verdict to the L3
    # fallback gate only in that case.
    signature_checked: bool = False

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


def _signature_report(index_dir: Path) -> "FtsSignatureReport":
    """Run the read-only signature comparison from ``<data_dir>/.index``."""
    from .fts_update import FtsSignatureReport, inspect_fts_index

    # ``index_dir`` is ``<user_data_dir>/.index``; deriving the journals tree
    # from it keeps ``index --check --data-dir`` coherent with the DB it reads.
    user_data_dir = index_dir.parent
    fts_db = index_dir / "journals_fts.db"
    if not fts_db.exists():
        return FtsSignatureReport(current=False, reasons=("no_fts_db",))
    try:
        conn = sqlite3.connect(str(fts_db))
    except sqlite3.Error as exc:
        return FtsSignatureReport(current=False, reasons=(f"db_error: {exc}",))
    try:
        return inspect_fts_index(conn, user_data_dir / "Journals", user_data_dir)
    except sqlite3.Error as exc:
        return FtsSignatureReport(current=False, reasons=(f"db_error: {exc}",))
    finally:
        conn.close()


def _signature_issue(report: "FtsSignatureReport") -> str:
    """Describe the first signature mismatch in a stable, actionable form."""
    if report.current:
        return ""
    if "no_fts_db" in report.reasons:
        return "no_fts_db: FTS index has not been built, run 'life-index index'"
    reasons = list(report.reasons)
    sample = "; ".join(reasons[:3])
    more = f" (+{len(reasons) - 3} more)" if len(reasons) > 3 else ""
    return (
        f"fts_signature_mismatch: {len(reasons)} fragment(s) need reindexing "
        f"[{sample}{more}], run 'life-index index'"
    )


def check_full_freshness(index_dir: Path) -> FreshnessReport:
    """Check freshness of the FTS index by per-fragment signature.

    Args:
        index_dir: Path to the .index directory.

    Returns:
        FreshnessReport with legacy vector_fresh=True.
    """
    issues: List[str] = []

    # Manifest presence/completeness is a build signal, not a row-count
    # freshness rule: a partial or missing manifest still warrants a build.
    manifest = read_manifest(index_dir)
    if manifest is None:
        issues.append("no_manifest: No index manifest found, run 'life-index index'")
    elif manifest.partial:
        issues.append("partial_build: Last index build was incomplete")

    report = _signature_report(index_dir)
    fts_fresh = report.current
    signature_issue = _signature_issue(report)
    if signature_issue:
        issues.append(signature_issue)
    else:
        # Schema/tokenizer/dictionary versions still force a full rebuild.
        try:
            from .search_index import check_needs_rebuild

            fts_db = index_dir / "journals_fts.db"
            conn = sqlite3.connect(str(fts_db))
            try:
                needs_rebuild = check_needs_rebuild(conn)
            finally:
                conn.close()
        except Exception:
            needs_rebuild = True
        if needs_rebuild:
            fts_fresh = False
            issues.append(
                "version_mismatch: tokenizer/dictionary/schema changed, "
                "run 'life-index index --rebuild'"
            )

    vector_fresh = True

    # Check pending queue
    if has_pending():
        issues.append("pending_writes: There are pending writes not yet indexed")

    overall_fresh = fts_fresh and len(issues) == 0

    return FreshnessReport(
        fts_fresh=fts_fresh,
        vector_fresh=vector_fresh,
        overall_fresh=overall_fresh,
        issues=issues,
        signature_checked=True,
    )
