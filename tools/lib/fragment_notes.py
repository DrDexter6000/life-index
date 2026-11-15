"""The one grammar of a fragment's notes region.

`docs/ARCHITECTURE.md` (*Fragment notes stored form*) owns the stored form;
this module is its only implementation. A file with notes carries one
frontmatter key ``notes_boundary`` (32 lowercase hex characters, generated
when the first note is added and checked not to occur anywhere in the file's
bytes) and a notes region at the end of the file::

    <!-- life-index:note <boundary> {"id":"..","noted_at":"..","by":"..","based_on":[..]} -->
    <note text, LF, one or more lines>
    <!-- /life-index:note <boundary> -->

Everything before the region is the user's original text: because the
boundary was generated after the original was written and is checked not to
occur in it, the original can contain any text at all — including text that
looks exactly like a note block — and is never refused or misread for it.
A file whose frontmatter has no valid ``notes_boundary`` has no notes: its
whole body is original text, whatever it contains.

Every reader gets the original text through :func:`split_fragment_notes`;
every writer renders the region through :func:`render_note_block`. No other
module knows the marker lines, the header JSON shape or the block layout.

The header escapes every ``<`` and ``>`` inside its JSON as the JSON unicode
escape (backslash + ``u003c`` / ``u003e``), so a header can never contain
``-->``. Those escape strings are built from character codes, not written as
source literals: an editor must never be able to turn the escape into the
character by saving the file.
"""

from __future__ import annotations

import json
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# The JSON unicode escapes for < and >, built from character codes (see the
# module docstring: the source file never carries a literal backslash escape).
_BACKSLASH = chr(92)
_LT = chr(60)
_GT = chr(62)
_LT_ESCAPE = _BACKSLASH + "u003c"
_GT_ESCAPE = _BACKSLASH + "u003e"

# `notes_boundary`: exactly 32 lowercase hexadecimal characters.
_BOUNDARY_RE = re.compile(r"^[0-9a-f]{32}$")

# A note id: exactly 32 lowercase hexadecimal characters (uuid4().hex).
_NOTE_ID_RE = re.compile(r"^[0-9a-f]{32}$")

# A basis content hash: exactly 64 lowercase hexadecimal characters.
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# The header JSON carries exactly these keys, in this order.
_HEADER_KEYS = ("id", "noted_at", "by", "based_on")
_BASIS_KEYS = ("path", "id", "quote", "sha256")

# Bounded attempts for boundary generation. A 32-hex value colliding with
# existing bytes (or with the note about to be written) has probability
# ~16**-32 per attempt, so exhaustion is unreachable in practice; the bound
# exists so the loop is visibly finite.
_MAX_BOUNDARY_ATTEMPTS = 64

# The marker prefixes without a boundary value: the grammar's line shapes.
NOTE_OPEN_MARKER_PREFIX = _LT + "!-- life-index:note "
NOTE_CLOSE_MARKER_PREFIX = _LT + "!-- /life-index:note "
_HEADER_SUFFIX = " --" + _GT


def is_valid_boundary(value: Any) -> bool:
    """Whether ``value`` is a stored ``notes_boundary``: 32 lowercase hex."""
    return isinstance(value, str) and _BOUNDARY_RE.fullmatch(value) is not None


def boundary_of(metadata: Mapping[str, Any] | Any) -> str | None:
    """The file's valid ``notes_boundary``, or ``None`` (no notes)."""
    if not isinstance(metadata, Mapping):
        return None
    value = metadata.get("notes_boundary")
    return value if is_valid_boundary(value) else None


def note_marker_prefix(boundary: str) -> str:
    """The text every note header line begins with (note the trailing space)."""
    return f"{NOTE_OPEN_MARKER_PREFIX}{boundary} "


def note_close_line(boundary: str) -> str:
    """The whole-line close marker of one note block."""
    return f"{NOTE_CLOSE_MARKER_PREFIX}{boundary} --{_GT}"


