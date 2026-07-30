#!/usr/bin/env python3
"""Contract tests for the additive import review queue & batch import (M7).

These tests are **additive**: they cover the new review-queue / batch / preview
behaviour and the hardened ``media.photo_timeline`` adapter. The legacy
``tests/contract/test_import_contract.py`` suite must keep passing unchanged.

All tests use synthetic source directories and a tmp ``LIFE_INDEX_DATA_DIR`` —
no real user data, no network, no AI/OCR/face/video.
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

ENVELOPE_SCHEMA_VERSION = "import_job.v1"


# ---------------------------------------------------------------------------
# CLI invocation helpers
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
        timeout=60,
    )


def _run_index(data_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "tools", "index", "--json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
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
# Photo synthesis helpers (synthetic EXIF, deterministic)
# ---------------------------------------------------------------------------


def _make_jpeg(
    path: Path,
    *,
    color: tuple[int, int, int] = (10, 20, 30),
    date_original: str | None = "2024:06:15 10:30:00",
    make: str = "TestCam",
    model: str = "X100",
) -> Path:
    """Write a small synthetic JPEG with optional naive DateTimeOriginal EXIF."""
    from PIL import Image

    img = Image.new("RGB", (8, 8), color)
    exif = Image.Exif()
    if date_original is not None:
        exif[36867] = date_original  # DateTimeOriginal (written at IFD0)
    if make:
        exif[271] = make
    if model:
        exif[272] = model
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", exif=exif.tobytes() if (date_original or make or model) else None)
    return path


def _photo_plan(data_dir: Path, input_dir: Path, *extra: str) -> dict[str, Any]:
    res = _run_import(
        data_dir, "plan", "--source", "media.photo_timeline", "--input", str(input_dir), "--json", *extra
    )
    return _ok(res)


def _plan_file(tmp_path: Path, plan_data: dict[str, Any], name: str = "plan.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(plan_data), encoding="utf-8")
    return p


# ===================================================================
# Slice A: adapter hardening — recursive scan, skip links/reparse/cycle,
# root escape, HEIC warning, exact-content dedup, capture authority,
# immutable source facts.
# ===================================================================


def test_photo_recursive_scan_finds_subdir_photos(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "top.jpg", color=(1, 2, 3))
    _make_jpeg(src / "sub" / "nested.jpg", color=(4, 5, 6))
    _make_jpeg(src / "sub" / "deep" / "deeper.jpg", color=(7, 8, 9))

    plan = _photo_plan(data_dir, src)
    assert plan["data"]["source"]["record_count"] == 3
    # All three attachment source_rel_paths present (relative, posix)
    rel_paths = sorted(
        att["source_rel_path"]
        for prop in plan["data"]["proposals"]
        for att in prop["attachments"]
    )
    assert "top.jpg" in rel_paths
    assert "sub/nested.jpg" in rel_paths
    assert "sub/deep/deeper.jpg" in rel_paths


def test_photo_scan_skips_symlink_and_root_escape(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "real.jpg", color=(1, 2, 3))
    # symlink inside the tree -> skipped
    os.symlink(src / "real.jpg", src / "link.jpg")
    # symlink to a file OUTSIDE the tree (root escape) -> skipped
    outside = tmp_path / "outside.jpg"
    _make_jpeg(outside, color=(9, 9, 9))
    os.symlink(outside, src / "escape.jpg")

    plan = _photo_plan(data_dir, src)
    assert plan["data"]["source"]["record_count"] == 1
    rel_paths = [
        att["source_rel_path"] for prop in plan["data"]["proposals"] for att in prop["attachments"]
    ]
    assert rel_paths == ["real.jpg"]


def test_photo_scan_skips_directory_cycle(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    sub = src / "sub"
    sub.mkdir()
    _make_jpeg(sub / "b.jpg", color=(4, 5, 6))
    # create a cycle via symlink dir pointing back at root (skipped as reparse)
    os.symlink(src, sub / "cycle")

    plan = _photo_plan(data_dir, src)
    assert plan["data"]["source"]["record_count"] == 2


def test_photo_heic_emits_unsupported_format_warning(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))
    (src / "img.heic").write_bytes(b"not really heic but extension matters")

    plan = _photo_plan(data_dir, src)
    assert plan["data"]["source"]["record_count"] == 1
    codes = [w.get("code") for w in plan["data"]["warnings"]]
    assert "PHOTO_UNSUPPORTED_FORMAT" in codes
    heic_warn = next(w for w in plan["data"]["warnings"] if w.get("code") == "PHOTO_UNSUPPORTED_FORMAT")
    assert heic_warn.get("preview_available") is False


def test_photo_exact_content_dedup_same_content_one_record(tmp_path: Path) -> None:
    """Same content (different names) -> one record; same name diff content -> two."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(1, 2, 3))  # identical bytes -> duplicate
    _make_jpeg(src / "copy.jpg", color=(9, 9, 9))  # same NAME? no; diff content -> kept

    plan = _photo_plan(data_dir, src)
    # a + copy are distinct content; b is a duplicate of a
    assert plan["data"]["source"]["record_count"] == 2
    codes = [w.get("code") for w in plan["data"]["warnings"]]
    assert "PHOTO_DUPLICATE_SKIPPED" in codes


def test_photo_same_name_different_content_kept(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    sub = src / "day1"
    sub.mkdir(parents=True)
    _make_jpeg(sub / "IMG_0001.jpg", color=(1, 2, 3))
    (src / "day2").mkdir(parents=True)
    _make_jpeg(src / "day2" / "IMG_0001.jpg", color=(9, 9, 9))  # same name, diff content

    plan = _photo_plan(data_dir, src)
    assert plan["data"]["source"]["record_count"] == 2


def test_photo_source_facts_immutable_and_topic_life(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))

    plan = _photo_plan(data_dir, src)
    prop = plan["data"]["proposals"][0]
    # canonical topic, never "imported"
    assert prop["journal"]["topic"] == "life"
    facts = prop["source_facts"]
    assert isinstance(facts, list) and len(facts) == 1
    f0 = facts[0]
    expected_sha = "sha256:" + hashlib.sha256((src / "shot.jpg").read_bytes()).hexdigest()
    assert f0["content_sha256"] == expected_sha
    assert f0["capture_time"]["timezone_authority"] == "exif_naive"
    assert f0["source_rel_path"] == "shot.jpg"
    assert f0["media_type"] == "image/jpeg"


def test_photo_capture_authority_offset_unit() -> None:
    from tools.ingest.adapters._exif_common import parse_capture_time

    iso, tag, conflicts, authority = parse_capture_time(
        {"DateTimeOriginal": "2024:06:15 10:30:00", "OffsetTimeOriginal": "+05:30"}
    )
    assert iso == "2024-06-15T10:30:00"
    assert conflicts == []
    assert authority == "exif_offset"

    iso2, _t2, conflicts2, authority2 = parse_capture_time(
        {"DateTimeOriginal": "2024:06:15 10:30:00"}
    )
    assert authority2 == "exif_naive"
    assert conflicts2 == []

    iso3, _t3, conflicts3, authority3 = parse_capture_time({})
    assert authority3 is None
    assert any(c.get("code") == "PHOTO_CAPTURE_TIME_MISSING" for c in conflicts3)


