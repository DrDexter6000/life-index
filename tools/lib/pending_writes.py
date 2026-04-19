"""Pending writes queue — mark journals as needing index updates.

Round 12 Phase 1 Task 1.1: lightweight file-based queue that tracks which
journal paths need incremental index updates. Write/edit operations append
paths here; search operations consume the queue before executing.
"""

import json
import tempfile
from pathlib import Path
from typing import List

from .paths import get_index_dir

# Module-level helper for testability
_pending_file = lambda: get_index_dir() / "pending_writes.json"


def _ensure_index_dir() -> None:
    """Ensure .index directory exists."""
    get_index_dir().mkdir(parents=True, exist_ok=True)


def mark_pending(journal_path: str) -> None:
    """Append a journal path to the pending queue (deduplicated).

    Uses atomic write (temp + rename) to avoid corruption on crash.
    """
    _ensure_index_dir()
    current = get_pending()
    if journal_path not in current:
        current.append(journal_path)
    _atomic_write(current)


def get_pending() -> List[str]:
    """Read all pending paths. Returns empty list if file missing or corrupt."""
    pfile = _pending_file()
    if not pfile.exists():
        return []
    try:
        data = json.loads(pfile.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("pending"), list):
            return list(dict.fromkeys(data["pending"]))  # deduplicate preserving order
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        pass
    return []


def clear_pending() -> None:
    """Clear the pending queue."""
    _ensure_index_dir()
    _atomic_write([])


def has_pending() -> bool:
    """Check if there are any pending writes."""
    return len(get_pending()) > 0


def _atomic_write(paths: List[str]) -> None:
    """Atomically write the pending list to disk (temp + rename)."""
    pfile = _pending_file()
    payload = json.dumps({"pending": paths}, ensure_ascii=False, indent=2)

    # Write to temp file in the same directory, then rename atomically
    fd, tmp_path = tempfile.mkstemp(
        dir=str(pfile.parent),
        prefix="pending_writes.json.tmp",
    )
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        Path(tmp_path).replace(pfile)
    except Exception:
        # Clean up temp file on failure
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise
