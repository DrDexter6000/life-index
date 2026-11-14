#!/usr/bin/env python3
"""
Life Index - Fragment Tool - CLI Entry Point
把用户刚说过的话原样存为一条碎片。
"""

import argparse
import json
import sys
from typing import Any, Dict

from ..lib.config import ensure_dirs
from ..lib.errors import ErrorCode, create_error_response
from ..lib.paths import get_journals_dir, get_user_data_dir


def _load_payload(args: argparse.Namespace) -> Dict[str, Any]:
    """Read the JSON payload from --data ('-' = stdin) or --data-file."""
    payload: Dict[str, Any]
    if args.data is not None:
        if args.data == "-":
            payload = json.loads(sys.stdin.read())
        elif args.data.startswith("@"):
            with open(args.data[1:], "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        else:
            payload = json.loads(args.data)
    else:
        with open(args.data_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    return payload


def _emit_json(payload: dict) -> None:
    """Print JSON safely across Windows console encodings."""
    from ..lib.events import detect_events
    from ..lib.event_detectors import register_all_detectors

    register_all_detectors()
    context = {"journals_dir": get_journals_dir(), "data_dir": get_user_data_dir()}
    events = detect_events(context=context)
    payload["events"] = [event.to_dict() for event in events]

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text)


def _cmd_add(args: argparse.Namespace) -> int:
    """Execute fragment add."""
    ensure_dirs()
    try:
        data = _load_payload(args)
    except json.JSONDecodeError as exc:
        _emit_json(
            create_error_response(
                ErrorCode.INVALID_INPUT,
                f"JSON解析错误: {exc}",
                details={"raw_input": (args.data or "")[:200]},
            )
        )
        return 1
    except FileNotFoundError:
        _emit_json(
            create_error_response(
                ErrorCode.FILE_NOT_FOUND,
                f"文件未找到: {args.data_file or args.data[1:]}",
                details={"path": args.data_file or args.data[1:]},
            )
        )
        return 1

    from .core import add_fragment

    result = add_fragment(data)
    _emit_json(result)
    return 0 if result.get("success") else 1


def main() -> None:
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="life-index fragment",
        description="Life Index - Fragment Tool (store the user's own words)",
        epilog="""
Examples:
    life-index fragment add --data '{"text":"用户刚说的话","expressed_at":"2026-11-12T15:02:10+01:00"}'
    life-index fragment add --data-file fragment.json
    life-index fragment add --data - < fragment.json
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser(
        "add", help="Store the user's words as a fragment (no title, no summary)"
    )
    input_group = add_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--data", help="JSON payload; '-' reads the payload from stdin, '@file' from a file"
    )
    input_group.add_argument("--data-file", help="Read the JSON payload from a file")
    add_parser.set_defaults(func=_cmd_add)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
