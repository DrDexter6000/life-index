"""Regression tests for create-only journal publication."""

import builtins
import json
import os
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

from tools.ingest.review import _publish_text_create_only
from tools.write_journal import core as write_core

REPO_ROOT = Path(__file__).resolve().parents[2]
DATE = "2026-03-14"
MONTH_DIR = Path("Journals/2026/03")
ALLOCATED_REL = MONTH_DIR / "life-index_2026-03-14_001.md"
TARGET_REL = MONTH_DIR / "life-index_2026-03-13_001.md"


def _payload(*attachments: Path) -> dict[str, Any]:
    return {
        "date": DATE,
        "title": "No overwrite journal",
        "content": "The new journal must survive a publish collision.",
        "topic": ["work"],
        "project": "Safety",
        "tags": ["no-overwrite"],
        "abstract": "Create-only publication",
        "location": "Test City",
        "weather": "Sunny",
        "related_entries": [TARGET_REL.as_posix()],
        "attachments": [{"source_path": str(path)} for path in attachments],
    }


def _seed_related_target(data_dir: Path) -> None:
    target = data_dir / TARGET_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        'title: "Earlier entry"\n'
        "date: 2026-03-13\n"
        'topic: ["work"]\n'
        "---\n\n"
        "Earlier body.\n",
        encoding="utf-8",
    )


def _install_racing_allocator(
    monkeypatch: pytest.MonkeyPatch,
    publisher: Callable[[Path], None],
) -> tuple[dict[str, bytes], dict[str, Path]]:
    original = write_core._generate_journal_path
    racing: dict[str, bytes] = {}
    captured: dict[str, Path] = {}

    def racing_allocator(date_str: str, timer: Any):
        journal_path, month_dir, year, month = original(date_str, timer)
        publisher(journal_path)
        racing["bytes"] = journal_path.read_bytes()
        return journal_path, month_dir, year, month

    def capture_candidates(**kwargs: Any) -> dict[str, Any]:
        captured["entity_path"] = kwargs["journal_path"]
        return {}

    monkeypatch.setattr(write_core, "_generate_journal_path", racing_allocator)
    monkeypatch.setattr(
        write_core,
        "suggest_related_entries",
        lambda *_args: [
            {
                "candidate_id": 1,
                "rel_path": TARGET_REL.as_posix(),
                "title": "Earlier entry",
                "date": "2026-03-13",
            }
        ],
    )
    monkeypatch.setattr(write_core, "capture_write_time_candidates", capture_candidates)
    return racing, captured


def _side_effect(result: dict[str, Any], name: str) -> dict[str, Any]:
    return next(record for record in result["side_effects"] if record["name"] == name)


def _normalized(path: Path) -> str:
    return str(path).replace("\\", "/")


def _assert_collision_result(
    data_dir: Path,
    result: dict[str, Any],
    racing: dict[str, bytes],
    captured: dict[str, Path],
) -> None:
    allocated = data_dir / ALLOCATED_REL
    actual = Path(result["journal_path"])
    actual_rel = actual.relative_to(data_dir).as_posix()
    allocated_rel = ALLOCATED_REL.as_posix()

    assert result["success"] is True
    assert actual.name == "life-index_2026-03-14_002.md"
    assert allocated.read_bytes() == racing["bytes"]
    assert actual.is_file()
    assert result["confirmation"]["journal_path"] == str(actual)
    assert str(actual) in result["confirmation_message"]
    assert str(allocated) not in result["confirmation_message"]
    assert captured["entity_path"] == actual

    snapshot_path = data_dir / ".index" / "confirmation_candidates.json"
    snapshots = json.loads(snapshot_path.read_text(encoding="utf-8"))["snapshots"]
    assert str(actual.resolve()) in snapshots
    assert str(allocated.resolve()) not in snapshots

    with sqlite3.connect(data_dir / ".index" / "journals_fts.db") as conn:
        fts_paths = {row[0] for row in conn.execute("SELECT path FROM journals")}
    assert actual_rel in fts_paths
    assert allocated_rel not in fts_paths

    with sqlite3.connect(data_dir / ".cache" / "metadata_cache.db") as conn:
        cache_paths = {row[0] for row in conn.execute("SELECT file_path FROM metadata_cache")}
        relation_sources = {
            row[0] for row in conn.execute("SELECT source_path FROM entry_relations")
        }
    assert _normalized(actual) in cache_paths
    assert _normalized(allocated) not in cache_paths
    assert actual_rel in relation_sources
    assert allocated_rel not in relation_sources

    by_topic = "\n".join(
        path.read_text(encoding="utf-8") for path in (data_dir / "by-topic").rglob("*.md")
    )
    assert actual_rel in by_topic
    assert allocated_rel not in by_topic


