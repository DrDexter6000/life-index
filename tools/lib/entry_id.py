"""The one module that owns the durable entry id rules.

Every entry file carries a durable ``id`` in its own frontmatter. This module
is the only place that knows how such an id is generated, what makes a stored
value valid, and how the id of a pre-id entry is derived. The rules live in
``docs/ARCHITECTURE.md`` (*Entry identity*); other documents point there.

Once written, an id is an opaque stored value: nothing in this module (or
anywhere else) recomputes a stored id or checks it against the legacy recipe.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Literal

# A stored id is valid exactly when it is a string of 32 lowercase
# hexadecimal characters. This is the one validity rule, everywhere.
_ENTRY_ID_RE = re.compile(r"^[0-9a-f]{32}$")

# The domain-separation prefix of the legacy-id recipe.
_LEGACY_ID_DOMAIN = "life-index/legacy-id/v1"

EntryIdState = Literal["missing", "valid", "malformed"]


def is_valid_entry_id(value: Any) -> bool:
    """Whether *value* is a valid stored entry id (the one validity rule)."""
    return isinstance(value, str) and _ENTRY_ID_RE.fullmatch(value) is not None


def new_entry_id() -> str:
    """The id a newly created entry gets: a random UUID v4 in hex."""
    return uuid.uuid4().hex


def legacy_entry_id(rel_path: str, original_bytes: bytes) -> str:
    """The id a pre-id entry gets, derived once from the file as it was.

    ``sha256("life-index/legacy-id/v1" + NUL + rel_path as UTF-8 + NUL +
    the file's bytes before this migration)``, lowercase hex, first 32
    characters. ``rel_path`` is the path relative to the data directory: it
    starts with ``Journals/``, uses ``/``, keeps case, and is not normalised
    in any other way; ``original_bytes`` is the snapshot read inside the
    lock, before any chain step or re-rendering (no line-ending or other
    normalisation).

    The exact promise: two copies of an archive that hold a byte-identical
    file at the same ``rel_path`` assign it the same id when migrated
    separately. Copies that differ (an edit, a line-ending conversion, a
    move) do not; the way to keep copies in step then is to migrate one and
    copy the migrated files.
    """
    digest = hashlib.sha256(
        _LEGACY_ID_DOMAIN.encode("utf-8")
        + b"\x00"
        + rel_path.encode("utf-8")
        + b"\x00"
        + original_bytes
    ).hexdigest()
    return digest[:32]


def classify_stored_entry_id(value: Any) -> EntryIdState:
    """Classify a stored ``id`` value: ``missing``, ``valid`` or ``malformed``.

    ``missing``: absent (``None``) or a blank string — the entry simply has
    no id yet and ``migrate`` assigns one. ``valid``: passes
    :func:`is_valid_entry_id`. ``malformed``: anything else (a non-string, or
    a string that is not 32 lowercase hex); such a value is never replaced —
    the file is left exactly as it is and reported.
    """
    if value is None:
        return "missing"
    if isinstance(value, str):
        if not value.strip():
            return "missing"
        return "valid" if _ENTRY_ID_RE.fullmatch(value) is not None else "malformed"
    return "malformed"
