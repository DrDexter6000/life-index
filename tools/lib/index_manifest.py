"""Index manifest — tracks last successful FTS index build state.

Records FTS counts, checksums, and build metadata so that index health checks
can detect corruption or staleness. Vector fields are retained for legacy
manifest compatibility but are not required.
"""

import hashlib
import json
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger(__name__)

MANIFEST_FILENAME = "index_manifest.json"


SCHEMA_VERSION = "v1.1.1"


@dataclass
class IndexManifest:
    """Snapshot of the last successful index build."""

    fts_count: int
    vector_count: int
    file_count: int
    fts_checksum: str
    vector_checksum: str
    build_timestamp: str
    build_version: str
    partial: bool = False
    schema_version: str = SCHEMA_VERSION


def write_manifest(manifest: IndexManifest, index_dir: Path) -> None:
    """Atomically write manifest to index_dir (temp + rename)."""
    index_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = index_dir / MANIFEST_FILENAME
    payload = json.dumps(asdict(manifest), ensure_ascii=False, indent=2)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(index_dir),
        prefix=f"{MANIFEST_FILENAME}.tmp",
    )
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        Path(tmp_path).replace(manifest_file)
    except Exception:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_manifest(index_dir: Path) -> Optional[IndexManifest]:
    """Read manifest from index_dir. Returns None if missing or corrupt."""
    manifest_file = index_dir / MANIFEST_FILENAME
    if not manifest_file.exists():
        return None
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        return IndexManifest(
            fts_count=data.get("fts_count", 0),
            vector_count=data.get("vector_count", 0),
            file_count=data.get("file_count", 0),
            fts_checksum=data.get("fts_checksum", ""),
            vector_checksum=data.get("vector_checksum", ""),
            build_timestamp=data.get("build_timestamp", ""),
            build_version=data.get("build_version", ""),
            partial=data.get("partial", False),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, TypeError):
        logger.warning("Corrupt or unreadable manifest, returning None")
        return None


def is_manifest_valid(manifest: IndexManifest, actual_file_count: int) -> bool:
    """Check whether manifest counts are internally consistent and match reality."""
    if manifest.partial:
        return False
    if manifest.fts_count != manifest.file_count:
        return False
    if manifest.file_count != actual_file_count:
        return False
    return True


def compute_fts_checksum(fts_db: Path) -> str:
    """Compute MD5 hex digest of FTS database file. Returns '' if missing."""
    if not fts_db.exists():
        return ""
    return hashlib.md5(fts_db.read_bytes()).hexdigest()


def compute_vector_checksum(vec_pkl: Path) -> str:
    """Compute MD5 digest of vector metadata pickle plus matrix sidecar.

    Returns '' if the metadata pickle is missing. The pickle remains the
    "index built" signal, while the split matrix sidecar participates in the
    freshness checksum when present.
    """
    if not vec_pkl.exists():
        return ""
    digest = hashlib.md5()
    digest.update(vec_pkl.read_bytes())
    matrix_path = vec_pkl.with_name("vectors_simple_emb.npz")
    if matrix_path.exists():
        digest.update(matrix_path.read_bytes())
    return digest.hexdigest()
