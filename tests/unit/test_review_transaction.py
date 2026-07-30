#!/usr/bin/env python3
"""Unit tests for the package-2 attachment transaction & reconciliation layer.

These tests exercise the low-level primitives that the batch run relies on,
*without* driving the full CLI: bounded chunk streaming, create-only staging
publication, committed-manifest validation, and ``_reconcile_parent`` crash
windows. They use synthetic temp directories only — no real data, network, AI,
OCR, face/video, or runtime/cloud.

The compensating mid-batch failure paths (which invoke ``execute_rollback``)
are covered behaviourally by the package-2 contract suite; this unit suite
covers the branches that do NOT call ``execute_rollback`` plus the manifest
validation gate that every reconciliation branch depends on.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

import tools.ingest.review as review
from tools.ingest.schemas import ROLLBACK_MANIFEST_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Disk helpers (mirror the on-disk ledger/manifest layout used by the runner)
# ---------------------------------------------------------------------------


def _ledger_path(data_dir: Path) -> Path:
    return data_dir / ".life-index" / "import-jobs" / "ledger.json"


def _read_ledger(data_dir: Path) -> dict[str, Any]:
    return json.loads(_ledger_path(data_dir).read_text("utf-8"))


def _write_ledger(data_dir: Path, ledger: dict[str, Any]) -> None:
    p = _ledger_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def _child_manifest_path(data_dir: Path, child_id: str) -> Path:
    return data_dir / ".life-index" / "import-jobs" / child_id / "rollback-manifest.json"


def _write_child_manifest(data_dir: Path, child_id: str, manifest: dict[str, Any]) -> None:
    p = _child_manifest_path(data_dir, child_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_child_manifest(data_dir: Path, child_id: str) -> dict[str, Any]:
    return json.loads(_child_manifest_path(data_dir, child_id).read_text("utf-8"))


def _assert_no_staging(parent_dir: Path) -> None:
    """No staging leftover under *parent_dir*, checked against the REAL naming.

    ``_unique_staging`` writes a hidden ``.{target}.staging-<rand>.tmp`` beside
    each target and unlinks it on every path. Assert against that real hidden
    ``.staging-*.tmp`` naming (a loose ``*staging*`` glob is only a coincidental
    substring match and could miss a leftover if the marker changed), plus a
    broad sweep so nothing slips through.
    """
    leftover = sorted(
        {*parent_dir.glob(".*.staging-*.tmp"), *parent_dir.glob("*staging*")}
    )
    assert leftover == [], f"staging leftovers: {[str(p) for p in leftover]}"


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _make_created_file(
    data_dir: Path,
    rel_path: str,
    content: bytes,
    *,
    kind: str = "attachment",
    created_by_import: bool = True,
) -> dict[str, Any]:
    """Create a confined file under data_dir and return a manifest created-file entry."""
    abs_path = data_dir / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(content)
    return {
        "kind": kind,
        "rel_path": rel_path,
        "sha256_after": _sha(content),
        "size_bytes": len(content),
        "created_by_import": created_by_import,
    }


def _basic_review_ledger(
    parent_id: str,
    child_id: str,
    proposal_ids: list[str],
    *,
    active: bool = True,
    proposal_state: str = "batching",
) -> dict[str, Any]:
    """A parent review job carrying an active child over the given proposals."""
    return {
        "schema_version": "import_job.v1",
        "jobs": {
            parent_id: {
                "kind": "review",
                "state": "confirmed",
                "proposal_states": {pid: proposal_state for pid in proposal_ids},
                "active_child_id": child_id if active else None,
                "recovery_required": False,
                "selected_proposal_ids": list(proposal_ids),
            },
        },
        "idempotency_index": {},
    }


def _child_job(
    parent_id: str, child_id: str, state: str, proposal_ids: list[str]
) -> dict[str, Any]:
    return {
        "kind": "batch",
        "parent_review_job_id": parent_id,
        "state": state,
        "rollback_manifest_rel_path": f".life-index/import-jobs/{child_id}/rollback-manifest.json",
        "proposal_ids": list(proposal_ids),
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def _reconcile_and_persist(data_dir: Path, parent_id: str) -> bool:
    """Call ``_reconcile_parent`` like the locking entry point would: read, mutate, persist-if-changed."""
    ledger = _read_ledger(data_dir)
    changed = review._reconcile_parent(ledger, parent_id, data_dir)
    if changed:
        _write_ledger(data_dir, ledger)
    return changed


# ===================================================================
# Bounded streaming: _drain_source_to_staging
# ===================================================================


class _RecordingReader:
    """File-like reader that records the size of every returned chunk."""

    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)
        self.returned: list[int] = []
        self.requested: list[int] = []

    def read(self, n: int) -> bytes:
        self.requested.append(n)
        chunk = self._buf.read(n)
        self.returned.append(len(chunk))
        return chunk


def test_drain_source_bounded_chunks(tmp_path: Path) -> None:
    """Streaming never loads the whole file: every returned chunk <= chunk_size."""
    payload = bytes((i * 7) % 256 for i in range(10_000))  # ~10 KiB, far over a 64 B window
    chunk_size = 64
    src = _RecordingReader(payload)
    dst = tmp_path / "stage.bin"
    with open(dst, "wb") as dst_fp:
        ok, info = review._drain_source_to_staging(
            src, dst_fp, _sha(payload), len(payload), chunk_size=chunk_size
        )
    assert ok is True
    assert info == _sha(payload)
    # Bounded: no chunk exceeded the window, and many reads happened.
    assert src.returned, "no reads occurred"
    assert max(src.returned) <= chunk_size
    assert len(src.returned) >= 2
    assert sum(src.returned) == len(payload)
    assert dst.read_bytes() == payload


def test_drain_source_ok_matches(tmp_path: Path) -> None:
    payload = b"hello world streaming bytes"
    src = _RecordingReader(payload)
    dst = tmp_path / "stage.bin"
    with open(dst, "wb") as dst_fp:
        ok, info = review._drain_source_to_staging(
            src, dst_fp, _sha(payload), len(payload), chunk_size=8
        )
    assert ok is True and info == _sha(payload)


def test_drain_source_sha_mismatch(tmp_path: Path) -> None:
    payload = b"some bytes"
    src = _RecordingReader(payload)
    dst = tmp_path / "stage.bin"
    with open(dst, "wb") as dst_fp:
        ok, info = review._drain_source_to_staging(
            src, dst_fp, "sha256:" + "0" * 64, len(payload), chunk_size=4
        )
    assert ok is False
    assert info == "sha_mismatch"


def test_drain_source_size_mismatch(tmp_path: Path) -> None:
    """Hash matches but the expected size is wrong -> size_mismatch (not sha)."""
    payload = b"exact content"
    src = _RecordingReader(payload)
    dst = tmp_path / "stage.bin"
    with open(dst, "wb") as dst_fp:
        ok, info = review._drain_source_to_staging(
            src, dst_fp, _sha(payload), len(payload) + 999, chunk_size=4
        )
    assert ok is False
    assert info == "size_mismatch"


# ===================================================================
# Create-only staging publication: _stream_copy / _publish_text_create_only
# ===================================================================


def test_stream_copy_publishes_create_only(tmp_path: Path) -> None:
    payload = b"attachment payload bytes"
    src = tmp_path / "src.jpg"
    src.write_bytes(payload)
    target = tmp_path / "out" / "import_abc.jpg"
    ok, info = review._stream_copy(src, target, _sha(payload), len(payload))
    assert ok is True and info == _sha(payload)
    assert target.exists()
    assert target.read_bytes() == payload
    # source untouched
    assert src.read_bytes() == payload


def test_stream_copy_target_exists_no_overwrite_no_staging(tmp_path: Path) -> None:
    payload = b"original attachment bytes"
    src = tmp_path / "src.jpg"
    src.write_bytes(payload)
    target = tmp_path / "out" / "import_abc.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    pre_existing = b"PRE-EXISTING DO NOT CLOBBER"
    target.write_bytes(pre_existing)

    ok, info = review._stream_copy(src, target, _sha(payload), len(payload))
    assert ok is False
    assert info == "target_exists"
    # never overwrote the existing target
    assert target.read_bytes() == pre_existing
    # no staging leftovers
    _assert_no_staging(target.parent)


def test_stream_copy_sha_mismatch_no_target_no_staging(tmp_path: Path) -> None:
    """A mutated/diverged source leaves no final artifact and no staging leftover."""
    payload = b"some attachment bytes"
    src = tmp_path / "src.jpg"
    src.write_bytes(payload)
    target = tmp_path / "out" / "import_abc.jpg"
    ok, info = review._stream_copy(src, target, "sha256:" + "f" * 64, len(payload))
    assert ok is False
    assert info == "sha_mismatch"
    assert not target.exists()
    _assert_no_staging(target.parent)


def test_stream_copy_missing_source(tmp_path: Path) -> None:
    target = tmp_path / "out" / "import_abc.jpg"
    ok, info = review._stream_copy(tmp_path / "missing.jpg", target, "sha256:x", 1)
    assert ok is False
    assert info.startswith("unreadable:")
    assert not target.exists()


def test_publish_text_create_only_ok(tmp_path: Path) -> None:
    target = tmp_path / "Journals" / "2024" / "06" / "entry.md"
    text = "---\ntitle: \"x\"\n---\n\nbody\n"
    ok, info = review._publish_text_create_only(target, text)
    assert ok is True and info == ""
    assert target.read_text(encoding="utf-8") == text


def test_publish_text_target_exists_no_overwrite_no_staging(tmp_path: Path) -> None:
    target = tmp_path / "Journals" / "2024" / "06" / "entry.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    pre_existing = "PRE-EXISTING JOURNAL"
    target.write_text(pre_existing, encoding="utf-8")
    ok, info = review._publish_text_create_only(target, "---\nnew\n---\n")
    assert ok is False
    assert info == "target_exists"
    assert target.read_text(encoding="utf-8") == pre_existing
    _assert_no_staging(target.parent)


def test_unique_staging_beside_target(tmp_path: Path) -> None:
    target = tmp_path / "out" / "import_abc.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    s1 = review._unique_staging(target)
    s2 = review._unique_staging(target)
    # same parent as the target, carries the staging marker, and unique
    assert s1.parent == target.parent
    assert ".staging-" in s1.name
    assert s1 != s2


# ===================================================================
# Canonical attachment entry shape + journal-relative path
# ===================================================================


def test_canonical_attachment_entry_shape() -> None:
    att = {
        "target_rel_path": "attachments/2024/06/import_deadbeefdead.jpg",
        "source_rel_path": "IMG_0001.jpg",
        "media_type": "image/jpeg",
        "size_bytes": 1234,
    }
    journal_rel = "Journals/2024/06/life-index_2024-06-15_001.md"
    entry = review._canonical_attachment_entry(att, journal_rel)
    assert set(entry.keys()) == {
        "filename",
        "rel_path",
        "description",
        "original_name",
        "auto_detected",
        "content_type",
        "size",
    }
    assert entry["filename"] == "import_deadbeefdead.jpg"
    assert entry["rel_path"] == "../../../attachments/2024/06/import_deadbeefdead.jpg"
    assert entry["original_name"] == "IMG_0001.jpg"
    assert entry["auto_detected"] is False
    assert entry["content_type"] == "image/jpeg"
    assert entry["size"] == 1234
    assert entry["description"] == ""
    # no source SHA / provenance leaks into the canonical stored attachment
    assert "source_sha256" not in entry
    assert "sha256" not in entry


def test_journal_relative_path_canonical() -> None:
    rel = review._journal_relative_path(
        "Journals/2024/06/life-index_2024-06-15_001.md",
        "attachments/2024/06/import_deadbeefdead.jpg",
    )
    assert rel == "../../../attachments/2024/06/import_deadbeefdead.jpg"


# ===================================================================
# Committed-manifest validation gate
# ===================================================================


def _valid_manifest(
    data_dir: Path, child_id: str, parent_id: str, rel: str, content: bytes
) -> dict[str, Any]:
    entry = _make_created_file(data_dir, rel, content)
    return {
        "schema_version": ROLLBACK_MANIFEST_SCHEMA_VERSION,
        "import_id": child_id,
        "parent_review_job_id": parent_id,
        "created_at": "2026-01-01T00:00:00+00:00",
        "state": "committed",
        "created_files": [entry],
        "preexisting_files": [],
        "errors": [],
    }


def test_validate_committed_manifest_valid(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is True and reason == ""


def test_validate_committed_manifest_missing(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", None)
    assert valid is False and reason == "manifest_missing"


def test_validate_committed_manifest_schema_mismatch(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    m["schema_version"] = "something.else.v9"
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is False and reason == "schema_mismatch"


def test_validate_committed_manifest_not_committed_state(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    m["state"] = "partially_committed"
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is False and reason == "manifest_not_committed"


def test_validate_committed_manifest_wrong_import_id(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    m["import_id"] = "other_child"
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is False and reason == "wrong_import_id"


def test_validate_committed_manifest_wrong_parent(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    m["parent_review_job_id"] = "other_parent"
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is False and reason == "wrong_parent"


def test_validate_committed_manifest_unconfined_path(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    # traversal escape: the entry points outside data_dir
    m["created_files"][0]["rel_path"] = "../../etc/evil.jpg"
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is False and reason.startswith("unconfined:")


def test_validate_committed_manifest_missing_artifact(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    # delete the artifact the manifest claims was created
    (data_dir / "attachments/2024/06/a.jpg").unlink()
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is False and reason.startswith("missing:")


def test_validate_committed_manifest_hash_mismatch(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    # tamper the artifact after it was recorded
    (data_dir / "attachments/2024/06/a.jpg").write_bytes(b"TAMPERED")
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is False and reason.startswith("hash_mismatch:")


def test_validate_committed_manifest_size_mismatch(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    m = _valid_manifest(data_dir, "child1", "parent1", "attachments/2024/06/a.jpg", b"data")
    # hash stays correct but the recorded size is wrong
    m["created_files"][0]["size_bytes"] = 999_999
    valid, reason = review._validate_committed_manifest(data_dir, "child1", "parent1", m)
    assert valid is False and reason.startswith("size_mismatch:")


# ===================================================================
# _reconcile_parent crash windows (branches that do not run execute_rollback)
# ===================================================================


def test_reconcile_parent_no_active_child_is_noop(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    ledger = _basic_review_ledger(parent_id, child_id, pids, active=False)
    _write_ledger(data_dir, ledger)
    assert _reconcile_and_persist(data_dir, parent_id) is False
    # unchanged
    after = _read_ledger(data_dir)["jobs"][parent_id]
    assert after["active_child_id"] is None


def test_reconcile_parent_missing_child_job_restores_confirmed(tmp_path: Path) -> None:
    """active_child_id set but the child job is gone and no evidence -> restore + clear."""
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    ledger = _basic_review_ledger(parent_id, child_id, pids, proposal_state="batching")
    # NOTE: the child job is intentionally absent; no manifest on disk either.
    _write_ledger(data_dir, ledger)

    changed = _reconcile_and_persist(data_dir, parent_id)
    assert changed is True
    parent = _read_ledger(data_dir)["jobs"][parent_id]
    assert parent["proposal_states"]["p1"] == "confirmed"
    assert parent["active_child_id"] is None
    assert parent["recovery_required"] is False


def test_reconcile_parent_committed_manifest_projects_imported(tmp_path: Path) -> None:
    """A valid committed manifest is the durable commit fact -> project imported."""
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    manifest = _valid_manifest(
        data_dir, child_id, parent_id, "attachments/2024/06/a.jpg", b"payload"
    )
    _write_child_manifest(data_dir, child_id, manifest)
    ledger = _basic_review_ledger(parent_id, child_id, pids, proposal_state="batching")
    # child ledger still says running (ledger projection interrupted after the manifest committed)
    ledger["jobs"][child_id] = _child_job(parent_id, child_id, "running", pids)
    _write_ledger(data_dir, ledger)

    changed = _reconcile_and_persist(data_dir, parent_id)
    assert changed is True
    after = _read_ledger(data_dir)
    parent = after["jobs"][parent_id]
    assert parent["proposal_states"]["p1"] == "imported"
    assert parent["active_child_id"] is None
    assert parent["recovery_required"] is False
    # the child ledger was reconciled to committed (the durable commit fact)
    assert after["jobs"][child_id]["state"] == "committed"


def test_reconcile_parent_committed_ledger_missing_manifest_fails_closed(tmp_path: Path) -> None:
    """child ledger claims committed but the manifest is missing -> fail closed."""
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    ledger = _basic_review_ledger(parent_id, child_id, pids, proposal_state="batching")
    ledger["jobs"][child_id] = _child_job(parent_id, child_id, "committed", pids)
    _write_ledger(data_dir, ledger)
    # NOTE: no manifest written for child1.

    changed = _reconcile_and_persist(data_dir, parent_id)
    assert changed is True
    parent = _read_ledger(data_dir)["jobs"][parent_id]
    assert parent["recovery_required"] is True
    assert parent["active_child_id"] == child_id  # retained, fail closed
    assert parent["proposal_states"]["p1"] == "batching"  # NOT projected imported


def test_reconcile_parent_committed_ledger_invalid_manifest_fails_closed(tmp_path: Path) -> None:
    """child ledger committed + manifest present but a hash mismatches -> fail closed."""
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    manifest = _valid_manifest(
        data_dir, child_id, parent_id, "attachments/2024/06/a.jpg", b"payload"
    )
    (data_dir / "attachments/2024/06/a.jpg").write_bytes(b"TAMPERED")  # invalidates hash
    _write_child_manifest(data_dir, child_id, manifest)
    ledger = _basic_review_ledger(parent_id, child_id, pids, proposal_state="batching")
    ledger["jobs"][child_id] = _child_job(parent_id, child_id, "committed", pids)
    _write_ledger(data_dir, ledger)

    _reconcile_and_persist(data_dir, parent_id)
    parent = _read_ledger(data_dir)["jobs"][parent_id]
    assert parent["recovery_required"] is True
    assert parent["active_child_id"] == child_id
    assert parent["proposal_states"]["p1"] == "batching"


def test_reconcile_parent_rolled_back_restores_confirmed(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    ledger = _basic_review_ledger(parent_id, child_id, pids, proposal_state="imported")
    ledger["jobs"][child_id] = _child_job(parent_id, child_id, "rolled_back", pids)
    _write_ledger(data_dir, ledger)

    changed = _reconcile_and_persist(data_dir, parent_id)
    assert changed is True
    parent = _read_ledger(data_dir)["jobs"][parent_id]
    assert parent["proposal_states"]["p1"] == "confirmed"
    assert parent["active_child_id"] is None
    assert parent["recovery_required"] is False


def test_reconcile_parent_running_no_evidence_retains_recovery(tmp_path: Path) -> None:
    """A running child with NO created evidence is ambiguous -> retain + recovery_required."""
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    ledger = _basic_review_ledger(parent_id, child_id, pids, proposal_state="batching")
    ledger["jobs"][child_id] = _child_job(parent_id, child_id, "running", pids)
    _write_ledger(data_dir, ledger)
    # NOTE: no manifest / no created_files on disk.

    changed = _reconcile_and_persist(data_dir, parent_id)
    assert changed is True
    parent = _read_ledger(data_dir)["jobs"][parent_id]
    assert parent["recovery_required"] is True
    assert parent["active_child_id"] == child_id  # retained, not auto-cleared


def test_reconcile_parent_converges_idempotent(tmp_path: Path) -> None:
    """Repeated reconciliation is a no-op once converged (no further mutation)."""
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    manifest = _valid_manifest(
        data_dir, child_id, parent_id, "attachments/2024/06/a.jpg", b"payload"
    )
    _write_child_manifest(data_dir, child_id, manifest)
    ledger = _basic_review_ledger(parent_id, child_id, pids, proposal_state="batching")
    ledger["jobs"][child_id] = _child_job(parent_id, child_id, "running", pids)
    _write_ledger(data_dir, ledger)

    first = _reconcile_and_persist(data_dir, parent_id)
    snap1 = _read_ledger(data_dir)["jobs"][parent_id]
    second = _reconcile_and_persist(data_dir, parent_id)
    snap2 = _read_ledger(data_dir)["jobs"][parent_id]

    assert first is True
    assert second is False  # converged: second pass changed nothing
    assert snap1 == snap2


# ===================================================================
# Compensation must preserve execute_rollback's durable child transition
# ===================================================================


def test_reconcile_parent_compensation_preserves_durable_child_state(
    tmp_path: Path,
) -> None:
    """Compensation must not clobber ``execute_rollback``'s durable child write.

    A ``partially_committed`` child with created evidence triggers checksum-
    guarded compensation (``execute_rollback``), which writes the child to
    ``rolled_back`` on its OWN fresh ledger read. The caller's read->reconcile->
    write pattern (mirrored by ``_reconcile_and_persist``) must carry that
    durable state forward, so the child job and its rollback manifest agree on
    exactly one terminal state instead of the child job lingering as
    ``partially_committed`` behind a ``rolled_back`` manifest.

    Synthetic temp data only. This is the focused RED witness for the stale-
    ledger overwrite: against the unfixed base the child job state assertion
    fails (it stays ``partially_committed``) while the manifest is already
    ``rolled_back``.
    """
    data_dir = tmp_path / "Life-Index"
    parent_id, child_id, pids = "parent1", "child1", ["p1"]
    # Durable created evidence: a real published attachment the manifest records.
    att_rel = "attachments/2024/06/import_deadbeefdead.jpg"
    payload = b"published-then-failed attachment"
    entry = _make_created_file(data_dir, att_rel, payload)
    manifest = {
        "schema_version": ROLLBACK_MANIFEST_SCHEMA_VERSION,
        "import_id": child_id,
        "parent_review_job_id": parent_id,
        "created_at": "2026-01-01T00:00:00+00:00",
        "state": "partially_committed",
        "created_files": [entry],
        "preexisting_files": [],
        "errors": ["simulated mid-write failure"],
    }
    _write_child_manifest(data_dir, child_id, manifest)
    ledger = _basic_review_ledger(parent_id, child_id, pids, proposal_state="batching")
    ledger["jobs"][child_id] = _child_job(
        parent_id, child_id, "partially_committed", pids
    )
    _write_ledger(data_dir, ledger)

    # Mirror run_batch / reconcile_review_authority's exact persistence pattern:
    # read -> reconcile (which runs execute_rollback on its own fresh ledger
    # read) -> persist the in-memory snapshot. Inlined so the witness is purely
    # behavioral and independent of _reconcile_parent's return shape across
    # bases.
    ledger = _read_ledger(data_dir)
    review._reconcile_parent(ledger, parent_id, data_dir)
    _write_ledger(data_dir, ledger)

    after = _read_ledger(data_dir)
    parent = after["jobs"][parent_id]
    # Parent is cleanly retryable: no half-product, no active child, no recovery.
    assert parent["proposal_states"]["p1"] == "confirmed"
    assert parent["active_child_id"] is None
    assert parent["recovery_required"] is False

    # ONE durable recovery truth: the child job and its rollback manifest agree
    # on ``rolled_back`` (the unfixed base leaves the child job diverged as
    # ``partially_committed`` behind a rolled_back manifest).
    assert after["jobs"][child_id]["state"] == "rolled_back"
    assert _read_child_manifest(data_dir, child_id)["state"] == "rolled_back"

    # The created evidence was compensated away; nothing of the batch survives.
    assert not (data_dir / att_rel).exists()

    # Repeated reconciliation is a stable no-op (convergence): the active child
    # is cleared, so a second pass persists an unchanged ledger and the child
    # stays rolled_back.
    snap1 = json.dumps(_read_ledger(data_dir)["jobs"], sort_keys=True)
    ledger2 = _read_ledger(data_dir)
    review._reconcile_parent(ledger2, parent_id, data_dir)
    _write_ledger(data_dir, ledger2)
    snap2 = json.dumps(_read_ledger(data_dir)["jobs"], sort_keys=True)
    assert snap1 == snap2
    assert _read_ledger(data_dir)["jobs"][child_id]["state"] == "rolled_back"


# ---------------------------------------------------------------------------
# R1b: resolved job-path containment primitive.
# Component-wise (not string-prefix), accepts not-yet-existing job paths, and
# resolves both sides so a linked data dir is a legitimate contained root while a
# planted link that escapes is rejected.
# ---------------------------------------------------------------------------


def test_r1b_resolve_confined_job_path_is_component_wise(tmp_path: Path) -> None:
    """Case 6: containment is component-wise; a sibling ``-evil`` is rejected."""
    import tools.ingest.runner as runner

    resolve = runner._resolve_confined_job_path
    data = tmp_path / "data"
    data.mkdir()
    sibling = tmp_path / "data-evil"  # shares the "data" string prefix
    sibling.mkdir()

    # Absolute locators are rejected outright (never joined into the data dir).
    assert resolve(data, str(sibling / "rollback-manifest.json")) is None
    # Traversal to a same-string-prefix sibling must NOT be string-prefix matched.
    assert resolve(data, "../data-evil/rollback-manifest.json") is None
    assert resolve(data, "../../data-evil/sub/x.json") is None
    # A not-yet-existing nested job path is accepted and returned RESOLVED.
    ok = resolve(data, ".life-index/import-jobs/imp-1/rollback-manifest.json")
    assert ok is not None
    assert ok == (data / ".life-index/import-jobs/imp-1/rollback-manifest.json").resolve()
    # Strict descendant: the data dir itself and an empty locator are rejected.
    assert resolve(data, ".") is None
    assert resolve(data, "") is None


def test_r1b_resolve_confined_job_path_accepts_linked_root(tmp_path: Path) -> None:
    """False-rejection: a data dir reached through a link resolves on both sides."""
    import os
    import subprocess
    import tools.ingest.runner as runner

    real = tmp_path / "real"
    real.mkdir()
    link_root = tmp_path / "link-root"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link_root), str(real)], capture_output=True)
    else:
        os.symlink(real, link_root, target_is_directory=True)
    assert link_root.is_dir()

    resolve = runner._resolve_confined_job_path
    outside = tmp_path / "outside"
    outside.mkdir()
    escape_link = real / ".life-index" / "import-jobs" / "imp-2"
    escape_link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(escape_link), str(outside)], capture_output=True)
    else:
        os.symlink(outside, escape_link, target_is_directory=True)

    try:
        # A path derived from the linked root resolves under the REAL root: accepted.
        ok = resolve(link_root, ".life-index/import-jobs/imp-3/rollback-manifest.json")
        assert ok is not None
        assert ok == (real / ".life-index/import-jobs/imp-3/rollback-manifest.json").resolve()
        # A junction planted inside the tree that escapes is still rejected, even
        # though the root itself is reached through a link (both sides resolved).
        assert resolve(link_root, ".life-index/import-jobs/imp-2/rollback-manifest.json") is None
    finally:
        try:
            os.rmdir(escape_link) if os.name == "nt" else escape_link.unlink()
        except OSError:
            pass
        try:
            os.rmdir(link_root) if os.name == "nt" else link_root.unlink()
        except OSError:
            pass

