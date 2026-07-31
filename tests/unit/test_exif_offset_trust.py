#!/usr/bin/env python3
"""Trust-boundary tests for EXIF UTC offset handling (package-1 rework, gap 3).

An EXIF offset is only trusted when it is well-formed AND carried by the offset
tag paired with the chosen capture tag. Anything else leaves the capture date as
camera-local ``exif_naive`` (the calendar date is still used verbatim, never
converted to UTC).
"""

from __future__ import annotations

from tools.ingest.adapters._exif_common import (
    _normalise_exif_offset,
    _read_exif_offset,
    parse_capture_time,
)


# ---------------------------------------------------------------------------
# _normalise_exif_offset — sign / minutes / real-world bounds
# ---------------------------------------------------------------------------


def test_normalise_requires_explicit_sign() -> None:
    # Missing sign must never be silently treated as positive.
    assert _normalise_exif_offset("0500") is None
    assert _normalise_exif_offset("05:00") is None
    assert _normalise_exif_offset("05") is None


def test_normalise_rejects_invalid_minutes() -> None:
    assert _normalise_exif_offset("+05:60") is None
    assert _normalise_exif_offset("-00:99") is None


def test_normalise_rejects_out_of_world_bounds() -> None:
    # Real-world UTC offsets are at most ±14:00.
    assert _normalise_exif_offset("+15:00") is None
    assert _normalise_exif_offset("-14:30") is None  # 14 only valid with :00
    assert _normalise_exif_offset("+14:01") is None


def test_normalise_accepts_valid_offsets() -> None:
    assert _normalise_exif_offset("+05:30") == "+05:30"
    assert _normalise_exif_offset("-08:00") == "-08:00"
    assert _normalise_exif_offset("+14:00") == "+14:00"  # max bound, :00 ok
    assert _normalise_exif_offset("+00:00") == "+00:00"
    # Compact forms still accepted when sign is present.
    assert _normalise_exif_offset("+0530") == "+05:30"
    assert _normalise_exif_offset("+05") == "+05:00"


# ---------------------------------------------------------------------------
# _read_exif_offset — only the paired tag, no cross-tag borrowing
# ---------------------------------------------------------------------------


def test_read_offset_uses_only_paired_tag() -> None:
    # DateTimeOriginal pairs with OffsetTimeOriginal only.
    exif = {"DateTimeOriginal": "2024:06:15 10:30:00", "OffsetTimeOriginal": "+05:30"}
    assert _read_exif_offset(exif, "DateTimeOriginal") == "+05:30"


def test_read_offset_does_not_borrow_digitized_for_original() -> None:
    # OffsetTimeDigitized must NOT be borrowed for DateTimeOriginal.
    exif = {
        "DateTimeOriginal": "2024:06:15 10:30:00",
        "OffsetTimeDigitized": "+05:30",
    }
    assert _read_exif_offset(exif, "DateTimeOriginal") is None


def test_read_offset_paired_tag_malformed_is_none() -> None:
    exif = {"DateTimeOriginal": "2024:06:15 10:30:00", "OffsetTimeOriginal": "+99:00"}
    assert _read_exif_offset(exif, "DateTimeOriginal") is None


# ---------------------------------------------------------------------------
# parse_capture_time — authority outcome (end-to-end at the helper level)
# ---------------------------------------------------------------------------


def test_parse_malformed_offset_falls_back_to_naive() -> None:
    iso, _tag, conflicts, authority = parse_capture_time(
        {"DateTimeOriginal": "2024:06:15 10:30:00", "OffsetTimeOriginal": "+14:30"}
    )
    assert iso == "2024-06-15T10:30:00"
    assert conflicts == []
    # malformed offset is not trusted → camera-local naive, date unchanged
    assert authority == "exif_naive"


def test_parse_mismatched_offset_tag_falls_back_to_naive() -> None:
    iso, _tag, conflicts, authority = parse_capture_time(
        {
            "DateTimeOriginal": "2024:06:15 10:30:00",
            "OffsetTimeDigitized": "+05:30",  # paired with CreateDate, not DateTimeOriginal
        }
    )
    assert iso == "2024-06-15T10:30:00"
    assert conflicts == []
    assert authority == "exif_naive"


def test_parse_valid_paired_offset_is_authoritative() -> None:
    iso, _tag, conflicts, authority = parse_capture_time(
        {"DateTimeOriginal": "2024:06:15 10:30:00", "OffsetTimeOriginal": "+05:30"}
    )
    assert iso == "2024-06-15T10:30:00"
    assert authority == "exif_offset"
