#!/usr/bin/env python3
"""Read-only journal get/list contract for Life Index CLI consumers."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any

from tools.lib.attachment import normalize_attachment_entries
from tools.lib.chinese_tokenizer import count_cjk_words
from tools.lib.entry_id import is_valid_entry_id
from tools.lib.entry_id_lookup import EntryIdLookup, resolve_entry_ids
from tools.lib.fragment_notes import split_fragment_notes
from tools.lib.frontmatter import (
    empty_indexable_metadata,
    normalize_indexable_metadata,
    parse_frontmatter,
)
from tools.lib.journal_files import classify_journal_path, display_label
from tools.lib.journal_ref import (
    JOURNAL_NAME_RE,
    canonical_journal_parts,
    resolves_within_data_dir,
)
from tools.lib.path_contract import build_journal_path_fields
from tools.lib.paths import get_journals_dir, get_user_data_dir
from tools.lib.tool_call_log import emit_tool_call_log

SCHEMA_VERSION = "m16.journal.v1"
MAX_BATCH_GET_ITEMS = 50
# A selector starting with this prefix is path-shaped and is treated exactly
# like `--path <value>`, permanently; every other non-id value is refused.
JOURNAL_PATH_PREFIX = "Journals/"


class JournalContractError(Exception):
    """A user-facing journal contract error."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _json_success(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "schema_version": SCHEMA_VERSION,
        "data": data,
        "error": None,
    }


