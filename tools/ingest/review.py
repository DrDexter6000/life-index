"""Review queue & batch import for ``media.photo_timeline`` (additive, M7).

This module is **additive** to the existing import provider
(``tools.ingest.runner``). It implements the recoverable photo review queue:

- ``import confirm`` — atomically persist a review plan and record a parent
  review job, after re-validating immutable source fingerprints and selected
  attachment ids.
- ``import validate`` / ``import rebind`` — source-root identity fingerprint.
- ``import status`` — additive proposal states / queue counts for review jobs.
- ``import rollback`` — refuse to roll back a parent review job.
- ``import preview`` — read-only attachment byte/metadata streaming.
- ``import run --import-id`` — single-active-child batch run with idempotent
  reconciliation.

Legacy ``--plan/--confirm`` (fixture) and child batch jobs keep using
``tools.ingest.runner`` unchanged; this module only adds the review/batch
surface on top of the same ledger / manifest / fingerprint authority.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from tools.ingest.fingerprint import (
    compute_attachment_fingerprint,
    compute_plan_fingerprint,
    compute_proposal_fingerprint,
    compute_source_fingerprint,
    compute_source_record_fingerprint,
    group_source_fingerprint,
    sha256_hash,
)
from tools.ingest.schemas import (
    DEFAULT_NORMALIZED_IMPORT_OPTIONS_HASH,
    DEFAULT_NORMALIZED_WRITE_POLICY_HASH,
    PLAN_SCHEMA_VERSION,
    PREVIEW_SCHEMA_VERSION,
    REVIEW_PLAN_SCHEMA_VERSION,
    REVIEW_SCHEMA_VERSION,
    ROLLBACK_MANIFEST_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
)
from tools.lib.file_lock import FileLock
from tools.lib.frontmatter import SCHEMA_VERSION, format_journal_content

# ---------------------------------------------------------------------------
# Review/batch error codes (additive)
# ---------------------------------------------------------------------------

IMPORT_ROLLBACK_PARENT_NOT_ALLOWED = "IMPORT_ROLLBACK_PARENT_NOT_ALLOWED"
IMPORT_BATCH_ALREADY_ACTIVE = "IMPORT_BATCH_ALREADY_ACTIVE"
IMPORT_NO_RUNNABLE_PROPOSALS = "IMPORT_NO_RUNNABLE_PROPOSALS"
IMPORT_SOURCE_ROOT_UNREADABLE = "IMPORT_SOURCE_ROOT_UNREADABLE"
IMPORT_SOURCE_ROOT_IDENTITY_MISMATCH = "IMPORT_SOURCE_ROOT_IDENTITY_MISMATCH"
IMPORT_REVIEW_PLAN_MISSING = "IMPORT_REVIEW_PLAN_MISSING"
IMPORT_PREVIEW_UNAVAILABLE = "IMPORT_PREVIEW_UNAVAILABLE"
IMPORT_RECOVERY_REQUIRED = "IMPORT_RECOVERY_REQUIRED"

# Proposal states (additive ``state`` field).
STATE_PENDING = "pending"
STATE_CONFIRMED = "confirmed"
STATE_SKIPPED = "skipped"
STATE_STALE = "stale"
STATE_BATCHING = "batching"
STATE_IMPORTED = "imported"

_PHOTO_CAPTURE_CONFLICT_CODES = frozenset(
    {"PHOTO_CAPTURE_TIME_MISSING", "PHOTO_CAPTURE_TIME_AMBIGUOUS"}
)


# ---------------------------------------------------------------------------
# Result helpers (mirror runner._ok / runner._err shape)
# ---------------------------------------------------------------------------


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def _err(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
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


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _review_dir(data_dir: Path, parent_id: str) -> Path:
    return data_dir / ".life-index" / "import-jobs" / parent_id


def _review_plan_rel_path(parent_id: str) -> str:
    return f".life-index/import-jobs/{parent_id}/review-plan.json"


def _review_plan_path(data_dir: Path, parent_id: str) -> Path:
    return data_dir / _review_plan_rel_path(parent_id)


def _review_lock_path(data_dir: Path, parent_id: str) -> Path:
    return _review_dir(data_dir, parent_id) / "review.lock"


# ---------------------------------------------------------------------------
# Ledger access (reuses runner helpers; additive fields only)
# ---------------------------------------------------------------------------


def _read_ledger(data_dir: Path) -> dict[str, Any]:
    from tools.ingest.runner import _read_ledger as _rl

    return _rl(data_dir)


def _write_ledger(data_dir: Path, ledger: dict[str, Any]) -> None:
    from tools.ingest.runner import _write_ledger as _wl

    _wl(data_dir, ledger)


def _get_job(ledger: dict[str, Any], import_id: str) -> dict[str, Any] | None:
    jobs = ledger.get("jobs", {})
    if not isinstance(jobs, dict):
        return None
    job = jobs.get(import_id)
    return job if isinstance(job, dict) else None


def _is_review_job(job: dict[str, Any] | None) -> bool:
    return bool(job) and job.get("kind") == "review"


# ---------------------------------------------------------------------------
# Source-root identity
# ---------------------------------------------------------------------------


def compute_source_root_identity(source_root: Path) -> str:
    """Deterministic identity fingerprint for a source root directory.

    Based on the canonical resolved path plus stable filesystem attributes
    (device / inode / creation time). The creation time survives renames and
    moves on the same volume, so a rebound locator that points at the same
    physical root re-validates after a path change. Fully reproducible from
    the directory alone (no persisted state required).
    """
    resolved = source_root.resolve()
    try:
        st = resolved.stat()
        attrs = [str(st.st_dev), str(st.st_ino), str(st.st_ctime_ns)]
    except OSError:
        attrs = []
    parts = [
        "life-index.source-root.v1",
        str(resolved).replace(os.sep, "/"),
        *attrs,
    ]
    return sha256_hash("\0".join(parts))


def validate_source_root(source_root: str | Path) -> dict[str, Any]:
    """``import validate``: return canonical readable dir + root identity."""
    root = Path(source_root)
    try:
        resolved = root.resolve()
    except OSError as exc:
        return _err(
            IMPORT_SOURCE_ROOT_UNREADABLE,
            f"Source root cannot be resolved: {exc}",
            {"source_root": str(root)},
            retryable=True,
        )
    if not resolved.exists() or not resolved.is_dir():
        return _err(
            IMPORT_SOURCE_ROOT_UNREADABLE,
            f"Source root is not a readable directory: {root}",
            {"source_root": str(root)},
            retryable=True,
        )
    identity = compute_source_root_identity(resolved)
    return _ok(
        {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "source_root": str(resolved),
            "source_root_identity": identity,
            "readable": True,
        }
    )


def rebind_source_root(
    parent_id: str, source_root: str | Path, data_dir: Path
) -> dict[str, Any]:
    """``import rebind``: re-validate that a locator is the same root identity."""
    ledger = _read_ledger(data_dir)
    job = _get_job(ledger, parent_id)
    if not _is_review_job(job):
        return _err(
            "IMPORT_JOB_NOT_FOUND",
            f"No parent review job found for import-id: {parent_id}",
            {"import_id": parent_id},
            retryable=False,
        )
    stored_identity = job.get("source_root_identity", "")
    validation = validate_source_root(source_root)
    if not validation["success"]:
        return validation
    new_identity = validation["data"]["source_root_identity"]
    if stored_identity and new_identity != stored_identity:
        return _err(
            IMPORT_SOURCE_ROOT_IDENTITY_MISMATCH,
            "Rebound source root identity does not match the parent review job.",
            {
                "import_id": parent_id,
                "expected": stored_identity,
                "actual": new_identity,
            },
            retryable=False,
        )
    # Identity matches (or parent had none yet): record the locator identity.
    job["source_root_identity"] = new_identity
    job["updated_at"] = _now_iso()
    _write_ledger(data_dir, ledger)
    return _ok(
        {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "import_id": parent_id,
            "source_root": validation["data"]["source_root"],
            "source_root_identity": new_identity,
            "rebound": True,
        }
    )


# ---------------------------------------------------------------------------
# Review-plan atomic persistence
# ---------------------------------------------------------------------------


def _write_review_plan_atomic(
    data_dir: Path, parent_id: str, plan: dict[str, Any]
) -> Path:
    """Persist the review plan via temp file + fsync + atomic replace."""
    target = _review_plan_path(data_dir, parent_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass
    os.replace(tmp, target)
    return target


def read_review_plan(data_dir: Path, parent_id: str) -> dict[str, Any] | None:
    """Read the persisted review plan, or None when absent."""
    path = _review_plan_path(data_dir, parent_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Confirm: immutability validation + state derivation
# ---------------------------------------------------------------------------


def _recompute_source_record_fingerprint(facts: dict[str, Any]) -> str | None:
    """Recompute a source-record fingerprint from immutable source facts."""
    try:
        return compute_source_record_fingerprint(
            adapter_id=facts["adapter_id"],
            adapter_version=facts["adapter_version"],
            normalized_identity=facts["content_sha256"],
            content_hash=facts["content_sha256"],
            metadata_hash=facts["metadata_hash"],
        )
    except KeyError:
        return None


def _attachment_fingerprint_from(att: dict[str, Any]) -> str:
    return compute_attachment_fingerprint(
        attachment_id=att["attachment_id"],
        source_sha256=att["source_sha256"],
        target_rel_path=att["target_rel_path"],
        media_type=att["media_type"],
        size_bytes=att["size_bytes"],
        copy_mode=att["copy_mode"],
    )


def _validate_proposal_immutability(proposal: dict[str, Any]) -> str | None:
    """Return an error code string when a proposal tampers immutable facts, else None."""
    facts_list = proposal.get("source_facts") or []
    member_fps = proposal.get("source_record_fingerprints") or []

    # Every source fact must re-derive to a known member fingerprint.
    valid_member_fps = set(member_fps)
    if member_fps and valid_member_fps:
        for facts in facts_list:
            recomputed = _recompute_source_record_fingerprint(facts)
            if recomputed is None or recomputed not in valid_member_fps:
                return "IMPORT_PLAN_INVALID"

    # Each selected attachment must reference a source fact in THIS proposal.
    proposal_shas = {f.get("content_sha256") for f in facts_list if isinstance(f, dict)}
    for att in proposal.get("attachments", []):
        if att.get("source_sha256") not in proposal_shas:
            return "IMPORT_PLAN_INVALID"
        # attachment_id must correspond to its own source content hash.
        expected_prefix = att.get("source_sha256", "").removeprefix("sha256:")[:12]
        if not str(att.get("attachment_id", "")).endswith(expected_prefix):
            return "IMPORT_PLAN_INVALID"

    # Group source_record_fingerprint must match the recomputed group fp.
    if member_fps:
        group_fp = group_source_fingerprint(list(member_fps))
        if group_fp != proposal.get("source_record_fingerprint"):
            return "IMPORT_PLAN_INVALID"

    return None


def _derive_confirm_state(proposal: dict[str, Any]) -> str:
    """Derive a proposal's state after confirm from selection + conflicts."""
    attachments = proposal.get("attachments", []) or []
    if not attachments:
        return STATE_SKIPPED
    has_capture_conflict = any(
        c.get("code") in _PHOTO_CAPTURE_CONFLICT_CODES for c in proposal.get("conflicts", [])
    )
    if has_capture_conflict:
        return STATE_PENDING
    return STATE_CONFIRMED


def _recompute_plan_fingerprints(plan: dict[str, Any]) -> dict[str, Any]:
    """Recompute proposal + plan fingerprints in-place from current content.

    Returns the (possibly updated) plan. Source-record fingerprints (immutable)
    are NOT changed; only the editable-journal-derived proposal/plan
    fingerprints are re-derived so the persisted review plan is internally
    consistent with the user's edits.
    """
    source = plan.get("source", {})
    adapter_id = source.get("adapter_id", "")
    adapter_version = source.get("adapter_version", "")
    source_record_fingerprints: list[str] = []

    for proposal in plan.get("proposals", []):
        member_fps = proposal.get("source_record_fingerprints")
        if isinstance(member_fps, list) and member_fps:
            source_record_fingerprints.extend(member_fps)
        else:
            source_record_fingerprints.append(proposal.get("source_record_fingerprint", ""))
        att_fps = [_attachment_fingerprint_from(a) for a in proposal.get("attachments", [])]
        journal = proposal.get("journal", {})
        proposal_fp = compute_proposal_fingerprint(
            source_record_fingerprint=proposal.get("source_record_fingerprint", ""),
            target_rel_path=journal.get("target_rel_path", ""),
            title=journal.get("title", ""),
            date=journal.get("date", ""),
            topic=journal.get("topic", ""),
            tags=journal.get("tags", []),
            content=journal.get("content", ""),
            attachment_fingerprints=att_fps,
        )
        proposal["proposal_fingerprint"] = proposal_fp

    src_fp = compute_source_fingerprint(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        normalized_import_options_hash=DEFAULT_NORMALIZED_IMPORT_OPTIONS_HASH,
        source_record_fingerprints=source_record_fingerprints,
    )
    proposal_fingerprints = [p.get("proposal_fingerprint", "") for p in plan.get("proposals", [])]
    plan_fp = compute_plan_fingerprint(
        schema_version=PLAN_SCHEMA_VERSION,
        source_fingerprint=src_fp,
        proposal_fingerprints=proposal_fingerprints,
        normalized_write_policy_hash=DEFAULT_NORMALIZED_WRITE_POLICY_HASH,
    )
    source["source_fingerprint"] = src_fp
    plan["source"] = source
    plan["plan_fingerprint"] = plan_fp
    # The idempotency_key is left as supplied by the plan; it is not consumed by
    # the review/batch flow (the child batch derives its own job identity).
    return plan


def confirm_review(  # noqa: C901
    plan_path: str,
    data_dir: Path,
    source_root: str | None = None,
    parent_id_override: str | None = None,
) -> dict[str, Any]:
    """``import confirm``: persist a review plan and record a parent review job."""
    plan_file = Path(plan_path)
    if not plan_file.exists():
        return _err(
            "IMPORT_PLAN_INVALID",
            f"Plan file not found: {plan_path}",
            {"plan_path": plan_path},
            retryable=False,
        )
    try:
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return _err(
            "IMPORT_PLAN_INVALID",
            f"Cannot parse plan file: {exc}",
            {"plan_path": plan_path},
            retryable=False,
        )
    if not isinstance(plan, dict):
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan file is not a JSON object.",
            {"plan_path": plan_path},
            retryable=False,
        )

    parent_id = parent_id_override or plan.get("import_id", "")
    if not parent_id:
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan has no import_id and no --import-id was supplied.",
            {"plan_path": plan_path},
            retryable=False,
        )

    proposals = plan.get("proposals", [])
    if not isinstance(proposals, list):
        return _err(
            "IMPORT_PLAN_INVALID",
            "Plan proposals must be a list.",
            retryable=False,
        )

    # --- Validate immutable source facts & selected attachment ids ---
    for index, proposal in enumerate(proposals):
        code = _validate_proposal_immutability(proposal)
        if code is not None:
            return _err(
                code,
                "Review plan failed immutable-fingerprint / selected-id validation.",
                {"proposal_index": index, "proposal_id": proposal.get("proposal_id")},
                retryable=False,
            )

    # --- Source-root identity (optional but recorded when supplied) ---
    source_root_identity = ""
    if source_root:
        validation = validate_source_root(source_root)
        if not validation["success"]:
            return validation
        source_root_identity = validation["data"]["source_root_identity"]

    # --- Recompute editable-derived fingerprints, derive states ---
    plan = _recompute_plan_fingerprints(plan)
    proposal_states: dict[str, str] = {}
    for proposal in proposals:
        state = _derive_confirm_state(proposal)
        proposal["state"] = state
        proposal_states[proposal.get("proposal_id", "")] = state

    plan["schema_version"] = REVIEW_PLAN_SCHEMA_VERSION
    plan["parent_id"] = parent_id
    plan["source_root_identity"] = source_root_identity
    plan["confirmed_at"] = _now_iso()

    counts = _queue_counts(proposal_states)

    # --- Per-parent single-writer lock: persist + ledger update ---
    lock = FileLock(_review_lock_path(data_dir, parent_id), timeout=30.0)
    with lock:
        _write_review_plan_atomic(data_dir, parent_id, plan)
        ledger = _read_ledger(data_dir)
        jobs = ledger.setdefault("jobs", {})
        jobs[parent_id] = {
            "kind": "review",
            "state": "confirmed",
            "source_root_identity": source_root_identity,
            "review_plan_rel_path": _review_plan_rel_path(parent_id),
            "proposal_states": proposal_states,
            "active_child_id": None,
            "recovery_required": False,
            "idempotency_key": plan.get("idempotency_key", ""),
            "plan_fingerprint": plan.get("plan_fingerprint", ""),
            "updated_at": _now_iso(),
        }
        _write_ledger(data_dir, ledger)

    return _ok(
        {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "parent_id": parent_id,
            "source_root_identity": source_root_identity,
            "review_plan_rel_path": _review_plan_rel_path(parent_id),
            "proposal_states": proposal_states,
            "queue_counts": counts,
            "proposals": [
                {
                    "proposal_id": p.get("proposal_id", ""),
                    "state": p.get("state", STATE_PENDING),
                    "attachment_count": len(p.get("attachments", []) or []),
                }
                for p in proposals
            ],
        }
    )