def test_allocated_path_collision_preserves_file_and_uses_committed_path_everywhere(
    isolated_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_related_target(isolated_data_dir)

    def publish_decoy(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"racing writer bytes\n")

    racing, captured = _install_racing_allocator(monkeypatch, publish_decoy)
    result = write_core.write_journal(_payload())

    _assert_collision_result(isolated_data_dir, result, racing, captured)


def test_real_import_publisher_collision_preserves_imported_bytes(
    isolated_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_related_target(isolated_data_dir)

    def publish_import(path: Path) -> None:
        published, detail = _publish_text_create_only(path, "imported journal bytes\n")
        assert published is True, detail

    racing, captured = _install_racing_allocator(monkeypatch, publish_import)
    result = write_core.write_journal(_payload())

    _assert_collision_result(isolated_data_dir, result, racing, captured)


def test_collision_postcommit_exception_fallback_uses_created_path(
    isolated_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_related_target(isolated_data_dir)

    def publish_decoy(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"racing writer bytes\n")

    racing, _captured = _install_racing_allocator(monkeypatch, publish_decoy)
    monkeypatch.setattr(
        write_core,
        "_update_postcommit_derived_projections",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("post-commit projection failed")),
    )
    result = write_core.write_journal(_payload())

    actual = Path(result["journal_path"])
    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    assert actual.name == "life-index_2026-03-14_002.md"
    assert (isolated_data_dir / ALLOCATED_REL).read_bytes() == racing["bytes"]
    assert result["confirmation"]["journal_path"] == str(actual)
    assert str(actual) in result["confirmation_message"]


def test_collision_exhaustion_preserves_files_and_compensates_attachment(
    isolated_data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "evidence.txt"
    source.write_bytes(b"attachment bytes")
    real_link = os.link

    def collide_every_journal(source_path: Path, target_path: Path) -> None:
        if Path(target_path).suffix == ".md":
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(f"existing {target.name}\n".encode("utf-8"))
            raise FileExistsError(str(target))
        real_link(source_path, target_path)

    monkeypatch.setattr(write_core.os, "link", collide_every_journal)
    result = write_core.write_journal(_payload(source))

    month_dir = isolated_data_dir / MONTH_DIR
    existing = sorted(month_dir.glob("life-index_2026-03-14_*.md"))
    assert result["success"] is False
    assert result["error"]["code"] == "E0207"
    assert _side_effect(result, "journal_commit")["status"] == "failed"
    assert len(existing) == 8
    for path in existing:
        assert path.read_bytes() == f"existing {path.name}\n".encode("utf-8")
    assert not (month_dir / "life-index_2026-03-14_009.md").exists()
    assert list(month_dir.glob(".write-*.tmp")) == []
    attachments_root = isolated_data_dir / "attachments"
    assert not any(path.is_file() for path in attachments_root.rglob("*"))


def test_hard_link_refusal_is_clear_and_compensates_attachment(
    isolated_data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "evidence.txt"
    source.write_bytes(b"attachment bytes")
    real_link = os.link

    def refuse_journal_link(source_path: Path, target_path: Path) -> None:
        if Path(target_path).suffix == ".md":
            raise OSError(1, "hard links refused")
        real_link(source_path, target_path)

    monkeypatch.setattr(write_core.os, "link", refuse_journal_link)
    result = write_core.write_journal(_payload(source))

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    message = result["error"]["message"]
    assert "refused a hard link" in message
    assert "write needs a hard link to publish without overwriting" in message
    assert "no journal was committed" in message
    assert "nothing was written" not in message
    assert result["error"]["recovery_strategy"] == "fail"
    assert result["error"]["details"]["os_error"] == "[Errno 1] hard links refused"
    assert _side_effect(result, "journal_commit")["status"] == "failed"
    assert _side_effect(result, "attachments")["status"] == "compensated"
    assert list((isolated_data_dir / MONTH_DIR).glob("life-index_*.md")) == []
    assert list((isolated_data_dir / MONTH_DIR).glob(".write-*.tmp")) == []
    assert not any(path.is_file() for path in (isolated_data_dir / "attachments").rglob("*"))


def test_temp_cleanup_failure_after_link_is_nonblocking(
    isolated_data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "evidence.txt"
    source.write_bytes(b"attachment bytes")
    real_unlink = Path.unlink

    def refuse_temp_unlink(path: Path, *args: Any, **kwargs: Any) -> None:
        if path.name.startswith(".write-") and path.suffix == ".tmp":
            raise PermissionError("temporary file is held open")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", refuse_temp_unlink)
    result = write_core.write_journal(_payload(source))

    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    assert Path(result["journal_path"]).is_file()
    assert (isolated_data_dir / "attachments/2026/03/evidence.txt").is_file()
    cleanup = _side_effect(result, "journal_cleanup")
    assert cleanup["status"] == "failed"
    assert cleanup["blocking"] is False
    assert "temporary file is held open" in cleanup["error"]
    assert len(list(Path(result["journal_path"]).parent.glob(".write-*.tmp"))) == 1


@pytest.mark.parametrize("failure", ["write", "fsync"])
def test_temp_write_or_fsync_failure_leaves_no_temp(
    isolated_data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    if failure == "write":
        real_open = builtins.open

        def fail_temp_open(file: Any, *args: Any, **kwargs: Any):
            if isinstance(file, (str, Path)) and Path(file).name.startswith(".write-"):
                raise OSError("synthetic temp write failure")
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", fail_temp_open)
        expected_error = "synthetic temp write failure"
    else:
        monkeypatch.setattr(
            write_core.os,
            "fsync",
            lambda _fd: (_ for _ in ()).throw(OSError("synthetic fsync failure")),
        )
        expected_error = "synthetic fsync failure"

    result = write_core.write_journal(_payload())

    assert result["success"] is False
    assert expected_error in result["error"]
    assert _side_effect(result, "journal_stage")["status"] == "failed"
    assert list((isolated_data_dir / MONTH_DIR).glob(".write-*.tmp")) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission modes")
@pytest.mark.parametrize("umask", [0o022, 0o077])
def test_published_file_mode_follows_process_umask(
    isolated_data_dir: Path,
    umask: int,
) -> None:
    original_umask = os.umask(0)
    os.umask(original_umask)
    try:
        os.umask(umask)
        result = write_core.write_journal(_payload())
    finally:
        os.umask(original_umask)

    assert result["success"] is True
    published_mode = stat.S_IMODE(Path(result["journal_path"]).stat().st_mode)
    assert published_mode == 0o666 & ~umask


def test_two_real_write_processes_both_succeed_with_distinct_files(
    isolated_data_dir: Path,
) -> None:
    env = os.environ.copy()
    env["LIFE_INDEX_DATA_DIR"] = str(isolated_data_dir)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONUTF8"] = "1"
    command = [
        sys.executable,
        "-m",
        "tools.write_journal",
        "--data",
        json.dumps(_payload(), ensure_ascii=False),
    ]
    processes = [
        subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        for _ in range(2)
    ]
    try:
        completed = [process.communicate(timeout=90) for process in processes]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()

    results = []
    for process, (stdout, stderr) in zip(processes, completed):
        assert process.returncode == 0, stderr
        results.append(json.loads(stdout))
    assert all(result["success"] is True for result in results)
    paths = {Path(result["journal_path"]) for result in results}
    assert len(paths) == 2
    assert {path.name for path in paths} == {
        "life-index_2026-03-14_001.md",
        "life-index_2026-03-14_002.md",
    }
    assert all(path.is_file() for path in paths)
