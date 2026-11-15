#!/usr/bin/env python3
"""Life Index - Fragment Tool - Notes (`fragment note`).

`fragment note` records a correction the user confirmed about a fragment as a
**note** stored next to the fragment's words, never inside them: the original
text stays byte-for-byte, a reader gets the original text and the notes as
separate things, and a search for the corrected word finds the fragment. The
stored form (the one ``notes_boundary`` frontmatter key and the notes region
at the end of the file) is owned by ``docs/ARCHITECTURE.md`` and implemented
only in ``tools/lib/fragment_notes.py``; the write goes through
``journal_rewrite.replace_journal_bytes`` after
``journal_rewrite.verify_outgoing_note_append`` reads the outgoing file back.

All rules run inside the journals lock against one snapshot of each file: the
target, every ``based_on`` basis, the replay comparison and the replace. A
note never edits a byte of the fragment's own words, so no revision copy is
saved.
"""

import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..lib.config import FILE_LOCK_TIMEOUT_DEFAULT, resolve_user_data_dir
from ..lib.errors import ErrorCode, create_error_response
from ..lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path
from ..lib.fragment_notes import (
    NOTE_CLOSE_MARKER_PREFIX,
    NOTE_OPEN_MARKER_PREFIX,
    FragmentNote,
    boundary_of,
    generate_boundary,
    insert_boundary_line,
    region_append_separator,
    render_note_block,
    split_fragment_notes,
)
from ..lib.frontmatter import frontmatter_rewrite_blocker, parse_frontmatter
from ..lib.journal_files import is_live_fragment_path
from ..lib.journal_rewrite import (
    OutgoingJournalRefused,
    normalize_lf,
    replace_journal_bytes,
    split_journal_bytes,
    verify_outgoing_note_append,
)
from ..lib.logger import get_logger
from ..lib.paths import get_journals_dir
from ..lib.timing import Timer
from ..lib.workflow_signals import SideEffectExecutionStatus, derive_write_statuses
from ..write_journal.core import _record_side_effect
from .core import _after_publish, _parse_offset_datetime, _rel_path, _validate_nonempty_string

logger = get_logger(__name__)

_ALLOWED_TOP_LEVEL = frozenset({"path", "expect_id", "text", "based_on", "by", "noted_at"})
_BASIS_KEYS = frozenset({"path", "id", "quote"})

_FRAGMENT_NAME_RE = re.compile(r"^life-index_\d{4}-\d{2}-\d{2}_\d+\.md$")

_GENERATED_INDEXES_REASON = "a fragment write does not regenerate the monthly/yearly indexes"
_GENERATED_INDEXES_RECOVERY = "life-index generate-index --rebuild"


