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
from pathlib import Path, PurePosixPath
from typing import Any

from tools.lib.paths import get_attachments_dir

SCHEMA_VERSION = "m16.attachment.v0"


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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    return parser.parse_args(argv)


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


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    raw_ref = args.info or args.export
    try:
        path, rel_path = _resolve_attachment_ref(raw_ref)
        if args.export:
            payload = _json_success(_export_payload(path, rel_path))
        else:
            payload = _json_success(_metadata(path, rel_path))
        _print_json(payload)
    except AttachmentContractError as exc:
        _print_json(_json_error(exc.code, exc.message))
        sys.exit(1)
    except OSError as exc:
        _print_json(_json_error("ATTACHMENT_READ_FAILED", str(exc)))
        sys.exit(1)


if __name__ == "__main__":
    main()