def _queue_counts(proposal_states: dict[str, str]) -> dict[str, int]:
    counts = {
        STATE_PENDING: 0,
        STATE_CONFIRMED: 0,
        STATE_SKIPPED: 0,
        STATE_STALE: 0,
        STATE_BATCHING: 0,
        STATE_IMPORTED: 0,
    }
    for state in proposal_states.values():
        if state in counts:
            counts[state] += 1
    return counts


# ---------------------------------------------------------------------------
# Additive status
# ---------------------------------------------------------------------------


def query_review_status(import_id: str, data_dir: Path) -> dict[str, Any]:
    """``import status`` for a parent review job (additive), else delegate."""
    ledger = _read_ledger(data_dir)
    job = _get_job(ledger, import_id)
    if not _is_review_job(job):
        # Legacy / child batch job — unchanged status behaviour.
        from tools.ingest.runner import query_status

        return query_status(import_id=import_id, data_dir=data_dir)

    proposal_states = job.get("proposal_states", {}) or {}
    return _ok(
        {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "import_id": import_id,
            "kind": "review",
            "state": job.get("state", "confirmed"),
            "source_root_identity": job.get("source_root_identity", ""),
            "proposal_states": proposal_states,
            "queue_counts": _queue_counts(proposal_states),
            "active_child_id": job.get("active_child_id"),
            "recovery_required": bool(job.get("recovery_required", False)),
            "review_plan_rel_path": job.get("review_plan_rel_path", ""),
        }
    )


# ---------------------------------------------------------------------------
# Rollback: parent review job is not rollable as a whole
# ---------------------------------------------------------------------------


def execute_review_rollback(import_id: str, data_dir: Path) -> dict[str, Any]:
    """``import rollback`` dispatch: refuse parent review jobs, else delegate.

    After a child batch job is rolled back, reconcile its parent review job so
    the rolled-back proposals are restored to ``confirmed`` (re-runnable). This
    is what makes "rollback restores confirmed" observable via ``import status``.
    """
    ledger = _read_ledger(data_dir)
    job = _get_job(ledger, import_id)
    if _is_review_job(job):
        return _err(
            IMPORT_ROLLBACK_PARENT_NOT_ALLOWED,
            "A parent review job cannot be rolled back as a whole; roll back its child batch job instead.",
            {"import_id": import_id},
            retryable=False,
        )
    from tools.ingest.runner import execute_rollback

    result = execute_rollback(import_id=import_id, data_dir=data_dir)

    # If this was a child batch job that just rolled back, re-project its parent
    # review job so proposals move out of imported/batching back to confirmed.
    # (The committed-run path already cleared ``active_child_id``, so we cannot
    # rely on ``_reconcile_parent`` here — restore the selected proposals
    # directly from the parent's recorded selection.)
    if result["success"]:
        parent_id = job.get("parent_review_job_id") if isinstance(job, dict) else None
        if parent_id:
            ledger = _read_ledger(data_dir)
            parent = _get_job(ledger, parent_id)
            if _is_review_job(parent):
                proposal_states = dict(parent.get("proposal_states", {}) or {})
                for pid in parent.get("selected_proposal_ids", []) or []:
                    if proposal_states.get(pid) in (STATE_BATCHING, STATE_IMPORTED):
                        proposal_states[pid] = STATE_CONFIRMED
                parent["proposal_states"] = proposal_states
                parent["recovery_required"] = False
                parent["updated_at"] = _now_iso()
                _write_ledger(data_dir, ledger)

    return result


