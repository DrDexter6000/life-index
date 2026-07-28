"""Read-only recursive source-directory scan for photo adapters.

The scan is strictly read-only and defensive:

- it never follows symlinks, Windows junctions or other reparse points;
- it skips any entry that resolves outside the source root (root escape);
- it detects directory cycles via a visited-real-dir set;
- it yields deterministic, sorted (rel_path) output.

Only ``scan_photo_directory`` should consume this. The helpers here are
private to the ingest adapter package.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Iterator

# Windows FILE_ATTRIBUTE_REPARSE_POINT
_REPARSE = 0x400


def is_link_or_reparse(path: Path) -> bool:
    """True for symlinks, junctions and other reparse points (never follows)."""
    try:
        st = os.lstat(path)
    except OSError:
        # Unreadable entry — be conservative and let the caller skip it.
        return True
    if stat.S_ISLNK(st.st_mode):
        return True
    if os.name == "nt":
        fa = getattr(st, "st_file_attributes", 0) or 0
        if fa & _REPARSE:
            return True
    return False


def iter_source_files(root: Path) -> Iterator[tuple[Path, str]]:
    """Yield ``(absolute_path, rel_path_posix)`` for every regular file under *root*.

    Read-only recursive walk that skips symlink/junction/reparse entries,
    root-escape targets and directory cycles. Output is sorted by lowercased
    relative path for determinism.
    """
    root_resolved = root.resolve()
    visited: set[str] = set()
    found: list[tuple[Path, str]] = []
    stack: list[tuple[Path, Path]] = [(root, Path(""))]

    while stack:
        current, rel_base = stack.pop()
        try:
            real = current.resolve()
        except OSError:
            continue
        key = (str(real)).lower() if os.name == "nt" else str(real)
        if key in visited:
            continue
        visited.add(key)
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for entry in entries:
            if is_link_or_reparse(entry):
                continue
            child_rel = rel_base / entry.name
            try:
                # is_dir()/is_file() default to following symlinks, but every
                # symlink/junction/reparse entry was already skipped above, so
                # the remaining entries are real dirs/files and default
                # behaviour is correct and safe here.
                if entry.is_dir():
                    try:
                        entry.resolve().relative_to(root_resolved)
                    except ValueError:
                        continue  # root escape
                    stack.append((entry, child_rel))
                elif entry.is_file():
                    try:
                        entry.resolve().relative_to(root_resolved)
                    except ValueError:
                        continue  # root escape
                    found.append((entry, child_rel.as_posix()))
            except OSError:
                continue

    found.sort(key=lambda item: item[1].lower())
    for item in found:
        yield item