class _InvalidNote(ValueError):
    """One invalid input field; message names the field."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


def _shared_validator(func: Callable[[Any, str], Any], value: Any, field: str) -> Any:
    """Run one of `fragment add`'s shared validators as a note validator.

    The shared validators raise ``add``'s ``_InvalidFragment``; this wrapper
    carries the same message and details out as this command's own
    ``_InvalidNote`` so the note envelope reports them uniformly.
    """
    from .core import _InvalidFragment

    try:
        return func(value, field)
    except _InvalidFragment as exc:
        raise _InvalidNote(str(exc), dict(exc.details or {})) from exc


class _NoteRefused(RuntimeError):
    """A checked refusal (mismatch / malformed region / rewrite blocker).

    ``response`` is the finished error envelope; nothing was written.
    """

    def __init__(self, response: Dict[str, Any]):
        super().__init__(str(response.get("error", {}).get("message", "refused")))
        self.response = response


# ---------------------------------------------------------------------------
# Input validation (before the lock; shapes only, no file reads)
# ---------------------------------------------------------------------------


def _validate_input(data: Any) -> Dict[str, Any]:
    """Validate the note input object and normalize what will be stored."""
    if not isinstance(data, dict):
        raise _InvalidNote("fragment note input must be a JSON object")
    unknown = sorted(str(key) for key in data if str(key) not in _ALLOWED_TOP_LEVEL)
    if unknown:
        raise _InvalidNote(f"unknown input key(s): {', '.join(unknown)}", {"unknown_keys": unknown})
    if "path" not in data:
        raise _InvalidNote("path is required", {"field": "path"})
    normalized: Dict[str, Any] = {"path": _normalize_rel_path(data["path"], "path")}
    expect_id = data.get("expect_id")
    if expect_id is not None:
        expect_id = _shared_validator(_validate_nonempty_string, expect_id, "expect_id")
    normalized["expect_id"] = expect_id
    normalized["text"] = _note_text(data.get("text"))
    normalized["based_on"] = _validate_based_on(data.get("based_on"))
    by = data.get("by")
    if not isinstance(by, str):
        raise _InvalidNote("by must be a string", {"field": "by"})
    by = by.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not by:
        raise _InvalidNote(
            "by must be one non-blank line of text; blank strings are rejected,"
            " not treated as absent",
            {"field": "by"},
        )
    if "\n" in by:
        raise _InvalidNote("by must be one line of text", {"field": "by"})
    normalized["by"] = by
    if data.get("noted_at") is not None:
        normalized["noted_at"] = _shared_validator(
            _parse_offset_datetime, data["noted_at"], "noted_at"
        ).isoformat(timespec="seconds")
    else:
        # Default: now, machine local zone, with offset, seconds precision.
        normalized["noted_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    return normalized


def _note_text(value: Any) -> str:
    """The correction text, normalized like fragment text (LF, boundaries)."""
    if not isinstance(value, str):
        raise _InvalidNote("text must be a string", {"field": "text"})
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise _InvalidNote(
            "text is empty after trimming; a note stores the user-confirmed correction",
            {"field": "text"},
        )
    # No line of the note text may start with a note marker prefix, whatever
    # follows: such a line could forge (or damage the reading of) the stored
    # region. The same characters mid-line are ordinary words.
    for line in text.split("\n"):
        if line.startswith(NOTE_OPEN_MARKER_PREFIX) or line.startswith(NOTE_CLOSE_MARKER_PREFIX):
            raise _InvalidNote(
                "text must not contain a line that starts with a note marker"
                " prefix (<!-- life-index:note / <!-- /life-index:note)",
                {"field": "text"},
            )
    return text


def _validate_based_on(value: Any) -> List[Dict[str, Any]]:
    """Each basis: ``{path, id?, quote}``, unknown keys rejected."""
    if not isinstance(value, list) or not value:
        raise _InvalidNote("based_on must be a non-empty list of objects", {"field": "based_on"})
    entries: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        field = f"based_on[{index}]"
        if not isinstance(item, dict):
            raise _InvalidNote(f"{field} must be a JSON object", {"field": field})
        unknown = sorted(str(key) for key in item if str(key) not in _BASIS_KEYS)
        if unknown:
            raise _InvalidNote(
                f"unknown {field} key(s): {', '.join(unknown)}",
                {"field": field, "unknown_keys": unknown},
            )
        if "quote" not in item:
            raise _InvalidNote(f"{field}.quote is required", {"field": f"{field}.quote"})
        quote = item["quote"]
        if not isinstance(quote, str):
            raise _InvalidNote(f"{field}.quote must be a string", {"field": f"{field}.quote"})
        quote = normalize_lf(quote)
        if not quote:
            raise _InvalidNote(f"{field}.quote must be non-empty", {"field": f"{field}.quote"})
        entry: Dict[str, Any] = {"path": _normalize_rel_path(item.get("path"), f"{field}.path")}
        if item.get("id") is not None:
            entry["id"] = _shared_validator(_validate_nonempty_string, item["id"], f"{field}.id")
        else:
            entry["id"] = None
        entry["quote"] = quote
        entries.append(entry)
    return entries


def _normalize_rel_path(value: Any, field: str) -> str:
    """A fragment ``rel_path``: relative, inside the tree, fragment-named."""
    if not isinstance(value, str):
        raise _InvalidNote(f"{field} must be a string", {"field": field})
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        raise _InvalidNote(f"{field} must not be blank", {"field": field})
    if "\x00" in normalized:
        raise _InvalidNote(f"{field} contains a NUL byte", {"field": field})
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise _InvalidNote(
            f"{field} must be relative to the Life Index data directory", {"field": field}
        )
    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise _InvalidNote(
            f"{field} must stay inside the Life Index data directory", {"field": field}
        )
    if len(parts) != 4 or parts[0] != "Journals" or not _FRAGMENT_NAME_RE.match(parts[-1]):
        raise _InvalidNote(
            f"{field} must be the rel_path of a fragment file"
            " (Journals/YYYY/MM/life-index_YYYY-MM-DD_NNN.md)",
            {"field": field, "value": normalized},
        )
    return "/".join(parts)


# ---------------------------------------------------------------------------
# In-lock helpers (one snapshot per file)
# ---------------------------------------------------------------------------


def _resolve_fragment_file(rel_path: str, field: str) -> Path:
    """The absolute path of one fragment named by the caller.

    The path must be a live fragment file inside the data directory (the
    existing admission predicate) and not a symbolic link; no revisions, no
    digests, nothing outside the tree.
    """
    absolute = resolve_user_data_dir().joinpath(*rel_path.split("/"))
    if absolute.is_symlink():
        raise _InvalidNote(
            f"{field} is a symbolic link; fragments are corrected in place,"
            " never through a link",
            {"field": field, "path": rel_path},
        )
    if not is_live_fragment_path(absolute, get_journals_dir()):
        raise _InvalidNote(
            f"{field} is not a live fragment file inside the data directory",
            {"field": field, "path": rel_path},
        )
    return absolute


def _read_snapshot(path: Path, rel_path: str, field: str) -> Tuple[bytes, Dict[str, Any], str]:
    """One file's bytes and the public reader's (metadata, body) for them."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise _NoteRefused(_not_found_response(rel_path, field)) from exc
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _InvalidNote(
            f"{field} is not valid UTF-8", {"field": field, "path": rel_path}
        ) from exc
    metadata, body = parse_frontmatter(content)
    return raw, metadata, body


