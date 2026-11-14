"""The one shared primitive for rewriting an existing journal file.

Every tool that rewrites an existing journal (``edit``, ``migrate``)
goes through this module: it splits the file's
bytes into the frontmatter block and the untouched suffix, renders a new
frontmatter block, and replaces the file atomically. The rule lives in
``docs/ARCHITECTURE.md`` (*Frontmatter 重写边界* / write-transaction text): a
tool that changes an existing journal changes exactly the bytes it was asked
to change — the suffix after the frontmatter block is never decoded and
re-encoded, and the journal is never truncated in place.
"""

from __future__ import annotations

import errno
import os
import stat
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .frontmatter import (
    _rewrite_form,
    _same_value,
    format_frontmatter,
    frontmatter_opens_block,
    is_frontmatter_delimiter_line,
    parse_frontmatter,
)

# Windows transient os.replace errors worth one bounded retry. WinError 5
# (ERROR_ACCESS_DENIED) and 32 (ERROR_SHARING_VIOLATION) can race a
# same-directory atomic replace on Windows and typically clear within
# milliseconds, so a tiny bounded retry absorbs them internally. Every other
# failure does not qualify and propagates unchanged. (Same pattern as
# ``tools/ingest/runner.py``.)
_WINDOWS_TRANSIENT_REPLACE_WINERRORS = (5, 32)
_REPLACE_MAX_ATTEMPTS = 3
# Backoff slept BETWEEN attempts, never after the final attempt.
_REPLACE_RETRY_BACKOFFS = (0.01, 0.05)


@dataclass(frozen=True)
class RawJournalSplit:
    """A journal file's bytes split at the frontmatter block boundary.

    ``frontmatter_block`` is the block exactly as stored: the opening
    delimiter line through the closing delimiter line *with* that line's line
    ending. ``suffix`` is every byte after it, untouched.
    """

    frontmatter_block: bytes
    suffix: bytes


def _line_is_delimiter(raw_line: bytes) -> bool:
    """The shared whole-line delimiter rule, applied to one raw line.

    The line is decoded and handed to :func:`is_frontmatter_delimiter_line`
    (the single rule the text parser also uses), so the byte split and the
    parser see the same boundary for the same file. A line that is not valid
    UTF-8 raises ``UnicodeDecodeError``; the caller then treats the file like
    any other non-UTF-8 journal (it cannot be rewritten without corrupting
    it).
    """
    return is_frontmatter_delimiter_line(raw_line.decode("utf-8"))


def split_journal_bytes(raw: bytes) -> RawJournalSplit | None:
    """Split journal file bytes into the frontmatter block and the suffix.

    The block opens only when the reader would read one (the one shared
    opening rule, :func:`frontmatter.frontmatter_opens_block`), and
    delimiters are recognised as whole lines via the one shared rule the
    text parser uses (:func:`is_frontmatter_delimiter_line`), so the file
    copes with LF, CRLF and mixed line endings, a field value containing
    ``---`` never splits the block, and this split always returns the
    boundary the parser sees — or ``None``, which means the file has no
    whole-line frontmatter block and the caller refuses to rewrite it. Only
    the block's own lines are decoded (to apply the rules); the suffix is
    never decoded or re-encoded.
    """
    lines = raw.split(b"\n")
    if not lines or not frontmatter_opens_block(lines[0].decode("utf-8")):
        return None
    # ``end`` walks just past each line's own "\n"; when the closing
    # delimiter is the last line without a trailing newline the +1 overshoots
    # and Python slicing clamps, leaving an empty suffix.
    end = len(lines[0]) + 1
    for line in lines[1:]:
        end += len(line) + 1
        if _line_is_delimiter(line):
            return RawJournalSplit(raw[:end], raw[end:])
    return None


def render_frontmatter_block(metadata: Mapping[str, Any]) -> bytes:
    """The newly formatted frontmatter block: UTF-8, LF, LF-terminated.

    The block is the only part a metadata rewrite may change; it is always
    written with LF line endings regardless of the file's original ones.
    """
    return (format_frontmatter(dict(metadata)) + "\n").encode("utf-8")