def find_notes_region(text: str, boundary: str) -> int | None:
    """Character offset where the notes region starts in ``text``, or ``None``.

    The region starts at the first line that begins with the note marker
    prefix. Because the boundary is checked at generation not to occur in the
    file's original bytes, that first occurrence is always the real region,
    whatever the original text contains. Works on the reader's body and on the
    raw file text alike: the region is at the end of the file and its lines
    are LF only.
    """
    prefix = note_marker_prefix(boundary)
    offset = 0
    for line in text.split("\n"):
        if line.startswith(prefix):
            return offset
        offset += len(line) + 1
    return None


def find_boundary_leak(text: str, boundary: str) -> int | None:
    """Offset of the first line that contains the boundary value, or ``None``.

    The boundary value itself, wherever it appears in a line the splitter
    would call original text, means the region has been damaged into the
    user's words (a rewritten marker, a pasted header): that is a damage
    signal, not original text. The first marker line contains the boundary
    too, so an undamaged region reports its own marker line here.
    """
    offset = 0
    for line in text.split("\n"):
        if boundary in line:
            return offset
        offset += len(line) + 1
    return None


def _normalize_region_endings(text: str) -> str:
    """Normalize the region's line endings to LF before parsing (one answer).

    The writer always stores the region as LF, but a file saved by a Windows
    editor can carry CRLF (or lone CR) through the region. Parsing normalizes
    those to LF first, so every caller — the text reader (which already sees
    LF through universal newlines) and the byte-based writers — reads the
    same notes. Only the region is normalized; the original text is returned
    exactly as the reader delivered it.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True)
class FragmentNote:
    """One stored note, as read back."""

    id: str
    noted_at: str
    by: str
    text: str
    based_on: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape every consumer sees (``based_on`` as a list)."""
        return {
            "id": self.id,
            "noted_at": self.noted_at,
            "by": self.by,
            "text": self.text,
            "based_on": [dict(item) for item in self.based_on],
        }


@dataclass(frozen=True)
class FragmentNotesSplit:
    """The one split of a journal body into original text and notes."""

    original_text: str
    notes: tuple[FragmentNote, ...]
    malformed: bool


def split_fragment_notes(metadata: Mapping[str, Any] | Any, body: str) -> FragmentNotesSplit:
    """Split the reader's body into the original text and the stored notes.

    ``metadata`` and ``body`` are what ``frontmatter.parse_frontmatter``
    returned for the file. Without a valid ``notes_boundary`` the whole body
    is the original text and there are no notes. With one:

    - everything before the first marker line is the original text (boundary
      whitespace stripped, the same normalization the reader applied) and the
      region — with its line endings normalized to LF — is parsed block by
      block; a region that breaks the grammar anywhere keeps the notes parsed
      so far and sets ``malformed``;
    - the boundary value occurring in a line the splitter would otherwise
      return as original text (before the first marker line, or with the
      marker line damaged so no line starts with the prefix) means the region
      has been damaged into the user's words: ``malformed`` is true and the
      original text is everything before the first line that contains the
      boundary (the safest reading — nothing after the leak is trusted);
    - a boundary with neither a marker line nor a leak (no region at all)
      reads as no notes, not malformed.
    """
    boundary = boundary_of(metadata)
    if boundary is None:
        return FragmentNotesSplit(body, (), False)
    marker_start = find_notes_region(body, boundary)
    leak_start = find_boundary_leak(body, boundary)
    if marker_start is None and leak_start is None:
        return FragmentNotesSplit(body, (), False)
    if leak_start is not None and (marker_start is None or leak_start < marker_start):
        # The marker line is damaged or gone and the boundary leaked into the
        # text above it: parse any later real region best-effort, but the
        # region as stored is malformed.
        notes: tuple[FragmentNote, ...] = ()
        if marker_start is not None:
            notes, _malformed = _parse_region(
                _normalize_region_endings(body[marker_start:]), boundary
            )
        return FragmentNotesSplit(body[:leak_start].strip(), notes, True)
    assert marker_start is not None  # leak_start is None or == marker_start here
    original = body[:marker_start].strip()
    notes, malformed = _parse_region(_normalize_region_endings(body[marker_start:]), boundary)
    return FragmentNotesSplit(original, notes, malformed)


