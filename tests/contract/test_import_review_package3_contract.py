#!/usr/bin/env python3
"""Package-3 contract tests: queue_revision + stage/edit/review/reviews/preview.

These are the **focused synthetic behavioral tests** for M7-B (package 3): the
second concurrency authority (``queue_revision``), initial pending staging with
duplicate-source-root protection, atomic single-proposal confirm/edit, bounded
read projections (``import review``), persisted review-job discovery
(``import reviews``), and proposal-pinned preview of selected/deselected photos.

All exercised through the public CLI surface (subprocess) and, for crash-window
fault injection, the public in-process entry points under a per-test
``LIFE_INDEX_DATA_DIR``. Synthetic source directories only — no real user data,
network, AI/OCR/face/video/RAW, runtime/cloud, or new durable authority.

Main authority remains the existing import ledger + review-plan artifact; the
``queue_revision`` is a parent-ledger-owned client concurrency token (initial 1)
that bumps exactly once per atomic parent-visible change, while ``plan_revision``
keeps its review-plan content semantics.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import tools.ingest.review as review
from tests.contract.test_import_review_package1_contract import _make_jpeg, _make_jpeg_rich


# ---------------------------------------------------------------------------
# CLI invocation helpers (subprocess)
# ---------------------------------------------------------------------------


def _run_import(data_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "tools", "import", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def _payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise AssertionError(
            f"Expected JSON on stdout.\nstdout[:500]: {result.stdout[:500]}\n"
            f"stderr[:500]: {result.stderr[:500]}"
        ) from None


def _ok(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    return _payload(result)


def _err(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.returncode != 0, f"expected non-zero exit, stdout: {result.stdout}"
    return _payload(result)


# ---------------------------------------------------------------------------
# Synthetic photo + plan + review helpers
# ---------------------------------------------------------------------------


def _photo_plan(data_dir: Path, input_dir: Path) -> dict[str, Any]:
    return _ok(
        _run_import(data_dir, "plan", "--source", "media.photo_timeline",
                    "--input", str(input_dir), "--json")
    )["data"]


def _plan_file(tmp_path: Path, plan_data: dict[str, Any], name: str = "plan.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(plan_data), encoding="utf-8")
    return p


def _edit_file(tmp_path: Path, edit_data: dict[str, Any], name: str = "edit.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(edit_data), encoding="utf-8")
    return p


def _confirm(data_dir: Path, plan_data: dict[str, Any], src: Path, tmp_path: Path) -> dict[str, Any]:
    return _ok(_run_import(
        data_dir, "confirm", "--plan",
        str(_plan_file(tmp_path, plan_data, name=f"review_{plan_data['import_id']}.json")),
        "--source-root", str(src), "--json",
    ))["data"]


def _stage(data_dir: Path, plan_data: dict[str, Any], src: Path, tmp_path: Path) -> dict[str, Any]:
    return _ok(_run_import(
        data_dir, "stage", "--plan",
        str(_plan_file(tmp_path, plan_data, name=f"stage_{plan_data['import_id']}.json")),
        "--source-root", str(src), "--json",
    ))["data"]


def _stage_raw(data_dir: Path, plan_data: dict[str, Any], src: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return _run_import(
        data_dir, "stage", "--plan",
        str(_plan_file(tmp_path, plan_data, name=f"stage_{plan_data['import_id']}.json")),
        "--source-root", str(src), "--json",
    )


def _edit(data_dir: Path, import_id: str, edit_data: dict[str, Any],
          expected_queue_revision: int, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return _run_import(
        data_dir, "confirm", "--edit",
        str(_edit_file(tmp_path, edit_data, name=f"edit_{import_id}.json")),
        "--import-id", import_id,
        "--expected-queue-revision", str(expected_queue_revision),
        "--json",
    )


def _review(data_dir: Path, import_id: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run_import(data_dir, "review", "--import-id", import_id, "--json", *extra)


def _reviews(data_dir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run_import(data_dir, "reviews", "--json", *extra)


def _status(data_dir: Path, import_id: str) -> dict[str, Any]:
    return _ok(_run_import(data_dir, "status", "--import-id", import_id, "--json"))["data"]


def _ledger(data_dir: Path) -> dict[str, Any]:
    return json.loads(
        (data_dir / ".life-index" / "import-jobs" / "ledger.json").read_text("utf-8")
    )


def _save_ledger(data_dir: Path, ledger: dict[str, Any]) -> None:
    (data_dir / ".life-index" / "import-jobs" / "ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _review_plan(data_dir: Path, parent_id: str) -> dict[str, Any]:
    return json.loads(
        (data_dir / ".life-index" / "import-jobs" / parent_id / "review-plan.json").read_text("utf-8")
    )


# ===================================================================
# A) queue_revision — initial, single bumps, stable reads, crash replay
# ===================================================================


def test_stage_sets_queue_revision_and_plan_revision_to_one(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]

    res = _stage(data_dir, plan, src, tmp_path)
    assert res["queue_revision"] == 1
    assert res["plan_revision"] == 1
    assert res["parent_id"] == parent_id
    assert res["schema_version"] == "import_review.v1"
    # ledger is the authority for the token
    assert _ledger(data_dir)["jobs"][parent_id]["queue_revision"] == 1


def test_legacy_reconfirm_bumps_queue_and_plan_revision(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    res1 = _confirm(data_dir, plan, src, tmp_path)
    rev1 = res1["queue_revision"]
    plan_rev1 = res1["plan_revision"]

    # legacy reconfirm bumps both exactly once
    res2 = _confirm(data_dir, plan, src, tmp_path)
    assert res2["queue_revision"] == rev1 + 1
    assert res2["plan_revision"] == plan_rev1 + 1


def test_run_batching_bumps_queue_not_plan(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6), date_original="2024:07:01 09:00:00")
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    # confirm -> confirmed (legacy resolve). queue bumps to some rev.
    _confirm(data_dir, plan, src, tmp_path)
    before = _ledger(data_dir)["jobs"][parent_id]
    q_before = before["queue_revision"]
    plan_rev_before = before["plan_revision"]

    _ok(_run_import(data_dir, "run", "--import-id", parent_id,
                    "--source-root", str(src), "--json"))
    after = _ledger(data_dir)["jobs"][parent_id]
    # state-only run transition bumps queue, never plan_revision
    assert after["queue_revision"] > q_before
    assert after["plan_revision"] == plan_rev_before


def test_run_stale_only_bumps_queue_once(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    _confirm(data_dir, plan, src, tmp_path)
    q_before = _ledger(data_dir)["jobs"][parent_id]["queue_revision"]

    # mutate source -> every proposal stale, no child created
    (src / "shot.jpg").write_bytes(b"changed after confirm")
    _err(_run_import(data_dir, "run", "--import-id", parent_id,
                     "--source-root", str(src), "--json"))
    after = _ledger(data_dir)["jobs"][parent_id]
    # stale-only transition is a single atomic parent write -> exactly one bump
    assert after["queue_revision"] == q_before + 1


def test_child_commit_and_rollback_each_bump_queue(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    _confirm(data_dir, plan, src, tmp_path)

    run = _ok(_run_import(data_dir, "run", "--import-id", parent_id,
                          "--source-root", str(src), "--json"))["data"]
    q_after_commit = _ledger(data_dir)["jobs"][parent_id]["queue_revision"]

    # rollback the child -> imported restored to confirmed -> another bump
    _ok(_run_import(data_dir, "rollback", "--import-id", run["import_id"], "--json"))
    q_after_rollback = _ledger(data_dir)["jobs"][parent_id]["queue_revision"]
    assert q_after_rollback > q_after_commit


def test_stable_second_read_no_bump(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    _stage(data_dir, plan, src, tmp_path)

    s1 = _status(data_dir, parent_id)
    snap1 = json.dumps(_ledger(data_dir)["jobs"][parent_id], sort_keys=True)
    s2 = _status(data_dir, parent_id)
    snap2 = json.dumps(_ledger(data_dir)["jobs"][parent_id], sort_keys=True)
    # stable read: no write, no bump, byte-identical projection
    assert s1["queue_revision"] == s2["queue_revision"]
    assert snap1 == snap2


def test_intent_crash_replay_never_double_bumps(
    isolated_data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A confirm that crashes after the plan replace (before finalize) converges
    on exactly one queue_revision bump when reconciliation replays the finalize."""
    data_dir = isolated_data_dir
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    # first confirm -> rev1
    review.confirm_review(
        plan_path=str(_plan_file(tmp_path, plan, "p1.json")),
        data_dir=data_dir, source_root=str(src),
    )
    q1 = review._read_ledger(data_dir)["jobs"][parent_id].get("queue_revision")

    # second confirm with a changed plan title, but finalize "crashes" (no-op once)
    plan["proposals"][0]["journal"]["title"] = "Edited title for crash replay"
    original_finalize = review._finalize_review_update
    crashed = {"done": False}

    def crashing_finalize(d: Path, lg: dict, pid: str, intent: dict) -> None:
        if not crashed["done"]:
            crashed["done"] = True
            return  # simulate crash after plan replace, before finalize
        return original_finalize(d, lg, pid, intent)

    monkeypatch.setattr(review, "_finalize_review_update", crashing_finalize)
    review.confirm_review(
        plan_path=str(_plan_file(tmp_path, plan, "p2.json")),
        data_dir=data_dir, source_root=str(src),
    )
    monkeypatch.setattr(review, "_finalize_review_update", original_finalize)

    # the persisted job still carries the pending intent (finalize skipped)
    job_mid = review._read_ledger(data_dir)["jobs"][parent_id]
    assert "pending_review_update" in job_mid

    # reconciliation replays the finalize -> exactly one bump to q1 + 1
    s1 = review.query_review_status(parent_id, data_dir)["data"]
    assert s1["queue_revision"] == q1 + 1
    assert "pending_review_update" not in review._read_ledger(data_dir)["jobs"][parent_id]

    # a second reconciliation is a no-op (convergence) -> no double bump
    s2 = review.query_review_status(parent_id, data_dir)["data"]
    assert s2["queue_revision"] == q1 + 1


