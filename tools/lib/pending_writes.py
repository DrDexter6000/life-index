"""Pending writes queue — mark journals as needing index updates.

Round 12 Phase 1 Task 1.1: lightweight file-based queue that tracks which
journal paths need an incremental FTS repair. Write/edit operations append
paths here when their FTS row write-through failed; search operations and
``life-index index`` consume the queue before executing.

Each queued path carries a generation. ``mark_pending`` gives the path the
next value of a queue-wide counter and an acknowledgement removes a path only
when the generation it read is still current. Without generations, a path
queued again while a repair scan is running (newer file content, same path)
would be removed by the finishing scan and its event silently lost. The
counter never goes back, also not when the queue empties, so a path that left
the queue and was queued again can never carry a generation an older snapshot
still holds.

The on-disk format stays backward compatible: ``pending`` remains a list of
path strings (the pre-generation format); ``generations`` and ``counter`` are
additive. A file without ``generations`` is read as generation 0 for every
path.

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
def _pending_file(index_dir: Optional[Path] = None) -> Path:
    return (index_dir if index_dir is not None else get_index_dir()) / "pending_writes.json"


def _queue_lock() -> FileLock:
    return FileLock(
        get_index_dir() / "pending_writes.lock",
        timeout=PENDING_QUEUE_LOCK_TIMEOUT_S,
    )


def _ensure_index_dir() -> None:
    """Ensure .index directory exists."""
    get_index_dir().mkdir(parents=True, exist_ok=True)


def _coerce_generation(value: object) -> int:
    """Return a usable generation, else the legacy generation.

    The queue file is user-writable state, so a hand-edited or truncated file
    may carry anything: strings, floats (including ``inf`` from JSON ``1e999``),
    negatives, nested objects. None of those may raise out of a search or a
    write; every unusable value reads as the pre-generation format.
    """
    if isinstance(value, bool):
        return LEGACY_GENERATION
    if isinstance(value, int) and value >= LEGACY_GENERATION:
        return value
    return LEGACY_GENERATION


def _read_state(index_dir: Optional[Path] = None) -> tuple[List[str], Dict[str, int], int]:
    """Read the queue: (paths, path -> generation, highest generation issued).

    Missing or corrupt state reads as an empty queue, as before. Entries in
    the legacy list-only format get ``LEGACY_GENERATION``. Any unusable
    generation or counter value is treated as the legacy generation instead of
    raising.
    """
    pfile = _pending_file(index_dir)
    if not pfile.exists():
        return [], {}, LEGACY_GENERATION
    try:
        data = json.loads(pfile.read_text(encoding="utf-8"))
    except (ValueError, OSError, RecursionError):
        # ValueError covers invalid JSON, invalid UTF-8 and an integer literal
        # too long to convert; RecursionError covers absurdly deep nesting.
        return [], {}, LEGACY_GENERATION
    if not isinstance(data, dict) or not isinstance(data.get("pending"), list):
        return [], {}, LEGACY_GENERATION

    paths = list(dict.fromkeys(path for path in data["pending"] if isinstance(path, str)))
    raw_generations = data.get("generations")
    generations: Dict[str, int] = {}
    for path in paths:
        generation = LEGACY_GENERATION
        if isinstance(raw_generations, dict):
            generation = _coerce_generation(raw_generations.get(path, LEGACY_GENERATION))
        generations[path] = generation
    counter = _coerce_generation(data.get("counter"))
    return paths, generations, max([counter, *generations.values()])


def mark_pending(journal_path: str) -> None:
    """Queue a journal path under a generation no snapshot has seen.

    Uses atomic write (temp + rename) to avoid corruption on crash, under the
    queue lock so concurrent mark/remove mutations cannot lose paths. A path
    marked again while a repair scan runs gets a newer generation, so that
    scan's acknowledgement will not remove it.
    """
    _ensure_index_dir()
    with _queue_lock():
        current, generations, counter = _read_state()
        if journal_path not in current:
            current.append(journal_path)
        counter += 1
        generations[journal_path] = counter
        _atomic_write(current, generations, counter)


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
        current, generations, counter = _read_state()
        target_set = set(paths)
        removed = [path for path in current if path in target_set]
        _atomic_write([path for path in current if path not in target_set], generations, counter)
        return removed


def ack_pending(
    snapshot: Mapping[str, int],
    only: Iterable[str],
) -> List[str]:
    """Acknowledge a snapshot read before a repair scan.

    A path is removed only when both hold:

    - its current generation equals the generation in ``snapshot`` (a path
      re-queued during the scan keeps its newer generation and survives), and
    - it was actually repaired (``only``; there is no permissive mode — a
      build result without a repaired list acknowledges nothing).

    Returns the paths removed, in queue order.
    """
    if not snapshot:
        return []
    repaired = set(only)
    _ensure_index_dir()
    with _queue_lock():
        current, generations, counter = _read_state()
        removed: List[str] = []
        kept: List[str] = []
        for path in current:
            expected_generation = snapshot.get(path)
            if (
                expected_generation is not None
                and generations.get(path, LEGACY_GENERATION) == expected_generation
                and path in repaired
            ):
                removed.append(path)
            else:
                kept.append(path)
        _atomic_write(kept, generations, counter)
        return removed


def get_pending(index_dir: Optional[Path] = None) -> List[str]:
    """Read all pending paths. Returns empty list if file missing or corrupt.

    ``index_dir`` reads the queue of another data directory's ``.index``
    (callers that are handed a data directory instead of the configured one).
    """
    return _read_state(index_dir)[0]


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
        _atomic_write([], {}, _read_state()[2])


def has_pending() -> bool:
    """Check if there are any pending writes."""
    return len(get_pending()) > 0


def _atomic_write(paths: List[str], generations: Mapping[str, int], counter: int) -> None:
    """Atomically write the pending list, its generations and the counter to disk."""
    pfile = _pending_file()
    kept_generations = {path: generations[path] for path in paths if path in generations}
    payload = json.dumps(
        {"pending": paths, "generations": kept_generations, "counter": counter},
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
