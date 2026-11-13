"""Pending writes queue — mark journals as needing index updates.

Round 12 Phase 1 Task 1.1: lightweight file-based queue that tracks which
journal paths need an incremental FTS repair. Write/edit operations append
paths here when their FTS row write-through failed; search operations and
``life-index index`` consume the queue before executing.

Each queued path carries a generation counter. ``mark_pending`` bumps the
path's generation and an acknowledgement removes a path only when the
generation it read is still current. Without generations, a path queued again
while a repair scan is running (newer file content, same path) would be
removed by the finishing scan and its event silently lost.

The on-disk format stays backward compatible: ``pending`` remains a list of
path strings (the pre-generation format), and ``generations`` is an additive
map. A file without ``generations`` is read as generation 0 for every path.

Mutations (mark / remove / ack / clear) serialize on a small queue lock file
via the shared ``FileLock`` helper: each mutation is a read-modify-write of
the same JSON file, and unserialized interleavings would silently drop paths.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

from .file_lock import FileLock
from .paths import get_index_dir

# Queue mutations are millisecond-scale; a stuck holder must not wedge a
# write's post-commit step for long.
PENDING_QUEUE_LOCK_TIMEOUT_S = 10.0

# Generation used for entries read from the pre-generation format.
LEGACY_GENERATION = 0


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


def _read_state() -> tuple[List[str], Dict[str, int]]:
    """Read the queue: (paths, path -> generation).

    Missing or corrupt state reads as an empty queue, as before. Entries in
    the legacy list-only format get ``LEGACY_GENERATION``.
    """
    pfile = _pending_file()
    if not pfile.exists():
        return [], {}
    try:
        data = json.loads(pfile.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return [], {}
    if not isinstance(data, dict) or not isinstance(data.get("pending"), list):
        return [], {}

    paths = list(dict.fromkeys(path for path in data["pending"] if isinstance(path, str)))
    raw_generations = data.get("generations")
    generations: Dict[str, int] = {}
    for path in paths:
        generation = LEGACY_GENERATION
        if isinstance(raw_generations, dict):
            try:
                generation = int(raw_generations.get(path, LEGACY_GENERATION))
            except (TypeError, ValueError):
                generation = LEGACY_GENERATION
        generations[path] = generation
    return paths, generations


def mark_pending(journal_path: str) -> None:
    """Queue a journal path and bump its generation.

    Uses atomic write (temp + rename) to avoid corruption on crash, under the
    queue lock so concurrent mark/remove mutations cannot lose paths. A path
    marked again while a repair scan runs gets a newer generation, so that
    scan's acknowledgement will not remove it.
    """
    _ensure_index_dir()
    with _queue_lock():
        current, generations = _read_state()
        if journal_path not in current:
            current.append(journal_path)
        generations[journal_path] = generations.get(journal_path, LEGACY_GENERATION) + 1
        _atomic_write(current, generations)


def remove_pending(paths: List[str]) -> List[str]:
    """Remove exactly these paths from the pending queue, unconditionally.

    The queue's other entries — including paths a concurrent ``mark_pending``
    queued while this call was running — are preserved. Returns the subset of
    ``paths`` that was actually present and removed, in queue order. Repair
    callers should prefer :func:`ack_pending` so a path re-queued during their
    scan survives.
    """
    if not paths:
        return []
    _ensure_index_dir()
    with _queue_lock():
        current, generations = _read_state()
        target_set = set(paths)
        removed = [path for path in current if path in target_set]
        _atomic_write([path for path in current if path not in target_set], generations)
        return removed


def ack_pending(
    snapshot: Mapping[str, int],
    only: Optional[Iterable[str]] = None,
) -> List[str]:
    """Acknowledge a snapshot read before a repair scan.

    A path is removed only when both hold:

    - its current generation equals the generation in ``snapshot`` (a path
      re-queued during the scan keeps its newer generation and survives), and
    - it was actually repaired (``only``; ``None`` means "trust the scan").

    Returns the paths removed, in queue order.
    """
    if not snapshot:
        return []
    repaired = None if only is None else set(only)
    _ensure_index_dir()
    with _queue_lock():
        current, generations = _read_state()
        removed: List[str] = []
        kept: List[str] = []
        for path in current:
            expected_generation = snapshot.get(path)
            if (
                expected_generation is not None
                and generations.get(path, LEGACY_GENERATION) == expected_generation
                and (repaired is None or path in repaired)
            ):
                removed.append(path)
            else:
                kept.append(path)
        _atomic_write(kept, generations)
        return removed


def get_pending() -> List[str]:
    """Read all pending paths. Returns empty list if file missing or corrupt."""
    return _read_state()[0]


def get_pending_generations() -> Dict[str, int]:
    """Read the queue as a ``path -> generation`` map (snapshot for ack)."""
    return _read_state()[1]


def clear_pending() -> None:
    """Clear the whole pending queue.

    Only for callers that really mean "empty everything" (for example test
    isolation); the search preflight must acknowledge its own snapshot so
    paths queued during its build survive.
    """
    _ensure_index_dir()
    with _queue_lock():
        _atomic_write([], {})


def has_pending() -> bool:
    """Check if there are any pending writes."""
    return len(get_pending()) > 0


def _atomic_write(paths: List[str], generations: Mapping[str, int]) -> None:
    """Atomically write the pending list (and generations) to disk."""
    pfile = _pending_file()
    kept_generations = {path: generations[path] for path in paths if path in generations}
    payload = json.dumps(
        {"pending": paths, "generations": kept_generations},
        ensure_ascii=False,
        indent=2,
    )

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
