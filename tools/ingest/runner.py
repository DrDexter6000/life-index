"""Core run/status orchestration for the import provider (PRD §8-§10).

Implements ``execute_run`` (write proposal files, create rollback manifest,
update ledger) and ``query_status`` (read ledger + manifest, return status).
"""

from __future__ import annotations

import datetime
import functools
import hashlib
import inspect
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

from tools.ingest.fingerprint import (
    compute_attachment_fingerprint,
    compute_idempotency_key,
    compute_plan_fingerprint,
    compute_proposal_fingerprint,
    compute_source_fingerprint,
)
from tools.ingest.ids import import_id_invalid, validate_import_id
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
from tools.lib.config import FILE_LOCK_TIMEOUT_DEFAULT
from tools.lib.pending_writes import mark_pending
from tools.lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path


class ImportLedgerCorruptError(RuntimeError):
    """The durable import ledger exists but cannot be trusted or recovered."""

    def __init__(self, ledger_path: Path, reason: str):
        self.ledger_path = ledger_path
        self.reason = reason
        super().__init__(f"Import ledger is corrupt at {ledger_path}: {reason}")


_LEDGER_LOCK_TIMEOUT_SECONDS = 30.0
_LEDGER_LOCK_STACK: ContextVar[tuple[str, ...]] = ContextVar(
    "life_index_import_ledger_lock_stack", default=()
)
_F = TypeVar("_F", bound=Callable[..., Any])


def _ledger_path(data_dir: Path) -> Path:
    return data_dir / ".life-index" / "import-jobs" / "ledger.json"


def _ledger_lock_path(data_dir: Path) -> Path:
    return data_dir / ".life-index" / "import-jobs" / "ledger.lock"


def _assert_import_jobs_area_confined(data_dir: Path) -> None:
    """Prove the resolved import-jobs area is a strict descendant of the data dir.

    The durable ledger / manifest / staging area (``.life-index/import-jobs``) may
    itself be a planted junction/reparse/symlink that redirects outside the
    trusted data directory. Both ``data_dir`` and the area are resolved before a
    component-wise (``relative_to``) containment proof; any escape fails closed
    as an untrusted durable area (surfaced by the CLI as ``IMPORT_LEDGER_CORRUPT``)
    BEFORE the first byte of ledger / lock I/O. Legitimate areas — including a
    data dir that itself contains a symlink component, resolved on both sides —
    keep working.
    """
    resolved_data = data_dir.resolve()
    area = (data_dir / ".life-index" / "import-jobs").resolve()
    try:
        area.relative_to(resolved_data)
    except ValueError:
        raise ImportLedgerCorruptError(
            _ledger_path(data_dir), "import_jobs_area_not_confined"
        )


@contextmanager
def _ledger_transaction(data_dir: Path) -> Iterator[None]:
    """Hold the one cross-process import-ledger lock, re-entrantly per context.

    Lock order is always ledger lock first, then an optional per-parent
    ``review.lock``, then the shared journals lock when rollback reaches its
    final delete critical section. Public runner/review transactions enter here
    before taking narrower locks. Nested helpers reuse the outer ledger lock
    rather than trying to acquire the non-reentrant file lock again.
    """
    key = str(data_dir.resolve())
    stack = _LEDGER_LOCK_STACK.get()
    if key in stack:
        yield
        return

    # Prove the import-jobs area is confined before creating the cross-process
    # lock file inside it (the first durable byte of a mutation transaction).
    _assert_import_jobs_area_confined(data_dir)
    lock = FileLock(_ledger_lock_path(data_dir), timeout=_LEDGER_LOCK_TIMEOUT_SECONDS)
    with lock:
        token = _LEDGER_LOCK_STACK.set((*stack, key))
        try:
            yield
        finally:
            _LEDGER_LOCK_STACK.reset(token)


