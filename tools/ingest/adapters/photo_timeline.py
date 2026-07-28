"""media.photo_timeline source adapter.

Scans a directory tree for JPEG photos (read-only, recursive), extracts EXIF
metadata via Pillow, and returns normalized import records compatible with the
import plan pipeline.

Source facts are immutable: content SHA-256, size, source relative path, capture
time value/source/timezone authority, GPS, camera make/model, orientation and
provenance. User edits may change journal title/date/topic/tags/content and
proposal/attachment selection, never the source facts.
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
from tools.ingest.adapters._scan import iter_source_files
from tools.ingest.fingerprint import (
    compute_source_record_fingerprint,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Supported photo formats (Tranche B additive)
_JPEG_EXTENSIONS = frozenset({".jpg", ".jpeg"})
# Explicitly-unsupported formats that must NOT be silently skipped.
_HEIC_EXTENSIONS = frozenset({".heic", ".heif"})
# Conflict codes that mark a photo's capture time as unresolved. Such records
# carry an empty date/target and an explicit ``date_resolution`` so the review
# queue keeps them pending until the user supplies a date.
_CAPTURE_CONFLICT_CODES = frozenset(
    {"PHOTO_CAPTURE_TIME_MISSING", "PHOTO_CAPTURE_TIME_AMBIGUOUS"}
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_photo_directory(
    input_dir: Path,
    *,
    known_shas: set[str] | None = None,
) -> dict[str, Any]:
    """Scan a photo directory tree and return normalised import records.

    Read-only recursive scan. Skips symlink/junction/reparse entries, root
    escape and directory cycles. Deduplicates by exact content SHA-256 (same
    name with different content is preserved; identical content is kept once).
    Files whose content SHA already appears in *known_shas* (confirmed/imported
    attachment SHAs from the import ledger authority) are skipped as duplicates.

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
    known = known_shas or set()
    seen_shas: set[str] = set()

    for file_path, rel_path in iter_source_files(input_dir):
        ext = file_path.suffix.lower()
        if ext in _HEIC_EXTENSIONS:
            # Unsupported format: warn explicitly, mark preview unavailable,
            # never silently skip.
            warnings.append(
                _warning(
                    "PHOTO_UNSUPPORTED_FORMAT",
                    f"Unsupported photo format (preview unavailable): {rel_path}",
                    runnable=False,
                    extra={"format": ext, "preview_available": False},
                )
            )
            continue
        if ext not in _JPEG_EXTENSIONS:
            warnings.append(
                _warning(
                    "PHOTO_UNSUPPORTED_FILE_SKIPPED",
                    f"Unsupported file type skipped: {rel_path}",
                )
            )
            continue

        record_result = _process_jpeg(file_path, rel_path, seen_shas, known, warnings)
        record = record_result["record"]
        if record is not None:
            records.append(record)
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


