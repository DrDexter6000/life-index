#!/usr/bin/env python3
"""CLI entry point for ``life-index import`` (PRD §4).

The public surface is::

    life-index import plan   --source <adapter> --input <path> --json
    life-index import run    --plan <path> --confirm <id> --json
    life-index import status --import-id <id> --json
    life-index import rollback --import-id <id> --json

S2 implements ``plan``.  S3 implements ``run`` and ``status``.
``rollback`` returns a structured "not implemented" error.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any

from tools.ingest.runner import execute_run, execute_rollback, query_status
from tools.ingest.schemas import (
    DEFAULT_NORMALIZED_IMPORT_OPTIONS_HASH,
    DEFAULT_NORMALIZED_WRITE_POLICY_HASH,
    PLAN_SCHEMA_VERSION,
    error_envelope,
    success_envelope,
)
from tools.ingest.fingerprint import (
    compute_attachment_fingerprint,
    compute_idempotency_key,
    compute_plan_fingerprint,
    compute_proposal_fingerprint,
    compute_source_fingerprint,
)
from tools.ingest.adapters.photo_timeline import scan_photo_directory
from tools.lib.paths import get_user_data_dir

# ---------------------------------------------------------------------------
# Supported source adapters (Tranche A: fixture only)
# ---------------------------------------------------------------------------

SUPPORTED_SOURCES = {"fixture.import_records", "media.photo_timeline"}

# ---------------------------------------------------------------------------
# Journal path helpers
# ---------------------------------------------------------------------------

_JOURNAL_SEQ_RE = re.compile(r"^life-index_(\d{4}-\d{2}-\d{2})_(\d+)\.md$")


def _next_seq_for_date(
    date: str,
    data_dir: Path,
    used_seqs: dict[str, int],
) -> int:
    """Return the next available sequence number for *date*.

    Considers both existing files in *data_dir* and sequences already
    allocated in the current plan (tracked via *used_seqs*).
    """
    year, month, _day = date.split("-")
    journal_dir = data_dir / "Journals" / year / month

    max_seq = 0
    if journal_dir.exists():
        for f in journal_dir.iterdir():
            m = _JOURNAL_SEQ_RE.match(f.name)
            if m:
                max_seq = max(max_seq, int(m.group(2)))

    if date in used_seqs:
        max_seq = max(max_seq, used_seqs[date])

    next_seq = max_seq + 1
    used_seqs[date] = next_seq
    return next_seq


def _journal_target_rel_path(date: str, seq: int) -> str:
    year, month, _day = date.split("-")
    return f"Journals/{year}/{month}/life-index_{date}_{seq:03d}.md"


# ---------------------------------------------------------------------------
# Plan command
# ---------------------------------------------------------------------------


def _cmd_plan(args: argparse.Namespace) -> None:
    """Implement ``import plan`` (PRD §6)."""
    source_adapter = args.source
    input_path = Path(args.input)
    data_dir = get_user_data_dir()

    # --- Validate source adapter ---
    if source_adapter not in SUPPORTED_SOURCES:
        _print_json(
            error_envelope(
                "import.plan",
                "IMPORT_SOURCE_UNSUPPORTED",
                f"Source adapter '{source_adapter}' is not supported.",
                {"adapter_id": source_adapter},
                retryable=False,
            )
        )
        sys.exit(1)

    # --- Pre-declare collections used by both branches ---
    all_conflicts: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []

    # --- Read source data (fixture or adapter scan) ---
    if not input_path.exists():
        _print_json(
            error_envelope(
                "import.plan",
                "IMPORT_SOURCE_UNREADABLE",
                f"Input path does not exist: {input_path}",
                {"input_path": str(input_path)},
                retryable=True,
            )
        )
        sys.exit(1)

    if source_adapter == "media.photo_timeline":
        if not input_path.is_dir():
            _print_json(
                error_envelope(
                    "import.plan",
                    "IMPORT_SOURCE_UNREADABLE",
                    f"Photo timeline input must be a directory: {input_path}",
                    {"input_path": str(input_path)},
                    retryable=True,
                )
            )
            sys.exit(1)
        scan_result = scan_photo_directory(input_path)
        adapter_id = scan_result["adapter_id"]
        adapter_version = scan_result["adapter_version"]
        input_label = scan_result["input_label"]
        records = scan_result["records"]
        all_warnings.extend(scan_result.get("warnings", []))
    else:
        try:
            fixture_text = input_path.read_text(encoding="utf-8")
            fixture_data: dict[str, Any] = json.loads(fixture_text)
        except (json.JSONDecodeError, OSError) as exc:
            _print_json(
                error_envelope(
                    "import.plan",
                    "IMPORT_SOURCE_UNREADABLE",
                    f"Cannot read input: {exc}",
                    {"input_path": str(input_path)},
                    retryable=True,
                )
            )
            sys.exit(1)

        adapter_id = fixture_data.get("adapter_id", source_adapter)
        adapter_version = fixture_data.get("adapter_version", "v1")
        input_label = fixture_data.get("input_label", "")
        records = fixture_data.get("records", [])

    # --- Build proposals ---
    used_seqs: dict[str, int] = {}
    proposals: list[dict[str, Any]] = []
    all_create_files: list[str] = []
    source_record_fingerprints: list[str] = []
    proposal_fingerprints: list[str] = []
    total_attachments = 0

    for record in records:
        src_record_id: str = record["source_record_id"]
        src_record_fp: str = record["source_record_fingerprint"]
        source_record_fingerprints.append(src_record_fp)

        journal_spec: dict[str, Any] = record.get("journal", {})
        attachment_specs: list[dict[str, Any]] = record.get("attachments", [])
        total_attachments += len(attachment_specs)

        # Determine journal target path
        force_path = record.get("force_target_rel_path")
        if force_path:
            target_rel_path = force_path
        else:
            seq = _next_seq_for_date(journal_spec["date"], data_dir, used_seqs)
            target_rel_path = _journal_target_rel_path(journal_spec["date"], seq)

        # --- Compute attachment fingerprints ---
        att_fingerprints: list[str] = []
        att_outputs: list[dict[str, Any]] = []
        for att in attachment_specs:
            att_fp = compute_attachment_fingerprint(
                attachment_id=att["attachment_id"],
                source_sha256=att["source_sha256"],
                target_rel_path=att["target_rel_path"],
                media_type=att["media_type"],
                size_bytes=att["size_bytes"],
                copy_mode=att["copy_mode"],
            )
            att_fingerprints.append(att_fp)
            att_outputs.append(
                {
                    "attachment_id": att["attachment_id"],
                    "source_ref": att["source_ref"],
                    "source_sha256": att["source_sha256"],
                    **(
                        {"source_rel_path": att["source_rel_path"]}
                        if "source_rel_path" in att
                        else {}
                    ),
                    "target_rel_path": att["target_rel_path"],
                    "media_type": att["media_type"],
                    "size_bytes": att["size_bytes"],
                    "copy_mode": att["copy_mode"],
                }
            )

        # --- Compute proposal fingerprint ---
        proposal_fp = compute_proposal_fingerprint(
            source_record_fingerprint=src_record_fp,
            target_rel_path=target_rel_path,
            title=journal_spec.get("title", ""),
            date=journal_spec.get("date", ""),
            topic=journal_spec.get("topic", ""),
            tags=journal_spec.get("tags", []),
            content=journal_spec.get("content", ""),
            attachment_fingerprints=att_fingerprints,
        )
        proposal_fingerprints.append(proposal_fp)

        # --- Conflict detection ---
        proposal_conflicts: list[dict[str, Any]] = []
        target_abs = data_dir / target_rel_path
        if target_abs.exists():
            conflict_entry = {
                "type": "existing_path",
                "target_rel_path": target_rel_path,
                "message": (f"Target path already exists: {target_rel_path}"),
            }
            if adapter_id == "media.photo_timeline":
                conflict_entry.update(
                    {
                        "code": "PHOTO_TARGET_PATH_CONFLICT",
                        "severity": "conflict",
                        "runnable": False,
                    }
                )
            proposal_conflicts.append(conflict_entry)
            all_conflicts.append(conflict_entry)

        for att_output in att_outputs:
            att_target_rel = att_output["target_rel_path"]
            att_target_abs = data_dir / att_target_rel
            if att_target_abs.exists():
                conflict_entry = {
                    "type": "existing_path",
                    "target_rel_path": att_target_rel,
                    "message": f"Target path already exists: {att_target_rel}",
                }
                if adapter_id == "media.photo_timeline":
                    conflict_entry.update(
                        {
                            "code": "PHOTO_TARGET_PATH_CONFLICT",
                            "severity": "conflict",
                            "runnable": False,
                        }
                    )
                proposal_conflicts.append(conflict_entry)
                all_conflicts.append(conflict_entry)

        # --- Build proposal output ---
        proposal_id = f"prop_{proposal_fp.removeprefix('sha256:')[:20]}"

        # Collect per-record warnings and conflicts from the source record
        record_warnings: list[dict[str, Any]] = record.get("warnings", [])
        record_conflicts: list[dict[str, Any]] = record.get("conflicts", [])

        proposals.append(
            {
                "proposal_id": proposal_id,
                "source_record_id": src_record_id,
                "source_record_fingerprint": src_record_fp,
                "proposal_fingerprint": proposal_fp,
                "journal": {
                    "target_rel_path": target_rel_path,
                    "title": journal_spec.get("title", ""),
                    "date": journal_spec.get("date", ""),
                    "topic": journal_spec.get("topic", ""),
                    "tags": journal_spec.get("tags", []),
                    "content": journal_spec.get("content", ""),
                },
                "attachments": att_outputs,
                "conflicts": proposal_conflicts + record_conflicts,
                "warnings": record_warnings,
            }
        )
        all_warnings.extend(record_warnings)
        all_conflicts.extend(record_conflicts)

        # Track files for write-set preview
        all_create_files.append(target_rel_path)
        for att in att_outputs:
            all_create_files.append(att["target_rel_path"])

    # --- Compute plan-level fingerprints ---
    src_fp = compute_source_fingerprint(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        normalized_import_options_hash=DEFAULT_NORMALIZED_IMPORT_OPTIONS_HASH,
        source_record_fingerprints=source_record_fingerprints,
    )

    plan_fp = compute_plan_fingerprint(
        schema_version=PLAN_SCHEMA_VERSION,
        source_fingerprint=src_fp,
        proposal_fingerprints=proposal_fingerprints,
        normalized_write_policy_hash=DEFAULT_NORMALIZED_WRITE_POLICY_HASH,
    )

    idem_key = compute_idempotency_key(
        source_fingerprint=src_fp,
        plan_fingerprint=plan_fp,
        normalized_target_root_identity=str(data_dir.resolve()),
    )

    # --- Derive import_id ---
    date_part = datetime.date.today().strftime("%Y%m%d")
    hash_part = idem_key.removeprefix("sha256:")[:12]
    import_id = f"imp_{date_part}_{hash_part}"

    # --- Build plan data ---
    plan_data: dict[str, Any] = {
        "import_id": import_id,
        "schema_version": PLAN_SCHEMA_VERSION,
        "dry_run": True,
        "source": {
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "input_label": input_label,
            "source_fingerprint": src_fp,
            "record_count": len(records),
            "sensitive_paths_redacted": True,
        },
        "plan_fingerprint": plan_fp,
        "idempotency_key": idem_key,
        "summary": {
            "proposed_journal_count": len(records),
            "proposed_attachment_count": total_attachments,
            "conflict_count": len(all_conflicts),
            "warning_count": len(all_warnings),
        },
        "proposals": proposals,
        "write_set_preview": {
            "create_files": sorted(all_create_files),
            "update_files": [],
            "delete_files": [],
        },
        "conflicts": all_conflicts,
        "warnings": all_warnings,
    }

    _print_json(success_envelope("import.plan", plan_data))


# ---------------------------------------------------------------------------
# Run command (S3)
# ---------------------------------------------------------------------------


def _cmd_run(args: argparse.Namespace) -> None:
    """Implement ``import run`` (PRD §8)."""
    result = execute_run(
        plan_path=args.plan,
        confirm_id=args.confirm,
        data_dir=get_user_data_dir(),
        source_root=args.source_root,
    )

    if result["success"]:
        _print_json(success_envelope("import.run", result["data"]))
    else:
        err = result["error"]
        _print_json(
            error_envelope(
                "import.run",
                err["code"],
                err["message"],
                err.get("details", {}),
                retryable=err.get("retryable", False),
            )
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Status command (S3)
# ---------------------------------------------------------------------------


def _cmd_status(args: argparse.Namespace) -> None:
    """Implement ``import status`` (PRD §10)."""
    result = query_status(
        import_id=args.import_id,
        data_dir=get_user_data_dir(),
    )

    if result["success"]:
        _print_json(success_envelope("import.status", result["data"]))
    else:
        err = result["error"]
        _print_json(
            error_envelope(
                "import.status",
                err["code"],
                err["message"],
                err.get("details", {}),
                retryable=err.get("retryable", False),
            )
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Rollback command (S4)
# ---------------------------------------------------------------------------


def _cmd_rollback(args: argparse.Namespace) -> None:
    """Implement ``import rollback`` (PRD §10)."""
    result = execute_rollback(
        import_id=args.import_id,
        data_dir=get_user_data_dir(),
    )

    if result["success"]:
        _print_json(success_envelope("import.rollback", result["data"]))
    else:
        err = result["error"]
        _print_json(
            error_envelope(
                "import.rollback",
                err["code"],
                err["message"],
                err.get("details", {}),
                retryable=err.get("retryable", False),
            )
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Not-yet-implemented subcommand stubs
# ---------------------------------------------------------------------------

_NOT_IMPLEMENTED: dict[str, tuple[str, str]] = {}


def _cmd_not_implemented(subcommand: str) -> None:
    code, message = _NOT_IMPLEMENTED[subcommand]
    _print_json(
        error_envelope(
            f"import.{subcommand}",
            code,
            message,
            {"subcommand": subcommand},
            retryable=False,
        )
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="life-index import",
        description="Import provider: plan, run, status, and rollback.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # --- plan ---
    plan_p = sub.add_parser("plan", help="Dry-run import plan.")
    plan_p.add_argument(
        "--source",
        required=True,
        help="Source adapter id (e.g. fixture.import_records).",
    )
    plan_p.add_argument(
        "--input",
        required=True,
        help="Path to source data or fixture file.",
    )
    plan_p.add_argument(
        "--json",
        action="store_true",
        help="Output JSON (always true for programmatic callers).",
    )

    # --- run ---
    run_p = sub.add_parser("run", help="Execute a confirmed import plan.")
    run_p.add_argument("--plan", required=True, help="Path to plan JSON.")
    run_p.add_argument("--confirm", required=False, default=None, help="import_id to confirm.")
    run_p.add_argument(
        "--source-root",
        required=False,
        default=None,
        help="Optional source root for adapters that copy original attachment bytes.",
    )
    run_p.add_argument("--json", action="store_true")

    # --- status ---
    status_p = sub.add_parser("status", help="Query import job status.")
    status_p.add_argument("--import-id", required=True, help="Import job id.")
    status_p.add_argument("--json", action="store_true")

    # --- rollback ---
    rb_p = sub.add_parser("rollback", help="Rollback an import job.")
    rb_p.add_argument("--import-id", required=True, help="Import job id.")
    rb_p.add_argument("--json", action="store_true")

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()

    if args.subcommand == "plan":
        _cmd_plan(args)
    elif args.subcommand == "run":
        _cmd_run(args)
    elif args.subcommand == "status":
        _cmd_status(args)
    elif args.subcommand == "rollback":
        _cmd_rollback(args)
    elif args.subcommand in _NOT_IMPLEMENTED:
        _cmd_not_implemented(args.subcommand)
    else:
        # Should not happen (argparse validates subcommand).
        _print_json(
            error_envelope(
                "import",
                "IMPORT_INTERNAL_ERROR",
                f"Unknown subcommand: {args.subcommand}",
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
