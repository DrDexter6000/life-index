"""Fault-injection tests for transactional journal writes."""

import builtins
import shutil
from pathlib import Path
from typing import Any

import pytest

from tools.lib.frontmatter import parse_frontmatter
from tools.write_journal import attachments as attachment_ops
from tools.write_journal import core as write_core


def _configure_sandbox(monkeypatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "Life-Index"
    journals_dir = data_dir / "Journals"
    attachments_dir = data_dir / "attachments"
    lock_path = data_dir / ".index" / "journals.lock"
    journals_dir.mkdir(parents=True)
    lock_path.parent.mkdir(parents=True)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    monkeypatch.setattr(write_core, "get_journals_dir", lambda: journals_dir)
    monkeypatch.setattr(write_core, "get_journals_lock_path", lambda: lock_path)
    monkeypatch.setattr(attachment_ops, "get_attachments_dir", lambda: attachments_dir)
    monkeypatch.setattr(write_core, "query_weather_for_location", lambda *_args: "Sunny 25C")
    return data_dir


def _payload(*source_files: Path) -> dict:
    return {
        "date": "2026-03-14",
        "title": "Synthetic journal",
        "content": "Synthetic content.",
        "topic": ["work"],
        "abstract": "Synthetic abstract.",
        "mood": [],
        "tags": [],
        "attachments": [
            {"source_path": str(source_file), "description": "Synthetic evidence"}
            for source_file in source_files
        ],
    }


def _files_under(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(str(item.relative_to(path)) for item in path.rglob("*") if item.is_file())


def test_attachment_existing_before_staging_gets_collision_safe_name(tmp_path: Path, monkeypatch):
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source = tmp_path / "same.txt"
    source.write_bytes(b"transaction bytes")
    target = data_dir / "attachments" / "2026" / "03" / "same.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"pre-existing bytes")
    staging = attachment_ops.stage_attachments([str(source)], "2026-03-14")

    attachment_ops.publish_staged_attachments(staging)

    assert target.read_bytes() == b"pre-existing bytes"
    assert (target.parent / "same_001.txt").read_bytes() == b"transaction bytes"


def test_attachment_publish_refuses_target_that_appears_after_staging(tmp_path: Path, monkeypatch):
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source = tmp_path / "same.txt"
    source.write_bytes(b"transaction bytes")
    staging = attachment_ops.stage_attachments([str(source)], "2026-03-14")
    target = data_dir / "attachments" / "2026" / "03" / "same.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"appeared after staging")

    with pytest.raises(FileExistsError):
        attachment_ops.publish_staged_attachments(staging)

    assert target.read_bytes() == b"appeared after staging"
    assert staging.published_paths == []


def test_attachment_target_appearing_after_staging_is_never_overwritten_or_removed(
    tmp_path: Path, monkeypatch
):
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source = tmp_path / "same.txt"
    source.write_bytes(b"transaction bytes")
    real_replace = Path.replace

    def inject_collision_then_fail_journal(self: Path, target: Path):
        if self.suffix == ".tmp":
            raise OSError("synthetic journal rename failure")
        return real_replace(self, target)

    real_stage = attachment_ops.stage_attachments

    def stage_then_create_collision(*args, **kwargs):
        staging = real_stage(*args, **kwargs)
        target = staging.final_dir / "same.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"appeared after staging")
        return staging

    monkeypatch.setattr(write_core, "stage_attachments", stage_then_create_collision)
    monkeypatch.setattr(Path, "replace", inject_collision_then_fail_journal)

    result = write_core.write_journal(_payload(source))
    target = data_dir / "attachments" / "2026" / "03" / "same.txt"

    assert result["success"] is False
    assert target.exists()
    assert target.read_bytes() == b"appeared after staging"
    record = next(item for item in result["side_effects"] if item["name"] == "attachments")
    assert record["status"] == "failed"


def test_url_attachment_full_transaction_publishes_and_compensates(tmp_path: Path, monkeypatch):
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    downloaded_to: list[Path] = []
    published_before_commit_failure: list[bytes] = []
    real_replace = Path.replace

    async def fake_download(url: str, target_dir: Path, date_str: str, timeout: float = 30.0):
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / "remote.txt"
        path.write_bytes(b"remote bytes")
        downloaded_to.append(path)
        return {"success": True, "path": str(path), "content_type": "text/plain", "size": 12}

    def fail_journal_rename(self: Path, target: Path):
        if self.suffix == ".tmp":
            published = data_dir / "attachments" / "2026" / "03" / "remote.txt"
            published_before_commit_failure.append(published.read_bytes())
            raise OSError("synthetic URL journal rename failure")
        return real_replace(self, target)

    monkeypatch.setattr(attachment_ops, "download_attachment_from_url", fake_download)
    monkeypatch.setattr(Path, "replace", fail_journal_rename)
    payload = _payload()
    payload["attachments"] = [{"source_url": "https://example.test/remote.txt"}]

    result = write_core.write_journal(payload)

    assert downloaded_to
    assert published_before_commit_failure == [b"remote bytes"]
    assert result["success"] is False
    assert _files_under(data_dir / "attachments") == []
    record = next(item for item in result["side_effects"] if item["name"] == "attachments")
    assert record["status"] == "compensated"


def test_compensation_skips_final_path_replaced_by_external_data(tmp_path: Path, monkeypatch):
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source = tmp_path / "same.txt"
    source.write_bytes(b"transaction bytes")
    external = tmp_path / "external.txt"
    external.write_bytes(b"external replacement")
    real_replace = Path.replace

    def replace_attachment_then_fail_journal(self: Path, target: Path):
        if self.suffix == ".tmp":
            final = data_dir / "attachments" / "2026" / "03" / "same.txt"
            external.replace(final)
            raise OSError("synthetic journal failure after external replacement")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", replace_attachment_then_fail_journal)

    result = write_core.write_journal(_payload(source))
    final = data_dir / "attachments" / "2026" / "03" / "same.txt"

    assert result["success"] is False
    assert final.read_bytes() == b"external replacement"


def test_mixed_valid_and_missing_attachments_commit_only_valid_frontmatter(
    tmp_path: Path, monkeypatch
):
    _configure_sandbox(monkeypatch, tmp_path)
    valid = tmp_path / "valid.txt"
    valid.write_bytes(b"valid bytes")
    missing = tmp_path / "missing.txt"

    result = write_core.write_journal(_payload(valid, missing))
    metadata, _body = parse_frontmatter(Path(result["journal_path"]).read_text(encoding="utf-8"))

    assert result["success"] is True
    assert result["attachments_processed_count"] == 1
    assert result["attachments_failed_count"] == 1
    assert [item["filename"] for item in metadata["attachments"]] == ["valid.txt"]
    assert all(item.get("rel_path") for item in metadata["attachments"])


def test_format_failure_with_staging_cleanup_failure_reports_leftover_path(
    tmp_path: Path, monkeypatch
):
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source = tmp_path / "evidence.txt"
    source.write_bytes(b"staged bytes")
    real_rmtree = shutil.rmtree

    def fail_when_errors_are_not_ignored(path, *args, **kwargs):
        if ".write-stage-" in str(path):
            if kwargs.get("ignore_errors"):
                return None
            raise OSError("synthetic staging-tree deletion failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(attachment_ops.shutil, "rmtree", fail_when_errors_are_not_ignored)
    monkeypatch.setattr(
        write_core,
        "format_content",
        lambda *_args: (_ for _ in ()).throw(ValueError("synthetic format failure")),
    )

    result = write_core.write_journal(_payload(source))
    leftovers = list((data_dir / "attachments").glob(".write-stage-*"))
    record = next(item for item in result["side_effects"] if item["name"] == "attachments")

    assert result["success"] is False
    assert leftovers
    assert record["status"] == "failed"
    assert str(leftovers[0]) in record["error"]
    assert str(leftovers[0]) in record["recovery_strategy"]


def test_stage_failure_with_cleanup_failure_reports_leftover_path(tmp_path: Path, monkeypatch):
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source = tmp_path / "evidence.txt"
    source.write_bytes(b"staged bytes")
    real_rmtree = shutil.rmtree

    def fail_when_errors_are_not_ignored(path, *args, **kwargs):
        if ".write-stage-" in str(path):
            if kwargs.get("ignore_errors"):
                return None
            raise OSError("synthetic staging-tree deletion failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(attachment_ops.shutil, "rmtree", fail_when_errors_are_not_ignored)
    monkeypatch.setattr(
        attachment_ops,
        "process_attachments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("synthetic stage failure")),
    )

    result = write_core.write_journal(_payload(source))
    leftovers = list((data_dir / "attachments").glob(".write-stage-*"))
    record = next(item for item in result["side_effects"] if item["name"] == "attachments")

    assert leftovers
    assert record["status"] == "failed"
    assert str(leftovers[0]) in record["error"]
    assert str(leftovers[0]) in record["recovery_strategy"]


def test_precommit_failure_leaves_no_orphan_attachment(tmp_path: Path, monkeypatch):
    """A journal temp-write failure compensates every newly copied attachment."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source_file = tmp_path / "evidence.txt"
    source_file.write_text("synthetic attachment", encoding="utf-8")
    real_open = builtins.open

    def fail_journal_temp_write(file, *args, **kwargs):
        if Path(file).suffix == ".tmp":
            raise OSError("synthetic journal temp-write failure")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fail_journal_temp_write)

    result = write_core.write_journal(_payload(source_file))

    assert result["success"] is False
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "attachments") == []
    assert _files_under(data_dir / "by-topic") == []
    journal_stage = next(
        record for record in result["side_effects"] if record["name"] == "journal_stage"
    )
    assert journal_stage["status"] == "failed"
    assert journal_stage["blocking"] is True
    assert "temp-write failure" in journal_stage["error"]


def test_partial_attachment_publish_is_compensated(tmp_path: Path, monkeypatch):
    """A publish failure after one move removes the already-published file."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    real_link = attachment_ops.os.link
    publish_count = 0

    def fail_second_attachment_publish(source: Path, target: Path):
        nonlocal publish_count
        if ".write-stage-" in str(source) and source.parent.name == "files":
            publish_count += 1
            if publish_count == 2:
                raise OSError("synthetic attachment publish failure")
        return real_link(source, target)

    monkeypatch.setattr(attachment_ops.os, "link", fail_second_attachment_publish)

    result = write_core.write_journal(_payload(first, second))

    assert result["success"] is False
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "attachments") == []
    assert (
        next(record for record in result["side_effects"] if record["name"] == "attachments")[
            "status"
        ]
        == "compensated"
    )


def test_journal_atomic_rename_failure_compensates_published_attachment(
    tmp_path: Path,
    monkeypatch,
):
    """A failed durable journal commit removes attachments published for it."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source_file = tmp_path / "evidence.txt"
    source_file.write_text("synthetic attachment", encoding="utf-8")
    real_replace = Path.replace

    def fail_journal_rename(self: Path, target: Path):
        if self.suffix == ".tmp":
            raise OSError("synthetic journal atomic-rename failure")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_journal_rename)

    result = write_core.write_journal(_payload(source_file))

    assert result["success"] is False
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "attachments") == []
    assert (
        next(record for record in result["side_effects"] if record["name"] == "attachments")[
            "status"
        ]
        == "compensated"
    )


def test_attachment_identity_read_failure_after_link_is_compensated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A linked final is transaction-owned before its identity is re-read."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source_file = tmp_path / "evidence.txt"
    source_file.write_text("synthetic attachment", encoding="utf-8")
    final_dir = data_dir / "attachments" / "2026" / "03"
    real_file_identity = attachment_ops._file_identity
    identity_read_failed = False

    def fail_first_final_identity_read(path: Path) -> tuple[int, int]:
        nonlocal identity_read_failed
        if path.parent == final_dir and not identity_read_failed:
            identity_read_failed = True
            raise OSError("synthetic final identity read failure")
        return real_file_identity(path)

    monkeypatch.setattr(attachment_ops, "_file_identity", fail_first_final_identity_read)

    result = write_core.write_journal(_payload(source_file))

    attachment_record = next(
        record for record in result["side_effects"] if record["name"] == "attachments"
    )
    assert identity_read_failed is True
    assert result["success"] is False
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "attachments") == []
    assert attachment_record["status"] == "compensated"
    assert "final identity read failure" in attachment_record["error"]


def test_temp_journal_cleanup_failure_does_not_skip_attachment_compensation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A temp unlink error is reported after bounded attachment compensation."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source_file = tmp_path / "evidence.txt"
    source_file.write_text("synthetic attachment", encoding="utf-8")
    real_replace = Path.replace
    real_unlink = Path.unlink

    def fail_journal_rename(self: Path, target: Path) -> Path:
        if self.suffix == ".tmp":
            raise OSError("synthetic journal atomic-rename failure")
        return real_replace(self, target)

    def fail_temp_journal_cleanup(self: Path, *args: Any, **kwargs: Any) -> None:
        if self.suffix == ".tmp":
            raise OSError("synthetic temp journal cleanup failure")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fail_journal_rename)
    monkeypatch.setattr(Path, "unlink", fail_temp_journal_cleanup)

    result = write_core.write_journal(_payload(source_file))

    temp_leftovers = list((data_dir / "Journals").rglob("*.tmp"))
    attachment_record = next(
        record for record in result["side_effects"] if record["name"] == "attachments"
    )
    journal_record = next(
        record for record in result["side_effects"] if record["name"] == "journal_commit"
    )
    assert result["success"] is False
    assert _files_under(data_dir / "attachments") == []
    assert attachment_record["status"] == "compensated"
    assert len(temp_leftovers) == 1
    assert "journal atomic-rename failure" in journal_record["error"]
    assert "temp journal cleanup failure" in journal_record["error"]
    assert str(temp_leftovers[0]) in journal_record["error"]
    assert str(temp_leftovers[0]) in journal_record["recovery_strategy"]


def test_derived_artifact_failures_cannot_create_half_updated_success(
    tmp_path: Path,
    monkeypatch,
):
    """No derived artifact may observe a journal before its durable rename."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    calls: list[str] = []
    real_replace = Path.replace

    monkeypatch.setattr(
        write_core,
        "update_monthly_abstract",
        lambda *_args: calls.append("monthly_abstract") or {"success": True},
    )
    monkeypatch.setattr(
        write_core,
        "_update_indices",
        lambda **_kwargs: calls.append("legacy_indices") or [],
    )
    monkeypatch.setattr(
        write_core,
        "_update_metadata_relations",
        lambda *_args: calls.append("metadata_relations") or "synthetic.md",
    )
    monkeypatch.setattr(
        write_core,
        "refresh_index_b",
        lambda *_args: calls.append("index_b") or {"success": True},
    )

    def fail_journal_rename(self: Path, target: Path):
        if self.suffix == ".tmp":
            raise OSError("synthetic journal atomic-rename failure")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_journal_rename)

    result = write_core.write_journal(_payload())

    assert result["success"] is False
    assert calls == []
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "by-topic") == []


def test_attachment_staging_failure_is_visible_before_any_write(
    tmp_path: Path,
    monkeypatch,
):
    """A staging-directory failure is blocking and leaves no durable artifacts."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source_file = tmp_path / "evidence.txt"
    source_file.write_text("synthetic attachment", encoding="utf-8")
    monkeypatch.setattr(
        attachment_ops.tempfile,
        "mkdtemp",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("synthetic attachment staging failure")),
    )

    result = write_core.write_journal(_payload(source_file))

    assert result["success"] is False
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "attachments") == []
    record = next(item for item in result["side_effects"] if item["name"] == "attachments")
    assert record["status"] == "failed"
    assert record["blocking"] is True
    assert "staging failure" in record["error"]


def test_attachment_copy_failure_is_visible_before_any_write(
    tmp_path: Path,
    monkeypatch,
):
    """A source-copy failure is blocking and leaves no durable artifacts."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source_file = tmp_path / "evidence.txt"
    source_file.write_text("synthetic attachment", encoding="utf-8")
    monkeypatch.setattr(
        attachment_ops.shutil,
        "copy",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("synthetic attachment copy failure")
        ),
    )

    result = write_core.write_journal(_payload(source_file))

    assert result["success"] is False
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "attachments") == []
    record = next(item for item in result["side_effects"] if item["name"] == "attachments")
    assert record["status"] == "failed"
    assert record["blocking"] is True
    assert "copy failure" in record["error"]