def _process_jpeg(
    file_path: Path,
    rel_path: str,
    seen_shas: set[str],
    known_shas: set[str],
    out_warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Process a single JPEG file and return a record dict (or None if skipped)."""
    from PIL import Image

    warnings: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []

    # --- Read file bytes and compute content hash ---
    try:
        file_bytes = file_path.read_bytes()
    except OSError as exc:
        out_warnings.append(
            _warning(
                "PHOTO_EXIF_UNREADABLE",
                f"Cannot read source file {rel_path}: {exc}",
            )
        )
        return {"record": None, "warnings": []}

    content_sha256 = hashlib.sha256(file_bytes).hexdigest()
    content_hash = f"sha256:{content_sha256}"
    content_hash_prefix = content_sha256[:12]

    # --- Exact content dedup (within scan and vs known imported SHAs) ---
    if content_hash in seen_shas or content_hash in known_shas:
        out_warnings.append(
            _warning(
                "PHOTO_DUPLICATE_SKIPPED",
                f"Duplicate photo content skipped: {rel_path}",
                extra={"content_sha256": content_hash},
            )
        )
        return {"record": None, "warnings": []}
    seen_shas.add(content_hash)

    # --- Open with Pillow and extract EXIF ---
    camera_make = ""
    camera_model = ""
    orientation: int | None = None
    gps: dict | None = None
    capture_time_iso: str | None = None
    capture_source_tag: str | None = None
    timezone_authority: str | None = None
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

                    # OffsetTimeOriginal (0x9011) / OffsetTimeDigitized (0x9012)
                    off_original = exif_ifd.get(0x9011)
                    if off_original:
                        piexif_data["OffsetTimeOriginal"] = off_original
                    off_digitized = exif_ifd.get(0x9012)
                    if off_digitized:
                        piexif_data["OffsetTimeDigitized"] = off_digitized

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

                # Parse capture time (with timezone authority)
                (
                    capture_time_iso,
                    capture_source_tag,
                    time_conflicts,
                    timezone_authority,
                ) = parse_capture_time(piexif_data)
                conflicts.extend(time_conflicts)

    except Exception as exc:
        # Corrupted EXIF or other PIL error — graceful degradation
        warnings.append(
            _warning(
                "PHOTO_EXIF_UNREADABLE",
                f"Cannot read EXIF from {rel_path}: {exc}",
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
        all_warnings.append(_warning("PHOTO_GPS_MISSING", f"No GPS data found in {rel_path}"))

    if exif_readable and (not camera_make or not camera_model):
        all_warnings.append(
            _warning(
                "PHOTO_CAMERA_MISSING",
                f"Camera make/model metadata incomplete in {rel_path}",
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
    # Capture-time authority is the EXIF date (offset = recorded local calendar
    # date, no UTC conversion; naive = camera-local) — never the filesystem
    # mtime. A record with a capture-time conflict (missing/ambiguous) is
    # UNRESOLVED: its date and target path stay empty and it carries an explicit
    # ``date_resolution`` so the review queue keeps it in the pending area until
    # the user supplies an explicit resolution. There is no 1970-01-01 sentinel.
    has_capture_conflict = any(
        conflict.get("code") in _CAPTURE_CONFLICT_CODES for conflict in conflicts
    )
    if has_capture_conflict:
        date = ""
        title = "Photo import: missing capture time"
        content = (
            "Imported photo with unknown capture time. "
            "Review and edit this entry before confirming."
        )
        date_resolution: dict[str, Any] = {"status": "unresolved", "date": ""}
    else:
        # No capture conflict => a trustworthy EXIF date was recovered; the
        # ``or ""`` keeps mypy happy (it cannot see the conflict/date invariant).
        date = (capture_time_iso or "")[:10]
        title = f"Photo import: {date}"
        content = (
            f"Imported photo captured on {date}. " f"Review and edit this entry before confirming."
        )
        date_resolution = {
            "status": "exif_authoritative",
            "date": date,
            "authority": timezone_authority or "exif_naive",
        }

    # --- Build source references ---
    src_record_id = f"photo_{content_hash_prefix}"
    src_ref = f"source://media.photo_timeline/{content_hash_prefix}"

    # --- Build attachment ---
    if date:
        year, month, _day = date.split("-")
        att_target = f"attachments/{year}/{month}/import_{content_hash_prefix}.jpg"
    else:
        # Unresolved: target deferred until the user resolves the date.
        att_target = ""

    attachment = {
        "attachment_id": f"att_{content_hash_prefix}",
        "source_ref": src_ref,
        "source_sha256": content_hash,
        "source_rel_path": rel_path,
        "target_rel_path": att_target,
        "media_type": "image/jpeg",
        "size_bytes": len(file_bytes),
        "copy_mode": "copy",
    }

    # --- Immutable source facts (provenance) ---
    source_facts: dict[str, Any] = {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "content_sha256": content_hash,
        "size_bytes": len(file_bytes),
        "source_rel_path": rel_path,
        "source_ref": src_ref,
        "media_type": "image/jpeg",
        "capture_time": {
            "value": capture_time_iso,
            "source_tag": capture_source_tag,
            "timezone_authority": timezone_authority,
        },
        "gps": gps,
        "camera_make": camera_make,
        "camera_model": camera_model,
        "orientation": orientation,
        "metadata_hash": metadata_hash,
    }

    # --- Build record ---
    record: dict[str, Any] = {
        "source_record_id": src_record_id,
        "source_record_fingerprint": source_record_fp,
        "source_ref": src_ref,
        "source_facts": source_facts,
        "journal": {
            "title": title,
            "date": date,
            "topic": "life",
            "tags": ["imported", "photo"],
            "content": content,
        },
        "date_resolution": date_resolution,
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


def _warning(
    code: str,
    message: str,
    *,
    runnable: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured photo warning."""
    entry: dict[str, Any] = {
        "code": code,
        "severity": "warning",
        "runnable": runnable,
        "message": message,
    }
    if extra:
        entry.update(extra)
    return entry


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
