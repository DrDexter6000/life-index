#!/usr/bin/env python3
"""Runtime behavior tests for verify command."""

from __future__ import annotations

import pickle
import sqlite3
from pathlib import Path

import pytest

from tools.verify.core import run_verify


def _write_journal(
    journals_dir: Path,
    *,
    year: str,
    month: str,
    filename: str,
    frontmatter: str,
    body: str,
) -> Path:
    target = journals_dir / year / month / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")
    return target


def _rel_path(base_dir: Path, file_path: Path) -> str:
    return str(file_path.relative_to(base_dir)).replace("\\", "/")


def _create_fts_db(base_dir: Path, indexed_paths: list[str]) -> None:
    index_dir = base_dir / ".index"
    index_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(index_dir / "journals_fts.db")
    try:
        conn.execute(
            """
            CREATE TABLE journals (
                path TEXT,
                title TEXT,
                content TEXT,
                date TEXT,
                location TEXT,
                weather TEXT,
                topic TEXT,
                project TEXT,
                tags TEXT,
                file_hash TEXT,
                modified_time TEXT
            )
            """
        )
        for path in indexed_paths:
            conn.execute(
                "INSERT INTO journals VALUES (?, '', '', '', '', '', '', '', '', '', '')",
                (path,),
            )
        conn.commit()
    finally:
        conn.close()


def _create_vector_index(base_dir: Path, indexed_paths: list[str]) -> None:
    index_dir = base_dir / ".index"
    index_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        path: {"embedding": [0.1, 0.2], "date": "2026-04-03", "hash": "abc"}
        for path in indexed_paths
    }
    with (index_dir / "vectors_simple.pkl").open("wb") as fh:
        pickle.dump(payload, fh)


