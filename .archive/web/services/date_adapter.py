"""Web GUI date adapter between browser controls and standard journal format."""

from __future__ import annotations

from datetime import datetime


def to_gui_datetime_value(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    try:
        normalized = datetime.fromisoformat(text)
        return normalized.replace(tzinfo=None).isoformat(timespec="seconds")
    except ValueError:
        pass

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt).isoformat(timespec="seconds")
        except ValueError:
            continue

    return text


def resolve_standard_date_value(
    gui_value: str | None, original_raw_value: str | None = None
) -> str:
    submitted = str(gui_value or "").strip()
    original_raw = str(original_raw_value or "").strip()

    if not submitted:
        return ""
    if not original_raw:
        return submitted
    if submitted == to_gui_datetime_value(original_raw):
        return original_raw
    return submitted
