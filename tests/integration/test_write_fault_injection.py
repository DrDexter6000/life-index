"""Fault-injection tests for transactional journal writes."""

import builtins
from pathlib import Path

import pytest

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
    real_replace = Path.replace
    publish_count = 0

    def fail_second_attachment_publish(self: Path, target: Path):
        nonlocal publish_count
        if ".write-stage-" in str(self) and self.parent.name == "files":
            publish_count += 1
            if publish_count == 2:
                raise OSError("synthetic attachment publish failure")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_second_attachment_publish)

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