def _ledger_serialized(func: _F) -> _F:
    """Decorate a public ledger operation as one complete locked transaction."""
    signature = inspect.signature(func)

    @functools.wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        bound = signature.bind_partial(*args, **kwargs)
        data_dir = bound.arguments.get("data_dir")
        if not isinstance(data_dir, Path):
            raise TypeError("ledger-serialized operation requires data_dir: Path")
        with _ledger_transaction(data_dir):
            return func(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# execute_run
# ---------------------------------------------------------------------------


@_ledger_serialized
def execute_run(  # noqa: C901
    plan_path: str,
    confirm_id: Any,
    data_dir: Path,
    source_root: str | None = None,
) -> dict[str, Any]:
    """Execute a confirmed import plan (PRD §8).

    Returns a dict with ``success`` (bool) and either ``data`` or ``error``.
    The caller wraps this into the standard envelope.
    """
    if confirm_id is not None:
        invalid_reason = validate_import_id(confirm_id, allow_child=False)
        if invalid_reason is not None:
            return import_id_invalid(invalid_reason)

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

    # --- 2. Validate plan import_id, then --confirm compatibility ---
    plan_import_id = plan.get("import_id", "")
    invalid_reason = validate_import_id(plan_import_id, allow_child=False)
    if invalid_reason is not None:
        return import_id_invalid(invalid_reason)
    if confirm_id is None:
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
    # Prove the job manifest path resolves inside the data directory BEFORE any
    # ledger reservation or manifest init: a planted link at the derived job path
    # must fail closed with no reservation and no outside write. Use the resolved
    # path for every subsequent I/O (never re-join a second expression).
    rollback_abs = _resolve_confined_job_path(data_dir, rollback_rel)
    if rollback_abs is None:
        return _err(
            "IMPORT_WRITE_FAILURE",
            "Import job path is not confined to the data directory.",
            {"reason": "job_path_not_confined", "import_id": plan_import_id},
            retryable=False,
        )

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


@_ledger_serialized
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


@_ledger_serialized
def execute_rollback(
    import_id: str,
    data_dir: Path,
) -> dict[str, Any]:
    """Execute a checksum-guarded rollback for an import job (PRD §10).

    Returns a dict with ``success`` (bool) and either ``data`` or ``error``.
    The caller wraps this into the standard envelope.
    """
    invalid_reason = validate_import_id(import_id, allow_child=True)
    if invalid_reason is not None:
        return import_id_invalid(invalid_reason)

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
    # The stored locator is untrusted: a corrupt or hostile absolute/traversal
    # ``rollback_manifest_rel_path`` must fail closed before any manifest write.
    # Use the resolved path for all subsequent audit writes (never re-join).
    manifest_abs = _resolve_confined_job_path(data_dir, rollback_rel)
    if manifest_abs is None:
        return _err(
            "IMPORT_ROLLBACK_UNSAFE",
            "Rollback aborted: rollback manifest path is not confined to the data directory.",
            {"reason": "rollback_manifest_path_not_confined", "import_id": import_id},
            retryable=False,
        )

    # --- 4. First pass: verify all manifest paths are confined under data_dir ---
    unsafe_paths: list[str] = []
    invalid_ownership: list[str] = []
    safe_paths: dict[str, Path] = {}
    safe_staging_paths: dict[str, Path] = {}
    ownership_proofs: dict[str, dict[str, Any]] = {}
    for file_entry in manifest.get("created_files", []):
        if not file_entry.get("created_by_import", False):
            continue
        rel_path = file_entry.get("rel_path", "")
        safe_path = _resolve_confined_file_path(data_dir, rel_path)
        if safe_path is None:
            unsafe_paths.append(rel_path)
        else:
            safe_paths[rel_path] = safe_path
        proof = file_entry.get("ownership_proof")
        if proof is None:
            continue
        if not isinstance(proof, dict) or proof.get("method") != "hardlink_identity":
            invalid_ownership.append(rel_path)
            continue
        staging_rel = proof.get("staging_rel_path")
        expected_prefix = f".life-index/import-jobs/{import_id}/publication-staging/"
        if (
            not isinstance(staging_rel, str)
            or not staging_rel.startswith(expected_prefix)
            or not isinstance(proof.get("device"), int)
            or not isinstance(proof.get("inode"), int)
        ):
            invalid_ownership.append(rel_path)
            continue
        staging_path = _resolve_confined_file_path(data_dir, staging_rel)
        if staging_path is None:
            invalid_ownership.append(rel_path)
            continue
        ownership_proofs[rel_path] = proof
        safe_staging_paths[rel_path] = staging_path

    if unsafe_paths or invalid_ownership:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        manifest["state"] = "rollback_failed"
        manifest["rollback_retryable"] = False
        manifest["errors"] = [
            *[f"Unsafe path (traversal/absolute): {p}" for p in unsafe_paths],
            *[f"Invalid hardlink ownership proof: {p}" for p in invalid_ownership],
        ]
        _write_manifest(manifest_abs, manifest)

        jobs[import_id]["state"] = "rollback_failed"
        jobs[import_id]["rollback_retryable"] = False
        jobs[import_id]["updated_at"] = now_iso
        _write_ledger(data_dir, ledger)

        return _err(
            "IMPORT_ROLLBACK_UNSAFE",
            "Rollback aborted: manifest path or ownership proof is unsafe.",
            {
                "unsafe_paths": unsafe_paths,
                "invalid_ownership": invalid_ownership,
            },
            retryable=False,
        )

    # --- 5. Second pass: check all checksums (PRD §10) ---
    to_delete: list[dict[str, Any]] = []
    staging_to_delete: list[Path] = []
    blocked: list[dict[str, Any]] = []
    target_baselines: dict[str, dict[str, Any] | None] = {}
    staging_baselines: dict[str, dict[str, Any] | None] = {}

    for file_entry in manifest.get("created_files", []):
        if not file_entry.get("created_by_import", False):
            continue

        rel_path = file_entry["rel_path"]
        expected_sha256 = file_entry["sha256_after"]
        expected_size = file_entry.get("size_bytes")
        file_path = safe_paths[rel_path]
        proof = ownership_proofs.get(rel_path)

        if proof is not None:
            expected_identity = (proof["device"], proof["inode"])
            staging_path = safe_staging_paths[rel_path]
            staging_evidence = _rollback_path_evidence(staging_path)
            staging_baselines[rel_path] = staging_evidence
            if staging_evidence is not None:
                if (
                    staging_evidence["identity"] != expected_identity
                    or staging_evidence["sha256"] != expected_sha256
                    or (expected_size is not None and staging_evidence["size"] != expected_size)
                ):
                    blocked.append(
                        {
                            "rel_path": rel_path,
                            "reason": "staging_ownership_mismatch",
                        }
                    )
                else:
                    staging_to_delete.append(staging_path)

        target_evidence = _rollback_path_evidence(file_path)
        target_baselines[rel_path] = target_evidence
        if target_evidence is None:
            # Already removed — idempotent, skip
            continue

        current_sha256 = target_evidence["sha256"]
        current_size = target_evidence["size"]
        if proof is not None and target_evidence["identity"] != (
            proof["device"],
            proof["inode"],
        ):
            # A prepared entry may encounter a create-only collision. The final
            # path is provably not our staged inode, so preserve it. A durable
            # "published" claim whose identity changed fails closed.
            if file_entry.get("publication_state") == "prepared":
                continue
            blocked.append(
                {
                    "rel_path": rel_path,
                    "reason": "target_ownership_mismatch",
                }
            )
        elif current_sha256 != expected_sha256 or (
            expected_size is not None and current_size != expected_size
        ):
            blocked.append(
                {
                    "rel_path": rel_path,
                    "expected_sha256": expected_sha256,
                    "current_sha256": current_sha256,
                    "expected_size": expected_size,
                    "current_size": current_size,
                    "reason": "content_mismatch",
                }
            )
        else:
            to_delete.append(
                {
                    "rel_path": rel_path,
                    "path": file_path,
                    "kind": file_entry.get("kind", ""),
                    "identity": target_evidence["identity"],
                }
            )

    # --- 6. If any blocked, refuse entire rollback (PRD §10) ---
    if blocked:
        return _record_rollback_mismatch(
            data_dir=data_dir,
            import_id=import_id,
            manifest_abs=manifest_abs,
            manifest=manifest,
            ledger=ledger,
            blocked=blocked,
        )

    # --- 7. Serialize the final rollback critical section with journal edits ---
    # Global order: import ledger -> optional parent review -> journals. Initial
    # validation stays outside this innermost lock; after acquisition we queue
    # pending removals, revalidate every target/staging fact, then unlink.
    journals_lock = FileLock(get_journals_lock_path(), timeout=FILE_LOCK_TIMEOUT_DEFAULT)
    try:
        journals_lock.acquire(blocking=True)
    except LockTimeoutError:
        return _err(
            "IMPORT_INTERNAL_ERROR",
            "Rollback could not acquire the journals lock.",
            {"import_id": import_id, "reason": "journals_lock_timeout"},
            retryable=True,
        )
    except OSError:
        return _err(
            "IMPORT_INTERNAL_ERROR",
            "Rollback could not acquire the journals lock.",
            {"import_id": import_id, "reason": "journals_lock_unavailable"},
            retryable=True,
        )

    try:
        # A successful rollback must let the next normal search remove stale FTS
        # rows. Queue under the journals lock, before any deletion.
        try:
            for file_entry in manifest.get("created_files", []):
                if (
                    file_entry.get("created_by_import", False)
                    and file_entry.get("kind") == "journal"
                ):
                    mark_pending(file_entry["rel_path"])
        except OSError as exc:
            return _err(
                "IMPORT_INTERNAL_ERROR",
                "Rollback could not queue journal removals for index update.",
                {"import_id": import_id, "error": str(exc)},
                retryable=True,
            )

        # Immediately before the first unlink, repeat confinement, presence,
        # filesystem identity, checksum, and size validation for EVERY manifest
        # target and prepared-ownership staging path. Any drift aborts the whole
        # rollback before a single file is deleted.
        final_blocked = _final_rollback_revalidation(
            data_dir=data_dir,
            manifest=manifest,
            safe_paths=safe_paths,
            safe_staging_paths=safe_staging_paths,
            ownership_proofs=ownership_proofs,
            target_baselines=target_baselines,
            staging_baselines=staging_baselines,
            to_delete=to_delete,
            staging_to_delete=staging_to_delete,
        )
        if final_blocked:
            return _record_rollback_mismatch(
                data_dir=data_dir,
                import_id=import_id,
                manifest_abs=manifest_abs,
                manifest=manifest,
                ledger=ledger,
                blocked=final_blocked,
            )

        # --- 8. Persist restart-safe intent, then delete revalidated files ---
        # Both existing authorities must say recovery is in progress before the
        # first unlink. If the process stops mid-loop, a later status/rollback
        # can recover from this durable fact instead of projecting committed.
        rollback_started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        manifest["state"] = "rollback_in_progress"
        manifest["rollback_retryable"] = True
        manifest["errors"] = []
        _write_manifest(manifest_abs, manifest)
        jobs[import_id]["state"] = "rollback_in_progress"
        jobs[import_id]["rollback_retryable"] = True
        jobs[import_id]["updated_at"] = rollback_started_at
        _write_ledger(data_dir, ledger)

        deleted_count = 0
        try:
            for entry in to_delete:
                entry["path"].unlink()
                deleted_count += 1
            for staging_path in dict.fromkeys(staging_to_delete):
                if staging_path.exists():
                    staging_path.unlink()
                try:
                    staging_path.parent.rmdir()
                except OSError:
                    pass
        except OSError:
            # ``rollback_in_progress`` was durably written to both authorities
            # before deletion began. Preserve that restart point instead of
            # introducing another two-write transition after partial deletion.
            return _err(
                "IMPORT_ROLLBACK_INTERRUPTED",
                "Rollback was interrupted while removing owned files.",
                {
                    "import_id": import_id,
                    "reason": "filesystem_delete_failed",
                    "deleted_count": deleted_count,
                },
                retryable=True,
            )
    finally:
        journals_lock.release()

    # --- 9. Preserve manifest as audit evidence, update ledger ---
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest["state"] = "rolled_back"
    manifest["rollback_retryable"] = False
    _write_manifest(manifest_abs, manifest)

    jobs[import_id]["state"] = "rolled_back"
    jobs[import_id]["rollback_retryable"] = False
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

        if _resolve_confined_file_path(data_dir, journal_rel) is None:
            unsafe_paths.append(journal_rel)

        # Aggregated photo proposals carry the full member source-record
        # fingerprint list so the plan-level source fingerprint can be
        # recomputed over every scanned record. Legacy/fixture proposals omit
        # the list and contribute their singular fingerprint, preserving the
        # original 1:1 reconciliation behaviour exactly.
        member_fps = proposal.get("source_record_fingerprints")
        if isinstance(member_fps, list) and member_fps:
            source_record_fingerprints.extend(member_fps)
        else:
            source_record_fingerprints.append(source_record_fp)

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


def _resolve_confined_job_path(data_dir: Path, rel_path: str) -> Path | None:
    """Return a RESOLVED import-job area path only when it is confined.

    Intended for job-area paths (manifest directories, staging files) that may
    not yet exist or that name a directory created on first use. Unlike
    :func:`_resolve_confined_file_path`, this does NOT require an existing target
    to be a regular file — a job area is created on demand. Returns the RESOLVED
    target so callers use the validated path for every subsequent I/O (never
    validate one expression and join a second path later).

    Rejects empty/absolute ``rel_path``, traversal escapes, and any resolved
    target that is not a strict descendant of the resolved data dir. Containment
    is component-wise (``relative_to``): a planted junction/reparse/symlink that
    escapes and a sibling ``<data_dir>-evil`` are both rejected, while a data dir
    that itself contains a symlink component is resolved on both sides.
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
    return resolved_target


def _read_ledger(data_dir: Path) -> dict[str, Any]:
    """Read one stable ledger snapshot; malformed durable state fails closed."""
    _assert_import_jobs_area_confined(data_dir)
    ledger_path = _ledger_path(data_dir)
    lock_key = str(data_dir.resolve())
    # Preserve plan/dry-run no-write semantics. If no ledger exists and this is
    # not already a mutation transaction, the empty snapshot linearizes before
    # any later creator; no lock file or import-jobs directory is created.
    if lock_key not in _LEDGER_LOCK_STACK.get() and not ledger_path.exists():
        return {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "jobs": {},
            "idempotency_index": {},
        }
    with _ledger_transaction(data_dir):
        if not ledger_path.exists():
            return {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "jobs": {},
                "idempotency_index": {},
            }
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            raise ImportLedgerCorruptError(ledger_path, str(exc)) from exc
        if not isinstance(ledger, dict):
            raise ImportLedgerCorruptError(ledger_path, "root must be a JSON object")
        if not isinstance(ledger.get("jobs"), dict):
            raise ImportLedgerCorruptError(ledger_path, "jobs must be a JSON object")
        if not isinstance(ledger.get("idempotency_index"), dict):
            raise ImportLedgerCorruptError(ledger_path, "idempotency_index must be a JSON object")
        # Job-key integrity gate. Every ``jobs`` key is a closed-lexical import id
        # (a parent id or a ``<parent>#batch-<seq>`` child id). A hostile durable
        # key — path-like, traversal, non-lexical — is unreachable to EVERY
        # consumer by failing closed HERE, before any key is used as a locator,
        # indexed into the batches projection, surfaced by the reviews list, or
        # promoted into an ``active_child_id`` by ``_reconcile_parent``'s settled
        # scan. The result is deterministic across the read and mutation paths:
        # no repair, no derivation, no leak, and byte-identical on repeat. The
        # offending key value is never placed in the error.
        for job_id in ledger["jobs"]:
            if validate_import_id(job_id, allow_child=True) is not None:
                raise ImportLedgerCorruptError(ledger_path, "job_id_invalid")
        return ledger


def _write_ledger(data_dir: Path, ledger: dict[str, Any]) -> None:
    """Atomically and durably replace the ledger while holding its lock."""
    with _ledger_transaction(data_dir):
        ledger.setdefault("schema_version", LEDGER_SCHEMA_VERSION)
        _atomic_write_json(_ledger_path(data_dir), ledger)


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Atomically and durably replace a rollback manifest."""
    _atomic_write_json(path, manifest)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON through a same-directory temp file, fsync, and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.tmp-")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
            finally:
                os.close(directory_fd)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _read_rollback_manifest(data_dir: Path, import_id: str) -> dict[str, Any] | None:
    """Read the rollback manifest for an import job, or None.

    The manifest path is resolved and proven confined before any read: a planted
    link in the job area that would redirect the read outside the data directory
    fails closed (None) rather than reading untrusted bytes.
    """
    manifest_path = _resolve_confined_job_path(
        data_dir, f".life-index/import-jobs/{import_id}/rollback-manifest.json"
    )
    if manifest_path is None:
        return None
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


def _path_identity(path: Path) -> tuple[int, int]:
    """Return the filesystem identity used by hard-link ownership proofs."""
    stat = path.stat()
    return stat.st_dev, stat.st_ino


def _rollback_path_evidence(path: Path) -> dict[str, Any] | None:
    """Snapshot the identity, content hash, and size used by rollback validation."""
    if not path.exists():
        return None
    return {
        "identity": _path_identity(path),
        "sha256": f"sha256:{_file_sha256(path)}",
        "size": path.stat().st_size,
    }


def _final_rollback_revalidation(
    *,
    data_dir: Path,
    manifest: dict[str, Any],
    safe_paths: dict[str, Path],
    safe_staging_paths: dict[str, Path],
    ownership_proofs: dict[str, dict[str, Any]],
    target_baselines: dict[str, dict[str, Any] | None],
    staging_baselines: dict[str, dict[str, Any] | None],
    to_delete: list[dict[str, Any]],
    staging_to_delete: list[Path],
) -> list[dict[str, Any]]:
    """Revalidate every rollback target immediately before the first unlink."""
    blocked: list[dict[str, Any]] = []
    delete_rel_paths = {entry["rel_path"] for entry in to_delete}
    staging_delete_paths = set(staging_to_delete)

    for file_entry in manifest.get("created_files", []):
        if not file_entry.get("created_by_import", False):
            continue
        rel_path = file_entry["rel_path"]
        expected_sha256 = file_entry["sha256_after"]
        expected_size = file_entry.get("size_bytes")
        expected_path = safe_paths[rel_path]
        current_path = _resolve_confined_file_path(data_dir, rel_path)
        if current_path is None or current_path != expected_path:
            blocked.append({"rel_path": rel_path, "reason": "target_path_changed_after_validation"})
            continue
        try:
            target_evidence = _rollback_path_evidence(current_path)
        except OSError:
            blocked.append({"rel_path": rel_path, "reason": "target_unreadable_after_validation"})
            continue
        if target_evidence != target_baselines.get(rel_path):
            blocked.append({"rel_path": rel_path, "reason": "target_changed_after_validation"})
            continue

        proof = ownership_proofs.get(rel_path)
        if rel_path in delete_rel_paths and target_evidence is not None:
            if (
                target_evidence["sha256"] != expected_sha256
                or (expected_size is not None and target_evidence["size"] != expected_size)
                or (
                    proof is not None
                    and target_evidence["identity"] != (proof["device"], proof["inode"])
                )
            ):
                blocked.append({"rel_path": rel_path, "reason": "target_revalidation_mismatch"})
                continue

        if proof is None:
            continue
        staging_rel = proof["staging_rel_path"]
        expected_staging_path = safe_staging_paths[rel_path]
        current_staging_path = _resolve_confined_file_path(data_dir, staging_rel)
        if current_staging_path is None or current_staging_path != expected_staging_path:
            blocked.append(
                {"rel_path": rel_path, "reason": "staging_path_changed_after_validation"}
            )
            continue
        try:
            staging_evidence = _rollback_path_evidence(current_staging_path)
        except OSError:
            blocked.append({"rel_path": rel_path, "reason": "staging_unreadable_after_validation"})
            continue
        if staging_evidence != staging_baselines.get(rel_path):
            blocked.append({"rel_path": rel_path, "reason": "staging_changed_after_validation"})
            continue
        if current_staging_path in staging_delete_paths and staging_evidence is not None:
            if (
                staging_evidence["identity"] != (proof["device"], proof["inode"])
                or staging_evidence["sha256"] != expected_sha256
                or (expected_size is not None and staging_evidence["size"] != expected_size)
            ):
                blocked.append({"rel_path": rel_path, "reason": "staging_revalidation_mismatch"})

    return blocked


def _record_rollback_mismatch(
    *,
    data_dir: Path,
    import_id: str,
    manifest_abs: Path,
    manifest: dict[str, Any],
    ledger: dict[str, Any],
    blocked: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist one fail-closed rollback mismatch result."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest["state"] = "rollback_failed"
    manifest["rollback_retryable"] = False
    manifest["errors"] = [
        f"Rollback ownership/content mismatch: {item['rel_path']} ({item['reason']})"
        for item in blocked
    ]
    _write_manifest(manifest_abs, manifest)

    ledger["jobs"][import_id]["state"] = "rollback_failed"
    ledger["jobs"][import_id]["rollback_retryable"] = False
    ledger["jobs"][import_id]["updated_at"] = now_iso
    _write_ledger(data_dir, ledger)

    return _err(
        "IMPORT_ROLLBACK_CHECKSUM_MISMATCH",
        (f"Rollback blocked: {len(blocked)} file(s) have " "ownership or content mismatches."),
        {"blocked_files": blocked},
        retryable=False,
    )


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
