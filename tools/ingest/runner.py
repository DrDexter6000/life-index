"""Core run/status orchestration for the import provider (PRD §8-§10).

Implements ``execute_run`` (write proposal files, create rollback manifest,
update ledger) and ``query_status`` (read ledger + manifest, return status).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from tools.ingest.fingerprint import (
    compute_attachment_fingerprint,
    compute_idempotency_key,
    compute_plan_fingerprint,
    compute_proposal_fingerprint,
    compute_source_fingerprint,
)
from tools.ingest.schemas import (
    DEFAULT_NORMALIZED_IMPORT_OPTIONS_HASH,
    DEFAULT_NORMALIZED_WRITE_POLICY_HASH,
    LEDGER_SCHEMA_VERSION,
    PLAN_SCHEMA_VERSION,
    ROLLBACK_MANIFEST_SCHEMA_VERSION,
    ROLLBACK_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    STATUS_SCHEMA_VERSION,
)

# ---------------------------------------------------------------------------
# execute_run
# ---------------------------------------------------------------------------


def execute_run(  # noqa: C901
    plan_path: str,
    confirm_id: str,
    data_dir: Path,
    source_root: str | None = None,
) -> dict[str, Any]:
    """Execute a confirmed import plan (PRD §8).

    Returns a dict with ``success`` (bool) and either ``data`` or ``error``.
    The caller wraps this into the standard envelope.
    """
    # --- 1. Read and parse plan JSON ---
    plan_file = Path(plan_path)
    if not plan_file.exists():
        return _err(
            "IMPORT_PLAN_INVALID",
            f"Plan file not found: {plan_path}",
            {"plan_path": plan_path},
            retryable=False,
        )

    try:
        plan_text = plan_file.read_text(encoding="utf-8")
        plan: dict[str, Any] = json.loads(plan_text)
    except (json.JSONDecodeError, OSError) as exc:
        return _err(
            "IMPORT_PLAN_INVALID",
            f"Cannot parse plan file: {exc}",
            {"plan_path": plan_path},
            retryable=False,
        )

    # --- 2. Validate --confirm ---
    plan_import_id = plan.get("import_id", "")
    if not confirm_id:
        return _err(
            "IMPORT_CONFIRMATION_REQUIRED",
            "The --confirm flag is required for import run.",
            {"import_id": plan_import_id},
            retryable=False,
        )
    if confirm_id != plan_import_id:
        return _err(
            "IMPORT_CONFIRMATION_REQUIRED",
            f"Confirm id '{confirm_id}' does not match plan import_id '{plan_import_id}'.",
            {"import_id": plan_import_id, "confirm_id": confirm_id},
            retryable=False,
        )

    # --- 3. Validate plan schema ---
    plan_fingerprint = plan.get("plan_fingerprint")
    idempotency_key = plan.get("idempotency_key")

    if plan_fingerprint is None or idempotency_key is None:
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan is missing required fingerprints (plan_fingerprint or idempotency_key is null).",
            {
                "plan_fingerprint": plan_fingerprint,
                "idempotency_key": idempotency_key,
            },
            retryable=False,
        )

    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        return _err(
            "IMPORT_PLAN_SCHEMA_UNSUPPORTED",
            f"Unsupported plan schema version: {plan.get('schema_version')}",
            {"schema_version": plan.get("schema_version")},
            retryable=False,
        )

    if plan.get("dry_run") is not True:
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan must have dry_run=true to be executed.",
            {"dry_run": plan.get("dry_run")},
            retryable=False,
        )

    proposals = plan.get("proposals", [])
    if not isinstance(proposals, list):
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan proposals must be a list.",
            {"field": "proposals"},
            retryable=False,
        )

    unresolved_conflicts = _collect_unresolved_conflicts(plan, proposals)
    if unresolved_conflicts:
        return _err(
            "IMPORT_PLAN_CONFLICTS_UNRESOLVED",
            "Plan has unresolved conflicts and cannot be run.",
            {"conflicts": unresolved_conflicts},
            retryable=False,
        )

    integrity_error = _validate_plan_integrity(plan, proposals, data_dir)
    if integrity_error is not None:
        return integrity_error

    # --- 4. Idempotency check ---
    ledger = _read_ledger(data_dir)
    idem_index: dict[str, str] = ledger.get("idempotency_index", {})

    if idempotency_key in idem_index:
        existing_import_id = idem_index[idempotency_key]
        if existing_import_id == plan_import_id:
            existing_job = ledger.get("jobs", {}).get(plan_import_id)
            if existing_job:
                existing_state = existing_job.get("state", "")
                existing_manifest = _read_rollback_manifest(data_dir, plan_import_id)

                if existing_state == "committed" and existing_manifest:
                    # Only committed jobs may return already_committed
                    return _ok(
                        {
                            "import_id": plan_import_id,
                            "schema_version": RUN_SCHEMA_VERSION,
                            "state": "already_committed",
                            "idempotency_key": idempotency_key,
                            "plan_fingerprint": plan_fingerprint,
                            "created_files": existing_manifest.get("created_files", []),
                            "created_journal_count": sum(
                                1
                                for f in existing_manifest.get("created_files", [])
                                if f.get("kind") == "journal"
                            ),
                            "created_attachment_count": sum(
                                1
                                for f in existing_manifest.get("created_files", [])
                                if f.get("kind") == "attachment"
                            ),
                            "rollback_manifest_rel_path": existing_job.get(
                                "rollback_manifest_rel_path", ""
                            ),
                            "post_run_actions": {
                                "index_rebuild_recommended": True,
                            },
                        }
                    )

                if existing_state == "partially_committed":
                    # Return the partial state with existing manifest evidence
                    return _ok(
                        {
                            "import_id": plan_import_id,
                            "schema_version": RUN_SCHEMA_VERSION,
                            "state": "partially_committed",
                            "idempotency_key": idempotency_key,
                            "plan_fingerprint": plan_fingerprint,
                            "created_files": (
                                existing_manifest.get("created_files", [])
                                if existing_manifest
                                else []
                            ),
                            "created_journal_count": sum(
                                1
                                for f in (
                                    existing_manifest.get("created_files", [])
                                    if existing_manifest
                                    else []
                                )
                                if f.get("kind") == "journal"
                            ),
                            "created_attachment_count": sum(
                                1
                                for f in (
                                    existing_manifest.get("created_files", [])
                                    if existing_manifest
                                    else []
                                )
                                if f.get("kind") == "attachment"
                            ),
                            "rollback_manifest_rel_path": existing_job.get(
                                "rollback_manifest_rel_path", ""
                            ),
                            "post_run_actions": {
                                "index_rebuild_recommended": True,
                            },
                        }
                    )

                if existing_state in ("running", "failed"):
                    # Non-committed states must NOT be reported as already_committed
                    return _err(
                        "IMPORT_JOB_NOT_COMMITTED",
                        (
                            f"Prior run exists for import_id '{plan_import_id}' "
                            f"with state '{existing_state}', which is not committed. "
                            f"Cannot re-execute."
                        ),
                        {
                            "import_id": plan_import_id,
                            "existing_state": existing_state,
                            "idempotency_key": idempotency_key,
                        },
                        retryable=False,
                    )
        else:
            return _err(
                "IMPORT_IDEMPOTENCY_CONFLICT",
                (
                    f"Idempotency key '{idempotency_key[:32]}…' already maps to "
                    f"import_id '{existing_import_id}', "
                    f"but plan has import_id '{plan_import_id}'."
                ),
                {
                    "idempotency_key": idempotency_key,
                    "existing_import_id": existing_import_id,
                    "plan_import_id": plan_import_id,
                },
                retryable=False,
            )

    # --- 5. Conflict and attachment-source checks ---
    attachment_source_paths: dict[tuple[int, int], Path] = {}
    source_root_path = Path(source_root).resolve() if source_root else None
    source_adapter_id = plan.get("source", {}).get("adapter_id", "")

    for proposal_index, proposal in enumerate(proposals):
        journal_rel = proposal.get("journal", {}).get("target_rel_path", "")
        if journal_rel:
            target = _resolve_confined_file_path(data_dir, journal_rel)
            if target is None:
                return _err(
                    "IMPORT_PLAN_INVALID",
                    f"Unsafe target path: {journal_rel}",
                    {"unsafe_paths": [journal_rel]},
                    retryable=False,
                )
            if target.exists():
                return _err(
                    "IMPORT_CONFLICT_EXISTING_PATH",
                    f"Target path already exists: {journal_rel}",
                    {"target_rel_path": journal_rel},
                    retryable=False,
                )
        for att_index, att in enumerate(proposal.get("attachments", [])):
            att_rel = att.get("target_rel_path", "")
            if att_rel:
                target = _resolve_confined_file_path(data_dir, att_rel)
                if target is None:
                    return _err(
                        "IMPORT_PLAN_INVALID",
                        f"Unsafe target path: {att_rel}",
                        {"unsafe_paths": [att_rel]},
                        retryable=False,
                    )
                if target.exists():
                    return _err(
                        "IMPORT_CONFLICT_EXISTING_PATH",
                        f"Target path already exists: {att_rel}",
                        {"target_rel_path": att_rel},
                        retryable=False,
                    )

            source_rel = att.get("source_rel_path")
            if source_adapter_id == "media.photo_timeline" and not source_rel:
                return _err(
                    "IMPORT_PLAN_INVALID",
                    "Photo attachment is missing source_rel_path for byte copy.",
                    {"proposal_index": proposal_index, "attachment_index": att_index},
                    retryable=False,
                )
            if source_rel:
                if source_root_path is None:
                    return _err(
                        "IMPORT_SOURCE_UNREADABLE",
                        "Attachment source_root is required to copy original bytes.",
                        {
                            "proposal_index": proposal_index,
                            "attachment_index": att_index,
                            "source_rel_path": source_rel,
                        },
                        retryable=False,
                    )
                source_abs = _resolve_confined_source_path(source_root_path, source_rel)
                if source_abs is None or not source_abs.exists():
                    return _err(
                        "IMPORT_SOURCE_UNREADABLE",
                        f"Attachment source file not found: {source_rel}",
                        {
                            "proposal_index": proposal_index,
                            "attachment_index": att_index,
                            "source_rel_path": source_rel,
                        },
                        retryable=False,
                    )
                expected_sha = att.get("source_sha256", "")
                actual_sha = f"sha256:{_file_sha256(source_abs)}"
                if expected_sha != actual_sha:
                    return _err(
                        "IMPORT_SOURCE_UNREADABLE",
                        "Attachment source hash no longer matches the plan.",
                        {
                            "proposal_index": proposal_index,
                            "attachment_index": att_index,
                            "source_rel_path": source_rel,
                            "expected": expected_sha,
                            "actual": actual_sha,
                        },
                        retryable=False,
                    )
                expected_size = att.get("size_bytes")
                actual_size = source_abs.stat().st_size
                if expected_size is not None and actual_size != expected_size:
                    return _err(
                        "IMPORT_SOURCE_UNREADABLE",
                        "Attachment source size no longer matches the plan.",
                        {
                            "proposal_index": proposal_index,
                            "attachment_index": att_index,
                            "source_rel_path": source_rel,
                            "expected": expected_size,
                            "actual": actual_size,
                        },
                        retryable=False,
                    )
                attachment_source_paths[(proposal_index, att_index)] = source_abs

    # --- 6. Create ledger entry with state=running BEFORE durable writes (PRD §9) ---
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rollback_rel = f".life-index/import-jobs/{plan_import_id}/rollback-manifest.json"

    ledger_jobs: dict[str, Any] = ledger.get("jobs", {})
    ledger_jobs[plan_import_id] = {
        "state": "running",
        "idempotency_key": idempotency_key,
        "plan_fingerprint": plan_fingerprint,
        "rollback_manifest_rel_path": rollback_rel,
        "updated_at": now_iso,
    }
    ledger["jobs"] = ledger_jobs
    ledger["idempotency_index"][idempotency_key] = plan_import_id
    _write_ledger(data_dir, ledger)

    # --- 7. Initialize rollback manifest BEFORE durable writes (PRD §10) ---
    rollback_abs = data_dir / rollback_rel
    rollback_abs.parent.mkdir(parents=True, exist_ok=True)

    created_files: list[dict[str, Any]] = []
    journal_count = 0
    attachment_count = 0

    manifest: dict[str, Any] = {
        "schema_version": ROLLBACK_MANIFEST_SCHEMA_VERSION,
        "import_id": plan_import_id,
        "idempotency_key": idempotency_key,
        "plan_fingerprint": plan_fingerprint,
        "created_at": now_iso,
        "state": "running",
        "created_files": created_files,
        "preexisting_files": [],
        "errors": [],
    }
    _write_manifest(rollback_abs, manifest)

    # --- 8. Execute writes with incremental evidence (PRD §10) ---
    write_error: str | None = None
    try:
        for proposal_index, proposal in enumerate(proposals):
            journal_spec = proposal.get("journal", {})
            journal_rel = journal_spec.get("target_rel_path", "")
            if journal_rel:
                journal_abs = _resolve_confined_file_path(data_dir, journal_rel)
                if journal_abs is None:
                    raise RuntimeError(f"Unsafe target path: {journal_rel}")
                journal_abs.parent.mkdir(parents=True, exist_ok=True)

                # Build journal content with YAML frontmatter
                title = journal_spec.get("title", "")
                date = journal_spec.get("date", "")
                topic = journal_spec.get("topic", "")
                tags = journal_spec.get("tags", [])

                tags_yaml = json.dumps(tags)  # produces ["tag1","tag2"]
                content = journal_spec.get("content", "")

                journal_text = (
                    "---\n"
                    f'title: "{title}"\n'
                    f"date: {date}\n"
                    f"topic: {topic}\n"
                    f"tags: {tags_yaml}\n"
                    "---\n\n"
                    f"{content}\n"
                )
                journal_abs.write_text(journal_text, encoding="utf-8")

                sha256 = _file_sha256(journal_abs)
                size = journal_abs.stat().st_size

                file_entry = {
                    "kind": "journal",
                    "rel_path": journal_rel,
                    "sha256_after": f"sha256:{sha256}",
                    "size_bytes": size,
                    "created_by_import": True,
                }
                created_files.append(file_entry)
                journal_count += 1
                _write_manifest(rollback_abs, manifest)  # evidence as each file is created

            for att_index, att in enumerate(proposal.get("attachments", [])):
                att_rel = att.get("target_rel_path", "")
                if att_rel:
                    att_abs = _resolve_confined_file_path(data_dir, att_rel)
                    if att_abs is None:
                        raise RuntimeError(f"Unsafe target path: {att_rel}")
                    att_abs.parent.mkdir(parents=True, exist_ok=True)

                    source_abs = attachment_source_paths.get((proposal_index, att_index))
                    if source_abs is not None:
                        shutil.copyfile(source_abs, att_abs)
                    else:
                        # Fixture adapters may only provide contract metadata.
                        att_id = att.get("attachment_id", "")
                        att_abs.write_text(att_id, encoding="utf-8")

                    sha256 = _file_sha256(att_abs)
                    size = att_abs.stat().st_size

                    file_entry = {
                        "kind": "attachment",
                        "rel_path": att_rel,
                        "sha256_after": f"sha256:{sha256}",
                        "size_bytes": size,
                        "created_by_import": True,
                    }
                    created_files.append(file_entry)
                    attachment_count += 1
                    _write_manifest(rollback_abs, manifest)  # evidence as each file is created
    except (OSError, RuntimeError) as exc:
        write_error = str(exc)

    # --- 9. Finalize ledger and manifest ---
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if write_error is not None:
        # Partial failure: some files were created before the error
        if created_files:
            manifest["state"] = "partially_committed"
            manifest["errors"] = [write_error]
            _write_manifest(rollback_abs, manifest)

            ledger_jobs[plan_import_id]["state"] = "partially_committed"
            ledger_jobs[plan_import_id]["updated_at"] = now_iso
            _write_ledger(data_dir, ledger)

            return _ok(
                {
                    "import_id": plan_import_id,
                    "schema_version": RUN_SCHEMA_VERSION,
                    "state": "partially_committed",
                    "idempotency_key": idempotency_key,
                    "plan_fingerprint": plan_fingerprint,
                    "created_files": created_files,
                    "created_journal_count": journal_count,
                    "created_attachment_count": attachment_count,
                    "rollback_manifest_rel_path": rollback_rel,
                    "post_run_actions": {
                        "index_rebuild_recommended": True,
                    },
                }
            )
        else:
            # Failed before any file was created
            manifest["state"] = "failed"
            manifest["errors"] = [write_error]
            _write_manifest(rollback_abs, manifest)

            ledger_jobs[plan_import_id]["state"] = "failed"
            ledger_jobs[plan_import_id]["updated_at"] = now_iso
            _write_ledger(data_dir, ledger)

            return _err(
                "IMPORT_WRITE_FAILURE",
                f"Write failed before any file was created: {write_error}",
                {"import_id": plan_import_id},
                retryable=True,
            )

    # All writes succeeded — commit
    manifest["state"] = "committed"
    _write_manifest(rollback_abs, manifest)

    ledger_jobs[plan_import_id]["state"] = "committed"
    ledger_jobs[plan_import_id]["updated_at"] = now_iso
    _write_ledger(data_dir, ledger)

    # --- 10. Return success ---
    return _ok(
        {
            "import_id": plan_import_id,
            "schema_version": RUN_SCHEMA_VERSION,
            "state": "committed",
            "idempotency_key": idempotency_key,
            "plan_fingerprint": plan_fingerprint,
            "created_files": created_files,
            "created_journal_count": journal_count,
            "created_attachment_count": attachment_count,
            "rollback_manifest_rel_path": rollback_rel,
            "post_run_actions": {
                "index_rebuild_recommended": True,
            },
        }
    )


# ---------------------------------------------------------------------------
# query_status
# ---------------------------------------------------------------------------


def query_status(
    import_id: str,
    data_dir: Path,
) -> dict[str, Any]:
    """Return the status of an import job (PRD §10).

    Returns a dict with ``success`` (bool) and either ``data`` or ``error``.
    """
    ledger = _read_ledger(data_dir)
    jobs: dict[str, Any] = ledger.get("jobs", {})

    if import_id not in jobs:
        return _err(
            "IMPORT_JOB_NOT_FOUND",
            f"Import job not found: {import_id}",
            {"import_id": import_id},
            retryable=False,
        )

    ledger_entry = jobs[import_id]
    rollback_rel = ledger_entry.get("rollback_manifest_rel_path", "")
    manifest = _read_rollback_manifest(data_dir, import_id)

    # Derive counts from manifest
    planned_journals = 0
    created_journals = 0
    planned_attachments = 0
    created_attachments = 0

    if manifest:
        created_journals = sum(
            1 for f in manifest.get("created_files", []) if f.get("kind") == "journal"
        )
        created_attachments = sum(
            1 for f in manifest.get("created_files", []) if f.get("kind") == "attachment"
        )
        planned_journals = created_journals
        planned_attachments = created_attachments

    return _ok(
        {
            "import_id": import_id,
            "schema_version": STATUS_SCHEMA_VERSION,
            "state": ledger_entry.get("state", "committed"),
            "idempotency_key": ledger_entry.get("idempotency_key", ""),
            "plan_fingerprint": ledger_entry.get("plan_fingerprint", ""),
            "counts": {
                "planned_journals": planned_journals,
                "created_journals": created_journals,
                "planned_attachments": planned_attachments,
                "created_attachments": created_attachments,
            },
            "last_error": None,
            "rollback_available": bool(manifest and rollback_rel),
            "rollback_manifest_rel_path": rollback_rel,
        }
    )


# ---------------------------------------------------------------------------
# execute_rollback (S4)
# ---------------------------------------------------------------------------


def execute_rollback(
    import_id: str,
    data_dir: Path,
) -> dict[str, Any]:
    """Execute a checksum-guarded rollback for an import job (PRD §10).

    Returns a dict with ``success`` (bool) and either ``data`` or ``error``.
    The caller wraps this into the standard envelope.
    """
    # --- 1. Read ledger, find job ---
    ledger = _read_ledger(data_dir)
    jobs: dict[str, Any] = ledger.get("jobs", {})

    if import_id not in jobs:
        return _err(
            "IMPORT_JOB_NOT_FOUND",
            f"Import job not found: {import_id}",
            {"import_id": import_id},
            retryable=False,
        )

    job = jobs[import_id]
    current_state = job.get("state", "")

    # --- 2. Idempotent: already rolled back ---
    if current_state == "rolled_back":
        return _ok(
            {
                "import_id": import_id,
                "schema_version": ROLLBACK_SCHEMA_VERSION,
                "state": "rolled_back",
                "idempotency_key": job.get("idempotency_key", ""),
                "plan_fingerprint": job.get("plan_fingerprint", ""),
                "deleted_count": 0,
                "rollback_manifest_rel_path": job.get("rollback_manifest_rel_path", ""),
            }
        )

    # --- 3. Read rollback manifest ---
    manifest = _read_rollback_manifest(data_dir, import_id)
    if manifest is None:
        return _err(
            "IMPORT_ROLLBACK_MANIFEST_MISSING",
            f"Rollback manifest not found for import job: {import_id}",
            {"import_id": import_id},
            retryable=False,
        )

    rollback_rel = job.get("rollback_manifest_rel_path", "")
    manifest_abs = data_dir / rollback_rel

    # --- 4. First pass: verify all manifest paths are confined under data_dir ---
    unsafe_paths: list[str] = []
    safe_paths: dict[str, Path] = {}
    for file_entry in manifest.get("created_files", []):
        if not file_entry.get("created_by_import", False):
            continue
        rel_path = file_entry["rel_path"]
        safe_path = _resolve_confined_file_path(data_dir, rel_path)
        if safe_path is None:
            unsafe_paths.append(rel_path)
        else:
            safe_paths[rel_path] = safe_path

    if unsafe_paths:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        manifest["state"] = "rollback_failed"
        manifest["errors"] = [f"Unsafe path (traversal/absolute): {p}" for p in unsafe_paths]
        _write_manifest(manifest_abs, manifest)

        jobs[import_id]["state"] = "rollback_failed"
        jobs[import_id]["updated_at"] = now_iso
        _write_ledger(data_dir, ledger)

        return _err(
            "IMPORT_ROLLBACK_UNSAFE",
            (
                f"Rollback aborted: {len(unsafe_paths)} manifest path(s) "
                f"resolve outside the data directory."
            ),
            {"unsafe_paths": unsafe_paths},
            retryable=False,
        )

    # --- 5. Second pass: check all checksums (PRD §10) ---
    to_delete: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for file_entry in manifest.get("created_files", []):
        if not file_entry.get("created_by_import", False):
            continue

        rel_path = file_entry["rel_path"]
        expected_sha256 = file_entry["sha256_after"]
        file_path = safe_paths[rel_path]

        if not file_path.exists():
            # Already removed — idempotent, skip
            continue

        current_sha256 = f"sha256:{_file_sha256(file_path)}"
        if current_sha256 != expected_sha256:
            blocked.append(
                {
                    "rel_path": rel_path,
                    "expected_sha256": expected_sha256,
                    "current_sha256": current_sha256,
                }
            )
        else:
            to_delete.append(
                {
                    "rel_path": rel_path,
                    "path": file_path,
                    "kind": file_entry.get("kind", ""),
                }
            )

    # --- 6. If any blocked, refuse entire rollback (PRD §10) ---
    if blocked:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        manifest["state"] = "rollback_failed"
        manifest["errors"] = [
            (
                f"Checksum mismatch: {b['rel_path']} "
                f"expected {b['expected_sha256']} "
                f"got {b['current_sha256']}"
            )
            for b in blocked
        ]
        _write_manifest(manifest_abs, manifest)

        jobs[import_id]["state"] = "rollback_failed"
        jobs[import_id]["updated_at"] = now_iso
        _write_ledger(data_dir, ledger)

        return _err(
            "IMPORT_ROLLBACK_CHECKSUM_MISMATCH",
            (f"Rollback blocked: {len(blocked)} file(s) have " f"checksum mismatches."),
            {"blocked_files": blocked},
            retryable=False,
        )

    # --- 7. Third pass: delete all matching files ---
    deleted_count = 0
    for entry in to_delete:
        entry["path"].unlink()
        deleted_count += 1

    # --- 8. Preserve manifest as audit evidence, update ledger ---
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest["state"] = "rolled_back"
    _write_manifest(manifest_abs, manifest)

    jobs[import_id]["state"] = "rolled_back"
    jobs[import_id]["updated_at"] = now_iso
    _write_ledger(data_dir, ledger)

    return _ok(
        {
            "import_id": import_id,
            "schema_version": ROLLBACK_SCHEMA_VERSION,
            "state": "rolled_back",
            "idempotency_key": job.get("idempotency_key", ""),
            "plan_fingerprint": job.get("plan_fingerprint", ""),
            "deleted_count": deleted_count,
            "rollback_manifest_rel_path": rollback_rel,
        }
    )


# ===================================================================
# Internal helpers
# ===================================================================


def _collect_unresolved_conflicts(
    plan: dict[str, Any],
    proposals: list[Any],
) -> list[dict[str, Any]]:
    """Return unresolved plan/proposal conflicts that make a plan unrunnable."""
    conflicts: list[dict[str, Any]] = []
    summary = plan.get("summary", {})
    conflict_count = summary.get("conflict_count", 0) if isinstance(summary, dict) else 0
    try:
        has_conflict_count = int(conflict_count or 0) > 0
    except (TypeError, ValueError):
        has_conflict_count = True

    top_level_conflicts = plan.get("conflicts", [])
    if isinstance(top_level_conflicts, list):
        conflicts.extend(c for c in top_level_conflicts if isinstance(c, dict))
    elif top_level_conflicts:
        conflicts.append({"source": "plan.conflicts", "value": str(top_level_conflicts)})

    for proposal in proposals:
        proposal_conflicts = proposal.get("conflicts", [])
        if isinstance(proposal_conflicts, list):
            conflicts.extend(c for c in proposal_conflicts if isinstance(c, dict))
        elif proposal_conflicts:
            conflicts.append(
                {
                    "source": "proposals[].conflicts",
                    "value": str(proposal_conflicts),
                }
            )

    if has_conflict_count and not conflicts:
        conflicts.append(
            {
                "source": "summary.conflict_count",
                "value": conflict_count,
            }
        )
    return conflicts


def _validate_plan_integrity(
    plan: dict[str, Any],
    proposals: list[Any],
    data_dir: Path,
) -> dict[str, Any] | None:
    """Recompute run-critical plan hashes and target confinement.

    ``import run`` consumes a user-provided JSON file, so it must not trust
    fingerprint fields emitted by ``import plan`` without recalculating them
    against the actual proposal content and target data directory.
    """
    mismatches: list[dict[str, Any]] = []
    unsafe_paths: list[str] = []
    source_record_fingerprints: list[str] = []
    proposal_fingerprints: list[str] = []

    source = plan.get("source", {})
    if not isinstance(source, dict):
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan source must be an object.",
            {"field": "source"},
            retryable=False,
        )

    try:
        adapter_id = source["adapter_id"]
        adapter_version = source["adapter_version"]
    except KeyError as exc:
        return _err(
            "IMPORT_PLAN_INVALID",
            f"Plan source is missing required field: {exc.args[0]}",
            {"field": f"source.{exc.args[0]}"},
            retryable=False,
        )

    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict):
            return _err(
                "IMPORT_PLAN_INVALID",
                "Every proposal must be an object.",
                {"proposal_index": index},
                retryable=False,
            )

        try:
            source_record_fp = proposal["source_record_fingerprint"]
            journal = proposal["journal"]
            attachments = proposal.get("attachments", [])
            journal_rel = journal["target_rel_path"]
        except (KeyError, TypeError) as exc:
            return _err(
                "IMPORT_PLAN_INVALID",
                f"Proposal is missing required field: {exc}",
                {"proposal_index": index},
                retryable=False,
            )

        source_record_fingerprints.append(source_record_fp)
        if _resolve_confined_file_path(data_dir, journal_rel) is None:
            unsafe_paths.append(journal_rel)

        attachment_fingerprints: list[str] = []
        for att_index, attachment in enumerate(attachments):
            try:
                attachment_rel = attachment["target_rel_path"]
                if _resolve_confined_file_path(data_dir, attachment_rel) is None:
                    unsafe_paths.append(attachment_rel)
                attachment_fingerprints.append(
                    compute_attachment_fingerprint(
                        attachment_id=attachment["attachment_id"],
                        source_sha256=attachment["source_sha256"],
                        target_rel_path=attachment_rel,
                        media_type=attachment["media_type"],
                        size_bytes=attachment["size_bytes"],
                        copy_mode=attachment["copy_mode"],
                    )
                )
            except (KeyError, TypeError) as exc:
                return _err(
                    "IMPORT_PLAN_INVALID",
                    f"Attachment is missing or has invalid field: {exc}",
                    {
                        "proposal_index": index,
                        "attachment_index": att_index,
                    },
                    retryable=False,
                )

        try:
            expected_proposal_fp = compute_proposal_fingerprint(
                source_record_fingerprint=source_record_fp,
                target_rel_path=journal_rel,
                title=journal.get("title", ""),
                date=journal.get("date", ""),
                topic=journal.get("topic", ""),
                tags=journal.get("tags", []),
                content=journal.get("content", ""),
                attachment_fingerprints=attachment_fingerprints,
            )
        except TypeError as exc:
            return _err(
                "IMPORT_PLAN_INVALID",
                f"Proposal fingerprint inputs are invalid: {exc}",
                {"proposal_index": index},
                retryable=False,
            )

        proposal_fingerprints.append(expected_proposal_fp)
        actual_proposal_fp = proposal.get("proposal_fingerprint")
        if actual_proposal_fp != expected_proposal_fp:
            mismatches.append(
                {
                    "field": "proposals[].proposal_fingerprint",
                    "proposal_index": index,
                    "expected": expected_proposal_fp,
                    "actual": actual_proposal_fp,
                }
            )

    if unsafe_paths:
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan contains target paths outside the data directory.",
            {"unsafe_paths": unsafe_paths},
            retryable=False,
        )

    expected_source_fp = compute_source_fingerprint(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        normalized_import_options_hash=DEFAULT_NORMALIZED_IMPORT_OPTIONS_HASH,
        source_record_fingerprints=source_record_fingerprints,
    )
    actual_source_fp = source.get("source_fingerprint")
    if actual_source_fp != expected_source_fp:
        mismatches.append(
            {
                "field": "source.source_fingerprint",
                "expected": expected_source_fp,
                "actual": actual_source_fp,
            }
        )

    expected_plan_fp = compute_plan_fingerprint(
        schema_version=PLAN_SCHEMA_VERSION,
        source_fingerprint=expected_source_fp,
        proposal_fingerprints=proposal_fingerprints,
        normalized_write_policy_hash=DEFAULT_NORMALIZED_WRITE_POLICY_HASH,
    )
    actual_plan_fp = plan.get("plan_fingerprint")
    if actual_plan_fp != expected_plan_fp:
        mismatches.append(
            {
                "field": "plan_fingerprint",
                "expected": expected_plan_fp,
                "actual": actual_plan_fp,
            }
        )

    expected_idempotency_key = compute_idempotency_key(
        source_fingerprint=expected_source_fp,
        plan_fingerprint=expected_plan_fp,
        normalized_target_root_identity=str(data_dir.resolve()),
    )
    actual_idempotency_key = plan.get("idempotency_key")
    if actual_idempotency_key != expected_idempotency_key:
        mismatches.append(
            {
                "field": "idempotency_key",
                "expected": expected_idempotency_key,
                "actual": actual_idempotency_key,
            }
        )

    if mismatches:
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan fingerprints do not match the proposed write content.",
            {"mismatches": mismatches},
            retryable=False,
        )
    return None


def _resolve_confined_file_path(data_dir: Path, rel_path: str) -> Path | None:
    """Return a resolved rollback file path only when it is confined.

    Rejects absolute *rel_path* values, traversal escapes (``../``), and
    any resolved target that is not a strict descendant of ``data_dir``. If the
    target currently exists, it must be a regular file.
    """
    if not rel_path:
        return None
    p = Path(rel_path)
    if p.is_absolute():
        return None
    resolved_data = data_dir.resolve()
    resolved_target = (data_dir / rel_path).resolve()
    if resolved_target == resolved_data:
        return None
    try:
        resolved_target.relative_to(resolved_data)
    except ValueError:
        return None
    if resolved_target.exists() and not resolved_target.is_file():
        return None
    return resolved_target


def _resolve_confined_source_path(source_root: Path, rel_path: str) -> Path | None:
    """Resolve a source-relative file path without allowing traversal escapes."""
    if not rel_path:
        return None
    p = Path(rel_path)
    if p.is_absolute():
        return None
    resolved_root = source_root.resolve()
    resolved_target = (source_root / rel_path).resolve()
    if resolved_target == resolved_root:
        return None
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError:
        return None
    if resolved_target.exists() and not resolved_target.is_file():
        return None
    return resolved_target


def _read_ledger(data_dir: Path) -> dict[str, Any]:
    """Read the import job ledger, returning defaults if it doesn't exist."""
    ledger_path = data_dir / ".life-index" / "import-jobs" / "ledger.json"
    if not ledger_path.exists():
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "jobs": {},
            "idempotency_index": {},
        }
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if isinstance(ledger, dict):
            return ledger
    except (json.JSONDecodeError, OSError):
        pass
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "jobs": {},
        "idempotency_index": {},
    }


def _write_ledger(data_dir: Path, ledger: dict[str, Any]) -> None:
    """Write the import job ledger."""
    ledger.setdefault("schema_version", LEDGER_SCHEMA_VERSION)
    ledger_path = data_dir / ".life-index" / "import-jobs" / "ledger.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Write the rollback manifest to the given path."""
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_rollback_manifest(data_dir: Path, import_id: str) -> dict[str, Any] | None:
    """Read the rollback manifest for an import job, or None."""
    manifest_path = data_dir / ".life-index" / "import-jobs" / import_id / "rollback-manifest.json"
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(manifest, dict):
            return manifest
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _file_sha256(path: Path) -> str:
    """Compute raw hex sha256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    """Return a success result dict."""
    return {"success": True, "data": data, "error": None}


def _err(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    """Return an error result dict."""
    return {
        "success": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "retryable": retryable,
        },
    }