# ---------------------------------------------------------------------------
# Preview (read-only)
# ---------------------------------------------------------------------------


def _resolve_source_root(
    parent_id: str, source_root: str | None, data_dir: Path
) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve + identity-check a source root against the parent review job.

    Returns ``(resolved_root, error_result)``. On success ``error_result`` is
    None and ``resolved_root`` is the validated directory. On failure
    ``resolved_root`` is None and ``error_result`` is a review error dict.
    """
    if source_root is None:
        return None, _err(
            IMPORT_SOURCE_ROOT_UNREADABLE,
            "preview/run require a --source-root locator (or a prior `import rebind`).",
            {"import_id": parent_id},
            retryable=True,
        )
    validation = validate_source_root(source_root)
    if not validation["success"]:
        return None, validation
    resolved = Path(validation["data"]["source_root"])
    actual_identity = validation["data"]["source_root_identity"]

    ledger = _read_ledger(data_dir)
    job = _get_job(ledger, parent_id)
    stored_identity = job.get("source_root_identity", "") if job else ""
    if stored_identity and actual_identity != stored_identity:
        return None, _err(
            IMPORT_SOURCE_ROOT_IDENTITY_MISMATCH,
            "Source root identity does not match the parent review job.",
            {"import_id": parent_id, "expected": stored_identity, "actual": actual_identity},
            retryable=False,
        )
    return resolved, None


def _find_attachment_in_plan(
    plan: dict[str, Any], attachment_id: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Find ``(attachment, proposal)`` by attachment_id in a review plan."""
    for proposal in plan.get("proposals", []):
        for att in proposal.get("attachments", []) or []:
            if att.get("attachment_id") == attachment_id:
                return att, proposal
    return None


def preview_attachment(  # noqa: C901
    parent_id: str,
    attachment_id: str,
    data_dir: Path,
    source_root: str | None = None,
    output: str | None = None,
    metadata_output: str | None = None,
) -> dict[str, Any]:
    """``import preview``: read-only attachment byte/metadata streaming.

    Reads only files referenced by the persisted review plan, after re-validating
    the expected SHA-256 and size. Never modifies the source hash or mtime.
    """
    plan = read_review_plan(data_dir, parent_id)
    if plan is None:
        return _err(
            IMPORT_REVIEW_PLAN_MISSING,
            f"No persisted review plan for parent: {parent_id}",
            {"import_id": parent_id},
            retryable=False,
        )

    found = _find_attachment_in_plan(plan, attachment_id)
    if found is None:
        return _err(
            IMPORT_PREVIEW_UNAVAILABLE,
            f"Attachment {attachment_id} is not referenced by the review plan.",
            {"import_id": parent_id, "attachment_id": attachment_id},
            retryable=False,
        )
    attachment, proposal = found

    root, err = _resolve_source_root(parent_id, source_root, data_dir)
    if err is not None:
        return err

    from tools.ingest.runner import _resolve_confined_source_path

    source_rel = attachment.get("source_rel_path", "")
    source_abs = _resolve_confined_source_path(root, source_rel)
    if source_abs is None or not source_abs.exists():
        return _err(
            IMPORT_PREVIEW_UNAVAILABLE,
            f"Attachment source is missing or escaped the source root: {source_rel}",
            {
                "import_id": parent_id,
                "attachment_id": attachment_id,
                "source_rel_path": source_rel,
                "reason": "missing",
            },
            retryable=False,
        )

    # Read-only: validate expected SHA + size before exposing bytes.
    try:
        data_bytes = source_abs.read_bytes()
        st = source_abs.stat()
    except OSError as exc:
        return _err(
            IMPORT_PREVIEW_UNAVAILABLE,
            f"Cannot read attachment source: {exc}",
            {"attachment_id": attachment_id, "source_rel_path": source_rel},
            retryable=True,
        )

    actual_sha = "sha256:" + hashlib.sha256(data_bytes).hexdigest()
    expected_sha = attachment.get("source_sha256", "")
    if expected_sha and actual_sha != expected_sha:
        return _err(
            IMPORT_PREVIEW_UNAVAILABLE,
            "Attachment source content no longer matches the review plan (stale).",
            {
                "import_id": parent_id,
                "attachment_id": attachment_id,
                "source_rel_path": source_rel,
                "expected": expected_sha,
                "actual": actual_sha,
                "reason": "stale",
            },
            retryable=False,
        )
    expected_size = attachment.get("size_bytes")
    if expected_size is not None and st.st_size != expected_size:
        return _err(
            IMPORT_PREVIEW_UNAVAILABLE,
            "Attachment source size no longer matches the review plan (stale).",
            {
                "import_id": parent_id,
                "attachment_id": attachment_id,
                "source_rel_path": source_rel,
                "expected": expected_size,
                "actual": st.st_size,
                "reason": "stale",
            },
            retryable=False,
        )

    metadata = {
        "schema_version": PREVIEW_SCHEMA_VERSION,
        "parent_id": parent_id,
        "attachment_id": attachment_id,
        "proposal_id": proposal.get("proposal_id", ""),
        "source_rel_path": source_rel,
        "source_sha256": actual_sha,
        "size_bytes": st.st_size,
        "media_type": attachment.get("media_type", ""),
        "available": True,
    }
    if metadata_output:
        Path(metadata_output).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _ok({"bytes": data_bytes, "metadata": metadata})