def original_and_note_texts(metadata: Mapping[str, Any] | Any, body: str) -> str:
    """The text a full-text reader indexes: the original plus the note texts.

    The note headers, marker lines, ``by`` lines, ids and quotes never enter
    this text — only the words of the corrections themselves.
    """
    split = split_fragment_notes(metadata, body)
    if not split.notes:
        return split.original_text
    note_texts = "\n".join(note.text for note in split.notes)
    return f"{split.original_text}\n{note_texts}"


def _parse_region(region: str, boundary: str) -> tuple[tuple[FragmentNote, ...], bool]:
    """Parse the region (from its first marker line) into note blocks."""
    lines = region.split("\n")
    close = note_close_line(boundary)
    notes: list[FragmentNote] = []
    index = 0
    while index < len(lines):
        header = _parse_header(lines[index], boundary)
        if header is None:
            return tuple(notes), True
        end = _find_close(lines, index + 1, close)
        if end is None:
            return tuple(notes), True
        text = "\n".join(lines[index + 1 : end])
        if not text.strip():
            return tuple(notes), True
        notes.append(
            FragmentNote(
                id=header["id"],
                noted_at=str(header["noted_at"]),
                by=str(header["by"]),
                text=text,
                based_on=tuple(dict(item) for item in header["based_on"]),
            )
        )
        index = end + 1
        if index >= len(lines):
            return tuple(notes), False
        # Between blocks: exactly one blank line, then the next header.
        if lines[index] != "":
            return tuple(notes), True
        index += 1
        if index >= len(lines):
            # Only the separator's blank line remains (the region's final LF
            # is normally eaten by the reader's strip); not a damage signal.
            return tuple(notes), False
    return tuple(notes), False


def _find_close(lines: list[str], start: int, close: str) -> int | None:
    """Index of this block's close line, or ``None`` (truncated / wrong boundary)."""
    for index in range(start, len(lines)):
        line = lines[index]
        if line.startswith(NOTE_CLOSE_MARKER_PREFIX):
            return index if line == close else None
    return None


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """``object_pairs_hook`` that refuses a duplicated JSON key.

    The writer never duplicates a key; a header (or basis object) that carries
    one was not written by this grammar, so the region is malformed.
    """
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicated key in note header: {key}")
        result[key] = value
    return result


def _is_offset_datetime(value: Any) -> bool:
    """Whether ``value`` parses as an ISO 8601 date-time that carries an offset."""
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _parse_header(line: str, boundary: str) -> dict[str, Any] | None:
    """The parsed header JSON, or ``None`` when the line is not a valid header."""
    prefix = note_marker_prefix(boundary)
    if not line.startswith(prefix) or not line.endswith(_HEADER_SUFFIX):
        return None
    payload = line[len(prefix) : -len(_HEADER_SUFFIX)]
    try:
        parsed = json.loads(payload, object_pairs_hook=_reject_duplicate_keys)
    except ValueError:
        return None
    if not isinstance(parsed, dict) or tuple(parsed) != _HEADER_KEYS:
        return None
    if not isinstance(parsed["id"], str) or not _NOTE_ID_RE.fullmatch(parsed["id"]):
        return None
    if not _is_offset_datetime(parsed["noted_at"]):
        return None
    if not isinstance(parsed["by"], str) or not parsed["by"]:
        return None
    if not isinstance(parsed["based_on"], list) or not parsed["based_on"]:
        return None
    for item in parsed["based_on"]:
        if not isinstance(item, dict) or tuple(item) != _BASIS_KEYS:
            return None
        if not isinstance(item["path"], str) or not item["path"]:
            return None
        if item["id"] is not None and not isinstance(item["id"], str):
            return None
        if not isinstance(item["quote"], str) or not item["quote"]:
            return None
        if not isinstance(item["sha256"], str) or not _SHA256_RE.fullmatch(item["sha256"]):
            return None
    return parsed


