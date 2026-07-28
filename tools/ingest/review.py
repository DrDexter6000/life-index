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
import posixpath
import re
import tempfile
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

# Authority status surfaced when the persisted review plan and the ledger
# disagree with no durable intent to explain it. Reconciliation never silently
# picks one side; it fails closed and leaves repair to the operator (or a fresh
# ``confirm`` that re-derives from an explicit incoming plan).
AUTHORITY_STATUS_PLAN_LEDGER_MISMATCH = "plan_ledger_mismatch"

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

# Proposal states that are durable / authoritative and must never be silently
# downgraded by a re-confirm: an imported/batching proposal is mid-flight or
# already committed, so a fresh confirm may only preserve it (and its frozen
# contents), never overwrite it with an edited journal.
FROZEN_STATES = frozenset({STATE_BATCHING, STATE_IMPORTED})

# States whose attachment content SHAs the scan must treat as already claimed
# (dedup authority): committed bytes plus any review proposal that is queued,
# mid-flight, or already imported. Rolled-back proposals project back to
# ``confirmed`` and therefore remain excluded.
DEDUP_STATES = frozenset({STATE_CONFIRMED, STATE_BATCHING, STATE_IMPORTED})

# ``date_resolution`` statuses (editable, proposal-level). The EXIF authority
# never supplies a date via filesystem mtime; an unresolved capture-time
# conflict can only be resolved by an explicit ``user_confirmed`` date.
DATE_STATUS_EXIF = "exif_authoritative"
DATE_STATUS_USER = "user_confirmed"
DATE_STATUS_UNRESOLVED = "unresolved"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
# Canonical journal target allocation (shared with the planner)
# ---------------------------------------------------------------------------

_JOURNAL_SEQ_RE = re.compile(r"^life-index_(\d{4}-\d{2}-\d{2})_(\d+)\.md$")