# ---------------------------------------------------------------------------
# Batch run: single active child + idempotent reconciliation
# ---------------------------------------------------------------------------


def _new_child_id(parent_id: str, selected_proposal_ids: list[str]) -> str:
    """Deterministic child batch id for a given parent + selection."""
    digest = hashlib.sha256(
        ("\0".join(sorted(selected_proposal_ids))).encode("utf-8")
    ).hexdigest()[:10]
    return f"{parent_id}#batch-{digest}"


def _detect_stale(
    proposals: list[dict[str, Any]], root: Path
) -> tuple[list[dict[str, Any]], list[str]]:
    """Re-hash each selected proposal's sources; partition runnable vs stale.

    Read-only. A proposal is stale if any of its attachments is missing or its
    content/size no longer matches the review plan.
    """
    from tools.ingest.runner import _resolve_confined_source_path

    runnable: list[dict[str, Any]] = []
    stale_ids: list[str] = []
    for proposal in proposals:
        is_stale = False
        for att in proposal.get("attachments", []) or []:
            src = _resolve_confined_source_path(root, att.get("source_rel_path", ""))
            if src is None or not src.exists():
                is_stale = True
                break
            try:
                actual_sha = "sha256:" + hashlib.sha256(src.read_bytes()).hexdigest()
                actual_size = src.stat().st_size
            except OSError:
                is_stale = True
                break
            if actual_sha != att.get("source_sha256") or actual_size != att.get("size_bytes"):
                is_stale = True
                break
        if is_stale:
            stale_ids.append(proposal.get("proposal_id", ""))
        else:
            runnable.append(proposal)
    return runnable, stale_ids


def _toctou_copy(
    source_abs: Path, target_abs: Path, expected_sha: str, expected_size: int
) -> tuple[bool, str]:
    """Read-only stream -> create-only staging -> atomic publish.

    Returns ``(ok, actual_sha_or_reason)``. Never writes to the source; the
    final attachment is published atomically only when the streamed SHA/size
    match the review plan.
    """
    try:
        data = source_abs.read_bytes()
    except OSError as exc:
        return False, f"unreadable:{exc}"
    actual_sha = "sha256:" + hashlib.sha256(data).hexdigest()
    if actual_sha != expected_sha:
        return False, "sha_mismatch"
    if len(data) != expected_size:
        return False, "size_mismatch"
    target_abs.parent.mkdir(parents=True, exist_ok=True)
    if target_abs.exists():
        return False, "target_exists"
    staging = target_abs.with_name(
        target_abs.name + ".staging-" + actual_sha.removeprefix("sha256:")[:8]
    )
    staging.write_bytes(data)
    try:
        os.replace(staging, target_abs)  # atomic publish
    finally:
        if staging.exists():
            try:
                staging.unlink()
            except OSError:
                pass
    return True, actual_sha


def _reconcile_parent(ledger: dict[str, Any], parent_id: str, data_dir: Path) -> None:
    """Idempotently reconcile a parent's active child across crash windows.

    Covers: crash-after-batching-before-child, child-before-manifest,
    commit-before-projection, and repeated reconciliation. Mutates the parent
    job in *ledger* in place (caller persists).
    """
    from tools.ingest.runner import _read_rollback_manifest, execute_rollback

    jobs = ledger.get("jobs", {})
    job = jobs.get(parent_id)
    if not isinstance(job, dict):
        return
    child_id = job.get("active_child_id")
    if not child_id:
        return
    proposal_states = dict(job.get("proposal_states", {}) or {})
    selected = job.get("selected_proposal_ids", []) or []

    def _restore_confirmed() -> None:
        # Any selected proposal this batch touched (batching or already
        # imported) goes back to confirmed so the user can re-run after a
        # rollback or a crashed/interrupted child.
        for pid in selected:
            if proposal_states.get(pid) in (STATE_BATCHING, STATE_IMPORTED):
                proposal_states[pid] = STATE_CONFIRMED

    child_job = jobs.get(child_id)
    child_manifest = _read_rollback_manifest(data_dir, child_id)
    child_state = child_job.get("state") if isinstance(child_job, dict) else None

    # Window 1: batch transition recorded but no child evidence at all.
    if not child_job and not child_manifest:
        job["active_child_id"] = None
        _restore_confirmed()
        job["proposal_states"] = proposal_states
        job["recovery_required"] = False
        return

    # Window 3: child committed -> project imported, clear active child.
    if child_state == "committed":
        for pid in selected:
            proposal_states[pid] = STATE_IMPORTED
        job["active_child_id"] = None
        job["proposal_states"] = proposal_states
        job["recovery_required"] = False
        return

    # Child rolled back -> restore confirmed.
    if child_state == "rolled_back":
        _restore_confirmed()
        job["active_child_id"] = None
        job["proposal_states"] = proposal_states
        job["recovery_required"] = False
        return

    has_created_evidence = bool(child_manifest and child_manifest.get("created_files"))

    # Child partial/failed WITH created evidence -> compensate, then restore.
    if child_state in ("partially_committed", "failed") and has_created_evidence:
        comp = execute_rollback(import_id=child_id, data_dir=data_dir)
        if comp["success"]:
            _restore_confirmed()
            job["active_child_id"] = None
            job["recovery_required"] = False
        else:
            job["recovery_required"] = True
        job["proposal_states"] = proposal_states
        return

    # Child still running (possible live writer) -> fail closed.
    if child_state == "running":
        job["recovery_required"] = True
        return

    # Unknown / failed-without-evidence -> safe to clear and restore.
    _restore_confirmed()
    job["active_child_id"] = None
    job["proposal_states"] = proposal_states
    job["recovery_required"] = False


