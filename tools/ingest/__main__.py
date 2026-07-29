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

from tools.ingest.runner import (
    ImportLedgerCorruptError,
    _read_ledger,
    _read_rollback_manifest,
    execute_run,
)
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
    group_source_fingerprint,
)
from tools.ingest.adapters.photo_timeline import scan_photo_directory
from tools.ingest import review as review_module
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
# Photo proposal aggregation (additive, M7 historical photo cold-start)
# ---------------------------------------------------------------------------

# Conflict codes that mark a photo's capture time as unresolved. Such records
# cannot be grouped into a per-day proposal and remain individual ``pending``
# proposals whose conflict blocks the run until the user resolves the date.
_PHOTO_CAPTURE_CONFLICT_CODES = frozenset(
    {"PHOTO_CAPTURE_TIME_MISSING", "PHOTO_CAPTURE_TIME_AMBIGUOUS"}
)


def _collect_known_attachment_shas(data_dir: Path) -> set[str]:
    """Return attachment content SHAs already claimed by the import authority.

    Read-only scan of the import ledger authority. Two sources:

    - Committed child/legacy jobs: the attachment ``sha256_after`` from each
      rollback manifest. Photo attachments are byte-copied, so the stored hash
      equals the original source content SHA.
    - Parent review jobs: the ``source_sha256`` of attachments in proposals
      whose authoritative state is confirmed/batching/imported
      (``DEDUP_STATES``). This keeps a queued-but-not-yet-imported photo from
      being re-proposed on rescan, and keeps a rolled-back-to-confirmed photo
      excluded. Rolled-back proposals project to ``confirmed``, so they remain
      in the dedup set. Same name with different bytes stays distinct.
    """
    known: set[str] = set()
    ledger = _read_ledger(data_dir)
    jobs = ledger.get("jobs", {})
    if not isinstance(jobs, dict):
        return known
    review_parents: list[str] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        if job.get("state") == "committed":
            manifest = _read_rollback_manifest(data_dir, job_id)
            if manifest:
                for entry in manifest.get("created_files", []):
                    if entry.get("kind") == "attachment":
                        sha = entry.get("sha256_after")
                        if sha:
                            known.add(sha)
        elif job.get("kind") == "review":
            review_parents.append(job_id)

    dedup_states = review_module.DEDUP_STATES
    for parent_id in review_parents:
        proposal_states = (jobs.get(parent_id) or {}).get("proposal_states", {}) or {}
        plan = review_module.read_review_plan(data_dir, parent_id)
        if not plan:
            continue
        for proposal in plan.get("proposals", []) or []:
            if not isinstance(proposal, dict):
                continue
            if proposal_states.get(proposal.get("proposal_id", "")) not in dedup_states:
                continue
            for att in proposal.get("attachments", []) or []:
                sha = att.get("source_sha256")
                if sha:
                    known.add(sha)
    return known


def _group_source_fingerprint(member_fingerprints: list[str]) -> str:
    """Delegate to :func:`tools.ingest.fingerprint.group_source_fingerprint`."""
    return group_source_fingerprint(member_fingerprints)


def _photo_record_is_unresolved(record: dict[str, Any]) -> bool:
    """True when a photo record has an unresolved capture-time conflict."""
    for conflict in record.get("conflicts", []):
        if conflict.get("code") in _PHOTO_CAPTURE_CONFLICT_CODES:
            return True
    return False