def next_seq_for_date(
    date: str, data_dir: Path, used_seqs: dict[str, int]
) -> int:
    """Return the next available sequence number for *date*.

    Considers existing journal files in *data_dir* and sequences already
    allocated in the current pass (tracked via *used_seqs*).
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


def journal_target_rel_path(date: str, seq: int) -> str:
    """Canonical journal target path for a *date* + sequence."""
    year, month, _day = date.split("-")
    return f"Journals/{year}/{month}/life-index_{date}_{seq:03d}.md"


def attachment_target_rel_path(date: str, content_sha256: str) -> str:
    """Canonical attachment target path derived from a resolved date + content."""
    year, month = date.split("-")[:2]
    prefix = content_sha256.removeprefix("sha256:")[:12]
    return f"attachments/{year}/{month}/import_{prefix}.jpg"


# ---------------------------------------------------------------------------
# Date-resolution helpers
# ---------------------------------------------------------------------------


def is_valid_calendar_date(value: Any) -> bool:
    """True only for a strict ``YYYY-MM-DD`` string that is a real calendar date."""
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _has_capture_conflict(proposal: dict[str, Any]) -> bool:
    return any(
        c.get("code") in _PHOTO_CAPTURE_CONFLICT_CODES
        for c in proposal.get("conflicts", [])
    )


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


# The durable parent-projection fields a review job carries. These are the only
# fields the confirm intent/finalize protocol snapshots, restores, and finalizes
# — everything else on the job is transient or managed elsewhere (e.g. child
# recovery by ``_reconcile_parent``). ``authority_status`` and
# ``pending_review_update`` are deliberately excluded: they are control-plane
# markers, not part of the authoritative projection.
_PROJECTION_FIELDS = (
    "kind",
    "state",
    "source_root_identity",
    "review_plan_rel_path",
    "proposal_states",
    "active_child_id",
    "recovery_required",
    "next_batch_sequence",
    "idempotency_key",
    "plan_fingerprint",
    "plan_revision",
)


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


def _is_confined_rel_path(rel_path: Any) -> bool:
    """True for a non-empty relative path with no traversal/absolute escape.

    A purely lexical check (no filesystem access): rejects absolute paths and
    any path containing a ``..`` segment. Full data-dir confinement is enforced
    again at run time via ``_resolve_confined_file_path``.
    """
    if not rel_path or not isinstance(rel_path, str):
        return False
    p = Path(rel_path)
    if p.is_absolute():
        return False
    return all(part != ".." for part in p.parts)


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

    # Each selected attachment must be immutably bound to exactly one source
    # fact in THIS proposal: source_sha256 + source_rel_path + source_ref +
    # media_type + size_bytes must all match the bound fact, the attachment_id
    # must be the deterministic derivation of its own source content, and any
    # supplied target must stay confined (no traversal / absolute escape).
    facts_by_sha: dict[str, dict[str, Any]] = {}
    for facts in facts_list:
        if isinstance(facts, dict):
            content_sha = facts.get("content_sha256")
            if isinstance(content_sha, str):
                facts_by_sha[content_sha] = facts

    for att in proposal.get("attachments", []):
        bound = facts_by_sha.get(att.get("source_sha256"))
        if bound is None:
            return "IMPORT_PLAN_INVALID"
        for att_field, fact_field in (
            ("source_sha256", "content_sha256"),
            ("source_rel_path", "source_rel_path"),
            ("source_ref", "source_ref"),
            ("media_type", "media_type"),
            ("size_bytes", "size_bytes"),
        ):
            if att.get(att_field) != bound.get(fact_field):
                return "IMPORT_PLAN_INVALID"
        # attachment_id is deterministic: att_<source content prefix>.
        expected_id = "att_" + str(att.get("source_sha256", "")).removeprefix("sha256:")[:12]
        if att.get("attachment_id") != expected_id:
            return "IMPORT_PLAN_INVALID"
        att_target = att.get("target_rel_path")
        if att_target and not _is_confined_rel_path(att_target):
            return "IMPORT_PLAN_INVALID"

    # Journal target (when supplied) must also stay confined.
    journal_target = (proposal.get("journal") or {}).get("target_rel_path")
    if journal_target and not _is_confined_rel_path(journal_target):
        return "IMPORT_PLAN_INVALID"

    # Group source_record_fingerprint must match the recomputed group fp.
    if member_fps:
        group_fp = group_source_fingerprint(list(member_fps))
        if group_fp != proposal.get("source_record_fingerprint"):
            return "IMPORT_PLAN_INVALID"

    return None


def _resolve_and_derive_proposal(
    proposal: dict[str, Any], data_dir: Path, used_seqs: dict[str, int]
) -> str:
    """Resolve a proposal's date, derive canonical targets, and return its state.

    Date authority (never filesystem mtime):

    - An explicit ``date_resolution`` with ``status='user_confirmed'`` and a
      valid ``YYYY-MM-DD`` is the highest authority — it resolves even an
      immutable EXIF capture-time conflict and overrides an EXIF date.
    - A proposal with no capture conflict is authoritative via its EXIF date
      (offset = recorded local calendar date, no UTC conversion; naive =
      camera-local; a malformed offset is not trusted but the date is still
      used as naive).
    - A proposal with a capture conflict and no valid ``user_confirmed``
      resolution stays ``pending`` (the explicit unresolved area) with empty
      date/target — it is never auto-dated and never runnable.

    Selection: an empty attachments list is ``skipped`` (no empty journal).
    """
    attachments = proposal.get("attachments", []) or []
    if not attachments:
        proposal["state"] = STATE_SKIPPED
        return STATE_SKIPPED

    has_conflict = _has_capture_conflict(proposal)
    dr = proposal.get("date_resolution") or {}
    status = dr.get("status")
    dr_date = dr.get("date", "")
    journal = proposal.setdefault("journal", {})

    effective_date: str | None = None
    if status == DATE_STATUS_USER and is_valid_calendar_date(dr_date):
        effective_date = dr_date
    elif not has_conflict:
        jdate = journal.get("date", "")
        if is_valid_calendar_date(jdate):
            effective_date = jdate

    if effective_date is not None:
        journal["date"] = effective_date
        # Canonical journal target derived from the effective date + sequence,
        # never trusted from incoming GUI edits (a non-frozen proposal's target
        # is always re-derived so it stays within the canonical date path).
        seq = next_seq_for_date(effective_date, data_dir, used_seqs)
        journal["target_rel_path"] = journal_target_rel_path(effective_date, seq)
        # Canonical attachment target derived from the effective date + content.
        for att in attachments:
            att["target_rel_path"] = attachment_target_rel_path(
                effective_date, att.get("source_sha256", "")
            )
        proposal["date_resolution"] = {
            "status": DATE_STATUS_USER if status == DATE_STATUS_USER else DATE_STATUS_EXIF,
            "date": effective_date,
        }
        proposal["state"] = STATE_CONFIRMED
        return STATE_CONFIRMED

    # Unresolved: keep date/target empty (non-runnable), record the conflict.
    journal["date"] = ""
    journal["target_rel_path"] = ""
    for att in attachments:
        # Attachments keep a content-derived identity; their target stays empty
        # until the proposal is resolved.
        att["target_rel_path"] = ""
    proposal["date_resolution"] = {"status": DATE_STATUS_UNRESOLVED, "date": ""}
    proposal["state"] = STATE_PENDING
    return STATE_PENDING


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


def _projection_snapshot(job: dict[str, Any] | None) -> dict[str, Any] | None:
    """Snapshot the authoritative projection of a review job, or None.

    Returns None when *job* is not a review job (first confirm). Used to capture
    the pre-update projection so a crashed confirm can restore it verbatim.
    """
    if not isinstance(job, dict) or job.get("kind") != "review":
        return None
    return {field: job.get(field) for field in _PROJECTION_FIELDS}


def _rebuild_review_job_from_plan(
    jobs: dict[str, Any], parent_id: str, plan: dict[str, Any]
) -> None:
    """Rebuild a parent review projection from a surviving persisted plan.

    Used when the ledger lost its parent job but the review plan survived
    (crash after plan replace, before the ledger was ever written on a first
    confirm with no shell, or a manual ledger wipe). The plan's recorded
    per-proposal states are authoritative; durable states are never reset.
    """
    proposal_states = {
        p.get("proposal_id", ""): p.get("state", STATE_PENDING)
        for p in plan.get("proposals", [])
        if isinstance(p, dict)
    }
    jobs[parent_id] = {
        "kind": "review",
        "state": "confirmed",
        "source_root_identity": plan.get("source_root_identity", ""),
        "review_plan_rel_path": _review_plan_rel_path(parent_id),
        "proposal_states": proposal_states,
        "active_child_id": None,
        "recovery_required": False,
        "next_batch_sequence": 1,
        "idempotency_key": plan.get("idempotency_key", ""),
        "plan_fingerprint": plan.get("plan_fingerprint", ""),
        "plan_revision": plan.get("plan_revision", 1) or 1,
        "updated_at": _now_iso(),
    }


def _apply_intent_finalize(
    jobs: dict[str, Any], parent_id: str, intent: dict[str, Any]
) -> None:
    """Apply a finalized projection from *intent* in place (caller persists).

    Idempotent: replaying a finalize whose projection is already applied yields
    the same authoritative job. Clears the pending intent and any stale fail-
    closed status.
    """
    projection = intent.get("projection") or {}
    job = jobs.get(parent_id)
    if not isinstance(job, dict):
        job = {"kind": "review"}
        jobs[parent_id] = job
    job["kind"] = "review"
    job["state"] = "confirmed"
    job["source_root_identity"] = projection.get("source_root_identity", "")
    job["review_plan_rel_path"] = _review_plan_rel_path(parent_id)
    job["proposal_states"] = projection.get("proposal_states", {})
    job["active_child_id"] = None
    job["recovery_required"] = False
    job["next_batch_sequence"] = projection.get("next_batch_sequence", 1)
    job["idempotency_key"] = projection.get("idempotency_key", "")
    job["plan_fingerprint"] = projection.get("plan_fingerprint", "")
    job["plan_revision"] = intent.get(
        "expected_plan_revision", job.get("plan_revision", 1) or 1
    )
    job.pop("pending_review_update", None)
    job.pop("authority_status", None)
    job["updated_at"] = _now_iso()


def _apply_intent_abort(
    jobs: dict[str, Any], parent_id: str, intent: dict[str, Any]
) -> None:
    """Abort a pending intent whose plan replace never happened (caller persists).

    - No prior projection (``intent.prior`` is None) → remove the empty
      first-confirm shell entirely.
    - Prior projection present → restore it verbatim and clear the intent.
    """
    prior = intent.get("prior")
    if not prior:
        jobs.pop(parent_id, None)
        return
    job = jobs.get(parent_id)
    if not isinstance(job, dict):
        job = {"kind": "review"}
        jobs[parent_id] = job
    for field in _PROJECTION_FIELDS:
        if field in prior:
            job[field] = prior[field]
    job.pop("pending_review_update", None)
    job.pop("authority_status", None)
    job["updated_at"] = _now_iso()


def _reconcile_review_authority_locked(
    ledger: dict[str, Any], parent_id: str, data_dir: Path
) -> bool:
    """Converge the parent review authority across the confirm crash windows.

    Mutates *ledger* in place; returns True if it changed. The caller holds the
    per-parent lock and persists.

    Three durable explanations are handled, in order:

    1. A pending ``pending_review_update`` intent is present:
       - persisted plan fingerprint == ``intent.expected_plan_fingerprint``
         → the plan replace succeeded but finalize was interrupted → finalize
         idempotently from the intent (crash after plan, before finalize);
       - otherwise the plan is still old / absent → the replace never happened
         → abort: retain the prior projection, or remove an empty first-confirm
         shell (crash after intent, before plan).
    2. No intent, but the persisted plan fingerprint disagrees with the ledger's
       ``plan_fingerprint`` → fail closed (``recovery_required`` +
       ``authority_status``); never silently choose one.
    3. No intent and consistent → leave the ledger authority intact; rebuild a
       missing parent from a surviving plan, and backfill empty states.

    Repeated reconciliation converges: each branch leaves the job either fully
    finalized, restored, or explicitly fail-closed, so a second pass is a no-op.
    """
    jobs = ledger.setdefault("jobs", {})
    job = jobs.get(parent_id)
    plan = read_review_plan(data_dir, parent_id)
    persisted_fp = plan.get("plan_fingerprint") if isinstance(plan, dict) else None
    intent = job.get("pending_review_update") if isinstance(job, dict) else None

    if isinstance(intent, dict):
        expected_fp = intent.get("expected_plan_fingerprint")
        if persisted_fp is not None and persisted_fp == expected_fp:
            _apply_intent_finalize(jobs, parent_id, intent)
        else:
            _apply_intent_abort(jobs, parent_id, intent)
        return True

    if not isinstance(job, dict) or job.get("kind") != "review":
        if isinstance(plan, dict):
            _rebuild_review_job_from_plan(jobs, parent_id, plan)
            return True
        return False

    # Review job present, no intent.
    ledger_fp = job.get("plan_fingerprint")
    if persisted_fp is not None and ledger_fp and persisted_fp != ledger_fp:
        # Unexplained mismatch: plan and ledger disagree with nothing to explain
        # it. Fail closed rather than silently picking an authority. Once
        # already fail-closed for this same mismatch, repeated status is a no-op
        # (convergence) and must not rewrite unchanged state.
        already_closed = (
            job.get("recovery_required") is True
            and job.get("authority_status") == AUTHORITY_STATUS_PLAN_LEDGER_MISMATCH
        )
        job["recovery_required"] = True
        job["authority_status"] = AUTHORITY_STATUS_PLAN_LEDGER_MISMATCH
        if already_closed:
            return False
        job["updated_at"] = _now_iso()
        return True

    changed = False
    if "authority_status" in job:
        job.pop("authority_status", None)
        changed = True
    states = job.get("proposal_states") or {}
    if not states and isinstance(plan, dict):
        job["proposal_states"] = {
            p.get("proposal_id", ""): p.get("state", STATE_PENDING)
            for p in plan.get("proposals", [])
            if isinstance(p, dict)
        }
        job["updated_at"] = _now_iso()
        changed = True
    return changed


def reconcile_review_authority(data_dir: Path, parent_id: str) -> None:
    """Locking entry point: reconcile a parent's plan/ledger authority + child.

    Both the plan/ledger authority and the active child are reconciled under
    the single per-parent lock, so ``status`` (which calls this) surfaces a
    converged, executable recovery state just like ``run``/``rollback``. The
    ledger is written only when something actually changed (convergence).
    """
    lock = FileLock(_review_lock_path(data_dir, parent_id), timeout=30.0)
    with lock:
        ledger = _read_ledger(data_dir)
        changed = _reconcile_review_authority_locked(ledger, parent_id, data_dir)
        changed = _reconcile_parent(ledger, parent_id, data_dir) or changed
        if changed:
            _write_ledger(data_dir, ledger)


# ---------------------------------------------------------------------------
# Durable intent/finalize protocol (crash-safe plan↔ledger update)
# ---------------------------------------------------------------------------


def _persist_review_intent(
    data_dir: Path,
    ledger: dict[str, Any],
    parent_id: str,
    intent: dict[str, Any],
) -> None:
    """Durably record a pending review-update intent on the parent job.

    Step I1 of the confirm protocol: write the intent (carrying the expected
    plan fingerprint/revision, the complete finalized projection, and a
    snapshot of the prior projection) to the ledger *before* the review plan is
    replaced. If the process crashes after this and before the plan replace,
    reconciliation aborts the intent and restores the prior projection (or
    removes an empty first-confirm shell). The caller holds the per-parent lock.
    """
    jobs = ledger.setdefault("jobs", {})
    job = jobs.get(parent_id)
    if not isinstance(job, dict):
        projection = intent.get("projection") or {}
        job = {
            "kind": "review",
            "state": "confirming",
            "review_plan_rel_path": _review_plan_rel_path(parent_id),
            "proposal_states": {},
            "active_child_id": None,
            "recovery_required": False,
            "next_batch_sequence": projection.get("next_batch_sequence", 1),
            "idempotency_key": projection.get("idempotency_key", ""),
            "plan_fingerprint": "",
            "plan_revision": 0,
        }
        jobs[parent_id] = job
    job["pending_review_update"] = intent
    job["updated_at"] = _now_iso()
    _write_ledger(data_dir, ledger)


def _finalize_review_update(
    data_dir: Path,
    ledger: dict[str, Any],
    parent_id: str,
    intent: dict[str, Any],
) -> None:
    """Apply the finalized projection from *intent* and clear it (step F).

    Idempotent with reconciliation: replaying this against the same intent is a
    no-op. The caller holds the per-parent lock and has just replaced the
    review plan atomically.
    """
    _apply_intent_finalize(ledger.setdefault("jobs", {}), parent_id, intent)
    _write_ledger(data_dir, ledger)


def confirm_review(  # noqa: C901
    plan_path: str,
    data_dir: Path,
    source_root: str | None = None,
    parent_id_override: str | None = None,
) -> dict[str, Any]:
    """``import confirm``: persist a review plan and record a parent review job.

    Under the per-parent lock this reconciles the plan/ledger authority, refuses
    to mutate while an active child batch is unsettled, then merges the incoming
    plan onto any existing review state: imported/batching proposals are frozen
    (never downgraded, their contents authoritative and unchanged), while
    pending/confirmed/skipped proposals accept safe edits and (re-)derive their
    date resolution and canonical targets.
    """
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

    # --- Per-parent single-writer lock: reconcile, merge, persist ---
    lock = FileLock(_review_lock_path(data_dir, parent_id), timeout=30.0)
    with lock:
        ledger = _read_ledger(data_dir)
        _reconcile_review_authority_locked(ledger, parent_id, data_dir)
        existing_job = _get_job(ledger, parent_id)

        # Refuse to mutate the queue while a child batch is unsettled.
        if existing_job and existing_job.get("active_child_id"):
            _write_ledger(data_dir, ledger)  # persist any reconciliation above
            return _err(
                IMPORT_BATCH_ALREADY_ACTIVE,
                "Cannot edit the review queue while a child batch is active.",
                {
                    "import_id": parent_id,
                    "active_child_id": existing_job.get("active_child_id"),
                },
                retryable=False,
            )

        existing_states = (existing_job or {}).get("proposal_states", {}) or {}
        existing_plan = read_review_plan(data_dir, parent_id)
        existing_by_id: dict[str, dict[str, Any]] = {}
        if isinstance(existing_plan, dict):
            for p in existing_plan.get("proposals", []):
                if isinstance(p, dict) and p.get("proposal_id"):
                    existing_by_id[p["proposal_id"]] = p

        # --- Merge: freeze imported/batching; re-derive the rest ---
        merged: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        used_seqs: dict[str, int] = {}
        for proposal in proposals:
            pid = proposal.get("proposal_id", "")
            seen_ids.add(pid)
            if existing_states.get(pid) in FROZEN_STATES and pid in existing_by_id:
                # Frozen: authoritative existing contents preserved unchanged.
                # The ledger's proposal_states is the authoritative state and may
                # be ahead of the persisted plan's per-proposal ``state`` field
                # (e.g. imported after a run), so it wins — frozen proposals never
                # downgrade and their contents are never overwritten by the
                # incoming plan.
                frozen = dict(existing_by_id[pid])
                frozen["state"] = existing_states[pid]
                merged.append(frozen)
            else:
                _resolve_and_derive_proposal(proposal, data_dir, used_seqs)
                merged.append(proposal)

        # Keep frozen proposals that the incoming plan no longer lists (still
        # committed to the queue truth).
        for pid, p in existing_by_id.items():
            if pid not in seen_ids and existing_states.get(pid) in FROZEN_STATES:
                frozen = dict(p)
                frozen["state"] = existing_states[pid]
                merged.append(frozen)

        plan["proposals"] = merged
        plan = _recompute_plan_fingerprints(plan)

        proposal_states: dict[str, str] = {}
        for p in merged:
            proposal_states[p.get("proposal_id", "")] = p.get("state", STATE_PENDING)

        plan["schema_version"] = REVIEW_PLAN_SCHEMA_VERSION
        plan["parent_id"] = parent_id
        # Prefer a freshly supplied identity, else preserve the recorded one.
        if not source_root_identity:
            source_root_identity = (existing_job or {}).get("source_root_identity", "")
        plan["source_root_identity"] = source_root_identity
        plan["confirmed_at"] = _now_iso()

        counts = _queue_counts(proposal_states)

        # --- Durable intent/revision protocol: crash-safe plan↔ledger update.
        # The merged plan + projection are computed first; a pending intent is
        # then atomically persisted on the parent job (I1) BEFORE the review plan
        # is replaced (P), and the parent projection is finalized from that
        # intent afterwards (F). A crash in either window converges via
        # reconciliation; the ledger stays the sole authority (no second store).
        plan_fingerprint = plan.get("plan_fingerprint", "")
        next_batch_sequence = (existing_job or {}).get("next_batch_sequence", 1)
        idempotency_key = plan.get("idempotency_key", "")
        new_revision = (int((existing_job or {}).get("plan_revision", 0)) or 0) + 1
        plan["plan_revision"] = new_revision

        intent = {
            "expected_plan_fingerprint": plan_fingerprint,
            "expected_plan_revision": new_revision,
            "projection": {
                "proposal_states": proposal_states,
                "plan_fingerprint": plan_fingerprint,
                "source_root_identity": source_root_identity,
                "next_batch_sequence": next_batch_sequence,
                "idempotency_key": idempotency_key,
            },
            "prior": _projection_snapshot(existing_job),
            "created_at": _now_iso(),
        }

        # I1: durable intent → P: atomic plan replace → F: finalize + clear.
        _persist_review_intent(data_dir, ledger, parent_id, intent)
        _write_review_plan_atomic(data_dir, parent_id, plan)
        _finalize_review_update(data_dir, ledger, parent_id, intent)

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
                for p in merged
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
    # Reconcile the plan/ledger authority first so a crashed ledger can be
    # restored from the persisted review plan (never a silent reset).
    reconcile_review_authority(data_dir, import_id)
    ledger = _read_ledger(data_dir)
    job = _get_job(ledger, import_id)
    if not isinstance(job, dict) or job.get("kind") != "review":
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
            "authority_status": job.get("authority_status"),
            "plan_fingerprint": job.get("plan_fingerprint", ""),
            "plan_revision": job.get("plan_revision", 1) or 1,
            "review_plan_rel_path": job.get("review_plan_rel_path", ""),
        }
    )


# ---------------------------------------------------------------------------
# Rollback: parent review job is not rollable as a whole
# ---------------------------------------------------------------------------


def _project_parent_after_child_rollback(
    data_dir: Path, parent_id: str, child_proposal_ids: list[str]
) -> None:
    """Restore a rolled-back child's exact membership to ``confirmed``.

    The caller holds the parent's per-parent lock. The projection is driven by
    the child's own ``proposal_ids`` (what THIS batch touched), never by the
    parent's last selection, and only batching/imported proposals move back to
    confirmed. Clears the active child + recovery flag.
    """
    ledger = _read_ledger(data_dir)
    parent = _get_job(ledger, parent_id)
    if not isinstance(parent, dict) or parent.get("kind") != "review":
        return
    proposal_states = dict(parent.get("proposal_states", {}) or {})
    for pid in child_proposal_ids:
        if proposal_states.get(pid) in (STATE_BATCHING, STATE_IMPORTED):
            proposal_states[pid] = STATE_CONFIRMED
    parent["proposal_states"] = proposal_states
    parent["active_child_id"] = None
    parent["recovery_required"] = False
    parent["updated_at"] = _now_iso()
    _write_ledger(data_dir, ledger)


def execute_review_rollback(import_id: str, data_dir: Path) -> dict[str, Any]:
    """``import rollback`` dispatch: refuse parent review jobs, else delegate.

    A child batch job is rolled back and re-projected onto its parent **under the
    parent's per-parent lock** — the same lock ``run`` takes — so the parent↔
    child lock order stays consistent and the projection cannot race a concurrent
    confirm/run/status. The plan/ledger authority is reconciled first, then the
    checksum-guarded child rollback runs, then the exact ``child.proposal_ids``
    projection restores the touched proposals to ``confirmed``. This is what
    makes "rollback restores confirmed" observable via ``import status``.
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

    # The rolled-back job is a child batch; capture its exact membership so the
    # parent projection is driven by what THIS child batch touched, never by the
    # parent's last selection.
    child_proposal_ids = (
        job.get("proposal_ids") if isinstance(job, dict) else None
    ) or []
    parent_id = job.get("parent_review_job_id") if isinstance(job, dict) else None

    # A child batch job rolls back + re-projects its parent under the parent's
    # per-parent lock (consistent parent→child lock order with run). Reconcile
    # the plan/ledger authority first so the projection starts from truth.
    if parent_id:
        lock = FileLock(_review_lock_path(data_dir, parent_id), timeout=30.0)
        with lock:
            pre_ledger = _read_ledger(data_dir)
            if _reconcile_review_authority_locked(pre_ledger, parent_id, data_dir):
                _write_ledger(data_dir, pre_ledger)

            # Checksum-guarded child rollback. execute_rollback holds no lock of
            # its own, so running it under the parent lock preserves a single
            # lock order (parent only) shared with run.
            result = execute_rollback(import_id=import_id, data_dir=data_dir)

            # Exact child.proposal_ids projection under the same lock.
            if result["success"]:
                _project_parent_after_child_rollback(
                    data_dir, parent_id, child_proposal_ids
                )
            return result

    # Legacy / standalone batch job (no parent review job) — unchanged path.
    return execute_rollback(import_id=import_id, data_dir=data_dir)


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