def _execute_child_batch(  # noqa: C901
    child_id: str,
    parent_id: str,
    proposals: list[dict[str, Any]],
    data_dir: Path,
    root: Path,
    ledger: dict[str, Any],
) -> dict[str, Any]:
    """Create the child batch job and durably write canonical journals + bytes.

    Reuses the same ledger / manifest / fingerprint authority as the legacy
    run path. Journals are canonical (``format_journal_content``); attachments
    are TOCTOU-copied via create-only staging + atomic publish.
    """
    from tools.ingest.runner import (
        _file_sha256,
        _resolve_confined_file_path,
        _resolve_confined_source_path,
        _write_manifest,
    )

    now = _now_iso()
    rollback_rel = f".life-index/import-jobs/{child_id}/rollback-manifest.json"
    jobs = ledger.setdefault("jobs", {})
    jobs[child_id] = {
        "kind": "batch",
        "parent_review_job_id": parent_id,
        "state": "running",
        "rollback_manifest_rel_path": rollback_rel,
        "updated_at": now,
    }
    _write_ledger(data_dir, ledger)

    rollback_abs = data_dir / rollback_rel
    rollback_abs.parent.mkdir(parents=True, exist_ok=True)
    created_files: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {
        "schema_version": ROLLBACK_MANIFEST_SCHEMA_VERSION,
        "import_id": child_id,
        "parent_review_job_id": parent_id,
        "created_at": now,
        "state": "running",
        "created_files": created_files,
        "preexisting_files": [],
        "errors": [],
    }
    _write_manifest(rollback_abs, manifest)

    write_error: str | None = None
    try:
        for proposal in proposals:
            journal = proposal.get("journal", {})
            journal_rel = journal.get("target_rel_path", "")
            journal_abs = _resolve_confined_file_path(data_dir, journal_rel)
            if journal_abs is None:
                raise RuntimeError(f"Unsafe journal target: {journal_rel}")
            journal_abs.parent.mkdir(parents=True, exist_ok=True)

            # Publish attachments first (TOCTOU); journal references FINAL paths.
            published: list[dict[str, Any]] = []
            for att in proposal.get("attachments", []) or []:
                att_rel = att["target_rel_path"]
                att_abs = _resolve_confined_file_path(data_dir, att_rel)
                if att_abs is None:
                    raise RuntimeError(f"Unsafe attachment target: {att_rel}")
                src_abs = _resolve_confined_source_path(root, att.get("source_rel_path", ""))
                if src_abs is None or not src_abs.exists():
                    raise RuntimeError(f"Attachment source missing: {att.get('source_rel_path')}")
                ok_copy, info = _toctou_copy(
                    src_abs, att_abs, att["source_sha256"], att["size_bytes"]
                )
                if not ok_copy:
                    raise RuntimeError(f"TOCTOU copy failed for {att_rel}: {info}")
                created_files.append(
                    {
                        "kind": "attachment",
                        "rel_path": att_rel,
                        "sha256_after": "sha256:" + _file_sha256(att_abs),
                        "size_bytes": att_abs.stat().st_size,
                        "created_by_import": True,
                    }
                )
                _write_manifest(rollback_abs, manifest)
                published.append(
                    {
                        "rel_path": att_rel,
                        "sha256": att["source_sha256"],
                        "size": att["size_bytes"],
                        "media_type": att.get("media_type", ""),
                    }
                )

            # Canonical journal (schema_version, valid topic=life, attachments SSOT).
            journal_data = {
                "schema_version": SCHEMA_VERSION,
                "title": journal.get("title", ""),
                "date": journal.get("date", ""),
                "topic": "life",
                "tags": journal.get("tags", ["imported", "photo"]),
                "attachments": published,
                "content": journal.get("content", ""),
            }
            journal_abs.write_text(format_journal_content(journal_data), encoding="utf-8")
            created_files.append(
                {
                    "kind": "journal",
                    "rel_path": journal_rel,
                    "sha256_after": "sha256:" + _file_sha256(journal_abs),
                    "size_bytes": journal_abs.stat().st_size,
                    "created_by_import": True,
                }
            )
            _write_manifest(rollback_abs, manifest)
    except (OSError, RuntimeError) as exc:
        write_error = str(exc)

    now = _now_iso()
    journal_count = sum(1 for f in created_files if f["kind"] == "journal")
    attachment_count = sum(1 for f in created_files if f["kind"] == "attachment")

    if write_error is not None:
        if created_files:
            manifest["state"] = "partially_committed"
            manifest["errors"] = [write_error]
            _write_manifest(rollback_abs, manifest)
            jobs[child_id]["state"] = "partially_committed"
            jobs[child_id]["updated_at"] = now
            _write_ledger(data_dir, ledger)
            return _err(
                "IMPORT_WRITE_FAILURE",
                f"Child batch partially committed then failed: {write_error}",
                {
                    "child_id": child_id,
                    "parent_id": parent_id,
                    "created_journal_count": journal_count,
                    "created_attachment_count": attachment_count,
                },
                retryable=True,
            )
        manifest["state"] = "failed"
        manifest["errors"] = [write_error]
        _write_manifest(rollback_abs, manifest)
        jobs[child_id]["state"] = "failed"
        jobs[child_id]["updated_at"] = now
        _write_ledger(data_dir, ledger)
        return _err(
            "IMPORT_WRITE_FAILURE",
            f"Child batch failed before any file was created: {write_error}",
            {"child_id": child_id, "parent_id": parent_id},
            retryable=True,
        )

    manifest["state"] = "committed"
    _write_manifest(rollback_abs, manifest)
    jobs[child_id]["state"] = "committed"
    jobs[child_id]["updated_at"] = now
    _write_ledger(data_dir, ledger)
    return _ok(
        {
            "schema_version": RUN_SCHEMA_VERSION,
            "import_id": child_id,
            "parent_id": parent_id,
            "kind": "batch",
            "state": "committed",
            "created_journal_count": journal_count,
            "created_attachment_count": attachment_count,
            "rollback_manifest_rel_path": rollback_rel,
            "post_run_actions": {"index_rebuild_recommended": True},
        }
    )