def _mismatch_response(message: str, details: Dict[str, Any]) -> Dict[str, Any]:
    recovery = (
        "Read the named file with `journal get`, fix the mismatched field,"
        " and retry; nothing was written"
    )
    if str(details.get("reason", "")).startswith("expect_id"):
        # The three expect_id_* reasons get one clause, the same guidance the
        # playbook gives: the id to send is the stored fragment id
        # (``metadata.id`` in `journal get` output), never the top-level
        # path id.
        recovery = (
            "expect_id (and based_on[].id) is the fragment id that"
            " `fragment add` returned — `metadata.id` in `journal get`"
            " output, never the top-level path id; copy it from metadata.id"
            " and retry; nothing was written"
        )
    return create_error_response(ErrorCode.FRAGMENT_NOTE_MISMATCH, message, details, recovery)


def _not_found_response(rel_path: str, field: str) -> Dict[str, Any]:
    return create_error_response(
        ErrorCode.JOURNAL_NOT_FOUND,
        f"{field} names a fragment file that does not exist: {rel_path}",
        {"field": field, "path": rel_path},
        "Check the rel_path with `journal list --recent` and retry",
    )


def _malformed_response(journal_path: Path) -> Dict[str, Any]:
    return create_error_response(
        ErrorCode.FRAGMENT_NOTES_MALFORMED,
        "the fragment's notes region is malformed; a note is never appended"
        " after a damaged region",
        {"path": str(journal_path)},
        "Leave the file unchanged and report the file and the damaged notes"
        " region to the user; do not retry or repair it automatically",
    )


def _blocker_response(journal_path: Path, reason: str) -> Dict[str, Any]:
    """The E0202 envelope `edit` gives for the same rewrite blocker."""
    return create_error_response(
        ErrorCode.FRONTMATTER_INVALID,
        f"Frontmatter cannot be rewritten without loss: {reason}",
        {"path": str(journal_path), "reason": reason},
        "Leave the file unchanged and report the file and reason to the user;"
        " do not retry or repair it automatically",
    )


def _basis_records(
    based_on: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, Optional[str], str]]]:
    """Validate every basis against its locked snapshot; build stored records.

    Returns the stored records (path, the id actually read, quote, sha256 of
    the basis file's original text) and the replay-comparison keys.
    """
    records: List[Dict[str, Any]] = []
    keys: List[Tuple[str, Optional[str], str]] = []
    for index, basis in enumerate(based_on):
        field = f"based_on[{index}]"
        rel_path = basis["path"]
        path = _resolve_fragment_file(rel_path, field)
        _raw, metadata, body = _read_snapshot(path, rel_path, field)
        original = split_fragment_notes(metadata, body).original_text
        actual_id = metadata.get("id")
        actual_id = actual_id if isinstance(actual_id, str) and actual_id.strip() else None
        given_id = basis["id"]
        if given_id is not None and given_id != actual_id:
            raise _NoteRefused(
                _mismatch_response(
                    f"{field}.id does not match the id stored in {rel_path}",
                    {"field": f"{field}.id", "path": rel_path, "reason": "basis_id_mismatch"},
                )
            )
        quote = basis["quote"]
        if quote not in normalize_lf(original):
            raise _NoteRefused(
                _mismatch_response(
                    f"{field}.quote does not occur verbatim in the original text of" f" {rel_path}",
                    {"field": f"{field}.quote", "path": rel_path, "reason": "quote_not_found"},
                )
            )
        records.append(
            {
                "path": rel_path,
                "id": actual_id,
                "quote": quote,
                # The hash of what `journal get` returns as `content`: the
                # reader serves LF text, so a CRLF basis hashes its
                # LF-normalized original.
                "sha256": hashlib.sha256(normalize_lf(original).encode("utf-8")).hexdigest(),
            }
        )
        keys.append((rel_path, actual_id, quote))
    return records, keys