def render_note_header(boundary: str, note: Mapping[str, Any]) -> str:
    """The single-line header: compact JSON, fixed key order, ``<``/``>`` escaped.

    With every ``<`` and ``>`` inside the JSON written as its unicode escape,
    the header can never contain ``-->``, so it can never be mistaken for —
    or break out of — an HTML comment.
    """
    ordered = {
        "id": str(note["id"]),
        "noted_at": str(note["noted_at"]),
        "by": str(note["by"]),
        "based_on": [
            {
                "path": str(basis["path"]),
                "id": basis["id"],
                "quote": str(basis["quote"]),
                "sha256": str(basis["sha256"]),
            }
            for basis in note["based_on"]
        ],
    }
    payload = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace(_LT, _LT_ESCAPE).replace(_GT, _GT_ESCAPE)
    return f"{note_marker_prefix(boundary)}{payload}{_HEADER_SUFFIX}"


def render_note_block(boundary: str, note: Mapping[str, Any], text: str) -> bytes:
    """One note block as stored bytes: header, LF, text lines, LF, close, LF."""
    return (
        render_note_header(boundary, note) + "\n" + text + "\n" + note_close_line(boundary) + "\n"
    ).encode("utf-8")


def generate_boundary(*occupied: bytes) -> str:
    """A fresh 32-hex boundary that occurs in none of the ``occupied`` byte strings.

    Callers pass every byte string the new boundary must not collide with:
    the target file's current bytes and the note block about to be appended.
    """
    for _ in range(_MAX_BOUNDARY_ATTEMPTS):
        candidate = secrets.token_hex(16)
        raw = candidate.encode("ascii")
        if not any(raw in blob for blob in occupied):
            return candidate
    raise RuntimeError("could not generate a boundary unused by the file")


def region_append_separator(old_bytes: bytes) -> bytes:
    """The separator between the old bytes and an appended note block.

    One LF when the old bytes already end with LF (the stored region ends
    with exactly one), two LFs otherwise — either way the block is preceded
    by one blank line.
    """
    return b"\n" if old_bytes.endswith(b"\n") else b"\n\n"


def insert_boundary_line(block: bytes, boundary: str) -> bytes:
    """Insert the ``notes_boundary`` line just before the block's closing delimiter.

    The line takes the line ending of the closing delimiter line, and nothing
    else in the block is touched — no re-serialization. ``block`` is the
    stored frontmatter block as ``journal_rewrite.split_journal_bytes``
    returns it (opening delimiter line through the closing delimiter line
    with that line's ending).
    """
    line = f'notes_boundary: "{boundary}"'
    closing_ending = _final_line_ending(block)
    return _insert_before_final_line(block, line.encode("utf-8") + closing_ending)


def split_suffix_region(suffix: bytes, boundary: str) -> tuple[bytes, bytes]:
    """Split stored suffix bytes into (original bytes, region bytes).

    The region bytes start at the marker line and run to the end of the
    suffix; the blank separator line before it belongs to the original bytes.
    No region in the suffix returns ``(suffix, b"")``.
    """
    text = suffix.decode("utf-8")
    start = find_notes_region(text, boundary)
    if start is None:
        return suffix, b""
    prefix_len = len(text[:start].encode("utf-8"))
    return suffix[:prefix_len], suffix[prefix_len:]


def _final_line_ending(block: bytes) -> bytes:
    """The line ending carried by the block's final (closing delimiter) line."""
    stripped = block[:-1] if block.endswith(b"\n") else block
    index = stripped.rfind(b"\n")
    final_line = stripped[index + 1 :]
    # A CRLF closing line leaves its CR at the end of the split line; the LF
    # itself was split off above.
    ending = final_line[len(final_line.rstrip(b"\r")) :]
    if block.endswith(b"\n"):
        ending += b"\n"
    # A closing line without any line ending still needs one after the
    # inserted line, or the block would glue two lines together.
    return ending or b"\n"


def _insert_before_final_line(block: bytes, inserted: bytes) -> bytes:
    """Insert whole-line ``inserted`` immediately before the block's final line."""
    stripped = block[:-1] if block.endswith(b"\n") else block
    index = stripped.rfind(b"\n")
    if index == -1:
        return inserted + block
    return block[: index + 1] + inserted + block[index + 1 :]