def run_batch(  # noqa: C901
    parent_id: str, data_dir: Path, source_root: str | None = None
) -> dict[str, Any]:
    """``import run --import-id``: single-active-child batch run.

    Per-parent locked. Reconciles any prior active child, enforces a single
    active child, re-hashes sources (stale detection), transitions selected
    ``confirmed`` proposals to ``batching`` (durable), then creates the child
    batch job. Idempotent reconciliation covers the four crash windows.
    """
    lock = FileLock(_review_lock_path(data_dir, parent_id), timeout=30.0)
    with lock:
        ledger = _read_ledger(data_dir)
        job = _get_job(ledger, parent_id)
        if not _is_review_job(job):
            return _err(
                "IMPORT_JOB_NOT_FOUND",
                f"No parent review job found for import-id: {parent_id}",
                {"import_id": parent_id},
                retryable=False,
            )

        # 1. Reconcile any prior active child (crash recovery).
        _reconcile_parent(ledger, parent_id, data_dir)
        _write_ledger(data_dir, ledger)
        job = _get_job(ledger, parent_id)

        # 2. Single active child.
        if job.get("active_child_id"):
            return _err(
                IMPORT_BATCH_ALREADY_ACTIVE,
                "Parent already has an unsettled active child batch.",
                {"import_id": parent_id, "active_child_id": job["active_child_id"]},
                retryable=False,
            )

        # 3. Persisted review plan.
        plan = read_review_plan(data_dir, parent_id)
        if plan is None:
            return _err(
                IMPORT_REVIEW_PLAN_MISSING,
                f"No persisted review plan for parent: {parent_id}",
                {"import_id": parent_id},
                retryable=False,
            )

        # 4. Source root identity.
        root, err = _resolve_source_root(parent_id, source_root, data_dir)
        if err is not None:
            return err

        # 5. Select confirmed proposals.
        proposal_states = dict(job.get("proposal_states", {}) or {})
        selected = [
            p
            for p in plan.get("proposals", [])
            if proposal_states.get(p.get("proposal_id")) == STATE_CONFIRMED
        ]

        # 6. Stale detection (re-hash sources).
        runnable, stale_ids = _detect_stale(selected, root)
        if stale_ids:
            for pid in stale_ids:
                proposal_states[pid] = STATE_STALE
            job = _get_job(ledger, parent_id)
            job["proposal_states"] = proposal_states
            _write_ledger(data_dir, ledger)
        if not runnable:
            return _err(
                IMPORT_NO_RUNNABLE_PROPOSALS,
                "No runnable proposals in this batch (all stale or skipped).",
                {
                    "import_id": parent_id,
                    "stale": stale_ids,
                    "skipped": [
                        pid
                        for pid, st in proposal_states.items()
                        if st == STATE_SKIPPED
                    ],
                },
                retryable=False,
            )

        # 7. Deterministic child id + durable batching transition.
        child_id = _new_child_id(parent_id, [p.get("proposal_id", "") for p in runnable])
        job = _get_job(ledger, parent_id)
        for proposal in runnable:
            proposal_states[proposal.get("proposal_id", "")] = STATE_BATCHING
        job["active_child_id"] = child_id
        job["selected_proposal_ids"] = [p.get("proposal_id", "") for p in runnable]
        job["proposal_states"] = proposal_states
        job["recovery_required"] = False
        _write_ledger(data_dir, ledger)

        # 8. Create + execute the child batch job.
        result = _execute_child_batch(child_id, parent_id, runnable, data_dir, root, ledger)

        # 9. Reconcile to project child outcome onto parent proposals.
        ledger = _read_ledger(data_dir)
        _reconcile_parent(ledger, parent_id, data_dir)
        _write_ledger(data_dir, ledger)

        if result["success"]:
            data = dict(result["data"])
            data["queue_counts"] = _queue_counts(
                (_get_job(ledger, parent_id) or {}).get("proposal_states", {}) or {}
            )
            return _ok(data)
        return result

