"""Shared EXIF normalization helpers for photo source adapters."""

from __future__ import annotations

import hashlib
import json
from typing import Any

# ---------------------------------------------------------------------------
# Adapter identity constants
# ---------------------------------------------------------------------------

ADAPTER_ID = "media.photo_timeline"
ADAPTER_VERSION = "v1"

# ---------------------------------------------------------------------------
# EXIF orientation mapping (TIFF/EXIF tag 274)
# ---------------------------------------------------------------------------

ORIENTATION_MAP: dict[int, str] = {
    1: "normal",
    2: "mirror_horizontal",
    3: "rotate_180",
    4: "mirror_vertical",
    5: "mirror_horizontal_rotate_90_cw",
    6: "rotate_90_cw",
    7: "mirror_horizontal_rotate_90_ccw",
    8: "rotate_90_ccw",
}

# ---------------------------------------------------------------------------
# GPS helpers
# ---------------------------------------------------------------------------


def _text_ref(value: Any) -> str:
    """Normalize EXIF reference values returned as bytes or strings."""
    if isinstance(value, bytes):
        return value.decode("ascii", errors="replace")
    return str(value)


def _rational_to_float(value: Any) -> float | None:
    """Convert Pillow/EXIF rational values to float."""
    try:
        if isinstance(value, tuple):
            numerator, denominator = value
            return float(numerator) / float(denominator)
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def gps_to_decimal(gps_value: tuple) -> float | None:
    """Convert EXIF GPS rational (degrees, minutes, seconds) to decimal degrees.

    Each element in *gps_value* is a 2-tuple (numerator, denominator).
    Returns None when a denominator is 0 (invalid rational).
    """
    if not isinstance(gps_value, tuple) or len(gps_value) != 3:
        return None
    try:
        degrees = _rational_to_float(gps_value[0])
        minutes = _rational_to_float(gps_value[1])
        seconds = _rational_to_float(gps_value[2])
        if degrees is None or minutes is None or seconds is None:
            return None
        return degrees + minutes / 60.0 + seconds / 3600.0
    except (IndexError, TypeError):
        return None


def canonicalize_gps(gps_info: dict) -> dict | None:
    """Extract and normalize GPS from EXIF GPSInfo tag.

    Returns::

        {
            "latitude": float,
            "longitude": float,
            "altitude": float | None,
            "source": "exif.GPSInfo",
        }

    or ``None`` when no valid GPS data is present.
    """
    try:
        lat_ref = gps_info.get(1)  # GPSLatitudeRef
        lat_val = gps_info.get(2)  # GPSLatitude
        lon_ref = gps_info.get(3)  # GPSLongitudeRef
        lon_val = gps_info.get(4)  # GPSLongitude
    except (TypeError, AttributeError):
        return None

    if lat_val is None or lon_val is None:
        return None

    try:
        lat_decimal = gps_to_decimal(lat_val)
        lon_decimal = gps_to_decimal(lon_val)
    except (TypeError, ValueError):
        return None

    if lat_decimal is None or lon_decimal is None:
        return None

    if _text_ref(lat_ref).upper() == "S":
        lat_decimal = -lat_decimal
    if _text_ref(lon_ref).upper() == "W":
        lon_decimal = -lon_decimal

    # Altitude (tag 6)
    alt: float | None = None
    try:
        alt_val = gps_info.get(6)
        alt_ref = gps_info.get(5, 0)
        if alt_val is not None:
            alt = _rational_to_float(alt_val)
            if alt_ref == 1:  # below sea level
                alt = -alt if alt is not None else None
    except (TypeError, ValueError):
        alt = None

    return {
        "latitude": lat_decimal,
        "longitude": lon_decimal,
        "altitude": alt,
        "source": "exif.GPSInfo",
    }


def gps_to_fingerprint_string(gps: dict | None) -> str:
    """Convert normalized GPS to a stable fingerprint string.

    Latitude and longitude as 6 fractional digits, altitude as 1 fractional digit.
    Returns the empty string when *gps* is None.
    """
    if gps is None:
        return ""
    lat = gps.get("latitude", 0.0)
    lon = gps.get("longitude", 0.0)
    alt = gps.get("altitude")
    parts = [f"{lat:.6f}", f"{lon:.6f}"]
    if alt is not None:
        parts.append(f"{alt:.1f}")
    return ",".join(parts)


# ---------------------------------------------------------------------------
# Metadata hash
# ---------------------------------------------------------------------------