def normalize_lf(text: str) -> str:
    """Normalize CRLF and lone CR to LF: written journal bytes contain no CR.

    The one normalizer for everything this module writes on the body side
    (an edit's ``--replace-content`` / ``--append-content`` body region) and
    for ``write``'s newly created journals.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


class OutgoingJournalRefused(ValueError):
    """The outgoing bytes would not preserve what the rewrite promised.

    Raised by :func:`verify_outgoing_journal` before anything is written:
    no revision is saved, no temp exists, and the caller reports
    ``E0202`` / ``not_round_trippable`` (edit) or lists the file in
    ``failed_files`` with that reason (migrate).
    """


def verify_outgoing_journal(
    old_bytes: bytes,
    new_bytes: bytes,
    intended_metadata: Mapping[str, Any],
    *,
    metadata_only: bool,
    computed_body: str | None = None,
) -> None:
    """Read the outgoing file back with the public reader before committing.

    The last line of defence for every rewrite: whatever partial rules
    produced ``new_bytes``, the file that is about to replace the journal
    must itself satisfy the promise. Raises :class:`OutgoingJournalRefused`
    unless all hold:

    1. the new bytes split, and the block the split returns is exactly the
       block rendered from ``intended_metadata``;
    2. the reader's metadata for the new file equals, type-sensitively
       (``frontmatter._same_value`` against ``frontmatter._rewrite_form``),
       the intended mapping — same keys, same values, nothing extra;
    3. a metadata-only rewrite: the new suffix is byte-identical to the old
       suffix, and the reader's body for the new file equals the reader's
       body for the old file;
    4. a content edit: the reader's body for the new file equals the body
       the edit computed (after the reader's own stripping).
    """
    rendered_block = render_frontmatter_block(intended_metadata)
    new_split = split_journal_bytes(new_bytes)
    if new_split is None or new_split.frontmatter_block != rendered_block:
        raise OutgoingJournalRefused(
            "the rendered frontmatter block did not survive into the outgoing file"
        )
    new_metadata, new_body = parse_frontmatter(new_bytes.decode("utf-8"))
    if not _same_value(new_metadata, _rewrite_form(dict(intended_metadata))):
        raise OutgoingJournalRefused(
            "the outgoing file does not read back as the intended frontmatter"
        )
    _old_metadata, old_body = parse_frontmatter(old_bytes.decode("utf-8"))
    if metadata_only:
        old_split = split_journal_bytes(old_bytes)
        if old_split is None or new_split.suffix != old_split.suffix:
            raise OutgoingJournalRefused("a metadata-only rewrite would change the body bytes")
        if new_body != old_body:
            raise OutgoingJournalRefused(
                "a metadata-only rewrite would change the reader-visible body"
            )
    elif computed_body is None or new_body != computed_body.strip():
        raise OutgoingJournalRefused("the outgoing body is not the computed body")


def ensure_replaceable_journal(journal_path: Path) -> None:
    """Preconditions for replacing this journal: it can be replaced at all.

    One check, called by :func:`replace_journal_bytes` itself and by ``edit``
    **before** it saves a revision copy: the path must not be a symbolic link
    (a replace would silently swap the link for a regular file and leave the
    target's old bytes in place), and the current user must be able to write
    the file. Either failure raises :class:`PermissionError` before any temp
    exists, so nothing is left behind and the caller reports its normal
    write failure on both platforms.
    """
    journal_path = Path(journal_path)
    if journal_path.is_symlink():
        raise PermissionError(
            errno.EACCES,
            "the journal path is a symbolic link; refusing to replace the link,"
            " nothing was changed",
            str(journal_path),
        )
    if not os.access(journal_path, os.W_OK):
        raise PermissionError(
            errno.EACCES,
            "the journal is not writable by the current user; nothing was changed",
            str(journal_path),
        )


def replace_journal_bytes(journal_path: Path, new_bytes: bytes) -> None:
    """Atomically replace an existing journal file's bytes.

    The complete new bytes go to a uniquely named temp file in the same
    directory (exclusive create), the temp is given the **original file's
    mode** (not ``mkstemp``'s 0600 and not a guessed default), then flushed
    and fsynced, closed, and ``os.replace``d onto the journal. On Windows a
    destination another process holds open makes ``os.replace`` raise
    ``PermissionError`` (WinError 5 / 32); those are retried a bounded number
    of times with short pauses, then the last error propagates with the
    original file untouched and no temp left. After a successful replace the
    parent directory is fsynced where the platform supports it. The journal
    is never truncated in place; the temp file is removed on every failure
    path.

    Limits: the replace keeps the content and the mode; it does not preserve
    hard links, ACLs, extended attributes, or alternate data streams.

    A journal that cannot be replaced (:func:`ensure_replaceable_journal`:
    a symbolic link, or not writable by the current user) is refused with
    ``PermissionError`` before any temp file exists, so both platforms fail
    identically with nothing left behind.
    """
    journal_path = Path(journal_path)
    ensure_replaceable_journal(journal_path)
    original_mode = stat.S_IMODE(os.stat(journal_path).st_mode)
    fd, temp_name = tempfile.mkstemp(
        dir=str(journal_path.parent), prefix=f".{journal_path.name}.tmp-"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(new_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, original_mode)
        _atomic_replace(temp_path, journal_path)
    except BaseException:
        _unlink_temp(temp_path)
        raise
    _fsync_parent_dir(journal_path.parent)


def _is_windows_transient_replace_error(exc: BaseException) -> bool:
    """True only for the Windows transient share/access os.replace errors.

    Requires BOTH ``os.name == "nt"`` AND ``winerror`` in ``{5, 32}``. Any
    other OSError and any non-OSError is False, so those do not qualify for
    the bounded retry and propagate after a single attempt.
    """
    return (
        isinstance(exc, OSError)
        and os.name == "nt"
        and getattr(exc, "winerror", None) in _WINDOWS_TRANSIENT_REPLACE_WINERRORS
    )


def _atomic_replace(temp_path: Path, path: Path) -> None:
    """``os.replace`` with a bounded retry for Windows transient locks.

    On exhaustion the last ``OSError`` is re-raised as-is, so the caller's
    failure path runs against the unchanged failure semantics.
    """
    last_exc: OSError | None = None
    for attempt in range(_REPLACE_MAX_ATTEMPTS):
        try:
            os.replace(temp_path, path)
            return
        except OSError as exc:
            if not _is_windows_transient_replace_error(exc):
                raise
            last_exc = exc
            if attempt + 1 < _REPLACE_MAX_ATTEMPTS:
                time.sleep(_REPLACE_RETRY_BACKOFFS[attempt])
    assert last_exc is not None  # loop ran >= 1 iteration; invariant for type checkers
    raise last_exc


def _unlink_temp(temp_path: Path) -> None:
    """Remove a temp file on a failure path; never mask the original error.

    The temp may carry the original's read-only mode (copied on purpose), so
    the write bit is restored first; otherwise a read-only original would
    leave the temp behind on every failure.
    """
    try:
        os.chmod(temp_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    try:
        temp_path.unlink(missing_ok=True)
    except OSError:
        pass


def _fsync_parent_dir(parent: Path) -> None:
    """fsync the parent directory where the platform supports it."""
    if os.name != "posix":
        return
    try:
        fd = os.open(parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