def test_format_failure_discards_attachment_staging(
    tmp_path: Path,
    monkeypatch,
):
    """A format failure between attachment staging and commit leaves no bytes."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source_file = tmp_path / "evidence.txt"
    source_file.write_text("synthetic attachment", encoding="utf-8")
    monkeypatch.setattr(
        write_core,
        "format_content",
        lambda *_args: (_ for _ in ()).throw(ValueError("synthetic journal formatting failure")),
    )

    result = write_core.write_journal(_payload(source_file))

    assert result["success"] is False
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "attachments") == []
    record = next(item for item in result["side_effects"] if item["name"] == "attachments")
    assert record["status"] == "compensated"
    assert "formatting failure" in record["error"]


def test_attachment_compensation_failure_is_reported(
    tmp_path: Path,
    monkeypatch,
):
    """An orphan that cannot be removed is named with an explicit recovery path."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    source_file = tmp_path / "evidence.txt"
    source_file.write_text("synthetic attachment", encoding="utf-8")
    real_replace = Path.replace
    real_unlink = Path.unlink

    def fail_journal_rename(self: Path, target: Path):
        if self.suffix == ".tmp":
            raise OSError("synthetic journal atomic-rename failure")
        return real_replace(self, target)

    def fail_final_attachment_cleanup(self: Path, *args, **kwargs):
        if "attachments" in self.parts and ".write-stage-" not in str(self):
            raise OSError("synthetic compensation failure")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "replace", fail_journal_rename)
    monkeypatch.setattr(Path, "unlink", fail_final_attachment_cleanup)

    result = write_core.write_journal(_payload(source_file))

    assert result["success"] is False
    assert _files_under(data_dir / "Journals") == []
    assert _files_under(data_dir / "attachments") == [str(Path("2026") / "03" / "evidence.txt")]
    record = next(item for item in result["side_effects"] if item["name"] == "attachments")
    assert record["status"] == "failed"
    assert "compensation failed" in record["error"]
    assert "orphan attachment" in record["recovery_strategy"]