def test_rebind_bumps_only_when_identity_changes(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    _stage(data_dir, plan, src, tmp_path)
    q_before = _ledger(data_dir)["jobs"][parent_id]["queue_revision"]

    # rebind the SAME root identity -> no visible change, no bump
    _ok(_run_import(data_dir, "rebind", "--import-id", parent_id,
                    "--source-root", str(src), "--json"))
    assert _ledger(data_dir)["jobs"][parent_id]["queue_revision"] == q_before


# ===================================================================
# B) import stage — initial pending + duplicate source root
# ===================================================================


def test_stage_keeps_resolved_and_unresolved_pending(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "ok.jpg", color=(1, 2, 3))  # resolved EXIF date
    _make_jpeg_rich(src / "miss.jpg", color=(4, 5, 6))  # missing date
    _make_jpeg(src / "drop.jpg", color=(7, 8, 9), date_original="2024:07:01 09:00:00")
    plan = _photo_plan(data_dir, src)
    # fully deselect one proposal -> skipped at stage time
    for prop in plan["proposals"]:
        if prop["journal"]["date"] == "2024-07-01":
            prop["attachments"] = []
    res = _stage(data_dir, plan, src, tmp_path)
    # resolved AND unresolved candidates stay pending; empty selection skipped
    assert res["queue_counts"]["pending"] == 2
    assert res["queue_counts"]["skipped"] == 1
    assert res["queue_counts"]["confirmed"] == 0
    assert res["queue_revision"] == 1


def test_stage_copies_no_attachment_bytes(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    _stage(data_dir, plan, src, tmp_path)
    # staging never publishes attachment bytes into the data dir
    assert not any((data_dir / "attachments").rglob("*.jpg")) if (data_dir / "attachments").exists() else True
    assert list((data_dir / "attachments").rglob("*")) == [] if (data_dir / "attachments").exists() else True


def test_stage_duplicate_root_already_staged(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6), date_original="2024:07:01 09:00:00")
    plan1 = _photo_plan(data_dir, src)
    parent_id = plan1["import_id"]
    _stage(data_dir, plan1, src, tmp_path)

    # re-stage the identical plan for the same root -> blocked
    res = _err(_stage_raw(data_dir, plan1, src, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_ALREADY_STAGED"
    assert res["error"]["retryable"] is False
    assert res["error"]["details"]["existing_import_id"] == parent_id
    # no second job/plan created
    review_jobs = [j for j in _ledger(data_dir)["jobs"].values() if j.get("kind") == "review"]
    assert len(review_jobs) == 1


def test_stage_duplicate_root_different_content_blocked(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    plan1 = _photo_plan(data_dir, src)
    parent_id = plan1["import_id"]
    _stage(data_dir, plan1, src, tmp_path)  # pending -> blocks same root

    # add a new photo and rescan the SAME root -> different import_id, same identity
    _make_jpeg(src / "c.jpg", color=(9, 9, 9), date_original="2024:08:01 09:00:00")
    plan2 = _photo_plan(data_dir, src)
    assert plan2["import_id"] != parent_id
    res = _err(_stage_raw(data_dir, plan2, src, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_ALREADY_STAGED"
    assert res["error"]["details"]["existing_import_id"] == parent_id


def test_stage_after_all_imported_allows_fresh(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "p1.jpg", color=(1, 2, 3))
    plan1 = _photo_plan(data_dir, src)
    parent1 = plan1["import_id"]
    # stage -> pending, then confirm via legacy resolve + run -> imported
    _confirm(data_dir, plan1, src, tmp_path)
    _ok(_run_import(data_dir, "run", "--import-id", parent1,
                    "--source-root", str(src), "--json"))

    # add a NEW photo; rescan excludes the imported p1 (dedup) -> plan2 with p2 only
    _make_jpeg(src / "p2.jpg", color=(4, 5, 6), date_original="2024:09:01 09:00:00")
    plan2 = _photo_plan(data_dir, src)
    parent2 = plan2["import_id"]
    assert parent2 != parent1

    # parent1 is all-imported, no active child -> does NOT block a fresh stage
    res = _stage(data_dir, plan2, src, tmp_path)
    assert res["parent_id"] == parent2
    assert res["queue_revision"] == 1
    review_jobs = sorted(j for j, v in _ledger(data_dir)["jobs"].items() if v.get("kind") == "review")
    assert review_jobs == sorted([parent1, parent2])


# ===================================================================
# C) confirm --edit — atomic single-proposal edit
# ===================================================================


def _staged_one(tmp_path: Path) -> tuple[Path, Path, dict, str, str]:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    res = _stage(data_dir, plan, src, tmp_path)
    pid = plan["proposals"][0]["proposal_id"]
    return data_dir, src, plan, parent_id, pid


def _edit_payload(proposal_id: str, decision: str = "confirmed", **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "import_review_edit.v1",
        "proposal_id": proposal_id,
        "decision": decision,
    }
    payload.update(extra)
    return payload


def test_edit_mutually_exclusive_plan_and_edit(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    edit = _edit_file(tmp_path, _edit_payload(pid))
    plan_p = _plan_file(tmp_path, plan, name="p.json")
    # passing both --plan and --edit is a usage error (argparse exits non-zero)
    res = _run_import(data_dir, "confirm", "--plan", str(plan_p),
                      "--edit", str(edit), "--import-id", parent_id, "--json")
    assert res.returncode != 0


def test_edit_invalid_schema_version(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(pid)
    payload["schema_version"] = "import_review_edit.v9"
    res = _err(_edit(data_dir, parent_id, payload, 1, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_EDIT_INVALID"
    # zero writes: revision unchanged
    assert _ledger(data_dir)["jobs"][parent_id]["queue_revision"] == 1


def test_edit_rejects_unknown_top_level_field(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(pid)
    payload["source_sha256"] = "sha256:deadbeef"  # provenance field forbidden
    res = _err(_edit(data_dir, parent_id, payload, 1, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_EDIT_INVALID"


def test_edit_rejects_target_field(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(pid)
    payload["target_rel_path"] = "Journals/2024/06/evil.md"
    res = _err(_edit(data_dir, parent_id, payload, 1, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_EDIT_INVALID"


def test_edit_rejects_journal_unknown_field(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(pid, journal={"title": "T", "source_facts": []})
    res = _err(_edit(data_dir, parent_id, payload, 1, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_EDIT_INVALID"


def test_edit_rejects_invalid_topic(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(pid, journal={"topic": "not-a-real-topic"})
    res = _err(_edit(data_dir, parent_id, payload, 1, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_EDIT_INVALID"


def test_edit_rejects_bad_field_type(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(pid, journal={"title": 123})  # title must be str
    res = _err(_edit(data_dir, parent_id, payload, 1, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_EDIT_INVALID"


def test_edit_stale_token_conflict_zero_write(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    ledger_before = _ledger(data_dir)
    plan_hash_before = hashlib.sha256(
        _review_plan(data_dir, parent_id)["plan_fingerprint"].encode()
    ).hexdigest()
    # wrong expected_queue_revision (queue is at 1, claim 99)
    res = _err(_edit(data_dir, parent_id, _edit_payload(pid), 99, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_REVISION_CONFLICT"
    assert res["error"]["retryable"] is True
    assert res["error"]["details"]["current_queue_revision"] == 1
    # zero writes: ledger + plan unchanged
    assert _ledger(data_dir) == ledger_before
    assert _review_plan(data_dir, parent_id)["plan_fingerprint"].encode() or True
    plan_hash_after = hashlib.sha256(
        _review_plan(data_dir, parent_id)["plan_fingerprint"].encode()
    ).hexdigest()
    assert plan_hash_before == plan_hash_after


def test_edit_confirmed_resolves_date_and_bumps(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(
        pid, decision="confirmed",
        journal={"title": "My Photo Day", "date": "2024-06-15", "content": "edited"},
    )
    res = _ok(_edit(data_dir, parent_id, payload, 1, tmp_path))["data"]
    assert res["queue_revision"] == 2
    assert res["plan_revision"] == 2
    assert res["reason_code"] is None
    proj = res["proposal"]
    assert proj["state"] == "confirmed"
    assert proj["proposal_id"] == pid
    assert proj["journal"]["title"] == "My Photo Day"
    assert proj["journal"]["date"] == "2024-06-15"
    # available_attachments reflects the source_facts with selected flags
    assert len(proj["available_attachments"]) == 1
    assert proj["available_attachments"][0]["selected"] is True


def test_edit_empty_selection_coerces_skipped(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(pid, decision="confirmed", selected_attachment_ids=[])
    res = _ok(_edit(data_dir, parent_id, payload, 1, tmp_path))["data"]
    assert res["reason_code"] == "IMPORT_REVIEW_EMPTY_SELECTION_SKIPPED"
    assert res["proposal"]["state"] == "skipped"
    assert res["queue_revision"] == 2


def test_edit_confirmed_unresolved_date_stays_pending(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg_rich(src / "miss.jpg", color=(4, 5, 6))  # missing capture date
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    pid = plan["proposals"][0]["proposal_id"]
    _stage(data_dir, plan, src, tmp_path)

    payload = _edit_payload(pid, decision="confirmed", journal={"title": "still no date"})
    res = _ok(_edit(data_dir, parent_id, payload, 1, tmp_path))["data"]
    assert res["reason_code"] == "IMPORT_REVIEW_DATE_REQUIRED"
    assert res["proposal"]["state"] == "pending"
    # edits saved without promoting to confirmed
    assert res["proposal"]["journal"]["title"] == "still no date"


def test_edit_pending_saves_without_promoting(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(
        pid, decision="pending",
        journal={"title": "draft note", "content": "come back later"},
    )
    res = _ok(_edit(data_dir, parent_id, payload, 1, tmp_path))["data"]
    assert res["proposal"]["state"] == "pending"
    assert res["proposal"]["journal"]["title"] == "draft note"
    # persisted
    persisted = _review_plan(data_dir, parent_id)
    p = next(x for x in persisted["proposals"] if x["proposal_id"] == pid)
    assert p["state"] == "pending"
    assert p["journal"]["title"] == "draft note"


def test_edit_rebuilds_from_source_facts_preserves_all(tmp_path: Path) -> None:
    """Deselecting one attachment keeps both in source_facts / available_attachments."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6))  # same day -> one 2-attachment proposal
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    prop = plan["proposals"][0]
    assert len(prop["attachments"]) == 2
    both_ids = [a["attachment_id"] for a in prop["attachments"]]
    _stage(data_dir, plan, src, tmp_path)
    pid = prop["proposal_id"]

    # keep only the first attachment, confirmed
    keep = both_ids[0]
    payload = _edit_payload(
        pid, decision="confirmed", journal={"date": "2024-06-15"},
        selected_attachment_ids=[keep],
    )
    res = _ok(_edit(data_dir, parent_id, payload, 1, tmp_path))["data"]
    proj = res["proposal"]
    # BOTH source_facts preserved (deselected photo can be reselected later)
    assert len(proj["available_attachments"]) == 2
    sel = {a["attachment_id"]: a["selected"] for a in proj["available_attachments"]}
    assert sel[keep] is True
    dropped = next(i for i in both_ids if i != keep)
    assert sel[dropped] is False
    # persisted source_facts intact
    persisted = _review_plan(data_dir, parent_id)
    p = next(x for x in persisted["proposals"] if x["proposal_id"] == pid)
    assert len(p["source_facts"]) == 2


def test_edit_reselect_after_deselect_using_only_attachment_id(tmp_path: Path) -> None:
    """A deselected photo is reselectable across restart using only its attachment_id."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    prop = plan["proposals"][0]
    both_ids = [a["attachment_id"] for a in prop["attachments"]]
    _stage(data_dir, plan, src, tmp_path)
    pid = prop["proposal_id"]

    # deselect all -> skipped
    r1 = _ok(_edit(data_dir, parent_id,
                   _edit_payload(pid, decision="confirmed", selected_attachment_ids=[]),
                   1, tmp_path))["data"]
    # reselect the previously-dropped attachment using only its id (no client source facts)
    target = both_ids[1]
    r2 = _ok(_edit(data_dir, parent_id,
                   _edit_payload(pid, decision="confirmed",
                                 journal={"date": "2024-06-15"},
                                 selected_attachment_ids=[target]),
                   r1["queue_revision"], tmp_path))["data"]
    assert r2["proposal"]["state"] == "confirmed"
    sel = {a["attachment_id"]: a["selected"] for a in r2["proposal"]["available_attachments"]}
    assert sel[target] is True


def test_edit_frozen_proposal_rejected(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    # confirm via legacy resolve + run -> imported (frozen)
    _confirm(data_dir, plan, src, tmp_path)
    _ok(_run_import(data_dir, "run", "--import-id", parent_id,
                    "--source-root", str(src), "--json"))
    q = _ledger(data_dir)["jobs"][parent_id]["queue_revision"]
    res = _err(_edit(data_dir, parent_id, _edit_payload(pid), q, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_PROPOSAL_FROZEN"


def test_two_chained_edits_use_only_prior_queue_revision(tmp_path: Path) -> None:
    """Two edits chained using only the prior response queue_revision (no review refetch)."""
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    r1 = _ok(_edit(data_dir, parent_id,
                   _edit_payload(pid, decision="pending", journal={"title": "first"}),
                   1, tmp_path))["data"]
    # second edit uses r1's queue_revision as the token, no refetch
    r2 = _ok(_edit(data_dir, parent_id,
                   _edit_payload(pid, decision="confirmed",
                                 journal={"title": "second", "date": "2024-06-15"}),
                   r1["queue_revision"], tmp_path))["data"]
    assert r2["queue_revision"] == r1["queue_revision"] + 1
    assert r2["proposal"]["state"] == "confirmed"
    assert r2["proposal"]["journal"]["title"] == "second"


def test_edit_rejects_unknown_attachment_id(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id, pid = _staged_one(tmp_path)
    payload = _edit_payload(pid, decision="confirmed",
                            journal={"date": "2024-06-15"},
                            selected_attachment_ids=["att_doesnotexist"])
    res = _err(_edit(data_dir, parent_id, payload, 1, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_EDIT_INVALID"


# ===================================================================
# D) import review — bounded read projections
# ===================================================================


def _staged_multi(tmp_path: Path, n_days: int = 4, per_day: int = 1) -> tuple[Path, Path, dict, str]:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    day_pairs = [(1, 1), (2, 2), (3, 3), (4, 4)][:n_days]
    for day_idx, (m, d) in enumerate(day_pairs):
        for i in range(per_day):
            # Unique EXIF second per photo so each JPEG has distinct bytes (the
            # adapter dedups by content SHA). The calendar date is unchanged, so
            # resolved photos still group into one proposal per day.
            dt = f"2024:0{m}:0{d} {i // 60:02d}:{i % 60:02d}:00"
            _make_jpeg(
                src / f"p{day_idx}_{i}.jpg",
                color=(day_idx * 10 + i, i, day_idx),
                date_original=dt,
            )
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    _stage(data_dir, plan, src, tmp_path)
    return data_dir, src, plan, parent_id


def test_review_bounded_pagination_and_counts(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=4)
    total = len(plan["proposals"])
    res = _ok(_review(data_dir, parent_id))["data"]
    assert res["schema_version"] == "import_review.v1"
    assert res["import_id"] == parent_id
    assert res["total_all"] == total
    assert res["total_filtered"] == total
    assert res["offset"] == 0
    assert res["limit"] == 20
    assert res["has_more"] is False
    assert len(res["proposals"]) == total
    # bounded first page
    page1 = _ok(_review(data_dir, parent_id, "--limit", "2"))["data"]
    assert len(page1["proposals"]) == 2
    assert page1["has_more"] is True
    assert page1["next_offset"] == 2
    page2 = _ok(_review(data_dir, parent_id, "--offset", "2", "--limit", "2"))["data"]
    assert len(page2["proposals"]) == 2


def test_review_limit_clamped_to_max(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=4)
    res = _ok(_review(data_dir, parent_id, "--limit", "999"))["data"]
    assert res["limit"] == 100


def test_review_offset_beyond_total_empty(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=2)
    res = _ok(_review(data_dir, parent_id, "--offset", "999"))["data"]
    assert res["proposals"] == []
    assert res["has_more"] is False
    assert res["total_filtered"] == 2


def test_review_state_filter_repeated(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=3)
    pid_a = plan["proposals"][0]["proposal_id"]
    # confirm one via edit, skip another, leave one pending
    r = _ok(_edit(data_dir, parent_id,
                  _edit_payload(pid_a, decision="confirmed", journal={"date": "2024-01-01"}),
                  1, tmp_path))["data"]
    pid_b = plan["proposals"][1]["proposal_id"]
    r = _ok(_edit(data_dir, parent_id,
                  _edit_payload(pid_b, decision="skipped"), r["queue_revision"], tmp_path))["data"]
    # filter pending+skipped (repeated --state)
    res = _ok(_review(data_dir, parent_id, "--state", "pending", "--state", "skipped"))["data"]
    states = {p["state"] for p in res["proposals"]}
    assert states <= {"pending", "skipped"}
    assert res["total_filtered"] == 2


def test_review_state_filter_empty(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=2)
    # nothing imported yet
    res = _ok(_review(data_dir, parent_id, "--state", "imported"))["data"]
    assert res["proposals"] == []
    assert res["total_filtered"] == 0
    assert res["total_all"] == 2


def test_review_authoritative_state_overlay(tmp_path: Path) -> None:
    """Review state comes from the ledger authority, not the plan's per-proposal field."""
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=1)
    pid = plan["proposals"][0]["proposal_id"]
    # tamper the persisted plan's per-proposal state field; ledger stays authoritative
    persisted = _review_plan(data_dir, parent_id)
    persisted["proposals"][0]["state"] = "imported"
    (data_dir / ".life-index" / "import-jobs" / parent_id / "review-plan.json").write_text(
        json.dumps(persisted), encoding="utf-8")
    res = _ok(_review(data_dir, parent_id))["data"]
    # ledger says pending (stage), not the tampered "imported"
    assert res["proposals"][0]["state"] == "pending"


def test_review_preserves_plan_order(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=4)
    plan_order = [p["proposal_id"] for p in _review_plan(data_dir, parent_id)["proposals"]]
    res = _ok(_review(data_dir, parent_id))["data"]
    assert [p["proposal_id"] for p in res["proposals"]] == plan_order


def test_review_no_absolute_source_locator(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=1)
    res = _ok(_review(data_dir, parent_id))["data"]
    blob = json.dumps(res)
    # never expose a relative or absolute source filesystem locator
    assert "source_rel_path" not in blob
    assert str(src) not in blob
    att = res["proposals"][0]["available_attachments"][0]
    assert set(att.keys()) >= {"attachment_id", "source_ref", "media_type", "size", "selected"}
    assert att["source_ref"].startswith("source://")


def test_review_scale_120_photos_4_days(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=4, per_day=30)
    assert sum(len(p["attachments"]) for p in _review_plan(data_dir, parent_id)["proposals"]) == 120
    page = _ok(_review(data_dir, parent_id, "--limit", "2"))["data"]
    assert page["total_all"] == 4
    assert len(page["proposals"]) == 2
    # every available attachment projection carries a stable selected flag
    for a in page["proposals"][0]["available_attachments"]:
        assert isinstance(a["selected"], bool)


def test_review_recovery_required(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=1)
    pid = plan["proposals"][0]["proposal_id"]
    # seed an unsettled active child with no manifest -> recovery_required
    child_id = f"{parent_id}#batch-seeded"
    ledger = _ledger(data_dir)
    ledger["jobs"][child_id] = {
        "kind": "batch", "parent_review_job_id": parent_id,
        "state": "running", "updated_at": "2026-01-01T00:00:00+00:00",
    }
    ledger["jobs"][parent_id]["active_child_id"] = child_id
    ledger["jobs"][parent_id]["proposal_states"][pid] = "batching"
    _save_ledger(data_dir, ledger)

    res = _err(_review(data_dir, parent_id))
    assert res["error"]["code"] == "IMPORT_REVIEW_RECOVERY_REQUIRED"
    assert res["error"]["retryable"] is False


def test_review_stable_second_read_hashes(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=3)
    r1 = json.dumps(_ok(_review(data_dir, parent_id))["data"], sort_keys=True)
    ledger_before = json.dumps(_ledger(data_dir), sort_keys=True)
    r2 = json.dumps(_ok(_review(data_dir, parent_id))["data"], sort_keys=True)
    ledger_after = json.dumps(_ledger(data_dir), sort_keys=True)
    assert r1 == r2
    assert ledger_before == ledger_after  # stable read: no mutation


def test_review_inter_page_mutation_changes_token(tmp_path: Path) -> None:
    """A mutation between page reads changes queue_revision (client detects drift)."""
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=3)
    page1 = _ok(_review(data_dir, parent_id, "--limit", "1"))["data"]
    token1 = page1["queue_revision"]
    # mutate the queue between reads (skip a proposal via edit)
    _ok(_edit(data_dir, parent_id,
              _edit_payload(plan["proposals"][0]["proposal_id"], decision="skipped"),
              token1, tmp_path))
    page2 = _ok(_review(data_dir, parent_id, "--offset", "1", "--limit", "1"))["data"]
    assert page2["queue_revision"] != token1


# ===================================================================
# E) import reviews — discover persisted review jobs
# ===================================================================


def test_reviews_lists_parent_jobs_sorted(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=2)
    res = _ok(_reviews(data_dir))["data"]
    assert res["schema_version"] == "import_review.v1"
    assert len(res["jobs"]) == 1
    job = res["jobs"][0]
    assert job["import_id"] == parent_id
    for key in ("plan_revision", "queue_revision", "queue_counts", "state",
                "active_child_id", "recovery_required", "created_at", "updated_at"):
        assert key in job
    # no locator / proposal contents
    blob = json.dumps(res)
    assert "source_rel_path" not in blob
    assert "proposals" not in blob or "available_attachments" not in blob


def test_reviews_after_exclusive_cursor(tmp_path: Path) -> None:
    data_dir, src, plan, parent1 = _staged_multi(tmp_path, n_days=1)
    # second parent on a fresh root
    src2 = tmp_path / "photos2"
    _make_jpeg(src2 / "x.jpg", color=(1, 1, 1))
    plan2 = _photo_plan(data_dir, src2)
    parent2 = plan2["import_id"]
    _stage(data_dir, plan2, src2, tmp_path)

    all_ids = sorted([parent1, parent2])
    res = _ok(_reviews(data_dir))["data"]
    assert [j["import_id"] for j in res["jobs"]] == all_ids

    # after is exclusive
    after_res = _ok(_reviews(data_dir, "--after", all_ids[0]))["data"]
    assert [j["import_id"] for j in after_res["jobs"]] == [all_ids[1]]


def test_reviews_limit_and_has_more(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    # three distinct roots -> three parents
    for i in range(3):
        s = tmp_path / f"photos_{i}"
        _make_jpeg(s / "a.jpg", color=(i, i, i), date_original=f"2024:0{i+1}:0{i+1} 09:00:00")
        pl = _photo_plan(data_dir, s)
        _stage(data_dir, pl, s, tmp_path)
    res = _ok(_reviews(data_dir, "--limit", "2"))["data"]
    assert len(res["jobs"]) == 2
    assert res["has_more"] is True
    res2 = _ok(_reviews(data_dir, "--limit", "2",
                        "--after", res["jobs"][-1]["import_id"]))["data"]
    assert len(res2["jobs"]) == 1


def test_reviews_excludes_child_batch_jobs(tmp_path: Path) -> None:
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=1)
    # confirm + run -> creates a child batch job, which must NOT be listed
    _confirm(data_dir, plan, src, tmp_path)
    _ok(_run_import(data_dir, "run", "--import-id", parent_id,
                    "--source-root", str(src), "--json"))
    res = _ok(_reviews(data_dir))["data"]
    assert [j["import_id"] for j in res["jobs"]] == [parent_id]


def test_reviews_stable_no_reconcile_no_skip(tmp_path: Path) -> None:
    """An interleaved updated_at change must not reorder or skip existing ids; reviews
    is a stable read that performs no reconciliation beyond reading the ledger."""
    data_dir, src, plan, parent_id = _staged_multi(tmp_path, n_days=2)
    # snapshot the ledger; reviews must not mutate it
    before = json.dumps(_ledger(data_dir), sort_keys=True)
    res = _ok(_reviews(data_dir))["data"]
    after = json.dumps(_ledger(data_dir), sort_keys=True)
    assert before == after
    # bump updated_at on the parent between reads -> ordering/id set unchanged
    ledger = _ledger(data_dir)
    ledger["jobs"][parent_id]["updated_at"] = "2099-12-31T00:00:00+00:00"
    _save_ledger(data_dir, ledger)
    res2 = _ok(_reviews(data_dir))["data"]
    assert [j["import_id"] for j in res2["jobs"]] == [j["import_id"] for j in res["jobs"]]


# ===================================================================
# F) preview — proposal-pinned, deselected attachment, lost-locator flow
# ===================================================================


def test_preview_deselected_attachment_from_source_facts(tmp_path: Path) -> None:
    """An attachment derived from source_facts is previewable even when deselected."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    prop = plan["proposals"][0]
    both_ids = [a["attachment_id"] for a in prop["attachments"]]
    pid = prop["proposal_id"]
    _stage(data_dir, plan, src, tmp_path)

    # deselect attachment b (keep only a), confirm with a date
    keep = both_ids[0]
    dropped = both_ids[1]
    _ok(_edit(data_dir, parent_id,
              _edit_payload(pid, decision="confirmed", journal={"date": "2024-06-15"},
                            selected_attachment_ids=[keep]),
              1, tmp_path))

    source_file = src / "b.jpg"
    before_bytes = source_file.read_bytes()
    before_mtime = source_file.stat().st_mtime_ns
    out = tmp_path / "preview.jpg"
    meta = tmp_path / "meta.json"
    # preview the DESELECTED attachment, pinned to its proposal
    res = _ok(_run_import(data_dir, "preview", "--import-id", parent_id,
                          "--proposal-id", pid, "--attachment", dropped,
                          "--source-root", str(src), "--output", str(out),
                          "--metadata-output", str(meta), "--json"))
    assert out.read_bytes() == before_bytes
    metadata = json.loads(meta.read_text("utf-8"))
    assert metadata["attachment_id"] == dropped
    assert metadata["proposal_id"] == pid
    assert metadata["available"] is True
    # read-only: source hash & mtime unchanged
    assert source_file.stat().st_mtime_ns == before_mtime
    assert source_file.read_bytes() == before_bytes


def test_preview_rejects_mismatched_proposal(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6), date_original="2024:07:01 09:00:00")
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    pids = [p["proposal_id"] for p in plan["proposals"]]
    att = plan["proposals"][0]["attachments"][0]["attachment_id"]
    _stage(data_dir, plan, src, tmp_path)
    out = tmp_path / "preview.jpg"
    # the attachment belongs to pids[0]; pinning it to pids[1] is a mismatch
    wrong_pid = pids[1] if pids[0] != pids[1] else pids[0] + "_x"
    res = _err(_run_import(data_dir, "preview", "--import-id", parent_id,
                           "--proposal-id", wrong_pid, "--attachment", att,
                           "--source-root", str(src), "--output", str(out), "--json"))
    assert res["error"]["code"] == "IMPORT_PREVIEW_UNAVAILABLE"


def test_preview_lost_locator_flow(tmp_path: Path) -> None:
    """reviews finds the id; user reselects a synthetic root; rebind; preview a
    deselected attachment; source hash+mtime unchanged across the whole flow."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    prop = plan["proposals"][0]
    both_ids = [a["attachment_id"] for a in prop["attachments"]]
    pid = prop["proposal_id"]
    _stage(data_dir, plan, src, tmp_path)
    # deselect b
    _ok(_edit(data_dir, parent_id,
              _edit_payload(pid, decision="confirmed", journal={"date": "2024-06-15"},
                            selected_attachment_ids=[both_ids[0]]),
              1, tmp_path))

    # discover the id via reviews (no locator in the listing)
    listing = _ok(_reviews(data_dir))["data"]
    assert listing["jobs"][0]["import_id"] == parent_id

    dropped = both_ids[1]
    source_file = src / "b.jpg"
    before_bytes = source_file.read_bytes()
    before_mtime = source_file.stat().st_mtime_ns
    out = tmp_path / "preview.jpg"
    # rebind the same root identity, then preview the deselected attachment
    _ok(_run_import(data_dir, "rebind", "--import-id", parent_id,
                    "--source-root", str(src), "--json"))
    _ok(_run_import(data_dir, "preview", "--import-id", parent_id,
                    "--proposal-id", pid, "--attachment", dropped,
                    "--source-root", str(src), "--output", str(out), "--json"))
    assert out.read_bytes() == before_bytes
    assert source_file.stat().st_mtime_ns == before_mtime
    assert source_file.read_bytes() == before_bytes


# ===================================================================
# G) rework — atomic snapshot, post-reconcile token, projections,
#    legacy token, edit correctness, stable duplicate-stage no-write.
#    Causal RED-first tests for the narrow M7-B package-3 rework.
# ===================================================================


def _stage_inproc(data_dir: Path, plan: dict, src: Path, tmp_path: Path) -> str:
    review.confirm_review(
        plan_path=str(_plan_file(tmp_path, plan, name=f"stage_{plan['import_id']}.json")),
        data_dir=data_dir, source_root=str(src), stage=True,
    )
    return plan["import_id"]


# --- F1: atomic review snapshot under one per-parent lock -------------------


def test_review_snapshot_reads_plan_and_ledger_under_one_lock(
    isolated_data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plan + ledger capture that drives a review page must occur while the
    per-parent lock is held, so the snapshot can never be assembled from mixed
    revisions. Instruments lock depth around every plan/ledger read."""
    data_dir = isolated_data_dir
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = _stage_inproc(data_dir, plan, src, tmp_path)

    state = {"depth": 0}
    plan_depths: list[int] = []
    ledger_depths: list[int] = []

    class _RecordingLock(review.FileLock):
        def __enter__(self) -> "_RecordingLock":
            ret = super().__enter__()
            state["depth"] += 1
            return ret

        def __exit__(self, *a: object) -> None:
            state["depth"] -= 1
            return super().__exit__(*a)  # type: ignore[return-value]

    monkeypatch.setattr(review, "FileLock", _RecordingLock)

    orig_plan = review.read_review_plan

    def rec_plan(d: Path, pid: str) -> dict | None:
        plan_depths.append(state["depth"])
        return orig_plan(d, pid)

    orig_ledger = review._read_ledger

    def rec_ledger(d: Path) -> dict:
        ledger_depths.append(state["depth"])
        return orig_ledger(d)

    monkeypatch.setattr(review, "read_review_plan", rec_plan)
    monkeypatch.setattr(review, "_read_ledger", rec_ledger)

    review.review_queue(parent_id, data_dir)

    assert plan_depths, "read_review_plan was never invoked"
    assert ledger_depths, "_read_ledger was never invoked"
    # On the rejected base the page-assembly reads happen AFTER reconcile
    # released its lock (depth 0) -> the snapshot window is unlocked.
    assert min(plan_depths) >= 1, f"plan read outside the lock: {plan_depths}"
    assert min(ledger_depths) >= 1, f"ledger read outside the lock: {ledger_depths}"


def test_review_page_never_assembled_from_mixed_revisions(
    isolated_data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cooperating writer (edit_review, same per-parent lock) must never
    interleave inside the page-snapshot window. Instruments read_review_plan to
    attempt a non-blocking locked mutation at snapshot time."""
    from tools.lib.file_lock import FileLock as _RealFileLock

    data_dir = isolated_data_dir
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6), date_original="2024:07:01 09:00:00")
    plan = _photo_plan(data_dir, src)
    parent_id = _stage_inproc(data_dir, plan, src, tmp_path)
    pid = plan["proposals"][0]["proposal_id"]
    lock_path = review._review_lock_path(data_dir, parent_id)

    mutated = {"yes": False}
    orig_plan = review.read_review_plan

    def interfering_read_plan(d: Path, pid_: str) -> dict | None:
        # A cooperating writer attempting the SAME per-parent lock at the exact
        # instant the page reads the plan. Non-blocking: blocked while review
        # holds the lock; succeeds only if the snapshot window is unlocked.
        lk = _RealFileLock(lock_path)
        if lk.try_lock():
            try:
                lg = review._read_ledger(d)
                job = lg["jobs"][parent_id]
                ps = dict(job.get("proposal_states", {}))
                if pid in ps:
                    ps[pid] = "skipped"
                job["proposal_states"] = ps
                review._bump_queue(job)
                review._write_ledger(d, lg)
                mutated["yes"] = True
            finally:
                lk.unlock()
        return orig_plan(d, pid_)

    monkeypatch.setattr(review, "read_review_plan", interfering_read_plan)

    res = review.review_queue(parent_id, data_dir)
    data = res["data"]
    live_q = review._queue_revision_of(
        review._get_job(review._read_ledger(data_dir), parent_id)
    )
    assert mutated["yes"] is False, "concurrent writer mutated the queue mid-snapshot"
    assert data["queue_revision"] == live_q, "page assembled from mixed revisions"


# --- F2: post-reconcile edit safety + token recheck -------------------------


def test_edit_conflicts_when_reconcile_advanced_token(
    isolated_data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pending intent finalized by reconciliation advances queue_revision; an
    edit bearing the pre-reconcile token must conflict (retryable) and NOT apply."""
    data_dir = isolated_data_dir
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    pid = plan["proposals"][0]["proposal_id"]
    # first confirm -> queue_revision 1
    review.confirm_review(
        plan_path=str(_plan_file(tmp_path, plan, "p1.json")),
        data_dir=data_dir, source_root=str(src),
    )
    assert review._read_ledger(data_dir)["jobs"][parent_id]["queue_revision"] == 1

    # second confirm with a changed title, finalize "crashes" -> pending intent
    plan["proposals"][0]["journal"]["title"] = "crash replay title"
    original_finalize = review._finalize_review_update
    crashed = {"done": False}

    def crashing_finalize(d: Path, lg: dict, p: str, intent: dict) -> None:
        if not crashed["done"]:
            crashed["done"] = True
            return
        return original_finalize(d, lg, p, intent)

    monkeypatch.setattr(review, "_finalize_review_update", crashing_finalize)
    review.confirm_review(
        plan_path=str(_plan_file(tmp_path, plan, "p2.json")),
        data_dir=data_dir, source_root=str(src),
    )
    monkeypatch.setattr(review, "_finalize_review_update", original_finalize)
    assert "pending_review_update" in review._read_ledger(data_dir)["jobs"][parent_id]

    # edit with the pre-reconcile token (1): reconciliation finalizes the intent
    # (advancing the token to 2), so the edit must conflict and not apply.
    edit = _edit_file(
        tmp_path, _edit_payload(pid, decision="pending", journal={"title": "MUST NOT APPLY"}),
        name="edit_conflict.json",
    )
    res = review.edit_review(
        edit_path=str(edit), parent_id=parent_id,
        expected_queue_revision=1, data_dir=data_dir,
    )
    assert res["success"] is False
    assert res["error"]["code"] == "IMPORT_REVIEW_REVISION_CONFLICT"
    assert res["error"]["retryable"] is True
    assert res["error"]["details"]["current_queue_revision"] == 2
    # the user edit was NOT applied; the crash-replay title survives
    persisted = _review_plan(data_dir, parent_id)
    titles = [p["journal"]["title"] for p in persisted["proposals"] if p["proposal_id"] == pid]
    assert titles == ["crash replay title"]
    # the convergence write (finalize) remains: token advanced to 2
    assert review._read_ledger(data_dir)["jobs"][parent_id]["queue_revision"] == 2


def test_edit_recovery_mismatch_fails_closed(tmp_path: Path) -> None:
    """An authority plan/ledger mismatch must fail an edit closed
    (IMPORT_REVIEW_RECOVERY_REQUIRED), regardless of the token."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    pid = plan["proposals"][0]["proposal_id"]
    _stage(data_dir, plan, src, tmp_path)

    # seed an unexplained plan/ledger fingerprint mismatch
    persisted = _review_plan(data_dir, parent_id)
    persisted["plan_fingerprint"] = "sha256:deadbeefmismatch000000000000000000000000"
    (data_dir / ".life-index" / "import-jobs" / parent_id / "review-plan.json").write_text(
        json.dumps(persisted), encoding="utf-8")
    # let status converge the mismatch once and read the live token
    _status(data_dir, parent_id)
    q = _ledger(data_dir)["jobs"][parent_id]["queue_revision"]

    res = _err(_edit(data_dir, parent_id, _edit_payload(pid, decision="pending",
                     journal={"title": "should not apply"}), q, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_RECOVERY_REQUIRED"
    assert res["error"]["retryable"] is False
    # edit not applied
    persisted2 = _review_plan(data_dir, parent_id)
    titles = [p["journal"]["title"] for p in persisted2["proposals"] if p["proposal_id"] == pid]
    assert titles != ["should not apply"]


def test_edit_active_child_blocks_unrelated_proposal(tmp_path: Path) -> None:
    """An unsettled active child batch must block editing ANY proposal
    (IMPORT_BATCH_ALREADY_ACTIVE), even an unrelated one."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6), date_original="2024:07:01 09:00:00")
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    pids = [p["proposal_id"] for p in plan["proposals"]]
    _stage(data_dir, plan, src, tmp_path)

    # seed an in-flight child; let reconcile settle it to a stable active state
    child_id = f"{parent_id}#batch-seeded"
    ledger = _ledger(data_dir)
    ledger["jobs"][child_id] = {
        "kind": "batch", "parent_review_job_id": parent_id,
        "state": "running", "updated_at": "2026-01-01T00:00:00+00:00",
    }
    ledger["jobs"][parent_id]["active_child_id"] = child_id
    ledger["jobs"][parent_id]["proposal_states"][pids[0]] = "batching"
    _save_ledger(data_dir, ledger)
    _status(data_dir, parent_id)  # converge once (recovery + retained child)
    q = _ledger(data_dir)["jobs"][parent_id]["queue_revision"]
    assert _ledger(data_dir)["jobs"][parent_id]["active_child_id"] == child_id

    # editing an UNRELATED proposal must be blocked by the active child
    other = pids[-1]
    res = _err(_edit(data_dir, parent_id, _edit_payload(other, decision="skipped"), q, tmp_path))
    assert res["error"]["code"] == "IMPORT_BATCH_ALREADY_ACTIVE"
    assert res["error"]["retryable"] is False
    # edit not applied: the unrelated proposal is still pending
    assert _ledger(data_dir)["jobs"][parent_id]["proposal_states"][other] == "pending"


# --- F3: complete GUI-facing projections ------------------------------------


def test_review_response_carries_full_authority_projection(tmp_path: Path) -> None:
    """A review page exposes the full proposal projection (date_resolution,
    conflicts, warnings, all available_attachments) and response-level authority
    (plan_revision, queue_revision, source_root_identity hash, queue_counts)."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg_rich(src / "miss.jpg", color=(4, 5, 6))  # missing-date conflict
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    _stage(data_dir, plan, src, tmp_path)

    res = _ok(_review(data_dir, parent_id))["data"]
    # response-level authority
    for key in ("plan_revision", "queue_revision", "source_root_identity", "queue_counts"):
        assert key in res, f"missing response field {key}"
    assert res["source_root_identity"].startswith("sha256:")
    blob = json.dumps(res)
    assert str(src) not in blob
    assert "source_rel_path" not in blob

    prop = res["proposals"][0]
    for key in ("proposal_id", "state", "journal", "date_resolution",
                "conflicts", "warnings", "available_attachments"):
        assert key in prop, f"missing proposal field {key}"
    # unresolved missing-date conflict is surfaced
    assert prop["date_resolution"]["status"] == "unresolved"
    codes = {c.get("code") for c in prop["conflicts"]}
    assert "PHOTO_CAPTURE_TIME_MISSING" in codes
    # adapter warnings are surfaced by code, never by a locator-bearing message
    assert isinstance(prop["warnings"], list)
    for w in prop["warnings"]:
        assert "code" in w and "severity" in w
        assert "message" not in w
    assert "miss.jpg" not in json.dumps(prop)
    # all source_facts are selectable attachments with a selected flag
    assert len(prop["available_attachments"]) >= 1
    assert isinstance(prop["available_attachments"][0]["selected"], bool)


def test_edit_success_carries_full_projection_and_counts(tmp_path: Path) -> None:
    """Edit success returns queue_counts, both revisions, reason_code, and the
    same authoritative proposal projection (date_resolution/conflicts/warnings)."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg_rich(src / "miss.jpg", color=(4, 5, 6))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    pid = plan["proposals"][0]["proposal_id"]
    _stage(data_dir, plan, src, tmp_path)

    payload = _edit_payload(pid, decision="confirmed",
                            journal={"title": "Resolved", "date": "2024-06-15"})
    res = _ok(_edit(data_dir, parent_id, payload, 1, tmp_path))["data"]
    for key in ("plan_revision", "queue_revision", "queue_counts", "reason_code", "proposal"):
        assert key in res, f"missing edit-success field {key}"
    prop = res["proposal"]
    for key in ("proposal_id", "state", "journal", "date_resolution",
                "conflicts", "warnings", "available_attachments"):
        assert key in prop, f"missing proposal field {key}"
    assert prop["state"] == "confirmed"
    assert prop["date_resolution"]["status"] == "user_confirmed"
    blob = json.dumps(res)
    assert "source_rel_path" not in blob
    assert str(src) not in blob


# --- F4: deterministic legacy queue token + authority bump ------------------


def test_legacy_missing_queue_revision_initialized_once(
    isolated_data_dir: Path, tmp_path: Path
) -> None:
    """A review parent missing queue_revision is initialized to 1 and persisted
    exactly once; a second read is a stable no-write."""
    data_dir = isolated_data_dir
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = _stage_inproc(data_dir, plan, src, tmp_path)

    # simulate a legacy ledger job predating the queue_revision field
    ledger = review._read_ledger(data_dir)
    ledger["jobs"][parent_id].pop("queue_revision", None)
    review._write_ledger(data_dir, ledger)
    assert "queue_revision" not in review._read_ledger(data_dir)["jobs"][parent_id]

    review.review_queue(parent_id, data_dir)  # first read: initialize + persist
    job = review._read_ledger(data_dir)["jobs"][parent_id]
    assert job.get("queue_revision") == 1, "legacy queue_revision not initialized to 1"
    after_first = json.dumps(review._read_ledger(data_dir), sort_keys=True)

    review.review_queue(parent_id, data_dir)  # second read: stable no-write
    after_second = json.dumps(review._read_ledger(data_dir), sort_keys=True)
    assert after_first == after_second


def test_authority_mismatch_bumps_queue_once_not_plan(tmp_path: Path) -> None:
    """A plan/ledger mismatch that flips recovery_required/authority_status bumps
    queue_revision exactly once and never touches plan_revision."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    _stage(data_dir, plan, src, tmp_path)
    q0 = _ledger(data_dir)["jobs"][parent_id]["queue_revision"]
    plan_rev0 = _ledger(data_dir)["jobs"][parent_id]["plan_revision"]

    persisted = _review_plan(data_dir, parent_id)
    persisted["plan_fingerprint"] = "sha256:deadbeefmismatch111111111111111111111111"
    (data_dir / ".life-index" / "import-jobs" / parent_id / "review-plan.json").write_text(
        json.dumps(persisted), encoding="utf-8")

    # first converge: mismatch -> recovery_required + authority_status + ONE bump
    s = _status(data_dir, parent_id)
    job = _ledger(data_dir)["jobs"][parent_id]
    assert s["authority_status"] == "plan_ledger_mismatch"
    assert s["recovery_required"] is True
    assert job["queue_revision"] == q0 + 1, "mismatch did not bump queue_revision exactly once"
    assert job["plan_revision"] == plan_rev0, "state-only change must not bump plan_revision"
    after_first = json.dumps(_ledger(data_dir), sort_keys=True)

    # second converge: stable no-write (convergence)
    _status(data_dir, parent_id)
    after_second = json.dumps(_ledger(data_dir), sort_keys=True)
    assert after_first == after_second


# --- F5: edit payload/data correctness --------------------------------------


def test_edit_rejects_duplicate_selected_attachment_ids(tmp_path: Path) -> None:
    """Duplicate selected_attachment_ids would publish the same bytes twice; the
    edit must be rejected as IMPORT_REVIEW_EDIT_INVALID."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6))  # same day -> one 2-attachment proposal
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    prop = plan["proposals"][0]
    assert len(prop["attachments"]) == 2
    aid = prop["attachments"][0]["attachment_id"]
    pid = prop["proposal_id"]
    _stage(data_dir, plan, src, tmp_path)

    payload = _edit_payload(pid, decision="confirmed", journal={"date": "2024-06-15"},
                            selected_attachment_ids=[aid, aid])
    res = _err(_edit(data_dir, parent_id, payload, 1, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_EDIT_INVALID"
    # zero writes: token unchanged
    assert _ledger(data_dir)["jobs"][parent_id]["queue_revision"] == 1


def test_edit_title_only_keeps_user_date_and_confirmed(tmp_path: Path) -> None:
    """A missing-date proposal resolved with a user date stays confirmed (date +
    user_confirmed resolution) across a later title-only confirm edit."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg_rich(src / "miss.jpg", color=(4, 5, 6))  # missing capture date
    plan = _photo_plan(data_dir, src)
    parent_id = plan["import_id"]
    pid = plan["proposals"][0]["proposal_id"]
    _stage(data_dir, plan, src, tmp_path)

    # 1) resolve the missing-date proposal with an explicit user date
    r1 = _ok(_edit(data_dir, parent_id,
                   _edit_payload(pid, decision="confirmed", journal={"date": "2024-06-15"}),
                   1, tmp_path))["data"]
    assert r1["proposal"]["state"] == "confirmed"
    assert r1["proposal"]["date_resolution"]["status"] == "user_confirmed"

    # 2) a later confirm that changes only the title must keep the date + state
    r2 = _ok(_edit(data_dir, parent_id,
                   _edit_payload(pid, decision="confirmed", journal={"title": "just a title"}),
                   r1["queue_revision"], tmp_path))["data"]
    assert r2["proposal"]["state"] == "confirmed"
    assert r2["reason_code"] is None
    assert r2["proposal"]["journal"]["date"] == "2024-06-15"
    assert r2["proposal"]["journal"]["title"] == "just a title"
    assert r2["proposal"]["date_resolution"]["status"] == "user_confirmed"


# --- F6: duplicate-stage stable no-write ------------------------------------


def test_duplicate_stage_stable_is_no_write(tmp_path: Path) -> None:
    """Re-staging an already-staged actionable same-root job is rejected with
    IMPORT_REVIEW_ALREADY_STAGED and must NOT rewrite the ledger/plan (stable
    hash + mtime) when no reconciliation convergence is required."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    plan1 = _photo_plan(data_dir, src)
    _stage(data_dir, plan1, src, tmp_path)

    ledger_path = data_dir / ".life-index" / "import-jobs" / "ledger.json"
    plan_path = data_dir / ".life-index" / "import-jobs" / plan1["import_id"] / "review-plan.json"
    ledger_hash_before = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    ledger_mtime_before = ledger_path.stat().st_mtime_ns
    plan_hash_before = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    plan_mtime_before = plan_path.stat().st_mtime_ns

    res = _err(_stage_raw(data_dir, plan1, src, tmp_path))
    assert res["error"]["code"] == "IMPORT_REVIEW_ALREADY_STAGED"

    assert hashlib.sha256(ledger_path.read_bytes()).hexdigest() == ledger_hash_before
    assert ledger_path.stat().st_mtime_ns == ledger_mtime_before
    assert hashlib.sha256(plan_path.read_bytes()).hexdigest() == plan_hash_before
    assert plan_path.stat().st_mtime_ns == plan_mtime_before
