"""Closed lexical validation for externally supplied import job ids."""

from __future__ import annotations

import re
from typing import Any

IMPORT_ID_INVALID = "IMPORT_ID_INVALID"
IMPORT_ID_INVALID_MESSAGE = "Import id is invalid."

_PARENT_RE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z", re.ASCII)
_CHILD_SEQUENCE_RE = re.compile(r"[1-9][0-9]{0,8}\Z", re.ASCII)
_MAX_IMPORT_ID_LENGTH = 128
_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)


def validate_import_id(value: Any, *, allow_child: bool) -> str | None:
    """Return a closed lexical failure reason, or ``None`` when valid.

    Validation is deliberately string-only and filesystem-free. The ordering
    is part of the public contract, so callers reject hostile input before
    constructing a path, consulting durable state, or reaching a network path.
    """

    if not isinstance(value, str):
        return "type"
    if value == "":
        return "empty"
    if not value.isascii():
        return "non_ascii"

    possible_parent = value.split("#", 1)[0]
    if possible_parent.upper() in _RESERVED_NAMES:
        return "reserved_name"

    if "#" in value:
        if value.count("#") != 1:
            return "child_syntax"
        parent, child_part = value.split("#", 1)
        if not parent or not child_part.startswith("batch-"):
            return "child_syntax"
        sequence = child_part.removeprefix("batch-")
        if len(parent) > _MAX_IMPORT_ID_LENGTH:
            return "child_parent_length"
        if _CHILD_SEQUENCE_RE.fullmatch(sequence) is None:
            return "child_sequence"
        if len(value) > _MAX_IMPORT_ID_LENGTH:
            return "length"
        if _PARENT_RE.fullmatch(parent) is None:
            return "syntax"
        if not allow_child:
            return "child_syntax"
        return None

    if len(value) > _MAX_IMPORT_ID_LENGTH:
        return "length"
    if _PARENT_RE.fullmatch(value) is None:
        return "syntax"
    return None


def import_id_invalid(reason: str) -> dict[str, Any]:
    """Return the exact safe public failure shape for a lexical id error."""

    return {
        "success": False,
        "data": None,
        "error": {
            "code": IMPORT_ID_INVALID,
            "message": IMPORT_ID_INVALID_MESSAGE,
            "details": {"reason": reason},
            "retryable": False,
        },
    }