def _create_topic_index(by_topic_dir: Path, links: list[str]) -> None:
    by_topic_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# 主题: work", ""] + [f"- [2026-04-03] [Entry]({link})" for link in links]
    (by_topic_dir / "主题_work.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _check(result: dict, name: str) -> dict:
    return next(check for check in result["checks"] if check["name"] == name)


@pytest.fixture
def verify_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    journals_dir = tmp_path / "Journals"
    by_topic_dir = tmp_path / "by-topic"
    attachments_dir = tmp_path / "attachments"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("tools.verify.core.get_journals_dir", lambda: journals_dir)
    monkeypatch.setattr("tools.verify.core.get_by_topic_dir", lambda: by_topic_dir)
    monkeypatch.setattr("tools.verify.core.get_attachments_dir", lambda: attachments_dir)
    monkeypatch.setattr("tools.verify.core.get_user_data_dir", lambda: tmp_path, raising=False)
    return {
        "base_dir": tmp_path,
        "journals_dir": journals_dir,
        "by_topic_dir": by_topic_dir,
        "attachments_dir": attachments_dir,
    }


class TestVerifyCommand:
    def test_clean_data_all_passed(self, verify_paths: dict[str, Path]) -> None:
        journal_a = _write_journal(
            verify_paths["journals_dir"],
            year="2026",
            month="04",
            filename="life-index_2026-04-03_001.md",
            frontmatter='title: "A"\ndate: 2026-04-03\ntopic: ["work"]\nabstract: "Alpha"',
            body="# A\n\nBody A",
        )
        journal_b = _write_journal(
            verify_paths["journals_dir"],
            year="2026",
            month="04",
            filename="life-index_2026-04-04_001.md",
            frontmatter='title: "B"\ndate: 2026-04-04\ntopic: ["work"]\nabstract: "Beta"',
            body="# B\n\nBody B",
        )
        indexed = [
            _rel_path(verify_paths["base_dir"], journal_a),
            _rel_path(verify_paths["base_dir"], journal_b),
        ]
        _create_fts_db(verify_paths["base_dir"], indexed)
        _create_vector_index(verify_paths["base_dir"], indexed)
        _create_topic_index(verify_paths["by_topic_dir"], indexed)

        result = run_verify()

        assert result["success"] is True
        assert result["issues_count"] == 0
        assert len(result["checks"]) == 6

    def test_missing_required_field_detected(
        self, verify_paths: dict[str, Path]
    ) -> None:
        _write_journal(
            verify_paths["journals_dir"],
            year="2026",
            month="04",
            filename="life-index_2026-04-03_001.md",
            frontmatter="date: 2026-04-03",
            body="Body",
        )

        result = run_verify()
        frontmatter_check = _check(result, "frontmatter_valid")

        assert frontmatter_check["status"] != "ok"
        assert any("missing title" in issue for issue in frontmatter_check["issues"])

    def test_orphan_fts_entry_detected(self, verify_paths: dict[str, Path]) -> None:
        _create_fts_db(
            verify_paths["base_dir"], ["Journals/2026/04/life-index_2026-04-03_001.md"]
        )

        result = run_verify()
        fts_check = _check(result, "fts_consistency")

        assert fts_check["status"] != "ok"
        assert any("orphan" in issue for issue in fts_check["issues"])

    def test_missing_fts_entry_detected(self, verify_paths: dict[str, Path]) -> None:
        _write_journal(
            verify_paths["journals_dir"],
            year="2026",
            month="04",
            filename="life-index_2026-04-03_001.md",
            frontmatter='title: "A"\ndate: 2026-04-03',
            body="Body",
        )
        _create_fts_db(verify_paths["base_dir"], [])

        result = run_verify()
        fts_check = _check(result, "fts_consistency")

        assert fts_check["status"] != "ok"
        assert any("missing" in issue for issue in fts_check["issues"])

    def test_vector_index_inconsistency_detected(
        self, verify_paths: dict[str, Path]
    ) -> None:
        journal = _write_journal(
            verify_paths["journals_dir"],
            year="2026",
            month="04",
            filename="life-index_2026-04-03_001.md",
            frontmatter='title: "A"\ndate: 2026-04-03',
            body="Body",
        )
        _create_fts_db(
            verify_paths["base_dir"], [_rel_path(verify_paths["base_dir"], journal)]
        )
        _create_vector_index(verify_paths["base_dir"], [])

        result = run_verify()
        vector_check = _check(result, "vector_consistency")

        assert vector_check["status"] != "ok"
        assert any("missing" in issue for issue in vector_check["issues"])

    def test_broken_attachment_ref_detected(
        self, verify_paths: dict[str, Path]
    ) -> None:
        journal = _write_journal(
            verify_paths["journals_dir"],
            year="2026",
            month="04",
            filename="life-index_2026-04-03_001.md",
            frontmatter='title: "A"\ndate: 2026-04-03',
            body="![](attachments/2026/04/foo.png)",
        )
        indexed = [_rel_path(verify_paths["base_dir"], journal)]
        _create_fts_db(verify_paths["base_dir"], indexed)
        _create_vector_index(verify_paths["base_dir"], indexed)

        result = run_verify()
        attachment_check = _check(result, "attachment_refs")

        assert attachment_check["status"] != "ok"
        assert any("foo.png" in issue for issue in attachment_check["issues"])

    def test_topic_index_orphan_detected(self, verify_paths: dict[str, Path]) -> None:
        _create_fts_db(verify_paths["base_dir"], [])
        _create_vector_index(verify_paths["base_dir"], [])
        _create_topic_index(
            verify_paths["by_topic_dir"],
            ["Journals/2026/04/life-index_2026-04-03_001.md"],
        )

        result = run_verify()
        topic_check = _check(result, "topic_consistency")

        assert topic_check["status"] != "ok"
        assert any("orphan" in issue for issue in topic_check["issues"])

    def test_verify_output_json_structure(self, verify_paths: dict[str, Path]) -> None:
        result = run_verify()

        assert set(result.keys()) >= {
            "success",
            "total_journals",
            "checks",
            "issues_count",
            "suggestion",
        }