def _stored_note_matches(
    stored: FragmentNote, text: str, by: str, keys: List[Tuple[str, Optional[str], str]]
) -> bool:
    """Replay rule: same text, same by, same basis list by (path, id, quote)."""
    if stored.text != text or stored.by != by:
        return False
    stored_keys = [
        (
            str(item.get("path")),
            item.get("id") if isinstance(item.get("id"), str) else None,
            str(item.get("quote")),
        )
        for item in stored.based_on
    ]
    return stored_keys == keys


def _note_dedup_envelope(
    result: Dict[str, Any],
    stored: FragmentNote,
    journal_path: Path,
    timer: Timer,
) -> Dict[str, Any]:
    """Success envelope for a replay: nothing written, rows refreshed again."""
    result["side_effects"].append(
        {
            "name": "journal_commit",
            "phase": "commit",
            "status": SideEffectExecutionStatus.SKIPPED,
            "blocking": False,
            "reason": "already stored",
        }
    )
    _after_publish(result, journal_path, timer)
    fts_failed = any(
        record["name"] == "fts_row" and record["status"] == SideEffectExecutionStatus.FAILED
        for record in result["side_effects"]
    )
    degraded = any(
        record["status"] in {SideEffectExecutionStatus.FAILED, SideEffectExecutionStatus.QUEUED}
        for record in result["side_effects"]
    )
    result.update(
        {
            "success": True,
            "note": stored.to_dict(),
            "deduplicated": True,
            # journal_commit is "skipped" by design, so derive_write_statuses
            # cannot express this outcome; these statuses describe this
            # invocation: nothing was written, the derived rows were refreshed.
            "write_outcome": "success_degraded" if degraded else "success",
            "index_status": "degraded" if fts_failed else "complete",
            "side_effects_status": "degraded" if degraded else "complete",
        }
    )
    timer.stop()
    result["metrics"] = timer.to_dict()
    return result


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def add_note_to_fragment(data: Any) -> Dict[str, Any]:
    """Record one user-confirmed correction as a note on a fragment."""
    timer = Timer().start()
    result: Dict[str, Any] = {
        "success": False,
        "note": None,
        "journal_path": None,
        "rel_path": None,
        "deduplicated": False,
        "notes_count": 0,
        "side_effects": [],
        "write_outcome": "failed",
        "index_status": "not_started",
        "side_effects_status": "not_started",
        "error": None,
        "metrics": {},
    }
    try:
        normalized = _validate_input(data)
        rel_path = normalized["path"]
        text = normalized["text"]
        by = normalized["by"]
        noted_at = normalized["noted_at"]

        with FileLock(get_journals_lock_path(), timeout=FILE_LOCK_TIMEOUT_DEFAULT):
            target = _resolve_fragment_file(rel_path, "path")
            raw, metadata, body = _read_snapshot(target, rel_path, "path")
            result["journal_path"] = str(target)
            result["rel_path"] = _rel_path(target)

            split = split_journal_bytes(raw)
            if split is None:
                raise _NoteRefused(_blocker_response(target, "no_frontmatter_block"))
            content = raw.decode("utf-8")
            blocker = frontmatter_rewrite_blocker(content)
            if blocker is not None:
                raise _NoteRefused(_blocker_response(target, blocker))

            target_id = metadata.get("id")
            target_id = target_id if isinstance(target_id, str) and target_id.strip() else None
            expect_id = normalized["expect_id"]
            if target_id is not None and expect_id is None:
                raise _NoteRefused(
                    _mismatch_response(
                        "the target fragment has an id; expect_id is required and" " must equal it",
                        {"field": "expect_id", "path": rel_path, "reason": "expect_id_required"},
                    )
                )
            if target_id is None and expect_id is not None:
                raise _NoteRefused(
                    _mismatch_response(
                        "the target fragment has no id; expect_id must be omitted",
                        {"field": "expect_id", "path": rel_path, "reason": "expect_id_unexpected"},
                    )
                )
            if target_id is not None and expect_id != target_id:
                raise _NoteRefused(
                    _mismatch_response(
                        "expect_id does not match the target fragment's id",
                        {"field": "expect_id", "path": rel_path, "reason": "expect_id_mismatch"},
                    )
                )

            boundary = boundary_of(metadata)
            notes_split = split_fragment_notes(metadata, body)
            if notes_split.malformed:
                raise _NoteRefused(_malformed_response(target))
            if boundary is not None and boundary in text:
                raise _InvalidNote(
                    "text must not contain the target fragment's notes_boundary value",
                    {"field": "text"},
                )

            records, basis_keys = _basis_records(normalized["based_on"])

            for stored in notes_split.notes:
                if _stored_note_matches(stored, text, by, basis_keys):
                    result["notes_count"] = len(notes_split.notes)
                    return _note_dedup_envelope(result, stored, target, timer)

            note_fields: Dict[str, Any] = {
                "id": uuid.uuid4().hex,
                "noted_at": noted_at,
                "by": by,
                "based_on": records,
            }
            if boundary is None:
                # The boundary must not occur in the file's bytes, nor in the
                # note text about to be stored (the only multi-line field: a
                # forged marker line inside it must stay impossible).
                boundary = generate_boundary(raw, text.encode("utf-8"))
                block_bytes = render_note_block(boundary, note_fields, text)
                new_block = insert_boundary_line(split.frontmatter_block, boundary)
                new_bytes = new_block + split.suffix + region_append_separator(raw) + block_bytes
            else:
                block_bytes = render_note_block(boundary, note_fields, text)
                new_bytes = raw + region_append_separator(raw) + block_bytes

            expected_note = FragmentNote(
                id=note_fields["id"],
                noted_at=noted_at,
                by=by,
                text=text,
                based_on=tuple(dict(item) for item in records),
            )
            try:
                verify_outgoing_note_append(raw, new_bytes, expected_note)
            except OutgoingJournalRefused as exc:
                logger.warning("note append refused by the outgoing check: %s", exc)
                raise _NoteRefused(_blocker_response(target, "not_round_trippable")) from exc

            replace_journal_bytes(target, new_bytes)
            _record_side_effect(
                result,
                name="journal_commit",
                phase="commit",
                status=SideEffectExecutionStatus.COMPLETE,
                blocking=True,
            )
            _after_publish(result, target, timer)
            result.update(
                {
                    "success": True,
                    "note": expected_note.to_dict(),
                    "notes_count": len(notes_split.notes) + 1,
                }
            )
            result.update(derive_write_statuses(result["side_effects"], needs_confirmation=False))

    except _InvalidNote as exc:
        error = create_error_response(
            ErrorCode.INVALID_INPUT,
            str(exc),
            exc.details,
            "fix the named field and retry; nothing was written",
        )
        error["side_effects"] = result["side_effects"]
        return error
    except _NoteRefused as exc:
        error = exc.response
        error["side_effects"] = result["side_effects"]
        return error
    except LockTimeoutError as exc:
        logger.error(f"fragment note lock timeout: {exc}")
        return create_error_response(
            ErrorCode.LOCK_TIMEOUT,
            f"无法获取写入锁，请稍后重试：{exc}",
            {
                "lock_path": str(get_journals_lock_path()),
                "timeout": FILE_LOCK_TIMEOUT_DEFAULT,
            },
            "等待几秒后重试，或检查是否有其他进程正在写入",
        )
    except (OSError, IOError, RuntimeError) as exc:
        logger.error(f"fragment note failed: {exc}", exc_info=True)
        error = create_error_response(
            ErrorCode.WRITE_FAILED,
            str(exc),
            {"path": result.get("journal_path")},
            "resolve the filesystem error, then retry fragment note;"
            " the fragment's own words were not modified",
        )
        error["side_effects"] = result["side_effects"]
        return error

    try:
        timer.stop()
        result["metrics"] = timer.to_dict()
    except Exception as exc:  # noqa: BLE001 - a committed note never fails
        if not result.get("success"):
            raise
        result["metrics"] = {"error": str(exc)}
    return result
