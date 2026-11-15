"""Resolve durable entry ids from the entry files, in one read-only pass.

The files are the only authority for which entry carries which id: there is no
cache, no index and no lock. One pass walks the Journals tree, reads every
candidate file once and parses its frontmatter; the response for a matched
file is built from the bytes read in that pass, and the path is never
reopened. The walk is strict — unlike ``journal_files.iter_journal_files`` it
reports directory and file read errors instead of suppressing them, because a
missing answer must never be mistaken for a complete one.

The candidates are exactly the files ``get --path`` would serve (the shared
predicates of :mod:`tools.lib.journal_ref`: the canonical
``Journals/<dir>/<dir>/life-index_*.md`` shape, and the resolved-path-stays-
inside-the-data-directory check). A file that fails them — an entry nested
one directory deeper, a canonical-looking symlink that resolves outside the
data directory — is not a candidate: it is neither a hit nor an unread path.

Physically read-only: nothing here creates a directory, writes a file or takes
a lock.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .entry_id import is_valid_entry_id
from .frontmatter import parse_frontmatter
from .journal_ref import canonical_journal_parts, resolves_within_data_dir
from .path_contract import safe_relative_path

EntryIdOutcomeStatus = Literal["found", "ambiguous", "not_found", "incomplete"]


@dataclass(frozen=True)
class EntryIdHit:
    """One file that carries a requested id, as read during the pass."""

    path: Path
    rel_path: str
    # The decoded text of the bytes read in the pass. The response is built
    # from this value; reopening the file would be a second, racy read.
    content: str


@dataclass(frozen=True)
class EntryIdOutcome:
    """The outcome for one requested id.

    ``found``: exactly one file carries it (``hits`` holds that one file).
    ``ambiguous``: two or more files carry it (``rel_paths`` names every one).
    ``not_found``: no file carries it and the pass was complete.
    ``incomplete``: no file carries it and the pass was **not** complete —
    an unread candidate path could have been carrying it, so this is never
    reported as ``not_found``.
    """

    status: EntryIdOutcomeStatus
    hits: tuple[EntryIdHit, ...] = ()
    rel_paths: tuple[str, ...] = ()
    unread_paths: int = 0


@dataclass(frozen=True)
class EntryIdLookup:
    """The result of one pass: one outcome per requested id, plus pass facts."""

    outcomes: Mapping[str, EntryIdOutcome] = field(default_factory=dict)
    complete: bool = True
    unread_paths: int = 0


def _read_bytes(path: Path) -> bytes:
    """The one file-read seam of the pass (kept hookable for tests)."""
    return path.read_bytes()


def _decode_reader_text(raw: bytes) -> str:
    """Decode pass bytes exactly the way the public reader serves text.

    UTF-8, universal newlines: ``\\r\\n`` and a lone ``\\r`` both read as
    ``\\n``, so an id-lookup response carries the same text a ``--path``
    read of the same file returns.
    """
    return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def _walk_candidate_dirs(journals_dir: Path) -> Iterator[tuple[Path, bool]]:
    """Yield ``(month_dir, is_unread)`` for every live month directory.

    Candidates live exactly two directory levels under ``Journals/`` (the
    canonical ``Journals/<dir>/<dir>/life-index_*.md`` shape), so the walk
    goes ``Journals/`` -> its non-dot subdirectories -> their non-dot
    subdirectories and stops there: deeper directories cannot hold a
    candidate and are never walked. A directory that cannot be listed is
    yielded as unread (it counts as one unread path — the files it hides
    cannot be counted).
    """
    root = Path(journals_dir)
    if not root.is_dir():
        return
    try:
        with os.scandir(root) as entries:
            year_dirs = [
                Path(entry.path)
                for entry in entries
                if entry.is_dir() and not entry.name.startswith(".")
            ]
    except OSError:
        yield (root, True)
        return
    for year_dir in year_dirs:
        try:
            with os.scandir(year_dir) as entries:
                month_dirs = [
                    Path(entry.path)
                    for entry in entries
                    if entry.is_dir() and not entry.name.startswith(".")
                ]
        except OSError:
            yield (year_dir, True)
            continue
        for month_dir in month_dirs:
            yield (month_dir, False)


def _walk_live_entries(journals_dir: Path) -> Iterator[tuple[Path, bool]]:
    """Yield ``(path, is_unread)`` pairs for the lookup's candidate scope.

    Every ``.md`` file of every live month directory is yielded (the
    candidate predicate — canonical shape and resolved-inside — is applied by
    the caller before a file is read); a month directory that cannot be
    listed is yielded as one unread path. Dot-directories are skipped: files
    inside one are never live journal-tree files of any kind.
    """
    for month_dir, dir_unread in _walk_candidate_dirs(journals_dir):
        if dir_unread:
            yield (month_dir, True)
            continue
        try:
            with os.scandir(month_dir) as entries:
                files = [
                    Path(entry.path)
                    for entry in entries
                    if entry.name.endswith(".md") and entry.is_file()
                ]
        except OSError:
            yield (month_dir, True)
            continue
        for path in files:
            yield (path, False)


def _is_lookup_candidate(path: Path, *, journals_dir: Path, data_root: Path) -> bool:
    """Whether *path* is a file ``get --path`` would serve (shared predicates)."""
    try:
        relative_parts = path.relative_to(journals_dir).parts
    except ValueError:
        return False
    if not canonical_journal_parts(("Journals", *relative_parts)):
        return False
    return resolves_within_data_dir(path, data_root)


def resolve_entry_ids(
    ids: Iterable[str],
    *,
    journals_dir: Path,
    user_data_dir: Path,
) -> EntryIdLookup:
    """Resolve every requested id in a single pass over the candidate files.

    Every selector must already be a valid durable id
    (:func:`tools.lib.entry_id.is_valid_entry_id`); callers refuse other
    shapes before reaching this function. Duplicate selectors collapse into
    one outcome entry.
    """
    wanted = {value for value in ids if is_valid_entry_id(value)}
    matches: dict[str, list[EntryIdHit]] = {value: [] for value in wanted}
    unread_paths = 0
    for path, is_unread in _walk_live_entries(journals_dir):
        if is_unread:
            unread_paths += 1
            continue
        if not _is_lookup_candidate(path, journals_dir=journals_dir, data_root=user_data_dir):
            continue
        try:
            content = _decode_reader_text(_read_bytes(path))
        except (OSError, UnicodeDecodeError):
            unread_paths += 1
            continue
        metadata, _body = parse_frontmatter(content)
        stored_id = metadata.get("id")
        if is_valid_entry_id(stored_id) and stored_id in matches:
            matches[stored_id].append(
                EntryIdHit(
                    path=path,
                    rel_path=safe_relative_path(path, user_data_dir),
                    content=content,
                )
            )

    outcomes: dict[str, EntryIdOutcome] = {}
    for value in wanted:
        hits = matches[value]
        if len(hits) == 1:
            outcomes[value] = EntryIdOutcome(
                status="found", hits=tuple(hits), unread_paths=unread_paths
            )
        elif len(hits) > 1:
            outcomes[value] = EntryIdOutcome(
                status="ambiguous",
                hits=tuple(hits),
                rel_paths=tuple(hit.rel_path for hit in hits),
                unread_paths=unread_paths,
            )
        elif unread_paths:
            outcomes[value] = EntryIdOutcome(status="incomplete", unread_paths=unread_paths)
        else:
            outcomes[value] = EntryIdOutcome(status="not_found")
    return EntryIdLookup(
        outcomes=outcomes,
        complete=not unread_paths,
        unread_paths=unread_paths,
    )
