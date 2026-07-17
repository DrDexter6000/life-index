#!/usr/bin/env python3
"""Read-only journal get/list contract for Life Index CLI consumers."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any

from tools.lib.attachment import normalize_attachment_entries
from tools.lib.chinese_tokenizer import count_cjk_words
from tools.lib.frontmatter import parse_frontmatter
from tools.lib.path_contract import build_journal_path_fields
from tools.lib.paths import get_journals_dir, get_user_data_dir
from tools.lib.tool_call_log import emit_tool_call_log

SCHEMA_VERSION = "m16.journal.v0"
JOURNAL_NAME_RE = re.compile(r"^life-index_(\d{4}-\d{2}-\d{2})_(\d+)\.md$")
MAX_BATCH_GET_ITEMS = 50


class JournalContractError(Exception):
    """A user-facing journal contract error."""

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
        prog="life-index journal",
        description="Read Life Index journals through a stable CLI contract.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    get_parser = subparsers.add_parser("get", help="Read one journal entry as JSON.")
    get_ref = get_parser.add_mutually_exclusive_group(required=True)
    get_ref.add_argument("--path", metavar="REL_PATH", help="Journal path under Journals/.")
    get_ref.add_argument("--id", metavar="JOURNAL_ID", help="Current v0 journal id.")
    get_parser.add_argument("--json", action="store_true", help="Accepted for compatibility.")

    batch_parser = subparsers.add_parser(
        "batch-get",
        help="Read multiple journal entries as one bounded JSON batch.",
    )
    batch_parser.add_argument(
        "--path",
        action="append",
        default=[],
        metavar="REL_PATH",
        help="Journal path under Journals/. Repeat for multiple entries.",
    )
    batch_parser.add_argument(
        "--id",
        action="append",
        default=[],
        metavar="JOURNAL_ID",
        help="Current v0 journal id. Repeat for multiple entries.",
    )
    batch_parser.add_argument("--json", action="store_true", help="Accepted for compatibility.")

    list_parser = subparsers.add_parser("list", help="List journal entries as JSON.")
    list_parser.add_argument(
        "--recent",
        action="store_true",
        required=True,
        help="Return journals in deterministic recent-first order.",
    )
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum items to return.")
    list_parser.add_argument("--offset", type=int, default=0, help="Pagination offset.")
    list_parser.add_argument("--json", action="store_true", help="Accepted for compatibility.")

    return parser.parse_args(argv)


def _normalized_ref(raw_ref: str) -> list[str]:
    normalized = raw_ref.strip().replace("\\", "/")
    if not normalized:
        raise JournalContractError("JOURNAL_PATH_INVALID", "Journal path is empty.")
    if "\x00" in normalized:
        raise JournalContractError("JOURNAL_PATH_INVALID", "Journal path contains a NUL byte.")
    if (
        normalized.startswith("/")
        or normalized.startswith("//")
        or re.match(r"^[A-Za-z]:/", normalized)
    ):
        raise JournalContractError(
            "JOURNAL_PATH_INVALID",
            "Journal path must be relative to the Life Index data directory.",
        )

    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise JournalContractError(
            "JOURNAL_PATH_INVALID",
            "Journal path must stay inside the Life Index Journals directory.",
        )
    if len(parts) != 4 or parts[0] != "Journals" or not JOURNAL_NAME_RE.match(parts[-1]):
        raise JournalContractError(
            "JOURNAL_PATH_INVALID",
            "Journal path must match Journals/YYYY/MM/life-index_YYYY-MM-DD_NNN.md.",
        )
    return parts


def _resolve_journal_ref(raw_ref: str) -> Path:
    parts = _normalized_ref(raw_ref)
    data_root = get_user_data_dir().resolve()
    candidate = data_root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(data_root)
    except ValueError as exc:
        raise JournalContractError(
            "JOURNAL_PATH_INVALID",
            "Journal path resolves outside the Life Index data directory.",
        ) from exc

    if not candidate.exists() or not candidate.is_file():
        raise JournalContractError("JOURNAL_NOT_FOUND", "Journal file was not found.")
    return candidate


def _read_journal(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    path_fields = build_journal_path_fields(
        path,
        journals_dir=get_journals_dir(),
        user_data_dir=get_user_data_dir(),
    )
    rel_path = path_fields["rel_path"]
    return {
        "id": rel_path,
        "rel_path": rel_path,
        "journal_route_path": path_fields["journal_route_path"],
        "metadata": metadata,
        "content": body,
        "attachments": normalize_attachment_entries(
            metadata.get("attachments"),
            mode="stored_metadata",
        ),
        "word_count": count_cjk_words(body),
    }


def run_journal_get(*, path: str | None = None, id: str | None = None) -> dict[str, Any]:
    """Run the canonical single-journal operation without CLI formatting.

    This is the shared application seam for the direct CLI and transport
    projections.  It preserves the established journal domain envelope for
    path safety and missing-file failures.
    """
    if (path is None) == (id is None):
        return _json_error(
            "JOURNAL_ARGUMENT_INVALID",
            "journal get requires exactly one of path or id.",
        )

    raw_ref = path if path is not None else id
    assert raw_ref is not None
    try:
        return _json_success(_read_journal(_resolve_journal_ref(raw_ref)))
    except JournalContractError as exc:
        return _json_error(exc.code, exc.message)
    except OSError as exc:
        return _json_error("JOURNAL_READ_FAILED", str(exc))


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or None
    return None


def _journal_paths_recent() -> list[Path]:
    journals_dir = get_journals_dir()
    if not journals_dir.exists():
        return []
    paths = [
        path
        for path in journals_dir.glob("*/*/life-index_*.md")
        if path.is_file() and JOURNAL_NAME_RE.match(path.name)
    ]

    def sort_key(path: Path) -> tuple[str, int, str]:
        match = JOURNAL_NAME_RE.match(path.name)
        if not match:
            return ("", 0, "")
        date_value, seq_value = match.groups()
        rel_path = build_journal_path_fields(
            path,
            journals_dir=get_journals_dir(),
            user_data_dir=get_user_data_dir(),
        )["rel_path"]
        return (date_value, int(seq_value), rel_path)

    return sorted(paths, key=sort_key, reverse=True)


def _journal_summary(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    path_fields = build_journal_path_fields(
        path,
        journals_dir=get_journals_dir(),
        user_data_dir=get_user_data_dir(),
    )
    rel_path = path_fields["rel_path"]
    filename_date = JOURNAL_NAME_RE.match(path.name).group(1)  # type: ignore[union-attr]
    title = metadata.get("title") or _first_heading(body) or path.stem
    return {
        "id": rel_path,
        "rel_path": rel_path,
        "journal_route_path": path_fields["journal_route_path"],
        "title": title,
        "date": str(metadata.get("date") or filename_date),
        "metadata": metadata,
        "attachments": normalize_attachment_entries(
            metadata.get("attachments"),
            mode="stored_metadata",
        ),
        "word_count": count_cjk_words(body),
    }


def _handle_get(args: argparse.Namespace) -> dict[str, Any]:
    return run_journal_get(path=args.path, id=args.id)


def _batch_refs(args: argparse.Namespace) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for raw_ref in [*(args.path or []), *(args.id or [])]:
        text = str(raw_ref).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        refs.append(text)
    if not refs:
        raise JournalContractError(
            "JOURNAL_ARGUMENT_INVALID",
            "journal batch-get requires at least one --path or --id.",
        )
    if len(refs) > MAX_BATCH_GET_ITEMS:
        raise JournalContractError(
            "JOURNAL_BATCH_TOO_LARGE",
            f"journal batch-get accepts at most {MAX_BATCH_GET_ITEMS} entries.",
        )
    return refs


def _handle_batch_get(args: argparse.Namespace) -> dict[str, Any]:
    refs = _batch_refs(args)
    items = [_read_journal(_resolve_journal_ref(raw_ref)) for raw_ref in refs]
    return _json_success(
        {
            "items": items,
            "total_requested": len(refs),
            "total_found": len(items),
            "max_items": MAX_BATCH_GET_ITEMS,
        }
    )


def _handle_list(args: argparse.Namespace) -> dict[str, Any]:
    if args.limit < 0 or args.offset < 0:
        raise JournalContractError(
            "JOURNAL_ARGUMENT_INVALID",
            "Journal list limit and offset must be non-negative.",
        )

    all_items = [_journal_summary(path) for path in _journal_paths_recent()]
    total_matches = len(all_items)
    window = all_items[args.offset :]
    if args.limit > 0:
        window = window[: args.limit]
    total_found = len(window)
    has_more = (args.offset + total_found) < total_matches if args.limit != 0 else False
    return _json_success(
        {
            "items": window,
            "total_matches": total_matches,
            "total_found": total_found,
            "limit": args.limit,
            "offset": args.offset,
            "has_more": has_more,
            "sort": "date_desc",
        }
    )


def _log_journal_call(args: argparse.Namespace, payload: dict[str, Any], elapsed_ms: float) -> None:
    if args.command not in {"get", "batch-get"}:
        return
    raw_data = payload.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    raw_error = payload.get("error")
    error: dict[str, Any] | None = raw_error if isinstance(raw_error, dict) else None

    if args.command == "batch-get":
        raw_items = data.get("items")
        items: list[Any] = raw_items if isinstance(raw_items, list) else []
        result = {
            "total_requested": data.get("total_requested"),
            "total_found": data.get("total_found"),
            "rel_paths": [
                item.get("rel_path")
                for item in items
                if isinstance(item, dict) and isinstance(item.get("rel_path"), str)
            ],
        }
        params = {"paths": list(args.path or []), "ids": list(args.id or [])}
        tool = "journal batch-get"
    else:
        result = {
            "rel_path": data.get("rel_path"),
            "word_count": data.get("word_count"),
        }
        params = {"path": args.path, "id": args.id}
        tool = "journal get"

    emit_tool_call_log(
        tool,
        params=params,
        result=result,
        elapsed_ms=elapsed_ms,
        success=bool(payload.get("success")),
        error_code=str(error.get("code")) if error else None,
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    started = time.perf_counter()
    try:
        if args.command == "get":
            payload = _handle_get(args)
        elif args.command == "batch-get":
            payload = _handle_batch_get(args)
        elif args.command == "list":
            payload = _handle_list(args)
        else:
            payload = _json_error("JOURNAL_ARGUMENT_INVALID", "Unsupported journal command.")
            _log_journal_call(args, payload, (time.perf_counter() - started) * 1000.0)
            _print_json(payload)
            sys.exit(1)
        _log_journal_call(args, payload, (time.perf_counter() - started) * 1000.0)
        _print_json(payload)
        if not payload.get("success"):
            sys.exit(1)
    except JournalContractError as exc:
        payload = _json_error(exc.code, exc.message)
        _log_journal_call(args, payload, (time.perf_counter() - started) * 1000.0)
        _print_json(payload)
        sys.exit(1)
    except OSError as exc:
        payload = _json_error("JOURNAL_READ_FAILED", str(exc))
        _log_journal_call(args, payload, (time.perf_counter() - started) * 1000.0)
        _print_json(payload)
        sys.exit(1)


if __name__ == "__main__":
    main()
