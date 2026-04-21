"""Index freshness — unified freshness detection for FTS + vector indexes.

Round 12 Phase 3 Task 3.1: Checks manifest counts against actual index counts
and pending queue status to determine whether indexes are up-to-date.

Phase 2b-4: Also checks jieba_version and dict_hash staleness for observability.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .index_manifest import read_manifest
from .pending_writes import has_pending
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class FreshnessReport:
    """Comprehensive freshness status of FTS + vector indexes."""

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
    """Get vector count from the simple vector index."""
    import pickle

    vec_pkl = index_dir / "vectors_simple.pkl"
    if not vec_pkl.exists():
        return 0
    try:
        with open(vec_pkl, "rb") as f:
            vectors = pickle.load(f)
        return len(vectors) if isinstance(vectors, dict) else 0
    except Exception:
        return 0


def check_full_freshness(index_dir: Path) -> FreshnessReport:
    """Check comprehensive freshness of FTS + vector indexes.

    Compares actual counts against manifest records and checks for pending writes.

    Args:
        index_dir: Path to the .index directory.

    Returns:
        FreshnessReport with fts_fresh, vector_fresh, overall_fresh, and issues.
    """
    issues: List[str] = []

    # Check manifest exists
    manifest = read_manifest(index_dir)
    if manifest is None:
        return FreshnessReport(
            fts_fresh=False,
            vector_fresh=False,
            overall_fresh=False,
            issues=["no_manifest: No index manifest found, run 'life-index index'"],
        )

    # Check partial build
    if manifest.partial:
        issues.append("partial_build: Last index build was incomplete")

    # Get actual counts
    actual_fts = get_fts_count(index_dir)
    actual_vector = get_vector_count(index_dir)

    # Compare with manifest
    fts_fresh = actual_fts == manifest.fts_count
    vector_fresh = actual_vector == manifest.vector_count

    if not fts_fresh:
        issues.append(
            f"fts_stale: FTS has {actual_fts} docs, manifest expects {manifest.fts_count}"
        )
    if not vector_fresh:
        issues.append(
            f"vector_stale: Vector has {actual_vector} entries, "
            f"manifest expects {manifest.vector_count}"
        )

    # Check pending queue
    if has_pending():
        issues.append("pending_writes: There are pending writes not yet indexed")

    overall_fresh = fts_fresh and vector_fresh and len(issues) == 0

    return FreshnessReport(
        fts_fresh=fts_fresh,
        vector_fresh=vector_fresh,
        overall_fresh=overall_fresh,
        issues=issues,
    )


def check_tokenizer_freshness(fts_db_path: Path) -> None:
    """Check jieba version and entity dict hash staleness; log suggestions.

    Reads jieba_version and dict_hash from index_meta, compares with current
    runtime values, and emits INFO-level log messages when they differ.

    Phase 2b-4: Observability — only logs, never forces rebuild.

    Args:
        fts_db_path: Path to the FTS SQLite database (journals_fts.db).
    """
    if not fts_db_path.exists():
        return

    try:
        conn = sqlite3.connect(str(fts_db_path))
        try:
            cursor = conn.cursor()

            # Check jieba version
            cursor.execute("SELECT value FROM index_meta WHERE key = 'jieba_version'")
            row = cursor.fetchone()
            if row is not None:
                stored_version = row[0]
                try:
                    import jieba

                    current_version = jieba.__version__
                except (ImportError, AttributeError):
                    current_version = None

                if current_version is not None and stored_version != current_version:
                    logger.info(
                        "jieba %s differs from index's %s; consider rebuild to refresh tokens",
                        current_version,
                        stored_version,
                    )

            # Check dict hash (entity dictionary)
            cursor.execute("SELECT value FROM index_meta WHERE key = 'dict_hash'")
            row = cursor.fetchone()
            if row is not None:
                stored_hash = row[0]
                from .chinese_tokenizer import get_dict_hash

                current_hash = get_dict_hash()
                if current_hash and stored_hash != current_hash:
                    logger.info(
                        "entity dict hash %s differs from index's %s;"
                        " consider rebuild to refresh tokens",
                        current_hash,
                        stored_hash,
                    )
        finally:
            conn.close()
    except sqlite3.Error:
        pass  # Non-critical — DB access failure should not block search