@pytest.mark.parametrize(
    ("effect_name", "failure_message"),
    [
        ("monthly_abstract", "synthetic monthly abstract failure"),
        ("legacy_indices", "synthetic legacy index failure"),
        ("metadata_relations", "synthetic metadata relation failure"),
        ("index_b", "synthetic Index B failure"),
        ("entity_candidates", "synthetic candidate capture failure"),
        ("confirmation_snapshot", "synthetic confirmation snapshot failure"),
    ],
)
def test_postcommit_failure_reports_committed_degraded_without_duplicate_retry_semantics(
    tmp_path: Path,
    monkeypatch,
    effect_name: str,
    failure_message: str,
):
    """A derived-view failure cannot make a durable journal look unsaved."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(
        write_core,
        "update_monthly_abstract",
        lambda *_args: {"success": True},
    )
    monkeypatch.setattr(write_core, "_update_indices", lambda **_kwargs: [])
    monkeypatch.setattr(
        write_core,
        "_update_metadata_relations",
        lambda *_args: "Journals/2026/03/synthetic.md",
    )
    monkeypatch.setattr(
        write_core,
        "refresh_index_b",
        lambda *_args: {"success": True},
    )
    monkeypatch.setattr(
        write_core,
        "capture_write_time_candidates",
        lambda **_kwargs: {},
    )

    def fail(*_args, **_kwargs):
        raise OSError(failure_message)

    if effect_name == "monthly_abstract":
        monkeypatch.setattr(write_core, "update_monthly_abstract", fail)
    elif effect_name == "legacy_indices":
        monkeypatch.setattr(write_core, "_update_indices", fail)
    elif effect_name == "metadata_relations":
        monkeypatch.setattr(write_core, "_update_metadata_relations", fail)
    elif effect_name == "entity_candidates":
        monkeypatch.setattr(write_core, "capture_write_time_candidates", fail)
    elif effect_name == "confirmation_snapshot":
        monkeypatch.setattr(write_core, "_write_confirmation_candidate_snapshot", fail)
    else:
        monkeypatch.setattr(
            write_core,
            "refresh_index_b",
            lambda *_args: {"success": False, "error": failure_message},
        )

    result = write_core.write_journal(_payload())

    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    assert result["journal_path"]
    assert Path(result["journal_path"]).exists()
    assert result["error"] is None
    record = next(item for item in result["side_effects"] if item["name"] == effect_name)
    assert record["status"] == "failed"
    assert record["blocking"] is False
    assert failure_message in record["error"]
    assert record["recovery_strategy"]
    assert "retry the write" not in record["recovery_strategy"].lower()
    assert len(_files_under(data_dir / "Journals")) == 1


def test_monthly_abstract_unsuccessful_result_is_degraded(
    tmp_path: Path,
    monkeypatch,
):
    """A non-raising unsuccessful builder result is still a failed side effect."""
    _configure_sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(
        write_core,
        "update_monthly_abstract",
        lambda *_args: {
            "success": False,
            "error": "synthetic monthly builder failure",
        },
    )
    monkeypatch.setattr(write_core, "_update_indices", lambda **_kwargs: [])
    monkeypatch.setattr(
        write_core,
        "refresh_index_b",
        lambda *_args: {"success": True},
    )
    monkeypatch.setattr(
        write_core,
        "capture_write_time_candidates",
        lambda **_kwargs: {},
    )

    result = write_core.write_journal(_payload())

    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    record = next(item for item in result["side_effects"] if item["name"] == "monthly_abstract")
    assert record["status"] == "failed"
    assert "monthly builder failure" in record["error"]


def test_generic_postcommit_confirmation_exception_returns_degraded_envelope(
    tmp_path: Path, monkeypatch
):
    _configure_sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(
        write_core,
        "_build_post_write_confirmation",
        lambda *_args: (_ for _ in ()).throw(Exception("synthetic envelope assembly failure")),
    )

    result = write_core.write_journal(_payload())

    assert result["success"] is True
    assert result["journal_path"] and Path(result["journal_path"]).exists()
    assert result["write_outcome"] == "success_degraded"
    record = next(
        item for item in result["side_effects"] if item["name"] == "confirmation_snapshot"
    )
    assert record["status"] == "failed"
    assert record["blocking"] is False
    assert "envelope assembly failure" in record["error"]
    assert "write" not in record["recovery_strategy"].lower()


def test_generic_final_projection_exception_returns_committed_degraded_envelope(
    tmp_path: Path, monkeypatch
):
    _configure_sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(
        write_core,
        "derive_write_statuses",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            Exception("synthetic final projection failure")
        ),
    )

    result = write_core.write_journal(_payload())

    assert result["success"] is True
    assert result["journal_path"] and Path(result["journal_path"]).exists()
    assert result["write_outcome"] == "success_degraded"
    assert result["error"] is None
    record = next(item for item in result["side_effects"] if item["name"] == "postcommit_envelope")
    assert record["status"] == "failed"
    assert record["blocking"] is False
    assert "final projection failure" in record["error"]
    assert "write" not in record["recovery_strategy"].lower()


def test_final_success_log_exception_returns_committed_degraded_envelope(
    tmp_path: Path, monkeypatch
):
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    real_info = write_core.logger.info

    def fail_final_success_log(message, *args, **kwargs):
        if str(message).startswith("写入完成"):
            raise Exception("synthetic final success log failure")
        return real_info(message, *args, **kwargs)

    monkeypatch.setattr(write_core.logger, "info", fail_final_success_log)

    escaped = None
    result = None
    try:
        result = write_core.write_journal(_payload())
    except Exception as exc:
        escaped = exc

    journals = list((data_dir / "Journals").rglob("life-index_*.md"))
    assert len(journals) == 1 and journals[0].exists()
    assert escaped is None, f"committed write escaped without an envelope: {escaped}"
    assert result is not None
    assert result["journal_path"] == str(journals[0])
    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    assert result["error"] is None
    record = next(item for item in result["side_effects"] if item["name"] == "postcommit_envelope")
    assert record["status"] == "failed"
    assert record["blocking"] is False
    assert "final success log failure" in record["error"]
    assert "write" not in record["recovery_strategy"].lower()


def test_recovery_logger_exception_cannot_escape_committed_degraded_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recovery diagnostics are best-effort after the journal is durable."""
    data_dir = _configure_sandbox(monkeypatch, tmp_path)
    real_record_side_effect = write_core._record_side_effect
    original_failure_raised = False

    def fail_first_monthly_record(*args: Any, **kwargs: Any) -> None:
        nonlocal original_failure_raised
        if kwargs.get("name") == "monthly_abstract" and not original_failure_raised:
            original_failure_raised = True
            raise OSError("synthetic original postcommit failure")
        return real_record_side_effect(*args, **kwargs)

    monkeypatch.setattr(write_core, "_record_side_effect", fail_first_monthly_record)
    monkeypatch.setattr(
        write_core.logger,
        "error",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            Exception("synthetic recovery logger failure")
        ),
    )

    escaped = None
    result = None
    try:
        result = write_core.write_journal(_payload())
    except Exception as exc:
        escaped = exc

    journals = list((data_dir / "Journals").rglob("life-index_*.md"))
    assert original_failure_raised is True
    assert len(journals) == 1 and journals[0].exists()
    assert escaped is None, f"committed write escaped during recovery logging: {escaped}"
    assert result is not None
    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    assert result["journal_path"] == str(journals[0])
    assert result["error"] is None
    record = next(item for item in result["side_effects"] if item["name"] == "postcommit_envelope")
    assert record["status"] == "failed"
    assert record["blocking"] is False
    assert "original postcommit failure" in record["error"]
    assert "write" not in record["recovery_strategy"].lower()


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_postcommit_interrupts_are_not_swallowed(tmp_path: Path, monkeypatch, interrupt):
    _configure_sandbox(monkeypatch, tmp_path)
    monkeypatch.setattr(
        write_core,
        "_build_post_write_confirmation",
        lambda *_args: (_ for _ in ()).throw(interrupt()),
    )

    with pytest.raises(interrupt):
        write_core.write_journal(_payload())


