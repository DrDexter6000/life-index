#!/usr/bin/env python3
"""Read-only attachment export contract for Life Index CLI consumers."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from tools.lib.paths import ValidationModeDataDirError, get_attachments_dir, get_cache_dir

SCHEMA_VERSION = "m16.attachment.v0"
MEDIA_SCHEMA_VERSION = "m17.attachment-media.v1"
MEDIA_CACHE_VERSION = "v1"
DEFAULT_THUMBNAIL_MAX_PX = 160
DEFAULT_PREVIEW_MAX_PX = 1400


class AttachmentContractError(Exception):
    """A user-facing attachment contract error."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _json_success(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "data": data,
        "error": None,
    }


def _json_error(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "schema_version": SCHEMA_VERSION,
        "data": None,
        "error": {"code": code, "message": message},
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _media_json_success(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "schema_version": MEDIA_SCHEMA_VERSION,
        "data": data,
        "error": None,
    }


def _media_json_error(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "schema_version": MEDIA_SCHEMA_VERSION,
        "data": None,
        "error": {"code": code, "message": message},
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "media":
        return _parse_media_args(raw_args[1:])

    parser = argparse.ArgumentParser(
        prog="life-index attachment",
        description="Read metadata or export bytes for archived attachments.",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--info",
        metavar="PATH",
        help="Return attachment metadata as JSON without embedded bytes.",
    )
    action.add_argument(
        "--export",
        metavar="PATH",
        help="Return attachment metadata plus base64-encoded bytes as JSON.",
    )
    return parser.parse_args(raw_args)


def _parse_media_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="life-index attachment media",
        description="Stream or file-export attachment media bytes without base64 wrapping.",
    )
    parser.add_argument(
        "path",
        help="Attachment reference under attachments/.",
    )
    parser.add_argument(
        "--variant",
        choices=("thumbnail", "preview", "original"),
        default="original",
        help="Media variant to emit. thumbnail and preview are deterministic image derivatives.",
    )
    parser.add_argument(
        "--max-px",
        type=int,
        default=None,
        help="Maximum width/height for thumbnail or preview variants.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output file path, or '-' for raw bytes on stdout. Defaults to stdout.",
    )
    parser.add_argument(
        "--metadata-output",
        help="Optional JSON metadata path when streaming raw bytes to stdout.",
    )
    parser.add_argument(
        "--range",
        dest="range_header",
        help="Optional byte range for original variant, e.g. 'bytes=0-1023'.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024 * 1024,
        help="Streaming chunk size in bytes.",
    )
    args = parser.parse_args(argv)
    args.media = True
    return args


def _resolve_attachment_ref(raw_ref: str) -> tuple[Path, str]:
    normalized = raw_ref.strip().replace("\\", "/")
    if not normalized:
        raise AttachmentContractError(
            "ATTACHMENT_PATH_INVALID",
            "Attachment path is empty.",
        )
    if "\x00" in normalized:
        raise AttachmentContractError(
            "ATTACHMENT_PATH_INVALID",
            "Attachment path contains a NUL byte.",
        )
    if (
        normalized.startswith("/")
        or normalized.startswith("//")
        or re.match(r"^[A-Za-z]:/", normalized)
    ):
        raise AttachmentContractError(
            "ATTACHMENT_PATH_INVALID",
            "Attachment path must be relative to the Life Index attachments directory.",
        )

    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".")]
    if "attachments" in parts:
        parts = parts[parts.index("attachments") + 1 :]
    if not parts or any(part == ".." for part in parts):
        raise AttachmentContractError(
            "ATTACHMENT_PATH_INVALID",
            "Attachment path must stay inside the Life Index attachments directory.",
        )

    root = get_attachments_dir().resolve()
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AttachmentContractError(
            "ATTACHMENT_PATH_INVALID",
            "Attachment path resolves outside the Life Index attachments directory.",
        ) from exc

    if not candidate.exists():
        raise AttachmentContractError(
            "ATTACHMENT_NOT_FOUND",
            "Attachment file was not found.",
        )
    if not candidate.is_file():
        raise AttachmentContractError(
            "ATTACHMENT_NOT_FILE",
            "Attachment reference does not point to a file.",
        )

    return candidate, "attachments/" + "/".join(parts)