def test_photo_missing_capture_time_yields_pending_unresolved(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "no_date.jpg", date_original=None)

    plan = _photo_plan(data_dir, src)
    prop = plan["data"]["proposals"][0]
    # Unresolved proposal is pending, carries the conflict, not auto-dated by mtime
    assert prop["state"] == "pending"
    codes = [c.get("code") for c in prop["conflicts"]]
    assert "PHOTO_CAPTURE_TIME_MISSING" in codes


# ===================================================================
# Slice B: planner — per-day aggregation + ledger-authority dedup
# ===================================================================


def test_photo_same_day_photos_aggregate_into_one_proposal(tmp_path: Path) -> None:
    """Two resolved photos captured the same day → one multi-attachment proposal."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    # Same default capture date (2024-06-15), distinct content
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6))

    plan = _photo_plan(data_dir, src)
    assert plan["data"]["source"]["record_count"] == 2
    props = plan["data"]["proposals"]
    assert len(props) == 1, f"expected 1 aggregated proposal, got {len(props)}"
    prop = props[0]
    assert len(prop["attachments"]) == 2
    assert len(prop["source_facts"]) == 2
    assert len(prop["source_record_fingerprints"]) == 2
    assert prop["state"] == "pending"
    assert prop["journal"]["topic"] == "life"
    assert "2024-06-15" in prop["journal"]["title"]
    assert prop["conflicts"] == []  # resolved day-group is runnable


def test_photo_aggregated_plan_fingerprint_is_stable(tmp_path: Path) -> None:
    """Aggregated plan/source fingerprints must be stable across runs."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "a.jpg", color=(1, 2, 3))
    _make_jpeg(src / "b.jpg", color=(4, 5, 6))

    p1 = _photo_plan(data_dir, src)
    p2 = _photo_plan(data_dir, src)
    assert p1["data"]["plan_fingerprint"] == p2["data"]["plan_fingerprint"]
    assert (
        p1["data"]["source"]["source_fingerprint"]
        == p2["data"]["source"]["source_fingerprint"]
    )


def test_photo_already_imported_sha_is_not_reproposed(tmp_path: Path) -> None:
    """A photo whose content SHA was already committed must be deduped on re-plan."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "only.jpg", color=(1, 2, 3))

    plan = _photo_plan(data_dir, src)
    assert plan["data"]["source"]["record_count"] == 1

    plan_file = _plan_file(tmp_path, plan["data"])
    run = _run_import(
        data_dir,
        "run",
        "--plan",
        str(plan_file),
        "--confirm",
        plan["data"]["import_id"],
        "--source-root",
        str(src),
        "--json",
    )
    assert run.returncode == 0, f"run failed: {run.stdout}\n{run.stderr}"

    # Re-planning the same source: the committed attachment SHA is now known and
    # the photo must be skipped as a duplicate (not re-proposed).
    plan2 = _photo_plan(data_dir, src)
    assert plan2["data"]["source"]["record_count"] == 0
    codes = [w.get("code") for w in plan2["data"]["warnings"]]
    assert "PHOTO_DUPLICATE_SKIPPED" in codes
    assert plan2["data"]["proposals"] == []


# ===================================================================
# Slice C: review queue — validate / confirm / status / rollback / rebind
# ===================================================================


def _confirm(
    data_dir: Path, plan_data: dict[str, Any], source_root: Path | None = None, import_id: str | None = None
) -> dict[str, Any]:
    plan_file = _plan_file(Path(data_dir).parent, plan_data, name=f"review_{plan_data['import_id']}.json")
    args = ["confirm", "--plan", str(plan_file), "--json"]
    if source_root is not None:
        args += ["--source-root", str(source_root)]
    if import_id is not None:
        args += ["--import-id", import_id]
    return _ok(_run_import(data_dir, *args))


def _status(data_dir: Path, import_id: str) -> dict[str, Any]:
    return _ok(_run_import(data_dir, "status", "--import-id", import_id, "--json"))


def _ledger(data_dir: Path) -> dict[str, Any]:
    return json.loads((data_dir / ".life-index" / "import-jobs" / "ledger.json").read_text("utf-8"))


def test_import_validate_returns_root_identity(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    src.mkdir()
    data = _ok(_run_import(data_dir, "validate", "--source-root", str(src), "--json"))["data"]
    assert data["schema_version"] == "import_review.v1"
    assert data["readable"] is True
    assert data["source_root_identity"].startswith("sha256:")
    # deterministic across calls
    data2 = _ok(_run_import(data_dir, "validate", "--source-root", str(src), "--json"))["data"]
    assert data["source_root_identity"] == data2["source_root_identity"]


def test_import_validate_rejects_non_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    missing = tmp_path / "does-not-exist"
    res = _err(_run_import(data_dir, "validate", "--source-root", str(missing), "--json"))
    assert res["error"]["code"] == "IMPORT_SOURCE_ROOT_UNREADABLE"


def test_import_confirm_persists_review_plan_and_review_job(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))

    plan = _photo_plan(data_dir, src)
    parent_id = plan["data"]["import_id"]
    res = _confirm(data_dir, plan["data"], source_root=src)["data"]

    assert res["schema_version"] == "import_review.v1"
    assert res["parent_id"] == parent_id
    assert res["queue_counts"]["confirmed"] == 1
    # review-plan.json persisted at the fixed path
    review_plan = data_dir / ".life-index" / "import-jobs" / parent_id / "review-plan.json"
    assert review_plan.exists()
    persisted = json.loads(review_plan.read_text("utf-8"))
    assert persisted["schema_version"] == "import_review_plan.v1"
    # ledger holds a parent review job
    job = _ledger(data_dir)["jobs"][parent_id]
    assert job["kind"] == "review"
    assert job["source_root_identity"] == res["source_root_identity"]
    assert job["active_child_id"] is None


def test_import_confirm_marks_deselected_proposal_skipped(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "keep.jpg", color=(1, 2, 3))
    _make_jpeg(src / "drop.jpg", color=(4, 5, 6), date_original="2024:07:01 09:00:00")

    plan = _photo_plan(data_dir, src)
    # user deselects the second day's proposal by emptying its attachments
    for prop in plan["data"]["proposals"]:
        if prop["journal"]["date"] == "2024-07-01":
            prop["attachments"] = []
    res = _confirm(data_dir, plan["data"], source_root=src)["data"]
    assert res["queue_counts"]["confirmed"] == 1
    assert res["queue_counts"]["skipped"] == 1


def test_import_confirm_detects_source_facts_tamper(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))

    plan = _photo_plan(data_dir, src)
    # tamper with an immutable content hash
    plan["data"]["proposals"][0]["source_facts"][0]["content_sha256"] = "sha256:deadbeef"
    plan_file = _plan_file(tmp_path, plan["data"], name="tampered.json")
    res = _err(_run_import(data_dir, "confirm", "--plan", str(plan_file), "--json"))
    assert res["error"]["code"] == "IMPORT_PLAN_INVALID"


def test_import_status_review_job_is_additive(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))

    plan = _photo_plan(data_dir, src)
    parent_id = plan["data"]["import_id"]
    _confirm(data_dir, plan["data"], source_root=src)

    status = _status(data_dir, parent_id)["data"]
    assert status["kind"] == "review"
    assert status["import_id"] == parent_id
    assert status["queue_counts"]["confirmed"] == 1
    assert parent_id in "".join(status["proposal_states"].keys()) or status["proposal_states"]
    assert status["active_child_id"] is None
    assert status["recovery_required"] is False


def test_import_rollback_parent_not_allowed(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))

    plan = _photo_plan(data_dir, src)
    parent_id = plan["data"]["import_id"]
    _confirm(data_dir, plan["data"], source_root=src)

    res = _err(_run_import(data_dir, "rollback", "--import-id", parent_id, "--json"))
    assert res["error"]["code"] == "IMPORT_ROLLBACK_PARENT_NOT_ALLOWED"


def test_import_rebind_same_root_ok_different_root_mismatch(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))

    plan = _photo_plan(data_dir, src)
    parent_id = plan["data"]["import_id"]
    _confirm(data_dir, plan["data"], source_root=src)

    # rebind to the SAME root -> ok
    ok_res = _ok(_run_import(data_dir, "rebind", "--import-id", parent_id, "--source-root", str(src), "--json"))["data"]
    assert ok_res["rebound"] is True

    # rebind to a DIFFERENT root -> identity mismatch
    other = tmp_path / "elsewhere"
    other.mkdir()
    res = _err(_run_import(data_dir, "rebind", "--import-id", parent_id, "--source-root", str(other), "--json"))
    assert res["error"]["code"] == "IMPORT_SOURCE_ROOT_IDENTITY_MISMATCH"


# ===================================================================
# Slice D: read-only import preview
# ===================================================================


def _preview_file(
    data_dir: Path, parent_id: str, attachment_id: str, src: Path, out: Path, meta: Path | None = None
) -> subprocess.CompletedProcess[str]:
    args = [
        "preview",
        "--import-id",
        parent_id,
        "--attachment",
        attachment_id,
        "--source-root",
        str(src),
        "--output",
        str(out),
        "--json",
    ]
    if meta is not None:
        args += ["--metadata-output", str(meta)]
    return _run_import(data_dir, *args)


def _confirmed_one_photo(data_dir: Path, src: Path) -> tuple[dict[str, Any], str, str]:
    """Plan+confirm one photo; return (plan_data, parent_id, attachment_id)."""
    _make_jpeg(src / "shot.jpg", color=(10, 20, 30))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["data"]["import_id"]
    _confirm(data_dir, plan["data"], source_root=src)
    att_id = plan["data"]["proposals"][0]["attachments"][0]["attachment_id"]
    return plan["data"], parent_id, att_id


def test_import_preview_streams_bytes_and_metadata(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _plan_data, parent_id, att_id = _confirmed_one_photo(data_dir, src)
    source_file = src / "shot.jpg"
    before_bytes = source_file.read_bytes()
    before_mtime = source_file.stat().st_mtime_ns

    out = tmp_path / "preview.jpg"
    meta = tmp_path / "meta.json"
    res = _ok(_preview_file(data_dir, parent_id, att_id, src, out, meta))
    assert out.read_bytes() == before_bytes
    metadata = json.loads(meta.read_text("utf-8"))
    assert metadata["schema_version"] == "import_preview.v1"
    assert metadata["attachment_id"] == att_id
    assert metadata["available"] is True
    expected_sha = "sha256:" + hashlib.sha256(before_bytes).hexdigest()
    assert metadata["source_sha256"] == expected_sha
    # read-only: source hash & mtime unchanged
    assert source_file.stat().st_mtime_ns == before_mtime
    assert source_file.read_bytes() == before_bytes


def test_import_preview_stale_source_errors(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _plan_data, parent_id, att_id = _confirmed_one_photo(data_dir, src)
    # mutate the source after confirm
    (src / "shot.jpg").write_bytes(b"different content now")
    out = tmp_path / "preview.jpg"
    res = _err(_preview_file(data_dir, parent_id, att_id, src, out))
    assert res["error"]["code"] == "IMPORT_PREVIEW_UNAVAILABLE"
    assert res["error"]["details"].get("reason") == "stale"


def test_import_preview_missing_attachment_errors(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _plan_data, parent_id, _att_id = _confirmed_one_photo(data_dir, src)
    out = tmp_path / "preview.jpg"
    res = _err(_preview_file(data_dir, parent_id, "att_nonexistent", src, out))
    assert res["error"]["code"] == "IMPORT_PREVIEW_UNAVAILABLE"


def test_import_preview_requires_confirmed_plan(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    src.mkdir()
    out = tmp_path / "preview.jpg"
    res = _err(_preview_file(data_dir, "imp_unknown", "att_x", src, out))
    assert res["error"]["code"] == "IMPORT_REVIEW_PLAN_MISSING"


# ===================================================================
# Slice E: batch run — single active child, batching -> imported,
# stale detection, TOCTOU (source unchanged), canonical journal,
# child rollback restores confirmed.
# ===================================================================


def _run_batch(
    data_dir: Path, parent_id: str, source_root: Path
) -> subprocess.CompletedProcess[str]:
    return _run_import(
        data_dir,
        "run",
        "--import-id",
        parent_id,
        "--source-root",
        str(source_root),
        "--json",
    )


def _confirmed_one_photo_batch(
    data_dir: Path, src: Path
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Plan + confirm one photo for a batch run.

    Returns (proposal, parent_id, attachment).
    """
    _make_jpeg(src / "shot.jpg", color=(10, 20, 30))
    plan = _photo_plan(data_dir, src)
    parent_id = plan["data"]["import_id"]
    _confirm(data_dir, plan["data"], source_root=src)
    proposal = plan["data"]["proposals"][0]
    return proposal, parent_id, proposal["attachments"][0]


