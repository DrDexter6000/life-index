"""Canonical Life Index journal file enumeration and kind classification."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

JOURNAL_FILENAME_RE = re.compile(r"^life-index_(\d{4}-\d{2}-\d{2})_\d+\.md$")

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


def fragment_date_from_filename(path: Path) -> str | None:
    """Return the ``YYYY-MM-DD`` date carried by a fragment filename, else None.

    Uses the one canonical filename rule (``JOURNAL_FILENAME_RE``) so callers
    that need a fallback date for an unparsable fragment never add a second
    filename regex.
    """
    match = JOURNAL_FILENAME_RE.match(Path(path).name)
    return match.group(1) if match else None


def is_live_fragment_path(path: Path, journals_dir: Path) -> bool:
    """Return whether one path is a live fragment of this journals tree.

    The single admission rule for a derived store that keeps per-fragment
    rows (FTS index, metadata cache): the path must live under ``journals_dir``,
    no component of its relative path may be a dot-directory (for example
    ``.revisions/``), and the filename must classify as a fragment.

    Path-only: never opens or stats the file, so callers can use it before
    writing to a derived store without touching the journals tree.
    """
    try:
        relative = Path(path).relative_to(Path(journals_dir))
    except ValueError:
        return False
    if not relative.parts:
        return False
    if any(part.startswith(".") for part in relative.parts[:-1]):
        return False
    return classify_journal_path(path) is JournalFileKind.FRAGMENT


@dataclass(frozen=True, slots=True)
class JournalFileStat:
    """Path plus the stat facts the metadata cache stores and compares.

    ``mtime`` is the same float ``Path.stat().st_mtime`` returns for the file
    (both come from ``os.stat_result.st_mtime``), so cache signatures stay
    exactly comparable with rows written by ``get_file_signature``.
    """

    path: Path
    mtime: float
    size: int


def _iter_live_markdown_entries(root: Path) -> Iterator[os.DirEntry[str]]:
    """Yield live ``.md`` directory entries under root (dot-directories skipped).

    Entries are yielded while their directory handle is still open, so callers
    can take ``entry.stat()`` from the same walk without re-opening the file.
    """
    root = Path(root)
    if not root.is_dir():
        return
    pending = [str(root)]
    while pending:
        current = pending.pop()
        try:
            with os.scandir(current) as entries:
                found: list[os.DirEntry[str]] = []
                for entry in entries:
                    if entry.is_dir():
                        if not entry.name.startswith("."):
                            pending.append(entry.path)
                    elif entry.name.endswith(".md") and entry.is_file():
                        found.append(entry)
                yield from found
        except OSError:
            continue


def _iter_live_markdown(root: Path) -> Iterator[Path]:
    """Yield .md files under root without descending into dot-directories.

    Files inside a directory whose name starts with a dot (for example
    ``.revisions/``) are never live journal-tree files of any kind.
    """
    for entry in _iter_live_markdown_entries(root):
        yield Path(entry.path)


def scan_journal_files(journals_dir: Path) -> list[JournalFileStat]:
    """Walk the Journals tree once and return stat facts for live fragments.

    Uses the same kind rule and dot-directory rule as ``iter_journal_files``
    (fragments only), in the same stable path order. The stat facts come from
    ``DirEntry.stat()``: on Windows that costs no extra system call per file;
    elsewhere it is one ``stat``. ``mtime`` compares equal to
    ``Path.stat().st_mtime`` for the same file on the same platform.
    """
    stats: list[JournalFileStat] = []
    for entry in _iter_live_markdown_entries(journals_dir):
        path = Path(entry.path)
        if classify_journal_path(path) is not JournalFileKind.FRAGMENT:
            continue
        try:
            info = entry.stat()
        except OSError:
            continue
        stats.append(JournalFileStat(path=path, mtime=info.st_mtime, size=info.st_size))
    stats.sort(key=lambda item: item.path)
    return stats


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


# The one display-label rule (docs/ARCHITECTURE.md, *Entry display label*).
_LABEL_TERMINATORS = "。！？!?"
_LABEL_MAX_CHARS = 30
_LABEL_STRUCTURE_ONLY = "#-=*_>`~ \t"


def display_label(title: str, body: str, path: Path) -> str:
    """Return the one display label for a journal entry.

    Deterministic and pure (no I/O). The rule, in order:

    1. ``title`` stripped, when non-empty: that text, unchanged.
    2. Otherwise the first line of ``body`` that carries text (a blank line,
       and a line made only of Markdown structure such as ``---``, ``***`` or
       ``##``, do not), with leading ``#`` characters and surrounding
       whitespace removed, cut at the first of ``。！？!?`` that follows some
       text (the terminator is kept) or at 30 characters, whichever comes
       first; when the cut was made by the length limit and text remains on
       that line, ``…`` is appended.
    3. Otherwise the file name without its extension. This is also the label
       when the first non-blank line of ``body`` is a ``---`` fence: that body
       is a frontmatter block that could not be read, kept as raw text, and
       its first lines are YAML, not what the user said.

    The label is a presentation aid only: it never replaces ``title``, which
    stays exactly what the file says (empty when there is none).
    """
    title_text = title.strip()
    if title_text:
        return title_text

    opening = True
    for line in body.splitlines():
        stripped = line.strip().lstrip("﻿")
        if not stripped:
            continue
        if opening and stripped == "---":
            break
        opening = False
        text = stripped.lstrip("#").strip()
        if not text.strip(_LABEL_STRUCTURE_ONLY):
            continue
        cut = None
        has_text = False
        for index, char in enumerate(text):
            if char not in _LABEL_TERMINATORS:
                has_text = True
            elif has_text:
                # A terminator ends the label only after some text: a line
                # that opens with one (``![image](a.jpg)``) is not cut there.
                cut = index + 1
                break
        if cut is not None and cut <= _LABEL_MAX_CHARS:
            return text[:cut]
        if len(text) > _LABEL_MAX_CHARS:
            return text[:_LABEL_MAX_CHARS] + "…"
        return text

    return Path(path).stem