def _build_photo_proposals(  # noqa: C901
    records: list[dict[str, Any]],
    data_dir: Path,
    used_seqs: dict[str, int],
    proposals: list[dict[str, Any]],
    all_create_files: list[str],
    source_record_fingerprints: list[str],
    proposal_fingerprints: list[str],
    all_warnings: list[dict[str, Any]],
    all_conflicts: list[dict[str, Any]],
) -> int:
    """Aggregate photo records into per-day proposals (additive M7).

    Resolved photos (a trustworthy EXIF capture date, no capture-time conflict)
    are grouped by calendar date into a single multi-attachment proposal per
    day. Unresolved photos (missing/ambiguous capture time) become individual
    ``pending`` proposals whose conflict blocks the run.

    Mutates the passed-in accumulators (``proposals``, ``all_create_files``,
    ``source_record_fingerprints``, ``proposal_fingerprints``, ``all_warnings``,
    ``all_conflicts``) and returns the total attachment count.
    """
    total_attachments = 0

    resolved_groups: dict[str, list[dict[str, Any]]] = {}
    unresolved: list[dict[str, Any]] = []

    for record in records:
        # Every record contributes its source-record fingerprint to the
        # plan-level source fingerprint (scan authority), independent of how
        # records are later grouped into proposals.
        source_record_fingerprints.append(record["source_record_fingerprint"])
        if _photo_record_is_unresolved(record):
            unresolved.append(record)
        else:
            date = record.get("journal", {}).get("date", "")
            resolved_groups.setdefault(date, []).append(record)

    def _member_sort_key(rec: dict[str, Any]) -> str:
        facts = rec.get("source_facts") or {}
        return str(facts.get("source_rel_path") or rec.get("source_record_id", ""))

    def _emit(
        members: list[dict[str, Any]],
        date: str,
        title: str,
        content: str,
        date_resolution: dict[str, Any] | None = None,
    ) -> None:
        nonlocal total_attachments
        members_sorted = sorted(members, key=_member_sort_key)

        # --- Attachments (concatenated, deterministic order) ---
        att_fingerprints: list[str] = []
        att_outputs: list[dict[str, Any]] = []
        for member in members_sorted:
            for att in member.get("attachments", []):
                att_fp = compute_attachment_fingerprint(
                    attachment_id=att["attachment_id"],
                    source_sha256=att["source_sha256"],
                    target_rel_path=att["target_rel_path"],
                    media_type=att["media_type"],
                    size_bytes=att["size_bytes"],
                    copy_mode=att["copy_mode"],
                )
                att_fingerprints.append(att_fp)
                att_out: dict[str, Any] = {
                    "attachment_id": att["attachment_id"],
                    "source_ref": att["source_ref"],
                    "source_sha256": att["source_sha256"],
                    "target_rel_path": att["target_rel_path"],
                    "media_type": att["media_type"],
                    "size_bytes": att["size_bytes"],
                    "copy_mode": att["copy_mode"],
                }
                if "source_rel_path" in att:
                    att_out["source_rel_path"] = att["source_rel_path"]
                att_outputs.append(att_out)
                total_attachments += 1

        # --- Journal target path ---
        # An empty date (unresolved capture time) defers target allocation: no
        # sequence is consumed and the target stays empty until the user
        # resolves the date during review.
        if date:
            seq = _next_seq_for_date(date, data_dir, used_seqs)
            target_rel_path = _journal_target_rel_path(date, seq)
        else:
            target_rel_path = ""

        # --- Fingerprints ---
        member_fps = [m["source_record_fingerprint"] for m in members_sorted]
        group_fp = _group_source_fingerprint(member_fps)
        tags = ["imported", "photo"]
        proposal_fp = compute_proposal_fingerprint(
            source_record_fingerprint=group_fp,
            target_rel_path=target_rel_path,
            title=title,
            date=date,
            topic="life",
            tags=tags,
            content=content,
            attachment_fingerprints=att_fingerprints,
        )
        proposal_id = f"prop_{proposal_fp.removeprefix('sha256:')[:20]}"
        primary_id = members_sorted[0]["source_record_id"]

        # --- Conflicts: target-path conflicts + member conflicts ---
        prop_conflicts: list[dict[str, Any]] = []
        if target_rel_path and (data_dir / target_rel_path).exists():
            prop_conflicts.append(
                {
                    "type": "existing_path",
                    "target_rel_path": target_rel_path,
                    "message": f"Target path already exists: {target_rel_path}",
                    "code": "PHOTO_TARGET_PATH_CONFLICT",
                    "severity": "conflict",
                    "runnable": False,
                }
            )
        for att_out in att_outputs:
            if att_out.get("target_rel_path") and (data_dir / att_out["target_rel_path"]).exists():
                prop_conflicts.append(
                    {
                        "type": "existing_path",
                        "target_rel_path": att_out["target_rel_path"],
                        "message": f"Target path already exists: {att_out['target_rel_path']}",
                        "code": "PHOTO_TARGET_PATH_CONFLICT",
                        "severity": "conflict",
                        "runnable": False,
                    }
                )
        for member in members_sorted:
            for conflict in member.get("conflicts", []):
                prop_conflicts.append(dict(conflict))

        # --- Warnings: per-member ---
        member_warnings: list[dict[str, Any]] = []
        for member in members_sorted:
            for warning in member.get("warnings", []):
                member_warnings.append(dict(warning))

        # --- Immutable source facts (provenance) ---
        source_facts = [member["source_facts"] for member in members_sorted]

        proposals.append(
            {
                "proposal_id": proposal_id,
                "source_record_id": primary_id,
                "source_record_fingerprint": group_fp,
                "source_record_fingerprints": member_fps,
                "proposal_fingerprint": proposal_fp,
                "date_resolution": date_resolution or {"status": "unresolved", "date": ""},
                "journal": {
                    "target_rel_path": target_rel_path,
                    "title": title,
                    "date": date,
                    "topic": "life",
                    "tags": tags,
                    "content": content,
                },
                "attachments": att_outputs,
                "source_facts": source_facts,
                "state": "pending",
                "conflicts": prop_conflicts,
                "warnings": member_warnings,
            }
        )

        # --- Accumulators ---
        proposal_fingerprints.append(proposal_fp)
        if target_rel_path:
            all_create_files.append(target_rel_path)
        for att_out in att_outputs:
            if att_out.get("target_rel_path"):
                all_create_files.append(att_out["target_rel_path"])
        for conflict in prop_conflicts:
            all_conflicts.append(conflict)
        for warning in member_warnings:
            all_warnings.append(warning)

    # --- Resolved day groups (deterministic date order) ---
    for date in sorted(resolved_groups):
        members = resolved_groups[date]
        count = len(members)
        if count == 1:
            journal = members[0].get("journal", {})
            title = journal.get("title", f"Photo import: {date}")
            content = journal.get("content", "")
        else:
            title = f"Photo import: {date} · {count} photos"
            content = (
                f"Imported {count} photos captured on {date}. "
                "Review and edit this entry before confirming."
            )
        date_resolution = members[0].get("date_resolution") or {
            "status": "exif_authoritative",
            "date": date,
        }
        _emit(members, date, title, content, date_resolution)

    # --- Unresolved individual proposals (deterministic rel-path order) ---
    for record in sorted(unresolved, key=_member_sort_key):
        journal = record.get("journal", {})
        date = journal.get("date", "")
        title = journal.get("title", "Photo import: missing capture time")
        content = journal.get("content", "")
        date_resolution = record.get("date_resolution") or {"status": "unresolved", "date": ""}
        _emit([record], date, title, content, date_resolution)

    return total_attachments


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
        scan_result = scan_photo_directory(
            input_path, known_shas=_collect_known_attachment_shas(data_dir)
        )
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

    is_photo = source_adapter == "media.photo_timeline"
    if is_photo:
        total_attachments = _build_photo_proposals(
            records,
            data_dir,
            used_seqs,
            proposals,
            all_create_files,
            source_record_fingerprints,
            proposal_fingerprints,
            all_warnings,
            all_conflicts,
        )

    for record in records:
        if is_photo:
            # Photo records are aggregated into per-day proposals by
            # ``_build_photo_proposals`` above; the generic 1:1 loop below only
            # handles fixture sources (whose golden snapshot must not change).
            continue
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
    """Implement ``import run`` (PRD §8).

    Two paths share this command: the legacy ``--plan/--confirm`` path
    (fixtures, unchanged) and the additive batch path ``--import-id`` for a
    parent review job.
    """
    if getattr(args, "import_id", None):
        result = review_module.run_batch(
            parent_id=args.import_id,
            data_dir=get_user_data_dir(),
            source_root=args.source_root,
        )
    else:
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
    """Implement ``import status`` (PRD §10).

    Additive: a parent review job returns proposal states / queue counts /
    active child / recovery; legacy and child-batch jobs keep the original
    status shape (``query_review_status`` delegates to ``query_status``).
    """
    result = review_module.query_review_status(
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
    """Implement ``import rollback`` (PRD §10).

    Additive: a parent review job cannot be rolled back as a whole
    (``IMPORT_ROLLBACK_PARENT_NOT_ALLOWED``); child batch / legacy jobs reuse
    the checksum-guarded rollback.
    """
    result = review_module.execute_review_rollback(
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
# Review queue commands (additive, M7)
# ---------------------------------------------------------------------------


def _emit(command: str, result: dict[str, Any]) -> None:
    """Print a review-module result dict as the standard import envelope."""
    if result["success"]:
        _print_json(success_envelope(command, result["data"]))
    else:
        err = result["error"]
        _print_json(
            error_envelope(
                command,
                err["code"],
                err["message"],
                err.get("details", {}),
                retryable=err.get("retryable", False),
            )
        )
        sys.exit(1)


def _cmd_confirm(args: argparse.Namespace) -> None:
    """``import confirm``: persist a review plan (``--plan``) or a single-proposal
    edit (``--edit``); the two are mutually exclusive."""
    data_dir = get_user_data_dir()
    if args.edit is not None:
        # --edit requires --import-id + --expected-queue-revision.
        if args.import_id is None or args.expected_queue_revision is None:
            _print_json(
                error_envelope(
                    "import.confirm",
                    review_module.IMPORT_REVIEW_EDIT_INVALID,
                    "--edit requires --import-id and --expected-queue-revision.",
                    {"import_id": args.import_id},
                    retryable=False,
                )
            )
            sys.exit(1)
        result = review_module.edit_review(
            edit_path=args.edit,
            parent_id=args.import_id,
            expected_queue_revision=args.expected_queue_revision,
            data_dir=data_dir,
        )
    else:
        result = review_module.confirm_review(
            plan_path=args.plan,
            data_dir=data_dir,
            source_root=args.source_root,
            parent_id_override=args.import_id,
        )
    _emit("import.confirm", result)


def _cmd_stage(args: argparse.Namespace) -> None:
    """``import stage``: stage a fresh pending review queue."""
    result = review_module.stage_review(
        plan_path=args.plan,
        data_dir=get_user_data_dir(),
        source_root=args.source_root,
        parent_id_override=args.import_id,
    )
    _emit("import.stage", result)


def _cmd_review(args: argparse.Namespace) -> None:
    """``import review``: bounded, paginated read of a review queue."""
    result = review_module.review_queue(
        parent_id=args.import_id,
        data_dir=get_user_data_dir(),
        offset=args.offset,
        limit=args.limit,
        states=args.state,
    )
    _emit("import.review", result)


def _cmd_reviews(args: argparse.Namespace) -> None:
    """``import reviews``: discover persisted parent review jobs."""
    result = review_module.list_reviews(
        data_dir=get_user_data_dir(),
        after=args.after,
        limit=args.limit,
    )
    _emit("import.reviews", result)


def _cmd_validate(args: argparse.Namespace) -> None:
    """``import validate``: canonical readable dir + root identity fingerprint."""
    result = review_module.validate_source_root(args.source_root)
    _emit("import.validate", result)


def _cmd_rebind(args: argparse.Namespace) -> None:
    """``import rebind``: re-validate a locator's root identity for a parent."""
    result = review_module.rebind_source_root(
        parent_id=args.import_id,
        source_root=args.source_root,
        data_dir=get_user_data_dir(),
    )
    _emit("import.rebind", result)


def _cmd_preview(args: argparse.Namespace) -> None:
    """``import preview``: read-only attachment byte/metadata streaming."""
    result = review_module.preview_attachment(
        parent_id=args.import_id,
        attachment_id=args.attachment,
        data_dir=get_user_data_dir(),
        source_root=args.source_root,
        output=args.output,
        metadata_output=args.metadata_output,
        proposal_id=args.proposal_id,
    )
    if not result["success"]:
        _emit("import.preview", result)
        return
    data = result["data"]
    # preview_attachment already honoured --metadata-output; here we only emit
    # the bytes: raw to stdout for `--output -`, else to the requested path with
    # a JSON acknowledgement envelope on stdout.
    out = args.output
    if out in (None, "", "-"):
        sys.stdout.buffer.write(data["bytes"])
    else:
        Path(out).write_bytes(data["bytes"])
        _print_json(
            success_envelope("import.preview", {k: v for k, v in data.items() if k != "bytes"})
        )


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
    run_p.add_argument(
        "--plan", required=False, default=None, help="Path to plan JSON (legacy path)."
    )
    run_p.add_argument(
        "--import-id",
        required=False,
        default=None,
        help="Parent review job id (additive batch path).",
    )
    run_p.add_argument(
        "--confirm", required=False, default=None, help="import_id to confirm (legacy path)."
    )
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

    # --- confirm (additive): --plan (legacy/stage) XOR --edit (single-proposal) ---
    confirm_p = sub.add_parser("confirm", help="Persist a photo review plan (review queue).")
    confirm_mx = confirm_p.add_mutually_exclusive_group(required=True)
    confirm_mx.add_argument("--plan", default=None, help="Path to review plan JSON.")
    confirm_mx.add_argument(
        "--edit", default=None, help="Path to an import_review_edit.v1 JSON (single-proposal edit)."
    )
    confirm_p.add_argument(
        "--source-root", required=False, default=None, help="Source root directory."
    )
    confirm_p.add_argument(
        "--import-id", required=False, default=None, help="Override parent review job id."
    )
    confirm_p.add_argument(
        "--expected-queue-revision",
        type=int,
        default=None,
        help="Client concurrency token (required with --edit).",
    )
    confirm_p.add_argument("--json", action="store_true")

    # --- stage (additive): fresh pending review queue ---
    stage_p = sub.add_parser("stage", help="Stage a fresh pending photo review queue.")
    stage_p.add_argument("--plan", required=True, help="Path to review plan JSON.")
    stage_p.add_argument("--source-root", required=True, help="Source root directory.")
    stage_p.add_argument(
        "--import-id", required=False, default=None, help="Override parent review job id."
    )
    stage_p.add_argument("--json", action="store_true")

    # --- review (additive): bounded read of a review queue ---
    review_p = sub.add_parser("review", help="Bounded read of a review queue.")
    review_p.add_argument("--import-id", required=True, help="Parent review job id.")
    review_p.add_argument("--offset", type=int, default=0, help="Zero-based page offset.")
    review_p.add_argument("--limit", type=int, default=20, help="Page size (clamped to 1..100).")
    review_p.add_argument(
        "--state",
        action="append",
        default=None,
        help="Filter by proposal state (repeatable).",
    )
    review_p.add_argument("--json", action="store_true")

    # --- reviews (additive): discover persisted review jobs ---
    reviews_p = sub.add_parser("reviews", help="Discover persisted parent review jobs.")
    reviews_p.add_argument("--after", default=None, help="Exclusive cursor import_id.")
    reviews_p.add_argument("--limit", type=int, default=20, help="Page size (clamped to 1..100).")
    reviews_p.add_argument("--json", action="store_true")

    # --- validate (additive) ---
    validate_p = sub.add_parser("validate", help="Validate a source root and return its identity.")
    validate_p.add_argument("--source-root", required=True, help="Source root directory.")
    validate_p.add_argument("--json", action="store_true")

    # --- rebind (additive) ---
    rebind_p = sub.add_parser("rebind", help="Re-validate a locator's root identity for a parent.")
    rebind_p.add_argument("--import-id", required=True, help="Parent review job id.")
    rebind_p.add_argument("--source-root", required=True, help="Source root directory to rebind.")
    rebind_p.add_argument("--json", action="store_true")

    # --- preview (additive) ---
    preview_p = sub.add_parser("preview", help="Read-only preview of an attachment (review queue).")
    preview_p.add_argument("--import-id", required=True, help="Parent review job id.")
    preview_p.add_argument("--attachment", required=True, help="Attachment id to preview.")
    preview_p.add_argument(
        "--proposal-id",
        required=False,
        default=None,
        help="Pin the attachment to a proposal (enables deselected-attachment preview).",
    )
    preview_p.add_argument(
        "--source-root", required=False, default=None, help="Source root directory."
    )
    preview_p.add_argument(
        "--output", required=False, default=None, help="- for stdout raw bytes, or an output path."
    )
    preview_p.add_argument(
        "--metadata-output",
        required=False,
        default=None,
        help="Path to write preview metadata JSON.",
    )
    preview_p.add_argument("--json", action="store_true")

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

    try:
        if args.subcommand == "plan":
            _cmd_plan(args)
        elif args.subcommand == "run":
            _cmd_run(args)
        elif args.subcommand == "status":
            _cmd_status(args)
        elif args.subcommand == "rollback":
            _cmd_rollback(args)
        elif args.subcommand == "confirm":
            _cmd_confirm(args)
        elif args.subcommand == "stage":
            _cmd_stage(args)
        elif args.subcommand == "review":
            _cmd_review(args)
        elif args.subcommand == "reviews":
            _cmd_reviews(args)
        elif args.subcommand == "validate":
            _cmd_validate(args)
        elif args.subcommand == "rebind":
            _cmd_rebind(args)
        elif args.subcommand == "preview":
            _cmd_preview(args)
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
    except ImportLedgerCorruptError as exc:
        _print_json(
            error_envelope(
                "import",
                "IMPORT_LEDGER_CORRUPT",
                "The import ledger is malformed or unreadable; no state was changed.",
                {"reason": exc.reason},
                retryable=False,
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