@pytest.mark.parametrize("mode", ["exception", "unsuccessful"])
def test_index_b_exception_and_unsuccessful_result_are_failed_records(
    tmp_path: Path, monkeypatch, mode: str
):
    _configure_sandbox(monkeypatch, tmp_path)
    if mode == "exception":
        monkeypatch.setattr(
            write_core,
            "refresh_index_b",
            lambda *_args: (_ for _ in ()).throw(Exception("synthetic Index B exception")),
        )
    else:
        monkeypatch.setattr(
            write_core,
            "refresh_index_b",
            lambda *_args: {"success": False, "error": "synthetic Index B unsuccessful"},
        )

    result = write_core.write_journal(_payload())
    record = next(item for item in result["side_effects"] if item["name"] == "index_b")

    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    assert record["status"] == "failed"
    assert "synthetic Index B" in record["error"]


def test_legacy_index_partial_update_preserves_completed_artifact_paths(
    tmp_path: Path, monkeypatch
):
    _configure_sandbox(monkeypatch, tmp_path)
    completed = tmp_path / "Life-Index" / "by-topic" / "work.md"
    monkeypatch.setattr(write_core, "update_topic_index", lambda *_args: [completed])
    monkeypatch.setattr(
        write_core,
        "update_tag_indices",
        lambda *_args: (_ for _ in ()).throw(OSError("synthetic late tag index failure")),
    )
    payload = _payload()
    payload["tags"] = ["late-failure"]

    result = write_core.write_journal(payload)
    record = next(item for item in result["side_effects"] if item["name"] == "legacy_indices")

    assert result["success"] is True
    assert result["write_outcome"] == "success_degraded"
    assert str(completed) in result["updated_indices"]
    assert record["status"] == "failed"