def compute_metadata_hash(
    capture_time: str | None,
    gps: dict | None,
    camera_make: str,
    camera_model: str,
    orientation: int | None,
) -> str:
    """Compute deterministic metadata SHA-256.

    UTF-8 JSON, sort_keys=True, fixed separators, no absolute paths.
    GPS values are decimal strings: latitude/longitude at 6 fractional digits,
    altitude at 1 fractional digit when present.
    """
    gps_str = gps_to_fingerprint_string(gps)
    payload: dict[str, Any] = {
        "capture_time": capture_time or "",
        "gps": gps_str,
        "camera_make": camera_make,
        "camera_model": camera_model,
        "orientation": orientation,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


# ---------------------------------------------------------------------------
# Capture time parsing
# ---------------------------------------------------------------------------


def parse_capture_time(exif_data: dict) -> tuple[str | None, str | None, list[dict]]:
    """Extract capture time from EXIF with precedence.

    Precedence: DateTimeOriginal (36867) > CreateDate (36868) > DateTime (306).

    Returns ``(iso_time, source_tag, conflicts)`` where *iso_time* is the
    selected time in ISO-8601 format, *source_tag* is the EXIF tag name, and
    *conflicts* is a list of conflict dicts (empty when unambiguous).
    """
    # EXIF tag IDs (piexif uses human-readable keys)
    date_original = exif_data.get("DateTimeOriginal")
    date_digitized = exif_data.get("DateTimeDigitized")  # CreateDate
    date_time = exif_data.get("DateTime")

    # Collect non-None candidate dates
    candidates: list[tuple[str, str, str | None]] = []  # (tag, iso, raw)
    tag_map = {
        "DateTimeOriginal": "DateTimeOriginal",
        "DateTimeDigitized": "CreateDate",
        "DateTime": "DateTime",
    }

    raw_tags = {
        "DateTimeOriginal": date_original,
        "DateTimeDigitized": date_digitized,
        "DateTime": date_time,
    }

    for piexif_key, exif_name in tag_map.items():
        raw_val = raw_tags[piexif_key]
        if raw_val is not None:
            # EXIF stores dates as "YYYY:MM:DD HH:MM:SS" (bytes or str)
            if isinstance(raw_val, bytes):
                raw_val = raw_val.decode("ascii", errors="replace")
            iso = _exif_date_to_iso(raw_val)
            if iso is not None:
                candidates.append((exif_name, iso, raw_val))

    if not candidates:
        return (
            None,
            None,
            [{"code": "PHOTO_CAPTURE_TIME_MISSING", "message": "No EXIF capture time found"}],
        )

    # Precedence: DateTimeOriginal > CreateDate > DateTime
    if len(candidates) == 1:
        return candidates[0][1], candidates[0][0], []

    # Check for ambiguous dates (different date parts)
    primary = candidates[0]
    primary_date = primary[1][:10]  # YYYY-MM-DD

    for other in candidates[1:]:
        other_date = other[1][:10]
        if other_date != primary_date:
            return (
                primary[1],
                primary[0],
                [
                    {
                        "code": "PHOTO_CAPTURE_TIME_AMBIGUOUS",
                        "message": (
                            f"Conflicting capture dates: "
                            f"{primary[0]}={primary[2]}, "
                            f"{other[0]}={other[2]}"
                        ),
                    }
                ],
            )

    # Same date, different times — use the primary (highest precedence)
    return primary[1], primary[0], []


def _exif_date_to_iso(raw: str) -> str | None:
    """Convert EXIF date string 'YYYY:MM:DD HH:MM:SS' to ISO 'YYYY-MM-DDTHH:MM:SS'.

    Returns None when the format is unrecognised.
    """
    if len(raw) < 19:
        return None
    try:
        date_part = raw[:10].replace(":", "-")
        time_part = raw[11:19]
        return f"{date_part}T{time_part}"
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Orientation normalisation
# ---------------------------------------------------------------------------


def normalize_orientation(exif_data: dict) -> tuple[dict | None, list[dict]]:
    """Normalize EXIF orientation tag.

    Returns ``(orientation_dict_or_none, warnings)``.

    - Missing: ``(None, [{"code": "PHOTO_ORIENTATION_MISSING", ...}])``
    - Present: ``({"exif_value": int, "display_hint": str}, [])``
    """
    raw = exif_data.get("Orientation")
    if raw is None:
        return (
            None,
            [{"code": "PHOTO_ORIENTATION_MISSING", "message": "No EXIF orientation tag found"}],
        )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return (
            None,
            [
                {
                    "code": "PHOTO_ORIENTATION_MISSING",
                    "message": f"Unparseable EXIF orientation: {raw}",
                }
            ],
        )
    display_hint = ORIENTATION_MAP.get(value, f"unknown_{value}")
    return {"exif_value": value, "display_hint": display_hint}, []