def _child_id_for_seq(parent_id: str, seq: int) -> str:
    """Monotonic child batch id for a parent + durable sequence number."""
    return f"{parent_id}#batch-{seq}"


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


# Bounded chunk size for streaming attachment/journal bytes into staging. The
# copy never loads a whole file into memory: bytes flow read->hash->write in
# fixed-size chunks, so even a very large source is published incrementally.
_STREAM_CHUNK_SIZE = 64 * 1024


def _drain_source_to_staging(
    src_fp: Any,
    dst_fp: Any,
    expected_sha: str,
    expected_size: int,
    chunk_size: int = _STREAM_CHUNK_SIZE,
) -> tuple[bool, str]:
    """Stream ``src_fp`` into ``dst_fp`` in bounded chunks while hashing.

    Hashes and counts bytes as they flow, then flushes + fsyncs the staging
    file. Returns ``(ok, actual_sha_or_reason)``. A source whose streamed
    content/size diverges from the expected values (mutation, truncation, or
    deletion during the copy) yields ``(False, reason)`` so the caller publishes
    nothing. Never writes to the source.
    """
    hasher = hashlib.sha256()
    written = 0
    try:
        while True:
            chunk = src_fp.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
            written += len(chunk)
            dst_fp.write(chunk)
        dst_fp.flush()
        try:
            os.fsync(dst_fp.fileno())
        except OSError:
            pass
    except OSError as exc:
        return False, f"unreadable:{exc}"
    actual_sha = "sha256:" + hasher.hexdigest()
    if actual_sha != expected_sha:
        return False, "sha_mismatch"
    if written != expected_size:
        return False, "size_mismatch"
    return True, actual_sha


