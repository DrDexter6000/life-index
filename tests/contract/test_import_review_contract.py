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
    child_id = f"{parent_id}#batch-seeded"
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
    # no staging leftovers inside the data dir
    staging = list((data_dir).rglob("*.staging-*"))
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