def test_import_run_batch_commits_child_and_projects_imported(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    proposal, parent_id, att = _confirmed_one_photo_batch(data_dir, src)

    run = _ok(_run_batch(data_dir, parent_id, src))["data"]
    assert run["kind"] == "batch"
    assert run["state"] == "committed"
    child_id = run["import_id"]
    assert child_id != parent_id

    # child batch job recorded in the ledger
    ledger = _ledger(data_dir)
    child = ledger["jobs"][child_id]
    assert child["kind"] == "batch"
    assert child["parent_review_job_id"] == parent_id
    assert child["state"] == "committed"

    # parent proposal projected to imported, active child cleared
    parent = ledger["jobs"][parent_id]
    pid = proposal["proposal_id"]
    assert parent["proposal_states"][pid] == "imported"
    assert parent["active_child_id"] is None

    # attachment published at its final target path, content matches source
    published = data_dir / att["target_rel_path"]
    assert published.exists()
    assert published.read_bytes() == (src / "shot.jpg").read_bytes()

    # additive status reflects the imported queue
    status = _status(data_dir, parent_id)["data"]
    assert status["queue_counts"]["imported"] == 1
    assert status["active_child_id"] is None


def test_import_run_batch_unknown_parent_errors(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    src.mkdir()
    res = _err(_run_batch(data_dir, "imp_unknown", src))
    assert res["error"]["code"] == "IMPORT_JOB_NOT_FOUND"


def test_import_run_batch_single_active_child(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    # Seed an unsettled (running) child on the parent to simulate a live writer.
    ledger_path = data_dir / ".life-index" / "import-jobs" / "ledger.json"
    ledger = json.loads(ledger_path.read_text("utf-8"))
    child_id = f"{parent_id}#batch-900000001"
    ledger["jobs"][child_id] = {
        "kind": "batch",
        "parent_review_job_id": parent_id,
        "state": "running",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    ledger["jobs"][parent_id]["active_child_id"] = child_id
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    res = _err(_run_batch(data_dir, parent_id, src))
    assert res["error"]["code"] == "IMPORT_BATCH_ALREADY_ACTIVE"
    # reconciliation marked the parent as needing recovery
    parent = _ledger(data_dir)["jobs"][parent_id]
    assert parent["recovery_required"] is True


def test_import_run_batch_stale_detection(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    # mutate the source after confirm -> stale at run time
    (src / "shot.jpg").write_bytes(b"changed after confirm")

    res = _err(_run_batch(data_dir, parent_id, src))
    assert res["error"]["code"] == "IMPORT_NO_RUNNABLE_PROPOSALS"
    # the proposal is now marked stale on the parent
    parent = _ledger(data_dir)["jobs"][parent_id]
    assert parent["proposal_states"][proposal["proposal_id"]] == "stale"


def test_import_run_batch_source_unchanged_toctou(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    _proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    source_file = src / "shot.jpg"
    before_bytes = source_file.read_bytes()
    before_mtime = source_file.stat().st_mtime_ns

    assert _run_batch(data_dir, parent_id, src).returncode == 0

    # TOCTOU-safe copy: source bytes and mtime untouched
    assert source_file.read_bytes() == before_bytes
    assert source_file.stat().st_mtime_ns == before_mtime
    # no staging leftovers inside the data dir: check the REAL hidden
    # ``.{target}.staging-<rand>.tmp`` naming the implementation writes, plus a
    # broad sweep (a bare ``*.staging-*`` glob could miss the real temp).
    staging = sorted(
        {*data_dir.rglob(".*.staging-*.tmp"), *data_dir.rglob("*staging*")}
    )
    assert staging == []


def test_import_run_batch_canonical_journal(tmp_path: Path) -> None:
    import posixpath
    from tools.lib.frontmatter import parse_frontmatter

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    proposal, parent_id, att = _confirmed_one_photo_batch(data_dir, src)

    assert _run_batch(data_dir, parent_id, src).returncode == 0

    journal_path = data_dir / proposal["journal"]["target_rel_path"]
    assert journal_path.exists()
    fm, _body = parse_frontmatter(journal_path.read_text("utf-8"))

    # canonical journal contract: schema_version + valid topic + attachments SSOT
    assert fm["schema_version"] == 3
    assert fm["topic"] == ["life"]
    attachments = fm["attachments"]
    assert isinstance(attachments, list) and len(attachments) == 1
    att_entry = attachments[0]
    # canonical stored attachment schema (matches write_journal SSOT): filename,
    # journal-relative rel_path, description, original_name, auto_detected,
    # content_type, size. No source SHA/provenance leaks into journal frontmatter.
    assert set(att_entry.keys()) == {
        "filename",
        "rel_path",
        "description",
        "original_name",
        "auto_detected",
        "content_type",
        "size",
    }
    assert att_entry["filename"] == posixpath.basename(att["target_rel_path"])
    # rel_path is journal-relative, not data-dir-relative
    journal_rel = proposal["journal"]["target_rel_path"]
    expected_rel = posixpath.relpath(
        att["target_rel_path"], start=posixpath.dirname(journal_rel)
    )
    assert att_entry["rel_path"] == expected_rel
    assert att_entry["rel_path"].startswith("../../../attachments/")
    assert att_entry["original_name"] == posixpath.basename(att["source_rel_path"])
    assert att_entry["auto_detected"] is False
    assert att_entry["content_type"] == att["media_type"]
    assert att_entry["description"] == ""
    assert att_entry["size"] == att["size_bytes"]
    published = data_dir / att["target_rel_path"]
    assert att_entry["size"] == published.stat().st_size
    # the published attachment resolves through the journal-relative rel_path
    resolved = (journal_path.parent / att_entry["rel_path"]).resolve()
    assert resolved == published.resolve()
    assert resolved.read_bytes() == (src / "shot.jpg").read_bytes()


def test_import_run_batch_rollback_restores_confirmed(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True, exist_ok=True)
    src = tmp_path / "photos"
    proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    run = _ok(_run_batch(data_dir, parent_id, src))["data"]
    child_id = run["import_id"]
    pid = proposal["proposal_id"]
    # before rollback: imported
    assert _status(data_dir, parent_id)["data"]["proposal_states"][pid] == "imported"
    journal_path = data_dir / proposal["journal"]["target_rel_path"]
    assert journal_path.exists()

    # roll back the child batch job
    rb = _ok(_run_import(data_dir, "rollback", "--import-id", child_id, "--json"))["data"]
    assert rb["state"] == "rolled_back"
    # published journal/attachment removed
    assert not journal_path.exists()

    # parent proposals restored to confirmed (re-runnable), active child cleared
    status = _status(data_dir, parent_id)["data"]
    assert status["proposal_states"][pid] == "confirmed"
    assert status["active_child_id"] is None
    assert status["queue_counts"]["confirmed"] == 1
    assert status["queue_counts"]["imported"] == 0


# ===================================================================
# R1a: lexical import-id authority and validation-before-access order
# ===================================================================

_R1A_PARENT_ONLY_SURFACES = (
    "confirm_override",
    "edit",
    "stage_override",
    "review",
    "rebind",
    "preview",
    "run_batch",
    "runner_execute_run_confirm",
)

_R1A_PARENT_OR_CHILD_SURFACES = (
    "status",
    "review_rollback",
    "runner_rollback",
)

_R1A_ALL_SURFACES = _R1A_PARENT_ONLY_SURFACES + _R1A_PARENT_OR_CHILD_SURFACES

_R1A_CORE_INVALID_CASES = (
    (None, "type"),
    ("", "empty"),
    ("é", "non_ascii"),
    ("CON", "reserved_name"),
    ("a" * 129 + "#batch-1", "child_parent_length"),
    ("valid-parent#batch-0", "child_sequence"),
    ("a" * 129, "length"),
)


def _r1a_invoke_surface(
    surface: str,
    import_id: Any,
    data_dir: Path,
    tmp_path: Path,
) -> dict[str, Any]:
    from tools.ingest import review, runner

    missing_plan = str(tmp_path / "missing-plan.json")
    missing_edit = str(tmp_path / "missing-edit.json")
    if surface == "confirm_override":
        if import_id is None:
            typed_plan = tmp_path / "confirm-type-plan.json"
            typed_plan.write_text(
                json.dumps({"import_id": None, "proposals": []}),
                encoding="utf-8",
            )
            return review.confirm_review(
                plan_path=str(typed_plan),
                data_dir=data_dir,
            )
        return review.confirm_review(
            plan_path=missing_plan,
            data_dir=data_dir,
            parent_id_override=import_id,
        )
    if surface == "edit":
        return review.edit_review(
            edit_path=missing_edit,
            parent_id=import_id,
            expected_queue_revision=1,
            data_dir=data_dir,
        )
    if surface == "stage_override":
        if import_id is None:
            typed_plan = tmp_path / "stage-type-plan.json"
            typed_plan.write_text(
                json.dumps({"import_id": None, "proposals": []}),
                encoding="utf-8",
            )
            return review.stage_review(
                plan_path=str(typed_plan),
                data_dir=data_dir,
                source_root=r"\\unreachable.invalid\photos",
            )
        return review.stage_review(
            plan_path=missing_plan,
            data_dir=data_dir,
            source_root=r"\\unreachable.invalid\photos",
            parent_id_override=import_id,
        )
    if surface == "review":
        return review.review_queue(parent_id=import_id, data_dir=data_dir)
    if surface == "rebind":
        return review.rebind_source_root(
            parent_id=import_id,
            source_root=r"\\unreachable.invalid\photos",
            data_dir=data_dir,
        )
    if surface == "preview":
        return review.preview_attachment(
            parent_id=import_id,
            attachment_id="att-safe",
            data_dir=data_dir,
            source_root=r"\\unreachable.invalid\photos",
            output=str(tmp_path / "outside-preview.bin"),
            metadata_output=str(tmp_path / "outside-preview.json"),
        )
    if surface == "run_batch":
        return review.run_batch(
            parent_id=import_id,
            data_dir=data_dir,
            source_root=r"\\unreachable.invalid\photos",
        )
    if surface == "runner_execute_run_confirm":
        if import_id is None:
            typed_plan = tmp_path / "runner-type-plan.json"
            typed_plan.write_text(
                json.dumps({"import_id": None, "proposals": []}),
                encoding="utf-8",
            )
            return runner.execute_run(
                plan_path=str(typed_plan),
                confirm_id="valid-confirm",
                data_dir=data_dir,
            )
        return runner.execute_run(
            plan_path=missing_plan,
            confirm_id=import_id,
            data_dir=data_dir,
            source_root=r"\\unreachable.invalid\photos",
        )
    if surface == "status":
        return review.query_review_status(import_id=import_id, data_dir=data_dir)
    if surface == "review_rollback":
        return review.execute_review_rollback(import_id=import_id, data_dir=data_dir)
    if surface == "runner_rollback":
        return runner.execute_rollback(import_id=import_id, data_dir=data_dir)
    raise AssertionError(f"unknown R1a surface: {surface}")


def _r1a_assert_invalid(result: dict[str, Any], reason: str, hostile: Any) -> None:
    assert result == {
        "success": False,
        "data": None,
        "error": {
            "code": "IMPORT_ID_INVALID",
            "message": "Import id is invalid.",
            "details": {"reason": reason},
            "retryable": False,
        },
    }
    if isinstance(hostile, str) and hostile:
        assert hostile not in json.dumps(result, ensure_ascii=False)


def _r1a_assert_no_data_or_outside_writes(data_dir: Path, tmp_path: Path) -> None:
    from tools.lib.file_lock import FileLock

    lock_path = data_dir / ".life-index" / "import-jobs" / "ledger.lock"
    allowed_dirs = {
        data_dir / ".life-index",
        data_dir / ".life-index" / "import-jobs",
    }
    found_dirs = {path for path in data_dir.rglob("*") if path.is_dir()}
    found_files = {path for path in data_dir.rglob("*") if path.is_file()}
    assert found_dirs <= allowed_dirs
    assert found_files <= {lock_path}
    assert not list(tmp_path.rglob("review.lock"))
    assert not list(tmp_path.rglob("ledger.json"))
    assert not list(tmp_path.rglob("rollback-manifest.json"))
    assert not list(tmp_path.rglob("review-plan.json"))
    assert not (tmp_path / "outside-preview.bin").exists()
    assert not (tmp_path / "outside-preview.json").exists()
    if lock_path.exists():
        with FileLock(lock_path, timeout=0.2):
            pass


@pytest.mark.parametrize(
    ("hostile", "reason"),
    _R1A_CORE_INVALID_CASES,
    ids=("type", "empty", "non-ascii", "reserved", "child-parent-length", "child-seq", "length"),
)
@pytest.mark.parametrize("surface", _R1A_ALL_SURFACES)
def test_r1a_all_import_id_surfaces_reject_core_invalid_ids_before_access(
    tmp_path: Path,
    surface: str,
    hostile: Any,
    reason: str,
) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()

    result = _r1a_invoke_surface(surface, hostile, data_dir, tmp_path)

    _r1a_assert_invalid(result, reason, hostile)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


@pytest.mark.parametrize("surface", _R1A_PARENT_ONLY_SURFACES)
def test_r1a_parent_only_surfaces_reject_canonical_child_before_access(
    tmp_path: Path, surface: str
) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    child_id = "valid-parent#batch-1"

    result = _r1a_invoke_surface(surface, child_id, data_dir, tmp_path)

    _r1a_assert_invalid(result, "child_syntax", child_id)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


def test_r1a_traversal_cli_fails_before_outside_review_lock_write(tmp_path: Path) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    hostile = "../../../outside-authority"

    result = _err(
        _run_import(data_dir, "review", "--import-id", hostile, "--json")
    )

    assert result["success"] is False
    assert result["data"] is None
    assert result["error"] == {
        "code": "IMPORT_ID_INVALID",
        "message": "Import id is invalid.",
        "details": {"reason": "syntax"},
        "retryable": False,
    }
    assert hostile not in json.dumps(result, ensure_ascii=False)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


@pytest.mark.parametrize(
    "hostile",
    (
        r"C:\outside-authority",
        r"C:outside-authority",
        r"\\unreachable.invalid\outside-authority",
    ),
    ids=("windows-absolute", "drive-relative", "unc"),
)
def test_r1a_windows_path_forms_are_rejected_before_filesystem_helper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hostile: str,
) -> None:
    from tools.ingest import review

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()

    def forbidden_parent_lock(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("hostile import id reached a per-parent filesystem helper")

    monkeypatch.setattr(review, "FileLock", forbidden_parent_lock)
    result = review.review_queue(parent_id=hostile, data_dir=data_dir)

    _r1a_assert_invalid(result, "syntax", hostile)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


def _r1a_write_plan(tmp_path: Path, import_id: Any, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        json.dumps({"import_id": import_id, "proposals": []}),
        encoding="utf-8",
    )
    return path


def test_r1a_confirm_validates_plan_import_id_without_override(tmp_path: Path) -> None:
    from tools.ingest import review

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    hostile = "../../../outside-authority"
    plan_path = _r1a_write_plan(tmp_path, hostile, "confirm-plan.json")

    result = review.confirm_review(plan_path=str(plan_path), data_dir=data_dir)

    _r1a_assert_invalid(result, "syntax", hostile)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


def test_r1a_confirm_valid_override_does_not_bypass_invalid_plan_id(tmp_path: Path) -> None:
    from tools.ingest import review

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    hostile = "../../../outside-authority"
    plan_path = _r1a_write_plan(tmp_path, hostile, "confirm-override-plan.json")

    result = review.confirm_review(
        plan_path=str(plan_path),
        data_dir=data_dir,
        parent_id_override="valid-override",
    )

    _r1a_assert_invalid(result, "syntax", hostile)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


def test_r1a_stage_validates_plan_import_id_without_override(tmp_path: Path) -> None:
    from tools.ingest import review

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    hostile = "../../../outside-authority"
    plan_path = _r1a_write_plan(tmp_path, hostile, "stage-plan.json")

    result = review.stage_review(
        plan_path=str(plan_path),
        data_dir=data_dir,
        source_root=r"\\unreachable.invalid\photos",
    )

    _r1a_assert_invalid(result, "syntax", hostile)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


def test_r1a_stage_valid_override_does_not_bypass_invalid_plan_id(tmp_path: Path) -> None:
    from tools.ingest import review

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    hostile = "../../../outside-authority"
    plan_path = _r1a_write_plan(tmp_path, hostile, "stage-override-plan.json")

    result = review.stage_review(
        plan_path=str(plan_path),
        data_dir=data_dir,
        source_root=r"\\unreachable.invalid\photos",
        parent_id_override="valid-override",
    )

    _r1a_assert_invalid(result, "syntax", hostile)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


def test_r1a_runner_validates_plan_import_id_before_schema_or_state(
    tmp_path: Path,
) -> None:
    from tools.ingest import runner

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    hostile = "../../../outside-authority"
    plan_path = _r1a_write_plan(tmp_path, hostile, "runner-plan.json")

    result = runner.execute_run(
        plan_path=str(plan_path),
        confirm_id="valid-confirm",
        data_dir=data_dir,
    )

    _r1a_assert_invalid(result, "syntax", hostile)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


def test_r1a_runner_preserves_missing_confirm_and_valid_mismatch_errors(
    tmp_path: Path,
) -> None:
    from tools.ingest import runner

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    plan_path = _r1a_write_plan(tmp_path, "valid-plan", "runner-confirm-plan.json")

    missing = runner.execute_run(
        plan_path=str(plan_path),
        confirm_id=None,
        data_dir=data_dir,
    )
    mismatch = runner.execute_run(
        plan_path=str(plan_path),
        confirm_id="valid-other",
        data_dir=data_dir,
    )

    assert missing["error"]["code"] == "IMPORT_CONFIRMATION_REQUIRED"
    assert missing["error"]["message"] == "The --confirm flag is required for import run."
    assert mismatch["error"]["code"] == "IMPORT_CONFIRMATION_REQUIRED"
    assert "does not match" in mismatch["error"]["message"]
    assert not (data_dir / ".life-index" / "import-jobs" / "ledger.json").exists()


@pytest.mark.parametrize("surface", _R1A_PARENT_OR_CHILD_SURFACES)
def test_r1a_parent_or_child_surfaces_accept_canonical_child_syntax(
    tmp_path: Path, surface: str
) -> None:
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()

    result = _r1a_invoke_surface(
        surface,
        "valid-parent#batch-999999999",
        data_dir,
        tmp_path,
    )

    assert result["success"] is False
    assert result["error"]["code"] == "IMPORT_JOB_NOT_FOUND"


@pytest.mark.parametrize(
    ("hostile", "reason"),
    (
        ("CON#batch-0", "reserved_name"),
        ("é#batch-0", "non_ascii"),
        ("a" * 129 + "#batch-0", "child_parent_length"),
        ("a" * 120 + "#batch-1000000000", "child_sequence"),
        ("valid-parent#not-batch-1", "child_syntax"),
        ("valid-parent#batch-01", "child_sequence"),
    ),
    ids=(
        "reserved-before-child",
        "non-ascii-before-child",
        "parent-length-before-sequence",
        "sequence-before-total-length",
        "malformed-child",
        "leading-zero",
    ),
)
def test_r1a_reason_precedence_is_closed_and_deterministic(
    tmp_path: Path,
    hostile: str,
    reason: str,
) -> None:
    from tools.ingest import review

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()

    result = review.query_review_status(import_id=hostile, data_dir=data_dir)

    _r1a_assert_invalid(result, reason, hostile)
    _r1a_assert_no_data_or_outside_writes(data_dir, tmp_path)


def test_r1a_valid_differing_confirm_override_remains_effective_parent(
    tmp_path: Path,
) -> None:
    from tools.ingest import review

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir()
    plan_path = _r1a_write_plan(tmp_path, "valid-plan", "valid-override-plan.json")

    result = review.confirm_review(
        plan_path=str(plan_path),
        data_dir=data_dir,
        parent_id_override="valid-override",
    )

    assert result["success"] is True
    assert result["data"]["parent_id"] == "valid-override"
    ledger = _ledger(data_dir)
    assert "valid-override" in ledger["jobs"]
    assert "valid-plan" not in ledger["jobs"]


# ===================================================================
# Slice R1b: resolved path containment for import-job derived paths.
#
# A planted reparse link (a Windows junction via ``cmd /c mklink /J``, or a
# POSIX symlink) at a derived job path must fail CLOSED: deterministic error,
# no outside file creation/read/delete, no child reservation or partial import,
# source bytes unchanged, and no hostile locator or traceback in the output.
# All escape targets stay inside the pytest ``tmp_path`` sandbox. Each link is
# removed (via its real target, then the link itself) before teardown so the
# sandbox cleanup never traverses a link.
# ===================================================================


def _make_dir_link(link: Path, target: Path) -> None:
    """Create a directory reparse link: junction on Windows, symlink on POSIX."""
    import shutil

    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_dir() and not link.is_symlink():
        link.rmdir()
    if os.name == "nt":
        # mklink output is GBK on this locale; capture bytes, never decode strictly.
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True
        )
    else:
        os.symlink(target, link, target_is_directory=True)
    assert link.is_dir(), f"failed to create reparse link at {link}"
    assert link.resolve() == target.resolve(), f"link {link} did not resolve to {target}"


def _remove_dir_link(link: Path, target: Path) -> None:
    """Remove a reparse link without traversing into its target.

    The target is cleared through its REAL path first (we own it; it lives in the
    sandbox), leaving the link empty, so removing the link never descends into
    the target. This stays safe whether or not the operation wrote through it.
    """
    import shutil

    try:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            target.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    try:
        if os.name == "nt":
            os.rmdir(link)  # junction: removes the link, not the target
        else:
            link.unlink()
    except OSError:
        pass


def _assert_clean_failure(raw, outside: Path) -> dict[str, Any]:
    """A containment failure must be deterministic and leak nothing hostile."""
    assert raw.returncode != 0, f"expected failure, stdout: {raw.stdout}"
    payload = _payload(raw)
    assert payload["success"] is False
    assert "Traceback" not in raw.stderr, raw.stderr
    assert "Traceback" not in raw.stdout, raw.stdout
    hostile = str(outside.resolve())
    assert hostile not in raw.stdout, raw.stdout
    assert hostile not in raw.stderr, raw.stderr
    return payload


def test_r1b_child_batch_junction_escape_is_contained(tmp_path: Path) -> None:
    """Case 1: a junction at the minted child job dir must fail the batch run."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    child_id = f"{parent_id}#batch-1"
    jobs_dir = data_dir / ".life-index" / "import-jobs"
    outside = tmp_path / "escape-child"
    link = jobs_dir / child_id
    _make_dir_link(link, outside)

    source_file = src / "shot.jpg"
    source_before = source_file.read_bytes()
    try:
        raw = _run_batch(data_dir, parent_id, src)
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_WRITE_FAILURE"
        assert payload["error"]["details"]["reason"] == "job_path_not_confined"
        # No outside file created/read/deleted; no child reservation; source intact.
        assert list(outside.iterdir()) == []
        assert _ledger(data_dir)["jobs"][parent_id].get("active_child_id") is None
        assert source_file.read_bytes() == source_before
    finally:
        _remove_dir_link(link, outside)


def test_r1b_confirm_parent_junction_escape_is_contained(tmp_path: Path) -> None:
    """Case 2a: a junction at the parent job path must fail confirm before any write."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(1, 2, 3))

    plan = _photo_plan(data_dir, src)
    parent_id = plan["data"]["import_id"]
    jobs_dir = data_dir / ".life-index" / "import-jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "escape-parent"
    link = jobs_dir / parent_id
    _make_dir_link(link, outside)

    plan_file = _plan_file(tmp_path, plan["data"], name="r1b_parent.json")
    try:
        raw = _run_import(
            data_dir, "confirm", "--plan", str(plan_file),
            "--source-root", str(src), "--json",
        )
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_WRITE_FAILURE"
        assert payload["error"]["details"]["reason"] == "review_path_not_confined"
        # Neither the per-parent lock nor the review plan was written outside.
        assert not (outside / "review.lock").exists()
        assert not (outside / "review-plan.json").exists()
        assert list(outside.iterdir()) == []
    finally:
        _remove_dir_link(link, outside)


def test_r1b_legacy_run_junction_escape_is_contained(tmp_path: Path) -> None:
    """Case 2b: a junction at the legacy run job path must fail ``import run --plan``."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(9, 8, 7))

    plan = _photo_plan(data_dir, src)
    import_id = plan["data"]["import_id"]
    jobs_dir = data_dir / ".life-index" / "import-jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "escape-legacy"
    link = jobs_dir / import_id
    _make_dir_link(link, outside)

    plan_file = _plan_file(tmp_path, plan["data"], name="r1b_legacy.json")
    try:
        raw = _run_import(
            data_dir, "run", "--plan", str(plan_file), "--confirm", import_id,
            "--source-root", str(src), "--json",
        )
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_WRITE_FAILURE"
        assert payload["error"]["details"]["reason"] == "job_path_not_confined"
        assert not (outside / "rollback-manifest.json").exists()
        assert list(outside.iterdir()) == []
    finally:
        _remove_dir_link(link, outside)


def test_r1b_import_jobs_area_link_is_contained(tmp_path: Path) -> None:
    """Case 4: a link at the import-jobs area itself must fail before any ledger I/O."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(2, 4, 6))

    plan = _photo_plan(data_dir, src)
    (data_dir / ".life-index").mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "escape-area"
    area = data_dir / ".life-index" / "import-jobs"
    _make_dir_link(area, outside)

    plan_file = _plan_file(tmp_path, plan["data"], name="r1b_area.json")
    try:
        raw = _run_import(
            data_dir, "confirm", "--plan", str(plan_file),
            "--source-root", str(src), "--json",
        )
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_LEDGER_CORRUPT"
        assert payload["error"]["details"]["reason"] == "import_jobs_area_not_confined"
        # No ledger or lock file was created through the area link.
        assert list(outside.iterdir()) == []
    finally:
        _remove_dir_link(area, outside)


def _committed_child_batch(
    data_dir: Path, src: Path
) -> tuple[str, str, str]:
    """Plan + confirm + run one photo; return (parent_id, child_id, attachment_rel)."""
    proposal, parent_id, att = _confirmed_one_photo_batch(data_dir, src)
    run = _ok(_run_batch(data_dir, parent_id, src))["data"]
    return parent_id, run["import_id"], att["target_rel_path"]


def test_r1b_rollback_corrupt_locator_is_contained(tmp_path: Path) -> None:
    """Case 3: a corrupt absolute/traversal rollback locator must fail closed."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _parent_id, child_id, att_rel = _committed_child_batch(data_dir, src)

    outside = tmp_path / "escape-locator"
    outside.mkdir()
    corrupt_target = outside / "audit-manifest.json"

    ledger_path = data_dir / ".life-index" / "import-jobs" / "ledger.json"
    ld = json.loads(ledger_path.read_text("utf-8"))
    ld["jobs"][child_id]["rollback_manifest_rel_path"] = str(corrupt_target)
    ledger_path.write_text(json.dumps(ld), encoding="utf-8")

    published = data_dir / att_rel
    assert published.exists()
    try:
        raw = _run_import(data_dir, "rollback", "--import-id", child_id, "--json")
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_ROLLBACK_UNSAFE"
        assert payload["error"]["details"]["reason"] == "rollback_manifest_path_not_confined"
        # No audit manifest written outside; the committed attachment was not deleted.
        assert not corrupt_target.exists()
        assert list(outside.iterdir()) == []
        assert published.exists()
    finally:
        # No link here, but keep symmetry; nothing to remove.
        pass


def test_r1b_rollback_outside_target_not_deleted(tmp_path: Path) -> None:
    """Case 5: a manifest entry pointing outside must not be deleted or truncated."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _parent_id, child_id, _att_rel = _committed_child_batch(data_dir, src)

    outside = tmp_path / "escape-destructive"
    outside.mkdir()
    victim = outside / "victim.txt"
    victim.write_text("VICTIM-CONTENT")

    manifest_path = data_dir / ".life-index" / "import-jobs" / child_id / "rollback-manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["created_files"].append(
        {
            "rel_path": str(victim),
            "sha256_after": "sha256:deadbeef",
            "size_bytes": len("VICTIM-CONTENT"),
            "created_by_import": True,
            "kind": "journal",
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    try:
        raw = _run_import(data_dir, "rollback", "--import-id", child_id, "--json")
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_ROLLBACK_UNSAFE"
        # The outside target was neither deleted nor truncated.
        assert victim.exists()
        assert victim.read_text() == "VICTIM-CONTENT"
    finally:
        pass


def test_r1b_staging_subpath_junction_is_contained(tmp_path: Path) -> None:
    """Vuln-map staging site: a junction at ``<child>/publication-staging`` is contained."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    child_id = f"{parent_id}#batch-1"
    jobs_dir = data_dir / ".life-index" / "import-jobs"
    (jobs_dir / child_id).mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "escape-staging"
    link = jobs_dir / child_id / "publication-staging"
    _make_dir_link(link, outside)

    source_file = src / "shot.jpg"
    source_before = source_file.read_bytes()
    try:
        raw = _run_batch(data_dir, parent_id, src)
        # The batch must fail (staging path not confined); no staging bytes outside.
        assert raw.returncode != 0
        assert "Traceback" not in raw.stderr
        assert list(outside.iterdir()) == []
        assert source_file.read_bytes() == source_before
    finally:
        _remove_dir_link(link, outside)


def test_r1b_safe_import_through_linked_data_dir(tmp_path: Path) -> None:
    """False-rejection guard: a data dir reached through a link must keep working.

    Both ``data_dir`` and the derived job area are resolved, so a data dir whose
    own path contains a link component is a legitimate, contained root.
    """
    real_data = tmp_path / "real-data"
    real_data.mkdir(parents=True)
    data_dir = tmp_path / "linked-data"
    _make_dir_link(data_dir, real_data)

    src = tmp_path / "photos"
    try:
        proposal, parent_id, att = _confirmed_one_photo_batch(data_dir, src)
        run = _ok(_run_batch(data_dir, parent_id, src))["data"]
        assert run["state"] == "committed"
        assert run["kind"] == "batch"
        # The committed artifact lands under the REAL data dir (resolved root).
        assert (real_data / att["target_rel_path"]).exists()
        assert (real_data / att["target_rel_path"]).read_bytes() == (src / "shot.jpg").read_bytes()
    finally:
        # data_dir is itself a link; clear real contents then remove the link.
        _remove_dir_link(data_dir, real_data)


def test_r1b_normal_import_and_rollback_still_work(tmp_path: Path) -> None:
    """Case 7: ordinary contained import and rollback are unchanged by R1b."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _proposal, parent_id, att = _confirmed_one_photo_batch(data_dir, src)

    run = _ok(_run_batch(data_dir, parent_id, src))["data"]
    child_id = run["import_id"]
    assert run["state"] == "committed"
    published = data_dir / att["target_rel_path"]
    assert published.exists()

    rollback = _ok(_run_import(data_dir, "rollback", "--import-id", child_id, "--json"))["data"]
    assert rollback["state"] == "rolled_back"
    assert rollback["deleted_count"] >= 1
    # The imported artifact was removed by the contained rollback.
    assert not published.exists()


def test_r1b_rollback_corrupt_stored_parent_id_is_contained(tmp_path: Path) -> None:
    """R1: a corrupt absolute stored ``parent_review_job_id`` must fail the child
    rollback before the per-parent lock is constructed through it.

    ``parent_review_job_id`` is a STORED ledger field (not the request id), so it
    is lexically validated and confinement-proven before the per-parent lock:
    without the guard the absolute component would reset the pathlib join and the
    lock file would be created outside the data dir.
    """
    import shutil

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _parent_id, child_id, _att_rel = _committed_child_batch(data_dir, src)

    outside = tmp_path / "escape-stored-parent"
    outside.mkdir()
    ledger_path = data_dir / ".life-index" / "import-jobs" / "ledger.json"
    ld = json.loads(ledger_path.read_text("utf-8"))
    ld["jobs"][child_id]["parent_review_job_id"] = str(outside)
    ledger_path.write_text(json.dumps(ld), encoding="utf-8")

    try:
        raw = _run_import(data_dir, "rollback", "--import-id", child_id, "--json")
        payload = _assert_clean_failure(raw, outside)
        # The stored locator is lexically invalid (absolute path) -> IMPORT_ID_INVALID.
        assert payload["error"]["code"] == "IMPORT_ID_INVALID"
        # No outside directory/file was created through the corrupt locator.
        assert list(outside.iterdir()) == []
    finally:
        pass


def test_r1b_review_junctioned_job_dir_is_contained(tmp_path: Path) -> None:
    """R2: a junction at a valid-but-nonexistent parent job dir must fail
    ``import review`` before the ledger read, with no outside review.lock."""
    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _make_jpeg(src / "shot.jpg", color=(5, 6, 7))

    plan = _photo_plan(data_dir, src)
    parent_id = plan["data"]["import_id"]  # valid format, never confirmed -> no job
    jobs_dir = data_dir / ".life-index" / "import-jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "escape-review"
    link = jobs_dir / parent_id
    _make_dir_link(link, outside)

    try:
        raw = _run_import(data_dir, "review", "--import-id", parent_id, "--json")
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_WRITE_FAILURE"
        assert payload["error"]["details"]["reason"] == "review_path_not_confined"
        # The per-parent lock was never created through the junction.
        assert not (outside / "review.lock").exists()
        assert list(outside.iterdir()) == []
    finally:
        _remove_dir_link(link, outside)


def test_r1b_run_batch_junctioned_parent_dir_is_contained(tmp_path: Path) -> None:
    """R2: a junction at the parent job dir before ``run`` must fail before the
    per-parent lock, with no outside lock, no child reservation, source intact."""
    import shutil

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    jobs_dir = data_dir / ".life-index" / "import-jobs"
    outside = tmp_path / "escape-run-parent"
    link = jobs_dir / parent_id
    # The parent job dir already exists from confirm; replace it with a junction.
    shutil.rmtree(link, ignore_errors=True)
    _make_dir_link(link, outside)

    source_file = src / "shot.jpg"
    source_before = source_file.read_bytes()
    try:
        raw = _run_batch(data_dir, parent_id, src)
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_WRITE_FAILURE"
        assert payload["error"]["details"]["reason"] == "review_path_not_confined"
        # No outside lock; no child batch reservation; source bytes unchanged.
        assert not (outside / "review.lock").exists()
        assert list(outside.iterdir()) == []
        assert _ledger(data_dir)["jobs"][parent_id].get("active_child_id") is None
        assert source_file.read_bytes() == source_before
    finally:
        _remove_dir_link(link, outside)


def test_r1b_status_after_junction_replace_fails_closed(tmp_path: Path) -> None:
    """R3 regression: after confirm, replacing the parent job dir with a junction
    must make ``status`` fail closed with ledger bytes/SHA, jobs, proposal_states,
    and any pending intent unchanged (no destructive jobs.pop / intent abort)."""
    import shutil

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    _proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    jobs_dir = data_dir / ".life-index" / "import-jobs"
    ledger_path = jobs_dir / "ledger.json"
    before_bytes = ledger_path.read_bytes()
    before_sha = hashlib.sha256(before_bytes).hexdigest()
    before_ledger = json.loads(before_bytes)
    before_states = before_ledger["jobs"][parent_id].get("proposal_states")
    before_intent = before_ledger["jobs"][parent_id].get("pending_review_update")

    outside = tmp_path / "escape-status"
    link = jobs_dir / parent_id
    shutil.rmtree(link, ignore_errors=True)
    _make_dir_link(link, outside)

    try:
        raw = _run_import(data_dir, "status", "--import-id", parent_id, "--json")
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_LEDGER_CORRUPT"
        assert payload["error"]["details"]["reason"] == "review_plan_path_not_confined"
        # No outside lock/plan written.
        assert not (outside / "review.lock").exists()
        assert list(outside.iterdir()) == []
        # Ledger bytes + SHA unchanged; parent job still present; states + intent
        # unchanged (containment failure must never mutate the in-root ledger).
        after_bytes = ledger_path.read_bytes()
        assert after_bytes == before_bytes
        assert hashlib.sha256(after_bytes).hexdigest() == before_sha
        after_ledger = json.loads(after_bytes)
        assert parent_id in after_ledger["jobs"]
        assert after_ledger["jobs"][parent_id].get("proposal_states") == before_states
        assert (
            after_ledger["jobs"][parent_id].get("pending_review_update") == before_intent
        )
    finally:
        _remove_dir_link(link, outside)


def test_r1b_edit_junctioned_parent_dir_is_contained(tmp_path: Path) -> None:
    """R2: a junction at the parent job dir before a single-proposal edit must
    fail before the per-parent lock, with no partial intent persisted."""
    import shutil

    data_dir = tmp_path / "Life-Index"
    data_dir.mkdir(parents=True)
    src = tmp_path / "photos"
    proposal, parent_id, _att = _confirmed_one_photo_batch(data_dir, src)

    # Structurally valid edit payload; the containment guard fires before the
    # lock, so the proposal is never acted upon.
    edit_payload = {
        "schema_version": "import_review_edit.v1",
        "proposal_id": proposal["proposal_id"],
        "decision": "confirmed",
    }
    edit_file = _plan_file(tmp_path, edit_payload, name="r1b_edit.json")

    jobs_dir = data_dir / ".life-index" / "import-jobs"
    ledger_path = jobs_dir / "ledger.json"
    before_bytes = ledger_path.read_bytes()
    outside = tmp_path / "escape-edit"
    link = jobs_dir / parent_id
    shutil.rmtree(link, ignore_errors=True)
    _make_dir_link(link, outside)

    try:
        raw = _run_import(
            data_dir,
            "confirm",
            "--edit",
            str(edit_file),
            "--import-id",
            parent_id,
            "--expected-queue-revision",
            "1",
            "--json",
        )
        payload = _assert_clean_failure(raw, outside)
        assert payload["error"]["code"] == "IMPORT_WRITE_FAILURE"
        assert payload["error"]["details"]["reason"] == "review_path_not_confined"
        # No outside lock; no partial intent persisted (ledger bytes unchanged).
        assert not (outside / "review.lock").exists()
        assert list(outside.iterdir()) == []
        assert ledger_path.read_bytes() == before_bytes
    finally:
        _remove_dir_link(link, outside)