def _metadata(path: Path, rel_path: str) -> dict[str, Any]:
    content_type, _ = mimetypes.guess_type(path.name)
    stat = path.stat()
    return {
        "rel_path": rel_path,
        "filename": path.name,
        "content_type": content_type or "application/octet-stream",
        "size": stat.st_size,
    }


def _export_payload(path: Path, rel_path: str) -> dict[str, Any]:
    content = path.read_bytes()
    data = _metadata(path, rel_path)
    data["sha256"] = hashlib.sha256(content).hexdigest()
    data["content_base64"] = base64.b64encode(content).decode("ascii")
    return data


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int
    total_size: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True)
class MediaBody:
    path: Path
    rel_path: str
    filename: str
    content_type: str
    source_sha256: str
    body_sha256: str
    source_size: int
    source_mtime_ns: int
    variant: str
    max_px: int | None
    cache_key: str | None
    cache_hit: bool | None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _guess_content_type(path: Path) -> str:
    content_type, _ = mimetypes.guess_type(path.name)
    return content_type or "application/octet-stream"


def _max_px_for_variant(variant: str, requested: int | None) -> int | None:
    if variant == "original":
        return None
    value = requested
    if value is None:
        value = DEFAULT_THUMBNAIL_MAX_PX if variant == "thumbnail" else DEFAULT_PREVIEW_MAX_PX
    if value <= 0:
        raise AttachmentContractError(
            "ATTACHMENT_MEDIA_INVALID",
            "--max-px must be a positive integer.",
        )
    return value


