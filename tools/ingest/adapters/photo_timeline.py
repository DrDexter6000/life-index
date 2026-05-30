"""media.photo_timeline source adapter.

Scans a directory for JPEG photos, extracts EXIF metadata via Pillow,
and returns normalized import records compatible with the import plan pipeline.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from tools.ingest.adapters._exif_common import (
    ADAPTER_ID,
    ADAPTER_VERSION,
    canonicalize_gps,
    compute_metadata_hash,
    normalize_orientation,
    parse_capture_time,
)
from tools.ingest.fingerprint import (
    compute_source_record_fingerprint,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg"})

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_photo_directory(input_dir: Path) -> dict[str, Any]:
    """Scan a photo directory and return normalised import records.

    Returns a dict with::

        {
            "adapter_id": "media.photo_timeline",
            "adapter_version": "v1",
            "input_label": "photo_timeline:<basename>",
            "records": [ ... ],   # see _build_record
            "warnings": [ ... ],  # scan-level warnings
        }
    """
    warnings: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    # Sort files deterministically by name for stable ordering
    files = sorted(
        [f for f in input_dir.iterdir() if f.is_file()],
        key=lambda f: f.name.lower(),
    )

    for file_path in files:
        ext = file_path.suffix.lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            warnings.append(
                _warning(
                    "PHOTO_UNSUPPORTED_FILE_SKIPPED",
                    f"Unsupported file type skipped: {file_path.name}",
                )
            )
            continue

        record_result = _process_jpeg(file_path)
        records.append(record_result["record"])
        warnings.extend(record_result.get("warnings", []))

    return {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "input_label": f"photo_timeline:{input_dir.name}",
        "records": records,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _process_jpeg(file_path: Path) -> dict[str, Any]:
    """Process a single JPEG file and return a record dict."""
    from PIL import Image

    warnings: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []

    # --- Read file bytes and compute content hash ---
    try:
        file_bytes = file_path.read_bytes()
    except OSError as exc:
        return _unreadable_record(file_path, exc)

    content_sha256 = hashlib.sha256(file_bytes).hexdigest()
    content_hash = f"sha256:{content_sha256}"
    content_hash_prefix = content_sha256[:12]

    # --- Open with Pillow and extract EXIF ---
    camera_make = ""
    camera_model = ""
    orientation: int | None = None
    gps: dict | None = None
    capture_time_iso: str | None = None
    exif_readable = False

    try:
        with Image.open(file_path) as img:
            exif_data = img.getexif()

            if exif_data:
                exif_readable = True
                # Extract basic tags
                camera_make = _decode_exif_text(exif_data.get(271, ""))  # Make
                camera_model = _decode_exif_text(exif_data.get(272, ""))  # Model
                orientation_raw = exif_data.get(274)  # Orientation
                if orientation_raw is not None:
                    try:
                        orientation = int(orientation_raw)
                    except (TypeError, ValueError):
                        pass

                # Build a piexif-compatible dict for our helpers
                piexif_data: dict[str, Any] = {
                    "Make": camera_make,
                    "Model": camera_model,
                }
                if orientation is not None:
                    piexif_data["Orientation"] = orientation

                # Read ExifIFD (sub-IFD) for DateTimeOriginal and DateTimeDigitized
                exif_ifd = exif_data.get_ifd(0x8769)  # ExifIFD
                if exif_ifd:
                    # DateTimeOriginal (tag 36867 in ExifIFD)
                    dt_original = exif_ifd.get(36867)
                    if dt_original:
                        piexif_data["DateTimeOriginal"] = dt_original

                    # DateTimeDigitized / CreateDate (tag 36868 in ExifIFD)
                    dt_digitized = exif_ifd.get(36868)
                    if dt_digitized:
                        piexif_data["DateTimeDigitized"] = dt_digitized

                    # DateTime (tag 306 in main IFD, but sometimes also in ExifIFD)
                    if "DateTime" not in piexif_data:
                        dt_generic = exif_data.get(306)
                        if dt_generic:
                            piexif_data["DateTime"] = dt_generic
                else:
                    # Fallback: read date tags from main IFD
                    dt_original = exif_data.get(36867)
                    if dt_original:
                        piexif_data["DateTimeOriginal"] = dt_original

                    dt_digitized = exif_data.get(36868)
                    if dt_digitized:
                        piexif_data["DateTimeDigitized"] = dt_digitized

                    dt_generic = exif_data.get(306)
                    if dt_generic:
                        piexif_data["DateTime"] = dt_generic

                # GPS data
                gps_info = exif_data.get_ifd(0x8825)  # GPSInfo IFD
                if gps_info and gps_info.get(2):
                    gps = canonicalize_gps(gps_info)

                # Parse capture time
                capture_time_iso, _source_tag, time_conflicts = parse_capture_time(piexif_data)
                conflicts.extend(time_conflicts)

    except Exception as exc:
        # Corrupted EXIF or other PIL error — graceful degradation
        warnings.append(
            _warning(
                "PHOTO_EXIF_UNREADABLE",
                f"Cannot read EXIF from {file_path.name}: {exc}",
            )
        )

    # --- If no capture time was found (no EXIF or unreadable), add conflict ---
    if capture_time_iso is None and not any(
        conflict.get("code") == "PHOTO_CAPTURE_TIME_MISSING" for conflict in conflicts
    ):
        conflicts.append(_conflict("PHOTO_CAPTURE_TIME_MISSING", "No EXIF capture time found"))

    # --- Normalize orientation (only when EXIF was readable) ---
    if exif_readable:
        _orientation_dict, orientation_warnings = normalize_orientation(
            {"Orientation": orientation} if orientation is not None else {}
        )
        all_warnings.extend(orientation_warnings)

    # --- GPS warning ---
    if exif_readable and gps is None:
        all_warnings.append(_warning("PHOTO_GPS_MISSING", f"No GPS data found in {file_path.name}"))

    if exif_readable and (not camera_make or not camera_model):
        all_warnings.append(
            _warning(
                "PHOTO_CAMERA_MISSING",
                f"Camera make/model metadata incomplete in {file_path.name}",
            )
        )

    # --- Compute metadata hash ---
    metadata_hash = compute_metadata_hash(
        capture_time=capture_time_iso,
        gps=gps,
        camera_make=camera_make,
        camera_model=camera_model,
        orientation=orientation,
    )

    # --- Compute source record fingerprint ---
    source_record_fp = compute_source_record_fingerprint(
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalized_identity=content_hash,
        content_hash=content_hash,
        metadata_hash=metadata_hash,
    )

    # --- Build journal ---
    if capture_time_iso:
        date = capture_time_iso[:10]
        title = f"Photo import: {date}"
        content = (
            f"Imported photo captured on {date}. " f"Review and edit this entry before confirming."
        )
    else:
        # Placeholder date for photos without capture time
        date = "1970-01-01"
        title = "Photo import: missing capture time"
        content = (
            "Imported photo with unknown capture time. "
            "Review and edit this entry before confirming."
        )

    # --- Build source references ---
    src_record_id = f"photo_{content_hash_prefix}"
    src_ref = f"source://media.photo_timeline/{content_hash_prefix}"

    # --- Build attachment ---
    if capture_time_iso:
        year, month, _day = capture_time_iso[:10].split("-")
    else:
        year, month = "1970", "01"

    attachment = {
        "attachment_id": f"att_{content_hash_prefix}",
        "source_ref": src_ref,
        "source_sha256": content_hash,
        "source_rel_path": file_path.name,
        "target_rel_path": f"attachments/{year}/{month}/import_{content_hash_prefix}.jpg",
        "media_type": "image/jpeg",
        "size_bytes": len(file_bytes),
        "copy_mode": "copy",
    }

    # --- Build record ---
    record: dict[str, Any] = {
        "source_record_id": src_record_id,
        "source_record_fingerprint": source_record_fp,
        "source_ref": src_ref,
        "journal": {
            "title": title,
            "date": date,
            "topic": "imported",
            "tags": ["imported", "photo"],
            "content": content,
        },
        "attachments": [attachment],
        "warnings": [_normalize_warning(warning) for warning in all_warnings],
        "conflicts": [_normalize_conflict(conflict) for conflict in conflicts],
    }

    return {
        "record": record,
        "warnings": [
            _normalize_warning(warning) for warning in warnings
        ],  # file-level warnings (EXIF unreadable, etc.)
    }


def _unreadable_record(file_path: Path, exc: OSError) -> dict[str, Any]:
    """Build a blocked record when the source file bytes cannot be read."""
    identity = hashlib.sha256(file_path.name.encode("utf-8")).hexdigest()
    content_hash = f"sha256:{hashlib.sha256(b'').hexdigest()}"
    metadata_hash = compute_metadata_hash(
        capture_time=None,
        gps=None,
        camera_make="",
        camera_model="",
        orientation=None,
    )
    source_record_fp = compute_source_record_fingerprint(
        adapter_id=ADAPTER_ID,
        adapter_version=ADAPTER_VERSION,
        normalized_identity=f"unreadable:{identity}",
        content_hash=content_hash,
        metadata_hash=metadata_hash,
    )
    record: dict[str, Any] = {
        "source_record_id": f"photo_unreadable_{identity[:12]}",
        "source_record_fingerprint": source_record_fp,
        "source_ref": f"source://media.photo_timeline/unreadable/{identity[:12]}",
        "journal": {
            "title": "Photo import: unreadable source",
            "date": "1970-01-01",
            "topic": "imported",
            "tags": ["imported", "photo"],
            "content": (
                "Imported photo source could not be read. "
                "Review the source file before confirming."
            ),
        },
        "attachments": [],
        "warnings": [],
        "conflicts": [
            _conflict(
                "PHOTO_SOURCE_UNREADABLE",
                f"Cannot read source file {file_path.name}: {exc}",
            )
        ],
    }
    return {"record": record, "warnings": []}


def _warning(code: str, message: str) -> dict[str, Any]:
    """Build a structured photo warning."""
    return {
        "code": code,
        "severity": "warning",
        "runnable": True,
        "message": message,
    }


def _conflict(code: str, message: str) -> dict[str, Any]:
    """Build a structured photo conflict."""
    return {
        "code": code,
        "severity": "conflict",
        "runnable": False,
        "message": message,
    }


def _normalize_warning(warning: dict[str, Any]) -> dict[str, Any]:
    """Ensure helper-origin warnings contain the public warning fields."""
    normalized = dict(warning)
    normalized.setdefault("severity", "warning")
    normalized.setdefault("runnable", True)
    return normalized


def _normalize_conflict(conflict: dict[str, Any]) -> dict[str, Any]:
    """Ensure helper-origin conflicts contain the public conflict fields."""
    normalized = dict(conflict)
    normalized.setdefault("severity", "conflict")
    normalized.setdefault("runnable", False)
    return normalized


def _decode_exif_text(value: Any) -> str:
    """Decode common EXIF text values without leaking Python bytes reprs."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()
