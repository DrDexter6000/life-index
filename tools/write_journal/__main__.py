#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - CLI Entry Point
写入日志并自动维护索引体系
"""

import argparse
import json
import sys

from .core import write_journal
from .prepare import prepare_journal_metadata
from ..lib.config import ensure_dirs


def _emit_json(payload: dict) -> None:
    """Print JSON safely across Windows console encodings."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text)


def _cmd_write(args) -> int:
    """Execute write command."""
    ensure_dirs()

    # Parse input data
    try:
        if args.data.startswith("@"):
            file_path = args.data[1:]
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(args.data)
    except json.JSONDecodeError as e:
        _emit_json({"success": False, "error": f"JSON解析错误: {e}"})
        return 1
    except FileNotFoundError:
        _emit_json({"success": False, "error": f"文件未找到: {args.data[1:]}"})
        return 1

    if args.verbose:
        print(
            f"[INFO] 输入数据: {json.dumps(data, ensure_ascii=False)}", file=sys.stderr
        )

    result = write_journal(data, dry_run=args.dry_run)
    _emit_json(result)
    return 0 if result["success"] else 1


def _cmd_enrich(args) -> int:
    """Execute enrich command - prepare metadata without writing.

    This command extracts/enriches metadata from content using:
    1. LLM-based extraction (if available)
    2. Rule-based fallbacks
    3. Project inference
    4. Weather auto-fill

    Returns the prepared metadata for preview/validation without writing a journal.
    """
    try:
        if args.data.startswith("@"):
            file_path = args.data[1:]
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(args.data)
    except json.JSONDecodeError as e:
        _emit_json({"success": False, "error": f"JSON解析错误: {e}"})
        return 1
    except FileNotFoundError:
        _emit_json({"success": False, "error": f"文件未找到: {args.data[1:]}"})
        return 1

    if args.verbose:
        print(
            f"[INFO] 输入数据: {json.dumps(data, ensure_ascii=False)}", file=sys.stderr
        )

    try:
        result = prepare_journal_metadata(data, use_llm=not args.no_llm)
        _emit_json({"success": True, "data": result})
        return 0
    except ValueError as e:
        _emit_json({"success": False, "error": str(e)})
        return 1
    except Exception as e:
        _emit_json({"success": False, "error": f"元数据准备失败: {e}"})
        return 1


def main() -> None:
    """CLI entry point"""
    # Check if we're in legacy mode (no subcommand, first arg is --data)
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        # Legacy mode: rewrite args to include 'write' subcommand
        sys.argv.insert(1, "write")

    parser = argparse.ArgumentParser(
        description="Life Index - Write Journal Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  write    Write a journal entry (default)
  enrich   Extract/enrich metadata without writing

Examples:
    # Write a journal
    python -m tools.write_journal write --data '{"date":"2026-03-04","title":"测试","content":"内容"}'
    python -m tools.write_journal --data @input.json --dry-run

    # Enrich metadata (for preview)
    python -m tools.write_journal enrich --data '{"content":"今天看到团团以前的照片..."}'
    python -m tools.write_journal enrich --data @draft.json --no-llm
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Write command (default)
    write_parser = subparsers.add_parser("write", help="Write a journal entry")
    write_parser.add_argument(
        "--data", required=True, help="JSON数据，或 @文件路径 (如 @input.json)"
    )
    write_parser.add_argument(
        "--dry-run", action="store_true", help="模拟运行，不实际写入文件"
    )
    write_parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    write_parser.set_defaults(func=_cmd_write)

    # Enrich command
    enrich_parser = subparsers.add_parser(
        "enrich",
        help="Extract/enrich metadata without writing",
        description=(
            "Prepare journal metadata from content using LLM and rule-based "
            "extraction. Returns enriched data without writing a journal."
        ),
    )
    enrich_parser.add_argument(
        "--data", required=True, help="JSON数据，或 @文件路径 (如 @input.json)"
    )
    enrich_parser.add_argument(
        "--no-llm", action="store_true", help="禁用 LLM 提取，仅使用规则"
    )
    enrich_parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    enrich_parser.set_defaults(func=_cmd_enrich)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