def _cache_key(
    *,
    rel_path: str,
    source_size: int,
    source_mtime_ns: int,
    variant: str,
    max_px: int,
    output_format: str,
) -> str:
    payload = {
        "rel_path": rel_path,
        "source_size": source_size,
        "source_mtime_ns": source_mtime_ns,
        "variant": variant,
        "max_px": max_px,
        "output_format": output_format,
        "implementation": MEDIA_CACHE_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _image_output_format(source_path: Path, image_format: str | None) -> tuple[str, str, str]:
    normalized = (image_format or "").upper()
    if normalized in {"JPEG", "JPG"}:
        return "JPEG", ".jpg", "image/jpeg"
    if normalized == "PNG":
        return "PNG", ".png", "image/png"
    if normalized == "WEBP":
        return "WEBP", ".webp", "image/webp"

    guessed = _guess_content_type(source_path)
    if guessed == "image/jpeg":
        return "JPEG", ".jpg", "image/jpeg"
    if guessed == "image/png":
        return "PNG", ".png", "image/png"
    if guessed == "image/webp":
        return "WEBP", ".webp", "image/webp"
    return "PNG", ".png", "image/png"


def _render_image_variant(path: Path, rel_path: str, variant: str, max_px: int) -> MediaBody:
    source_type = _guess_content_type(path)
    if not source_type.startswith("image/"):
        raise AttachmentContractError(
            "ATTACHMENT_UNSUPPORTED_MEDIA",
            f"{variant} is only supported for image attachments.",
        )

    stat = path.stat()
    output_format, extension, content_type = _image_output_format(path, None)
    key = _cache_key(
        rel_path=rel_path,
        source_size=stat.st_size,
        source_mtime_ns=stat.st_mtime_ns,
        variant=variant,
        max_px=max_px,
        output_format=output_format,
    )
    cache_dir = get_cache_dir() / "attachment-media" / MEDIA_CACHE_VERSION
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{key}{extension}"
    sidecar_path = cache_dir / f"{key}.json"
    cache_hit = cache_path.exists() and sidecar_path.exists()

    if cache_hit:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        return MediaBody(
            path=cache_path,
            rel_path=rel_path,
            filename=path.name,
            content_type=content_type,
            source_sha256=str(sidecar["source_sha256"]),
            body_sha256=str(sidecar["body_sha256"]),
            source_size=stat.st_size,
            source_mtime_ns=stat.st_mtime_ns,
            variant=variant,
            max_px=max_px,
            cache_key=key,
            cache_hit=True,
        )

    source_sha256 = _sha256_file(path)
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise AttachmentContractError(
            "ATTACHMENT_DECODE_FAILED",
            "Pillow is required to decode image media variants.",
        ) from exc

    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened)
            image.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
            if output_format == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            save_kwargs: dict[str, Any] = {}
            if output_format == "JPEG":
                save_kwargs = {"quality": 85, "optimize": True}
            image.save(cache_path, format=output_format, **save_kwargs)
    except UnidentifiedImageError as exc:
        raise AttachmentContractError(
            "ATTACHMENT_DECODE_FAILED",
            "Attachment could not be decoded as an image.",
        ) from exc
    except OSError as exc:
        raise AttachmentContractError(
            "ATTACHMENT_DECODE_FAILED",
            f"Attachment media decoding failed: {exc}",
        ) from exc

    body_sha256 = _sha256_file(cache_path)
    sidecar_path.write_text(
        json.dumps(
            {
                "source_sha256": source_sha256,
                "body_sha256": body_sha256,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return MediaBody(
        path=cache_path,
        rel_path=rel_path,
        filename=path.name,
        content_type=content_type,
        source_sha256=source_sha256,
        body_sha256=body_sha256,
        source_size=stat.st_size,
        source_mtime_ns=stat.st_mtime_ns,
        variant=variant,
        max_px=max_px,
        cache_key=key,
        cache_hit=False,
    )


def _original_body(path: Path, rel_path: str) -> MediaBody:
    stat = path.stat()
    source_sha256 = _sha256_file(path)
    return MediaBody(
        path=path,
        rel_path=rel_path,
        filename=path.name,
        content_type=_guess_content_type(path),
        source_sha256=source_sha256,
        body_sha256=source_sha256,
        source_size=stat.st_size,
        source_mtime_ns=stat.st_mtime_ns,
        variant="original",
        max_px=None,
        cache_key=None,
        cache_hit=None,
    )


def _parse_byte_range(range_header: str | None, total_size: int) -> ByteRange | None:
    if not range_header:
        return None
    if total_size <= 0:
        raise AttachmentContractError(
            "ATTACHMENT_RANGE_INVALID",
            "Cannot serve a byte range for an empty attachment.",
        )
    if not range_header.startswith("bytes=") or "," in range_header:
        raise AttachmentContractError(
            "ATTACHMENT_RANGE_INVALID",
            "Range must use a single bytes=start-end specifier.",
        )

    spec = range_header[len("bytes=") :].strip()
    if "-" not in spec:
        raise AttachmentContractError(
            "ATTACHMENT_RANGE_INVALID",
            "Range must include '-'.",
        )
    start_raw, end_raw = spec.split("-", 1)
    try:
        if start_raw == "":
            suffix_length = int(end_raw)
            if suffix_length <= 0:
                raise ValueError
            start = max(total_size - suffix_length, 0)
            end = total_size - 1
        else:
            start = int(start_raw)
            end = total_size - 1 if end_raw == "" else int(end_raw)
    except ValueError as exc:
        raise AttachmentContractError(
            "ATTACHMENT_RANGE_INVALID",
            "Range start and end must be non-negative integers.",
        ) from exc

    if start < 0 or end < start or start >= total_size:
        raise AttachmentContractError(
            "ATTACHMENT_RANGE_INVALID",
            "Range is outside the attachment byte length.",
        )
    return ByteRange(start=start, end=min(end, total_size - 1), total_size=total_size)


def _ascii_filename_fallback(filename: str) -> str:
    fallback = "".join(
        char if 32 <= ord(char) < 127 and char not in {'"', "\\", "/", ";"} else "_"
        for char in filename
    ).strip(" ._")
    return fallback or "attachment"


def _content_disposition(filename: str) -> str:
    fallback = _ascii_filename_fallback(filename)
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


def _media_headers(body: MediaBody, byte_range: ByteRange | None) -> dict[str, str]:
    content_length = byte_range.length if byte_range else body.path.stat().st_size
    headers = {
        "Content-Type": body.content_type,
        "Content-Length": str(content_length),
        "ETag": f'"sha256-{body.source_sha256}"',
        "Cache-Control": "private, max-age=3600",
        "Content-Disposition": _content_disposition(body.filename),
    }
    if body.variant == "original":
        headers["Accept-Ranges"] = "bytes"
    if byte_range:
        headers["Content-Range"] = (
            f"bytes {byte_range.start}-{byte_range.end}/{byte_range.total_size}"
        )
    return headers


def _media_payload(
    body: MediaBody,
    *,
    byte_range: ByteRange | None,
    output_path: str,
    status_code: int,
) -> dict[str, Any]:
    return _media_json_success(
        {
            "rel_path": body.rel_path,
            "filename": body.filename,
            "variant": body.variant,
            "max_px": body.max_px,
            "content_type": body.content_type,
            "size": byte_range.length if byte_range else body.path.stat().st_size,
            "sha256": body.body_sha256 if byte_range is None else None,
            "source": {
                "size": body.source_size,
                "sha256": body.source_sha256,
                "mtime_ns": body.source_mtime_ns,
            },
            "cache": {
                "eligible": body.variant in {"thumbnail", "preview"},
                "hit": body.cache_hit,
                "key": body.cache_key,
                "implementation": MEDIA_CACHE_VERSION,
            },
            "stream": {
                "status_code": status_code,
                "range": (
                    None
                    if byte_range is None
                    else {
                        "start": byte_range.start,
                        "end": byte_range.end,
                        "total_size": byte_range.total_size,
                    }
                ),
            },
            "headers": _media_headers(body, byte_range),
            "output": output_path,
        }
    )


def _copy_body_to_output(
    body_path: Path,
    *,
    output: str,
    byte_range: ByteRange | None,
    chunk_size: int,
) -> None:
    if chunk_size <= 0:
        raise AttachmentContractError(
            "ATTACHMENT_MEDIA_INVALID",
            "--chunk-size must be a positive integer.",
        )

    with body_path.open("rb") as source:
        if byte_range:
            source.seek(byte_range.start)
            remaining: int | None = byte_range.length
        else:
            remaining = None

        if output == "-":
            destination = sys.stdout.buffer
            _copy_stream(source, destination, chunk_size=chunk_size, remaining=remaining)
            destination.flush()
            return

        destination_path = Path(output)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with destination_path.open("wb") as destination:
            _copy_stream(source, destination, chunk_size=chunk_size, remaining=remaining)


def _copy_stream(
    source: Any,
    destination: Any,
    *,
    chunk_size: int,
    remaining: int | None,
) -> None:
    while remaining is None or remaining > 0:
        read_size = chunk_size if remaining is None else min(chunk_size, remaining)
        chunk = source.read(read_size)
        if not chunk:
            break
        destination.write(chunk)
        if remaining is not None:
            remaining -= len(chunk)


def _write_metadata(path: str, payload: dict[str, Any]) -> None:
    metadata_path = Path(path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_media(args: argparse.Namespace) -> None:
    source_path, rel_path = _resolve_attachment_ref(args.path)
    max_px = _max_px_for_variant(args.variant, args.max_px)
    if args.range_header and args.variant != "original":
        raise AttachmentContractError(
            "ATTACHMENT_RANGE_INVALID",
            "Byte ranges are only supported for the original variant.",
        )

    if args.variant == "original":
        body = _original_body(source_path, rel_path)
    else:
        assert max_px is not None
        body = _render_image_variant(source_path, rel_path, args.variant, max_px)

    byte_range = _parse_byte_range(args.range_header, body.source_size)
    status_code = 206 if byte_range else 200
    payload = _media_payload(
        body,
        byte_range=byte_range,
        output_path=args.output,
        status_code=status_code,
    )
    _copy_body_to_output(
        body.path,
        output=args.output,
        byte_range=byte_range,
        chunk_size=args.chunk_size,
    )

    if args.metadata_output:
        _write_metadata(args.metadata_output, payload)
    if args.output != "-":
        _print_json(payload)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        if getattr(args, "media", False):
            _run_media(args)
            return

        raw_ref = args.info or args.export
        path, rel_path = _resolve_attachment_ref(raw_ref)
        if args.export:
            payload = _json_success(_export_payload(path, rel_path))
        else:
            payload = _json_success(_metadata(path, rel_path))
        _print_json(payload)
    except AttachmentContractError as exc:
        if getattr(args, "media", False):
            print(
                json.dumps(_media_json_error(exc.code, exc.message), ensure_ascii=False),
                file=sys.stderr,
            )
        else:
            _print_json(_json_error(exc.code, exc.message))
        sys.exit(1)
    except ValidationModeDataDirError as exc:
        if getattr(args, "media", False):
            print(
                json.dumps(
                    _media_json_error("ATTACHMENT_DATA_DIR_INVALID", str(exc)),
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
        else:
            _print_json(_json_error("ATTACHMENT_DATA_DIR_INVALID", str(exc)))
        sys.exit(2)
    except OSError as exc:
        if getattr(args, "media", False):
            print(
                json.dumps(
                    _media_json_error("ATTACHMENT_READ_FAILED", str(exc)),
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
        else:
            _print_json(_json_error("ATTACHMENT_READ_FAILED", str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
