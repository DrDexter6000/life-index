"""Canonical Life Index journal file enumeration and kind classification."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator
from enum import StrEnum
from pathlib import Path

JOURNAL_FILENAME_RE = re.compile(r"^life-index_\d{4}-\d{2}-\d{2}_\d+\.md$")

DIGEST_FILENAME_PREFIX = "digest_"
DERIVED_INDEX_FILENAME_PREFIXES = ("index_", "monthly_", "yearly_")


class JournalFileKind(StrEnum):
    """Closed kind enumeration for files under a Journals directory."""

    FRAGMENT = "fragment"
    DIGEST = "digest"
    DERIVED_INDEX = "derived_index"
    UNKNOWN = "unknown"


def classify_journal_path(path: Path) -> JournalFileKind:
    """Classify a path under Journals/ from the filename alone.

    Pure path classification: never opens the file and never touches the
    filesystem. Rules, in order:

    - ``life-index_YYYY-MM-DD_<digits>.md`` → fragment (the user's own words)
    - ``digest_*.md`` → digest (Host-Agent-authored narrative; not implemented yet)
    - ``index_`` / ``monthly_`` / ``yearly_`` prefixes → derived index
      (same rule backup uses for rebuildable journal artifacts)
    - anything else → unknown
    """
    name = Path(path).name
    if JOURNAL_FILENAME_RE.match(name):
        return JournalFileKind.FRAGMENT
    if name.startswith(DIGEST_FILENAME_PREFIX) and name.endswith(".md"):
        return JournalFileKind.DIGEST
    if name.startswith(DERIVED_INDEX_FILENAME_PREFIXES):
        return JournalFileKind.DERIVED_INDEX
    return JournalFileKind.UNKNOWN


def is_journal_file(path: Path) -> bool:
    """Return whether path name matches the canonical journal filename contract."""
    return path.is_file() and JOURNAL_FILENAME_RE.match(path.name) is not None


def _iter_live_markdown(root: Path) -> Iterator[Path]:
    """Yield .md files under root without descending into dot-directories.

    Files inside a directory whose name starts with a dot (for example
    ``.revisions/``) are never live journal-tree files of any kind.
    """
    root = Path(root)
    if not root.is_dir():
        return
    # os.scandir answers is_dir()/is_file() from the directory listing, so the
    # walk costs no extra stat call per file.
    pending = [str(root)]
    while pending:
        current = pending.pop()
        found: list[Path] = []
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_dir():
                        if not entry.name.startswith("."):
                            pending.append(entry.path)
                    elif entry.name.endswith(".md") and entry.is_file():
                        found.append(Path(entry.path))
        except OSError:
            continue
        yield from found


def _normalize_kinds(kinds: Iterable[JournalFileKind]) -> frozenset[JournalFileKind]:
    return frozenset(JournalFileKind(kind) for kind in kinds)


def iter_journal_files_of_kind(
    journals_dir: Path,
    kinds: Iterable[JournalFileKind] = (JournalFileKind.FRAGMENT,),
) -> Iterator[Path]:
    """Yield live files of the given kinds under a Journals directory.

    Default is fragments only; callers wanting another kind must ask for it
    by name. Order is stable (sorted by path).
    """
    wanted = _normalize_kinds(kinds)
    for path in sorted(_iter_live_markdown(journals_dir)):
        if classify_journal_path(path) in wanted:
            yield path


def iter_journal_files(journals_dir: Path) -> Iterator[Path]:
    """Yield canonical journal (fragment) files under a Journals directory in stable order."""
    yield from iter_journal_files_of_kind(journals_dir)


def iter_year_journal_files(
    year_dir: Path,
    kinds: Iterable[JournalFileKind] = (JournalFileKind.FRAGMENT,),
) -> Iterator[Path]:
    """Yield live files of the given kinds under one year directory, sorted."""
    yield from iter_journal_files_of_kind(year_dir, kinds)


def iter_month_journal_files(
    month_dir: Path,
    kinds: Iterable[JournalFileKind] = (JournalFileKind.FRAGMENT,),
) -> Iterator[Path]:
    """Yield live files of the given kinds under one month directory, sorted."""
    yield from iter_journal_files_of_kind(month_dir, kinds)


def has_journal_files(
    directory: Path,
    kinds: Iterable[JournalFileKind] = (JournalFileKind.FRAGMENT,),
) -> bool:
    """Return whether the directory tree holds at least one file of the given kinds."""
    for _path in iter_journal_files_of_kind(directory, kinds):
        return True
    return False


def count_journal_files(journals_dir: Path) -> int:
    """Count canonical journal files under a Journals directory."""
    return sum(1 for _path in iter_journal_files(journals_dir))
