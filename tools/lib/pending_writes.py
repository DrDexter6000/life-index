"""Pending writes queue — mark journals as needing index updates.

Round 12 Phase 1 Task 1.1: lightweight file-based queue that tracks which
journal paths need incremental index updates. Write/edit operations append
paths here when their FTS row write-through failed; search operations consume
the queue before executing, removing only the paths that were queued when
their build started.

Mutations (mark / remove / clear) serialize on a small queue lock file via
the shared ``FileLock`` helper: each mutation is a read-modify-write of the
same JSON file, and unserialized interleavings would silently drop paths.
"""

import json
import tempfile
from pathlib import Path
from typing import List

from .file_lock import FileLock
from .paths import get_index_dir

# Queue mutations are millisecond-scale; a stuck holder must not wedge a
# write's post-commit step for long.
PENDING_QUEUE_LOCK_TIMEOUT_S = 10.0


# Module-level helper for testability
def _pending_file() -> Path:
    return get_index_dir() / "pending_writes.json"


def _queue_lock() -> FileLock:
    return FileLock(
        get_index_dir() / "pending_writes.lock",
        timeout=PENDING_QUEUE_LOCK_TIMEOUT_S,
    )


def _ensure_index_dir() -> None:
    """Ensure .index directory exists."""
    get_index_dir().mkdir(parents=True, exist_ok=True)


def mark_pending(journal_path: str) -> None:
    """Append a journal path to the pending queue (deduplicated).

    Uses atomic write (temp + rename) to avoid corruption on crash, under the
    queue lock so concurrent mark/remove mutations cannot lose paths.
    """
    _ensure_index_dir()
    with _queue_lock():
        current = get_pending()
        if journal_path not in current:
            current.append(journal_path)
        _atomic_write(current)


def remove_pending(paths: List[str]) -> List[str]:
    """Remove exactly these paths from the pending queue.

    The queue's other entries — including paths a concurrent ``mark_pending``
    queued while this call was running — are preserved. Returns the subset of
    ``paths`` that was actually present and removed, in queue order.
    """
    if not paths:
        return []
    _ensure_index_dir()
    with _queue_lock():
        current = get_pending()
        target_set = set(paths)
        _atomic_write([path for path in current if path not in target_set])
        return [path for path in current if path in target_set]


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
    """Clear the whole pending queue.

    Only for callers that really mean "empty everything" (for example test
    isolation); the search preflight must use ``remove_pending`` so paths
    queued during its build survive.
    """
    _ensure_index_dir()
    with _queue_lock():
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