def _json_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {
        "success": False,
        "schema_version": SCHEMA_VERSION,
        "data": None,
        "error": error,
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
    get_ref.add_argument(
        "--id",
        metavar="JOURNAL_ID",
        help="Durable entry id, or a Journals/... path (treated as --path).",
    )
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
        help=(
            "Durable entry id (or Journals/... path, treated as --path)."
            " Repeat for multiple entries."
        ),
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
    if not canonical_journal_parts(parts):
        raise JournalContractError(
            "JOURNAL_PATH_INVALID",
            "Journal path must match Journals/YYYY/MM/life-index_YYYY-MM-DD_NNN.md.",
        )
    return parts


def _resolve_journal_ref(raw_ref: str) -> Path:
    parts = _normalized_ref(raw_ref)
    data_root = get_user_data_dir().resolve()
    candidate = data_root.joinpath(*parts).resolve()
    if not resolves_within_data_dir(candidate, data_root):
        raise JournalContractError(
            "JOURNAL_PATH_INVALID",
            "Journal path resolves outside the Life Index data directory.",
        )

    if not candidate.exists() or not candidate.is_file():
        raise JournalContractError("JOURNAL_NOT_FOUND", "Journal file was not found.")
    return candidate


def _stored_entry_id(metadata: dict[str, Any]) -> str | None:
    """The entry's durable id when the file stores a valid one, else None.

    Never the path, never a computed value: the id is exactly what the file's
    own frontmatter stores, and only when it passes the one validity rule
    (`tools.lib.entry_id.is_valid_entry_id`). `metadata` still shows whatever
    the file stores, valid or not.
    """
    stored = metadata.get("id")
    return stored if is_valid_entry_id(stored) else None


def _journal_item_from_content(path: Path, content: str) -> dict[str, Any]:
    """Build one get/batch-get item from already-read file text.

    `content` comes from a single read of the file (a `--path` read or the
    id-lookup pass); it is never re-read here.
    """
    metadata, body = parse_frontmatter(content)
    # `content` is the user's original text; notes (fragment corrections) are
    # returned separately through the one notes grammar.
    notes_split = split_fragment_notes(metadata, body)
    path_fields = build_journal_path_fields(
        path,
        journals_dir=get_journals_dir(),
        user_data_dir=get_user_data_dir(),
    )
    rel_path = path_fields["rel_path"]
    item: dict[str, Any] = {
        "id": _stored_entry_id(metadata),
        "rel_path": rel_path,
        "journal_route_path": path_fields["journal_route_path"],
        "metadata": metadata,
        "content": notes_split.original_text,
        "notes": [note.to_dict() for note in notes_split.notes],
        "attachments": normalize_attachment_entries(
            metadata.get("attachments"),
            mode="stored_metadata",
        ),
        "word_count": count_cjk_words(notes_split.original_text),
    }
    if notes_split.malformed:
        item["notes_malformed"] = True
    return item


def _read_journal(path: Path) -> dict[str, Any]:
    return _journal_item_from_content(path, path.read_text(encoding="utf-8"))


def _lookup_outcome_error(lookup: EntryIdLookup, entry_id: str) -> JournalContractError:
    outcome = lookup.outcomes[entry_id]
    if outcome.status == "ambiguous":
        return JournalContractError(
            "JOURNAL_ID_AMBIGUOUS",
            "Entry id is carried by more than one file: " + ", ".join(outcome.rel_paths) + ".",
            {"rel_paths": list(outcome.rel_paths)},
        )
    if outcome.status == "incomplete":
        return JournalContractError(
            "JOURNAL_LOOKUP_INCOMPLETE",
            "No entry file carries this id, but "
            f"{outcome.unread_paths} path(s) could not be read during the scan.",
            {"unread_paths": outcome.unread_paths},
        )
    return JournalContractError(
        "JOURNAL_NOT_FOUND", "No entry file carries this id.", {"id": entry_id}
    )


def _entry_from_id_lookup(lookup: EntryIdLookup, entry_id: str) -> dict[str, Any]:
    """One get item from the single lookup pass (never a second read)."""
    outcome = lookup.outcomes[entry_id]
    hit = outcome.hits[0]
    data = _journal_item_from_content(hit.path, hit.content)
    if outcome.unread_paths:
        # The pass was not complete; the entry was found anyway. Reporting the
        # unread count keeps one stray unreadable file from disabling id
        # lookup for the whole archive, without hiding the gap.
        data["lookup"] = {"unread_paths": outcome.unread_paths}
    return data


def _classify_id_selector(raw_ref: str) -> tuple[str, str]:
    """Classify one `--id` value: ``("path"|"id", stripped_value)``.

    The one whitespace rule for `--id`, shared by `get` and `batch-get`:
    surrounding whitespace is stripped before classification. A path-shaped
    value (it starts with `Journals/`) is a path forever; a valid durable id
    is an id; anything else is refused as invalid input.
    """
    value = raw_ref.strip()
    if value.startswith(JOURNAL_PATH_PREFIX):
        return ("path", value)
    if is_valid_entry_id(value):
        return ("id", value)
    raise JournalContractError(
        "JOURNAL_ARGUMENT_INVALID",
        "journal --id expects a durable entry id (32 lowercase hex"
        " characters) or a Journals/... path.",
    )


def run_journal_get(*, path: str | None = None, id: str | None = None) -> dict[str, Any]:
    """Run the canonical single-journal operation without CLI formatting.

    This is the shared application seam for the direct CLI and transport
    projections.  It preserves the established journal domain envelope for
    path safety and missing-file failures.

    `--id` accepts a durable entry id (one scan over the entry files resolves
    it) or a path-shaped value starting with `Journals/`, which is treated
    exactly like `--path`; every other value is refused as invalid input.
    """
    if (path is None) == (id is None):
        return _json_error(
            "JOURNAL_ARGUMENT_INVALID",
            "journal get requires exactly one of path or id.",
        )

    try:
        if path is not None:
            return _json_success(_read_journal(_resolve_journal_ref(path)))
        assert id is not None
        kind, selector = _classify_id_selector(id)
        if kind == "path":
            return _json_success(_read_journal(_resolve_journal_ref(selector)))
        lookup = resolve_entry_ids(
            [selector], journals_dir=get_journals_dir(), user_data_dir=get_user_data_dir()
        )
        outcome = lookup.outcomes[selector]
        if outcome.status != "found":
            raise _lookup_outcome_error(lookup, selector)
        return _json_success(_entry_from_id_lookup(lookup, selector))
    except JournalContractError as exc:
        return _json_error(exc.code, exc.message, exc.details)
    except OSError as exc:
        return _json_error("JOURNAL_READ_FAILED", str(exc))


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
    # Label and word count come from the original text, never from notes.
    original = split_fragment_notes(metadata, body).original_text
    path_fields = build_journal_path_fields(
        path,
        journals_dir=get_journals_dir(),
        user_data_dir=get_user_data_dir(),
    )
    rel_path = path_fields["rel_path"]
    filename_date = JOURNAL_NAME_RE.match(path.name).group(1)  # type: ignore[union-attr]
    # The normalized title text: verbatim what the file says, "" when absent.
    indexable = normalize_indexable_metadata(metadata) or empty_indexable_metadata()
    title = indexable["title"]
    return {
        "id": _stored_entry_id(metadata),
        "rel_path": rel_path,
        "journal_route_path": path_fields["journal_route_path"],
        "title": title,
        "kind": classify_journal_path(path).value,
        "display_label": display_label(title, original, path),
        "date": str(metadata.get("date") or filename_date),
        "metadata": metadata,
        "attachments": normalize_attachment_entries(
            metadata.get("attachments"),
            mode="stored_metadata",
        ),
        "word_count": count_cjk_words(original),
    }


def _handle_get(args: argparse.Namespace) -> dict[str, Any]:
    return run_journal_get(path=args.path, id=args.id)


def _batch_refs(args: argparse.Namespace) -> list[tuple[str, str]]:
    """Deduplicated selectors in command order, each tagged with its origin.

    The command has always grouped every `--path` before every `--id`, each
    group in the order given; an identical text under both flags collapses to
    its first occurrence (with that occurrence's origin).
    """
    refs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for origin, raw_ref in [("path", value) for value in (args.path or [])] + [
        ("id", value) for value in (args.id or [])
    ]:
        text = str(raw_ref).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        refs.append((origin, text))
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
    # A `--path` value is always resolved as a path, exactly as before this
    # package; only `--id` values are classified. One scan then resolves
    # every id-shaped selector of this call.
    selectors: list[tuple[str, str]] = [
        ("path", text) if origin == "path" else _classify_id_selector(text) for origin, text in refs
    ]
    id_selectors = [text for kind, text in selectors if kind == "id"]
    lookup = (
        resolve_entry_ids(
            id_selectors, journals_dir=get_journals_dir(), user_data_dir=get_user_data_dir()
        )
        if id_selectors
        else None
    )
    # Files already matched by an id selector: whichever selector position
    # the file first appears at, its one item is the one built from the
    # lookup pass — a separate path read never displaces it.
    id_hit_files: dict[str, str] = {}
    for kind, text in selectors:
        if kind != "id":
            continue
        assert lookup is not None
        outcome = lookup.outcomes[text]
        if outcome.status == "found":
            key = os.path.normcase(str(outcome.hits[0].path.resolve()))
            id_hit_files.setdefault(key, text)

    items: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    consumed_ids: set[str] = set()
    for kind, text in selectors:
        if kind == "id":
            if text in consumed_ids:
                # Its file was already emitted at an earlier selector.
                continue
            assert lookup is not None
            outcome = lookup.outcomes[text]
            if outcome.status != "found":
                raise _lookup_outcome_error(lookup, text)
            data = _entry_from_id_lookup(lookup, text)
            file_key = os.path.normcase(str(outcome.hits[0].path.resolve()))
        else:
            resolved = _resolve_journal_ref(text)
            file_key = os.path.normcase(str(resolved))
            owning_id = id_hit_files.get(file_key)
            if owning_id is not None:
                # This file is also selected by id: serve the lookup-pass
                # item here, at the file's first selector position.
                assert lookup is not None
                data = _entry_from_id_lookup(lookup, owning_id)
                consumed_ids.add(owning_id)
            else:
                data = _read_journal(resolved)
        if file_key in seen_files:
            continue
        seen_files.add(file_key)
        items.append(data)
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
        payload = _json_error(exc.code, exc.message, exc.details)
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
