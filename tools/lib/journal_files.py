"""Canonical Life Index journal file enumeration helpers."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

JOURNAL_FILENAME_RE = re.compile(r"^life-index_\d{4}-\d{2}-\d{2}_\d+\.md$")


def is_journal_file(path: Path) -> bool:
    """Return whether path name matches the canonical journal filename contract."""
    return path.is_file() and JOURNAL_FILENAME_RE.match(path.name) is not None


def iter_journal_files(journals_dir: Path) -> Iterator[Path]:
    """Yield canonical journal files under a Journals directory in stable order."""
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return
    for path in sorted(journals_dir.rglob("life-index_*.md")):
        if is_journal_file(path):
            yield path


def count_journal_files(journals_dir: Path) -> int:
    """Count canonical journal files under a Journals directory."""
    return sum(1 for _path in iter_journal_files(journals_dir))
