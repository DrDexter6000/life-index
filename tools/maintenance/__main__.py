#!/usr/bin/env python3
"""CLI entry point for maintenance and Data Doctor commands.

Usage:
    python -m tools maintenance audit --json
    python -m tools maintenance plan --issue-id <id> --json
    python -m tools maintenance repair --issue-id <id> --dry-run --json
    python -m tools maintenance --dry-run
    python -m tools maintenance --dry-run --output=json

The maintenance command exposes the m33 Data Doctor audit/plan/repair
contracts and preserves the legacy m16 dry-run/report-only health cycle.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import parse_domains, run_audit
from .core import run_maintenance, format_text_report, to_json
from .plan import PLAN_SCHEMA_VERSION, build_plan
from .proposal import validate_proposal
from .repair import run_repair


def _attach_provenance(result: dict) -> dict:
    from ..lib.observability import build_provenance_envelope

    provenance_envelope = build_provenance_envelope(
        source_data=result,
        generator="maintenance",
        params={},
    )
    result["schema_version"] = provenance_envelope["schema_version"]
    result["provenance"] = provenance_envelope["provenance"]
    return result


def _run_audit_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="life-index maintenance audit",
        description="Audit Life Index user-data maintenance health.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Comma-separated domain filter, e.g. layout,frontmatter.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override data directory (sets LIFE_INDEX_DATA_DIR).",
    )
    args = parser.parse_args(argv)

    data_dir: str | None = None
    if args.data_dir:
        data_dir = str(args.data_dir)
        import os

        os.environ["LIFE_INDEX_DATA_DIR"] = data_dir

    try:
        domains = parse_domains(args.domain)
    except ValueError as exc:
        payload = {
            "success": False,
            "schema_version": "m33.maintenance_audit.v0",
            "command": "maintenance audit",
            "error": {"code": "MAINTENANCE_AUDIT_INVALID_DOMAIN", "message": str(exc)},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(2)

    result = run_audit(data_dir=data_dir, domains=domains)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


def _run_plan_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="life-index maintenance plan",
        description="Build a dry-run maintenance repair plan for one issue.",
    )
    parser.add_argument("--issue-id", required=True, help="Issue ID from maintenance audit.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override data directory (sets LIFE_INDEX_DATA_DIR).",
    )
    args = parser.parse_args(argv)

    data_dir: str | None = None
    if args.data_dir:
        data_dir = str(args.data_dir)
        import os

        os.environ["LIFE_INDEX_DATA_DIR"] = data_dir

    result, exit_code = build_plan(data_dir=data_dir, issue_id=args.issue_id)
    result.setdefault("schema_version", PLAN_SCHEMA_VERSION)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def _run_repair_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="life-index maintenance repair",
        description="Dry-run or apply a low-risk maintenance repair.",
    )
    parser.add_argument("--issue-id", required=True, help="Issue ID from maintenance audit.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview repair only.")
    mode.add_argument("--apply", action="store_true", help="Apply repair if allowed.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override data directory (sets LIFE_INDEX_DATA_DIR).",
    )
    args = parser.parse_args(argv)

    data_dir: str | None = None
    if args.data_dir:
        data_dir = str(args.data_dir)
        import os

        os.environ["LIFE_INDEX_DATA_DIR"] = data_dir

    result, exit_code = run_repair(data_dir=data_dir, issue_id=args.issue_id, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def _run_proposal_command(argv: list[str]) -> None:
    if not argv or argv[0] != "validate":
        parser = argparse.ArgumentParser(prog="life-index maintenance proposal")
        parser.error("expected subcommand: validate")

    parser = argparse.ArgumentParser(
        prog="life-index maintenance proposal validate",
        description="Validate a maintenance proposal file without applying it.",
    )
    parser.add_argument("--file", required=True, help="Proposal JSON file to validate.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override data directory (sets LIFE_INDEX_DATA_DIR).",
    )
    args = parser.parse_args(argv[1:])

    data_dir: str | None = None
    if args.data_dir:
        data_dir = str(args.data_dir)
        import os

        os.environ["LIFE_INDEX_DATA_DIR"] = data_dir
    else:
        import os

        data_dir = os.environ.get("LIFE_INDEX_DATA_DIR")

    if data_dir is None:
        data_dir = str(Path.home() / "Documents" / "Life-Index")

    result, exit_code = validate_proposal(data_dir=data_dir, proposal_file=args.file)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "audit":
        _run_audit_command(argv[1:])
        return
    if argv and argv[0] == "plan":
        _run_plan_command(argv[1:])
        return
    if argv and argv[0] == "repair":
        _run_repair_command(argv[1:])
        return
    if argv and argv[0] == "proposal":
        _run_proposal_command(argv[1:])
        return

    parser = argparse.ArgumentParser(
        description="Life Index - Maintenance and Data Doctor commands",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Data Doctor:
    python -m tools maintenance audit --json
    python -m tools maintenance audit --domain layout,search_index --json
    python -m tools maintenance plan --issue-id <id> --json
    python -m tools maintenance repair --issue-id <id> --dry-run --json
    python -m tools maintenance repair --issue-id <id> --apply --json
    python -m tools maintenance proposal validate --file <path> --json

Legacy maintenance cycle:
    python -m tools maintenance --dry-run
    python -m tools maintenance --dry-run --output=json
    python -m tools maintenance --dry-run --output=json --data-dir /tmp/sandbox
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run legacy maintenance cycle in dry-run/report-only mode (default).",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="text",
        choices=["text", "json"],
        help='Legacy maintenance cycle output format: "text" (default) or "json".',
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override data directory (sets LIFE_INDEX_DATA_DIR).",
    )

    args = parser.parse_args(argv)

    # Set data directory if provided
    data_dir: str | None = None
    if args.data_dir:
        data_dir = str(args.data_dir)
        import os

        os.environ["LIFE_INDEX_DATA_DIR"] = data_dir

    # Run maintenance checks
    result = run_maintenance(data_dir=data_dir)

    # Output
    if args.output == "json":
        result = _attach_provenance(result)
        text = to_json(result)
    else:
        text = format_text_report(result)

    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback for Windows console encoding issues
        if args.output == "json":
            import json

            print(json.dumps(result, ensure_ascii=True, indent=2))
        else:
            print(text.encode("ascii", errors="replace").decode("ascii"))

    # Always exit 0 for the command itself — check health is reported
    # in the output, not the exit code. A failing check does not mean
    # the maintenance command failed.
    sys.exit(0)


if __name__ == "__main__":
    main()