def _stream_to_staging(
    source_abs: Path,
    staging_abs: Path,
    expected_sha: str,
    expected_size: int,
    chunk_size: int = _STREAM_CHUNK_SIZE,
) -> tuple[bool, str]:
    """Open source + staging and stream bounded chunks into ``staging_abs``."""
    try:
        with open(source_abs, "rb") as src, open(staging_abs, "wb") as dst:
            return _drain_source_to_staging(
                src, dst, expected_sha, expected_size, chunk_size
            )
    except OSError as exc:
        return False, f"unreadable:{exc}"


def _file_identity(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_dev, st.st_ino


def _publish_create_only(staging_abs: Path, target_abs: Path) -> None:
    """Atomically publish a staged file via a create-only hard link.

    The hard link fails (``FileExistsError``) if the final path already exists,
    so a transaction never overwrites an existing target. The staged bytes and
    the final path share one inode on the same filesystem; the caller unlinks
    the staging name afterwards. Any other ``OSError`` is raised so the caller
    can compensate and fail closed rather than fall back to a clobbering
    rename/replace. Works on POSIX and Windows.
    """
    target_abs.parent.mkdir(parents=True, exist_ok=True)
    staged_identity = _file_identity(staging_abs)
    os.link(staging_abs, target_abs)
    if _file_identity(target_abs) != staged_identity:
        # Another writer raced the publication; do not trust the link.
        raise OSError(f"publication identity changed: {target_abs}")


def _unique_staging(target_abs: Path) -> Path:
    """Allocate a unique same-filesystem staging path beside ``target_abs``."""
    fd, staging_str = tempfile.mkstemp(
        dir=str(target_abs.parent),
        prefix=f".{target_abs.name}.staging-",
        suffix=".tmp",
    )
    os.close(fd)
    return Path(staging_str)


def _stream_copy(
    source_abs: Path,
    target_abs: Path,
    expected_sha: str,
    expected_size: int,
    chunk_size: int = _STREAM_CHUNK_SIZE,
) -> tuple[bool, str]:
    """Read-only stream -> unique same-filesystem staging -> create-only publish.

    Returns ``(ok, actual_sha_or_reason)``. Never writes to the source; the
    final attachment is published (create-only) only when the streamed SHA/size
    match the review plan. Staging is removed on every path (success, mismatch,
    collision, and publish failure), so a mutated/deleted/colliding source
    leaves no final artifact and no staging leftover. Source hash and mtime
    stay unchanged.
    """
    target_abs.parent.mkdir(parents=True, exist_ok=True)
    staging_abs = _unique_staging(target_abs)
    try:
        ok, info = _stream_to_staging(
            source_abs, staging_abs, expected_sha, expected_size, chunk_size
        )
        if not ok:
            return False, info
        try:
            _publish_create_only(staging_abs, target_abs)
        except FileExistsError:
            return False, "target_exists"
        except OSError as exc:
            return False, f"publish_failed:{exc}"
        return True, info
    finally:
        if staging_abs.exists():
            try:
                staging_abs.unlink()
            except OSError:
                pass


def _publish_text_create_only(target_abs: Path, text: str) -> tuple[bool, str]:
    """Stage UTF-8 text + fsync, then create-only publish; never overwrite.

    Used for canonical journal publication: the journal bytes are staged on the
    same filesystem, fsynced, then hard-linked into place only when the target
    does not already exist. Staging is removed on every path.
    """
    target_abs.parent.mkdir(parents=True, exist_ok=True)
    staging_abs = _unique_staging(target_abs)
    try:
        with open(staging_abs, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                pass
        try:
            _publish_create_only(staging_abs, target_abs)
        except FileExistsError:
            return False, "target_exists"
        except OSError as exc:
            return False, f"publish_failed:{exc}"
        return True, ""
    finally:
        if staging_abs.exists():
            try:
                staging_abs.unlink()
            except OSError:
                pass


def _journal_relative_path(journal_rel: str, att_rel: str) -> str:
    """Attachment path relative to the journal file (POSIX, OS-independent).

    Both inputs are data-dir-relative POSIX paths. For the canonical layout a
    journal at ``Journals/YYYY/MM/...`` references an attachment at
    ``attachments/YYYY/MM/...`` as ``../../../attachments/...``.
    """
    return posixpath.relpath(att_rel, start=posixpath.dirname(journal_rel))


def _canonical_attachment_entry(
    att: dict[str, Any], journal_rel: str
) -> dict[str, Any]:
    """Build the canonical stored attachment object for journal frontmatter.

    Matches ``tools/write_journal/attachments.process_attachments`` exactly:
    ``{filename, rel_path, description, original_name, auto_detected,
    content_type, size}`` where ``rel_path`` is journal-relative. Source SHA /
    provenance live only in the import plan / child manifest, never in journal
    frontmatter. The source is never sent through content auto-detection.
    """
    att_rel = att.get("target_rel_path", "")
    return {
        "filename": posixpath.basename(att_rel),
        "rel_path": _journal_relative_path(journal_rel, att_rel),
        "description": "",
        "original_name": posixpath.basename(
            att.get("source_rel_path", "") or att_rel
        ),
        "auto_detected": False,
        "content_type": att.get("media_type", ""),
        "size": att.get("size_bytes"),
    }


def _validate_committed_manifest(
    data_dir: Path,
    child_id: str,
    parent_id: str,
    manifest: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Validate a committed rollback manifest before trusting it as the commit fact.

    Confines every created-file path under ``data_dir`` and verifies each
    artifact against its recorded hash/size, and checks schema / state /
    import-id / parent linkage. Returns ``(valid, reason)``. A child ledger
    that claims committed but has a missing, invalid, non-committed,
    wrong-parent, or wrong-import manifest fails closed here; it is never used
    to project imported.
    """
    from tools.ingest.runner import _file_sha256, _resolve_confined_file_path

    if not isinstance(manifest, dict):
        return False, "manifest_missing"
    if manifest.get("schema_version") != ROLLBACK_MANIFEST_SCHEMA_VERSION:
        return False, "schema_mismatch"
    if manifest.get("state") != "committed":
        return False, "manifest_not_committed"
    if manifest.get("import_id") != child_id:
        return False, "wrong_import_id"
    if manifest.get("parent_review_job_id") != parent_id:
        return False, "wrong_parent"
    created = manifest.get("created_files")
    if not isinstance(created, list):
        return False, "no_created_files"
    for entry in created:
        if not isinstance(entry, dict) or not entry.get("created_by_import", False):
            continue
        rel = entry.get("rel_path")
        confined = _resolve_confined_file_path(data_dir, rel)
        if confined is None:
            return False, f"unconfined:{rel}"
        if not confined.exists():
            return False, f"missing:{rel}"
        if entry.get("sha256_after") != "sha256:" + _file_sha256(confined):
            return False, f"hash_mismatch:{rel}"
        expected_size = entry.get("size_bytes")
        if expected_size is not None and confined.stat().st_size != expected_size:
            return False, f"size_mismatch:{rel}"
    return True, ""


def _reconcile_parent(
    ledger: dict[str, Any], parent_id: str, data_dir: Path
) -> bool:
    """Idempotently reconcile a parent's active child across crash windows.

    Returns True iff the parent projection changed; callers persist only then,
    so repeated status/run/rollback converge without rewriting unchanged state.
    The caller holds the per-parent lock.

    Crash windows handled:

    - No child job and no durable created evidence -> restore the exact child
      ``proposal_ids`` to confirmed and clear the active child.
    - A valid committed rollback manifest is the durable commit fact: if the
      child ledger projection was interrupted, reconcile the child to committed
      and project its proposals to imported.
    - A child ledger that claims committed but has a missing/invalid/
      non-committed/wrong-parent/wrong-import manifest fails closed
      (``recovery_required``); it never projects imported.
    - running / partially_committed / failed with created evidence ->
      checksum-guarded compensation; restore confirmed only on complete
      compensation, else retain batching + ``recovery_required``.
    - running with no evidence is ambiguous (possible live writer) ->
      ``recovery_required``, retain the active child.
    """
    from tools.ingest.runner import _read_rollback_manifest, execute_rollback

    jobs = ledger.get("jobs", {})
    job = jobs.get(parent_id)
    if not isinstance(job, dict) or job.get("kind") != "review":
        return False
    child_id = job.get("active_child_id")
    if not child_id:
        # Already settled (no active child): a pure no-op for convergence.
        return False

    proposal_states = dict(job.get("proposal_states", {}) or {})
    child_job = jobs.get(child_id)
    child_manifest = _read_rollback_manifest(data_dir, child_id)
    child_state = child_job.get("state") if isinstance(child_job, dict) else None

    # The exact membership this child batch touched lives on the child job
    # (``proposal_ids``); only fall back to the parent's recorded selection for
    # legacy/seeded children that predate the mapping.
    selected = (
        (child_job.get("proposal_ids") if isinstance(child_job, dict) else None)
        or job.get("selected_proposal_ids")
        or []
    )
    has_evidence = bool(
        isinstance(child_manifest, dict)
        and isinstance(child_manifest.get("created_files"), list)
        and child_manifest["created_files"]
    )

    def restore_confirmed() -> None:
        # Any selected proposal this batch touched (batching or already
        # imported) goes back to confirmed so the user can re-run after a
        # rollback or a crashed/interrupted child.
        for pid in selected:
            if proposal_states.get(pid) in (STATE_BATCHING, STATE_IMPORTED):
                proposal_states[pid] = STATE_CONFIRMED

    def project_imported() -> None:
        for pid in selected:
            proposal_states[pid] = STATE_IMPORTED

    def apply(*, active_child_id: str | None, recovery_required: bool) -> bool:
        changed = False
        if job.get("proposal_states") != proposal_states:
            job["proposal_states"] = proposal_states
            changed = True
        if job.get("active_child_id") != active_child_id:
            job["active_child_id"] = active_child_id
            changed = True
        if bool(job.get("recovery_required", False)) != recovery_required:
            job["recovery_required"] = recovery_required
            changed = True
        if changed:
            job["updated_at"] = _now_iso()
        return changed

    # 1. A valid committed manifest is the durable commit fact. This covers a
    #    child whose ledger projection was interrupted (manifest committed, but
    #    the child/parent ledger writes did not complete): trust the manifest,
    #    reconcile the child to committed, and project imported. A child that
    #    claims committed but has a missing/invalid/non-committed/wrong-linkage
    #    manifest fails closed here and never projects imported.
    if (
        isinstance(child_manifest, dict) and child_manifest.get("state") == "committed"
    ) or child_state == "committed":
        valid, _reason = _validate_committed_manifest(
            data_dir, child_id, parent_id, child_manifest
        )
        if valid:
            if isinstance(child_job, dict) and child_state != "committed":
                child_job["state"] = "committed"
                child_job["updated_at"] = _now_iso()
            project_imported()
            return apply(active_child_id=None, recovery_required=False)
        return apply(active_child_id=child_id, recovery_required=True)

    # 2. Child rolled back -> restore confirmed.
    if child_state == "rolled_back":
        restore_confirmed()
        return apply(active_child_id=None, recovery_required=False)

    # 3. Our write-failure states, or a crashed running child that left created
    #    evidence -> checksum-guarded compensation of only this child's files.
    #    Restore confirmed only on complete compensation; a prior compensation
    #    that already failed (manifest rolled back_failed) stays fail-closed
    #    without re-attempting.
    if child_state in ("partially_committed", "failed") or (
        child_state == "running" and has_evidence
    ):
        if has_evidence:
            manifest_state = (
                child_manifest.get("state") if isinstance(child_manifest, dict) else None
            )
            if manifest_state == "rollback_failed":
                return apply(active_child_id=child_id, recovery_required=True)
            comp = execute_rollback(import_id=child_id, data_dir=data_dir)
            if comp["success"]:
                restore_confirmed()
                return apply(active_child_id=None, recovery_required=False)
            return apply(active_child_id=child_id, recovery_required=True)
        restore_confirmed()
        return apply(active_child_id=None, recovery_required=False)

    # 4. running with no evidence is ambiguous (possible live writer): fail
    #    closed and retain the active child rather than auto-clearing.
    if child_state == "running":
        return apply(active_child_id=child_id, recovery_required=True)

    # 5. No child job / unknown settled state -> restore confirmed + clear.
    restore_confirmed()
    return apply(active_child_id=None, recovery_required=False)


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
    proposal_ids = [p.get("proposal_id", "") for p in proposals]
    jobs = ledger.setdefault("jobs", {})
    jobs[child_id] = {
        "kind": "batch",
        "parent_review_job_id": parent_id,
        "state": "running",
        "rollback_manifest_rel_path": rollback_rel,
        # Exact batch membership so later rollback/reconciliation projects from
        # what THIS child touched, never the parent's last selection.
        "proposal_ids": proposal_ids,
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

            # Publish attachments first via bounded streaming + create-only
            # publish; the journal references FINAL canonical attachment
            # objects. A mutated/deleted/colliding source raises and triggers
            # manifest-guarded compensation so no half-product survives. The
            # copy-time SHA/size verification is the second TOCTOU gate
            # (confirm-time precheck is ``_detect_stale``).
            published: list[dict[str, Any]] = []
            for att in proposal.get("attachments", []) or []:
                att_rel = att["target_rel_path"]
                att_abs = _resolve_confined_file_path(data_dir, att_rel)
                if att_abs is None:
                    raise RuntimeError(f"Unsafe attachment target: {att_rel}")
                src_abs = _resolve_confined_source_path(root, att.get("source_rel_path", ""))
                if src_abs is None or not src_abs.exists():
                    raise RuntimeError(f"Attachment source missing: {att.get('source_rel_path')}")
                ok_copy, info = _stream_copy(
                    src_abs, att_abs, att["source_sha256"], att["size_bytes"]
                )
                if not ok_copy:
                    raise RuntimeError(f"stream copy failed for {att_rel}: {info}")
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
                published.append(_canonical_attachment_entry(att, journal_rel))

            # Canonical journal: staged bytes -> create-only publish (never
            # overwrite an existing target). Attachments are the SSOT using the
            # canonical stored schema; no source SHA/provenance in frontmatter.
            journal_data = {
                "schema_version": SCHEMA_VERSION,
                "title": journal.get("title", ""),
                "date": journal.get("date", ""),
                "topic": "life",
                "tags": journal.get("tags", ["imported", "photo"]),
                "attachments": published,
                "content": journal.get("content", ""),
            }
            journal_text = format_journal_content(journal_data)
            ok_j, j_info = _publish_text_create_only(journal_abs, journal_text)
            if not ok_j:
                raise RuntimeError(f"journal publish failed for {journal_rel}: {j_info}")
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

        # 1. Reconcile review authority (recover ledger from plan) and any
        #    prior active child (crash recovery).
        _reconcile_review_authority_locked(ledger, parent_id, data_dir)
        _reconcile_parent(ledger, parent_id, data_dir)
        _write_ledger(data_dir, ledger)
        job = _get_job(ledger, parent_id)

        # 1b. Fail closed when the persisted plan and ledger disagree with no
        #     durable intent to explain it — running would act on an untrusted
        #     plan. (An unsettled active child keeps its own recovery_required;
        #     this gate fires only on an explicit plan/ledger mismatch.)
        if job.get("authority_status") == AUTHORITY_STATUS_PLAN_LEDGER_MISMATCH:
            return _err(
                IMPORT_RECOVERY_REQUIRED,
                "Review plan and ledger disagree (plan_ledger_mismatch); "
                "resolve the authority before running.",
                {
                    "import_id": parent_id,
                    "authority_status": AUTHORITY_STATUS_PLAN_LEDGER_MISMATCH,
                },
                retryable=False,
            )

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

        # 7. Monotonic child id (durable next_batch_sequence) + durable
        #    batching transition. The child job records the exact proposal_ids
        #    of THIS batch so later rollback/reconciliation projects from the
        #    child's own membership, never the parent's last selection.
        #    ``next_batch_sequence`` holds the NEXT available sequence, so it is
        #    always strictly greater than any child seq already assigned.
        seq = int(job.get("next_batch_sequence", 1))
        child_id = _child_id_for_seq(parent_id, seq)
        proposal_ids = [p.get("proposal_id", "") for p in runnable]
        job = _get_job(ledger, parent_id)
        for proposal in runnable:
            proposal_states[proposal.get("proposal_id", "")] = STATE_BATCHING
        job["next_batch_sequence"] = seq + 1
        job["active_child_id"] = child_id
        job["selected_proposal_ids"] = proposal_ids
        job["proposal_states"] = proposal_states
        job["recovery_required"] = False
        _write_ledger(data_dir, ledger)

        # 8. Create + execute the child batch job.
        result = _execute_child_batch(child_id, parent_id, runnable, data_dir, root, ledger)

        # 9. Reconcile to project the child outcome onto the parent. On a
        #    mid-batch write failure this performs checksum-guarded compensation
        #    of only the files this child created: full compensation restores
        #    the touched proposals to confirmed (a clean, retryable failure with
        #    no half-product); a compensation that cannot safely remove an
        #    artifact leaves recovery_required and fails closed.
        ledger = _read_ledger(data_dir)
        _reconcile_parent(ledger, parent_id, data_dir)
        _write_ledger(data_dir, ledger)

        if result["success"]:
            data = dict(result["data"])
            data["queue_counts"] = _queue_counts(
                (_get_job(ledger, parent_id) or {}).get("proposal_states", {}) or {}
            )
            return _ok(data)

        parent_after = _get_job(ledger, parent_id) or {}
        if parent_after.get("recovery_required"):
            return _err(
                IMPORT_RECOVERY_REQUIRED,
                "Batch failed and compensation could not fully remove its "
                "artifacts; resolve the recovery state before retrying.",
                {
                    "import_id": parent_id,
                    "child_id": child_id,
                    "original_error": result["error"],
                },
                retryable=False,
            )
        # Compensation succeeded: no half-product remains and the touched
        # proposals are back to confirmed — surface an explicit retryable
        # failure rather than an ambiguous partial success.
        return _err(
            "IMPORT_WRITE_FAILURE",
            "Batch failed mid-write and was fully compensated; re-run to retry.",
            {
                "import_id": parent_id,
                "child_id": child_id,
                "queue_counts": _queue_counts(
                    parent_after.get("proposal_states", {}) or {}
                ),
                "original_error": result["error"],
            },
            retryable=True,
        )

