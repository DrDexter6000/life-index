#!/usr/bin/env python3
"""Tests for DocRecord, DocID utility, and doc catalog builder (R2-B3a).

Covers:
  1. make_doc_id_from_route: valid, backslash, absolute, empty
  2. DocRecord round-trip: to_dict/from_dict semantic equality, extra fields
  3. DocRecord route path validation: absolute raises, backslash normalizes
  4. Catalog builder with tempfile: correct fields, no body content
  5. build_title_to_doc_ids: unique and duplicate titles
  6. detect_doc_id_collisions: duplicate and clean catalogs
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tools.eval.eval_doc_catalog import (
    DocRecord,
    build_title_to_doc_ids,
    collect_eval_doc_catalog,
    detect_doc_id_collisions,
    make_doc_id_from_route,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def data_dir() -> Path:
    """Provide a temporary directory that avoids pytest's shared basetemp."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


# ---------------------------------------------------------------------------
# 1. make_doc_id_from_route
# ---------------------------------------------------------------------------


class TestMakeDocIdFromRoute:
    def test_valid_route_path(self) -> None:
        assert (
            make_doc_id_from_route("2026/03/life-index_2026-03-14_001.md")
            == "2026/03/life-index_2026-03-14_001.md"
        )

    def test_backslash_normalized(self) -> None:
        assert (
            make_doc_id_from_route("2026\\03\\life-index_2026-03-14_001.md")
            == "2026/03/life-index_2026-03-14_001.md"
        )

    def test_absolute_windows_path_raises(self) -> None:
        with pytest.raises(ValueError, match="Absolute path"):
            make_doc_id_from_route(
                "C:\\Users\\user\\Documents\\Life-Index\\Journals\\"
                "2026\\03\\life-index_2026-03-14_001.md"
            )

    def test_absolute_unix_path_raises(self) -> None:
        with pytest.raises(ValueError, match="Absolute path"):
            make_doc_id_from_route(
                "/home/user/Documents/Life-Index/Journals/" "2026/03/life-index_2026-03-14_001.md"
            )

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            make_doc_id_from_route("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            make_doc_id_from_route("   ")


# ---------------------------------------------------------------------------
# 2. DocRecord round-trip
# ---------------------------------------------------------------------------


def _sample_record(**overrides) -> DocRecord:
    if "doc_id" in overrides and "journal_route_path" not in overrides:
        overrides["journal_route_path"] = overrides["doc_id"]
    defaults = dict(
        doc_id="2026/03/life-index_2026-03-14_001.md",
        title="Test Entry",
        date="2026-03-14",
        journal_route_path="2026/03/life-index_2026-03-14_001.md",
        topic=["work", "reflection"],
        location="Shanghai",
        rel_path="Journals/2026/03/life-index_2026-03-14_001.md",
    )
    defaults.update(overrides)
    return DocRecord(**defaults)


class TestDocRecordRoundTrip:
    def test_to_dict_from_dict_equality(self) -> None:
        original = _sample_record()
        restored = DocRecord.from_dict(original.to_dict())
        assert restored == original

    def test_extra_fields_preserved(self) -> None:
        rec = _sample_record(extra={"custom_field": 42, "flag": True})
        d = rec.to_dict()
        assert d["custom_field"] == 42
        assert d["flag"] is True
        restored = DocRecord.from_dict(d)
        assert restored.extra == {"custom_field": 42, "flag": True}

    def test_minimal_record(self) -> None:
        rec = DocRecord(
            doc_id="2026/01/life-index_2026-01-01_001.md",
            title="",
            date="2026-01-01",
            journal_route_path="2026/01/life-index_2026-01-01_001.md",
        )
        d = rec.to_dict()
        assert "topic" not in d
        assert "location" not in d
        assert "rel_path" not in d
        restored = DocRecord.from_dict(d)
        assert restored.topic == []
        assert restored.location is None

    def test_from_dict_uses_doc_id_if_present(self) -> None:
        d = {
            "doc_id": "2026/03/life-index_2026-03-14_001.md",
            "title": "T",
            "date": "2026-03-14",
            "journal_route_path": "2026/03/life-index_2026-03-14_001.md",
        }
        rec = DocRecord.from_dict(d)
        assert rec.doc_id == "2026/03/life-index_2026-03-14_001.md"


# ---------------------------------------------------------------------------
# 3. DocRecord route path validation
# ---------------------------------------------------------------------------


class TestDocRecordRoutePathValidation:
    def test_from_dict_absolute_route_path_raises(self) -> None:
        d = {
            "doc_id": "2026/03/life-index_2026-03-14_001.md",
            "title": "T",
            "date": "2026-03-14",
            "journal_route_path": ("C:\\Users\\user\\2026\\03\\life-index_2026-03-14_001.md"),
        }
        with pytest.raises(ValueError, match="Absolute path"):
            DocRecord.from_dict(d)

    def test_from_dict_backslash_route_path_normalizes(self) -> None:
        d = {
            "title": "T",
            "date": "2026-03-14",
            "journal_route_path": "2026\\03\\life-index_2026-03-14_001.md",
        }
        rec = DocRecord.from_dict(d)
        assert rec.journal_route_path == "2026/03/life-index_2026-03-14_001.md"
        assert rec.doc_id == "2026/03/life-index_2026-03-14_001.md"

    def test_from_dict_doc_id_defaults_to_normalized_route(self) -> None:
        d = {
            "title": "T",
            "date": "2026-03-14",
            "journal_route_path": "2026\\03\\life-index_2026-03-14_001.md",
        }
        rec = DocRecord.from_dict(d)
        assert rec.doc_id == rec.journal_route_path

    def test_from_dict_mismatched_doc_id_route_raises(self) -> None:
        d = {
            "doc_id": "2026/03/a.md",
            "title": "T",
            "date": "2026-03-14",
            "journal_route_path": "2026/03/b.md",
        }
        with pytest.raises(ValueError, match="must equal"):
            DocRecord.from_dict(d)

    def test_direct_construction_absolute_route_raises(self) -> None:
        with pytest.raises(ValueError, match="Absolute path"):
            DocRecord(
                doc_id="2026/03/life-index_2026-03-14_001.md",
                title="T",
                date="2026-03-14",
                journal_route_path=("C:\\Users\\bad\\2026\\03\\life-index_2026-03-14_001.md"),
            )

    def test_direct_construction_absolute_doc_id_raises(self) -> None:
        with pytest.raises(ValueError, match="Absolute path"):
            DocRecord(
                doc_id="/home/user/2026/03/life-index_2026-03-14_001.md",
                title="T",
                date="2026-03-14",
                journal_route_path="2026/03/life-index_2026-03-14_001.md",
            )

    def test_direct_construction_backslash_normalizes_both(self) -> None:
        rec = DocRecord(
            doc_id="2026\\03\\life-index_2026-03-14_001.md",
            title="T",
            date="2026-03-14",
            journal_route_path="2026\\03\\life-index_2026-03-14_001.md",
        )
        assert rec.doc_id == "2026/03/life-index_2026-03-14_001.md"
        assert rec.journal_route_path == "2026/03/life-index_2026-03-14_001.md"
        assert rec.doc_id == rec.journal_route_path

    def test_direct_construction_mismatched_raises(self) -> None:
        with pytest.raises(ValueError, match="must equal"):
            DocRecord(
                doc_id="2026/03/a.md",
                title="T",
                date="2026-03-14",
                journal_route_path="2026/03/b.md",
            )


# ---------------------------------------------------------------------------
# 4. Catalog builder with tempfile
# ---------------------------------------------------------------------------


def _write_journal(
    data_dir: Path,
    year: str,
    month: str,
    filename: str,
    frontmatter: str,
    body: str = "# Test Title\n\nBody content here.",
) -> Path:
    """Write a journal file with frontmatter and body under data_dir/Journals."""
    journals_dir = data_dir / "Journals" / year / month
    journals_dir.mkdir(parents=True, exist_ok=True)
    file_path = journals_dir / filename
    content = f"---\n{frontmatter}\n---\n\n{body}\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path


class TestCollectEvalDocCatalog:
    def test_single_entry(self, data_dir: Path) -> None:
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-14_001.md",
            "title: Morning Reflection\n"
            'date: "2026-03-14"\n'
            "topic: [reflection]\n"
            'location: "Shanghai"',
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert len(catalog) == 1
        rec = catalog[0]
        assert rec.doc_id == "2026/03/life-index_2026-03-14_001.md"
        assert rec.title == "Morning Reflection"
        assert rec.date == "2026-03-14"
        assert rec.topic == ["reflection"]
        assert rec.location == "Shanghai"
        assert rec.journal_route_path == "2026/03/life-index_2026-03-14_001.md"

    def test_no_body_content_in_record(self, data_dir: Path) -> None:
        body = "# Secret Title\n\nThis is private body content."
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-14_001.md",
            'title: "Public Title"\ndate: "2026-03-14"',
            body=body,
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert len(catalog) == 1
        d = catalog[0].to_dict()
        for key in d:
            assert "body" not in key.lower()
            assert "secret" not in str(d[key]).lower()
            assert "private" not in str(d[key]).lower()

    def test_multiple_entries(self, data_dir: Path) -> None:
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-14_001.md",
            'title: "Entry A"\ndate: "2026-03-14"',
        )
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-15_001.md",
            'title: "Entry B"\ndate: "2026-03-15"',
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert len(catalog) == 2
        ids = [r.doc_id for r in catalog]
        assert "2026/03/life-index_2026-03-14_001.md" in ids
        assert "2026/03/life-index_2026-03-15_001.md" in ids

    def test_empty_journals_dir(self, data_dir: Path) -> None:
        (data_dir / "Journals").mkdir()
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert catalog == []

    def test_nonexistent_journals_dir(self, data_dir: Path) -> None:
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert catalog == []

    def test_rel_path_populated(self, data_dir: Path) -> None:
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-14_001.md",
            'title: "Test"\ndate: "2026-03-14"',
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert len(catalog) == 1
        assert catalog[0].rel_path is not None
        assert "Journals" in catalog[0].rel_path


# ---------------------------------------------------------------------------
# 4b. Revision backup exclusion
# ---------------------------------------------------------------------------


def _write_revision(
    data_dir: Path,
    year: str,
    month: str,
    filename: str,
    frontmatter: str,
    body: str = "# Test Title\n\nBody content here.",
) -> Path:
    """Write a revision backup file under .revisions/ subdirectory."""
    revisions_dir = data_dir / "Journals" / year / month / ".revisions"
    revisions_dir.mkdir(parents=True, exist_ok=True)
    file_path = revisions_dir / filename
    content = f"---\n{frontmatter}\n---\n\n{body}\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path


class TestRevisionBackupExclusion:
    def test_excludes_revision_backups_from_catalog(self, data_dir: Path) -> None:
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001.md",
            'title: "Shared Title"\ndate: "2026-03-01"',
        )
        _write_revision(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001_20260416_000000_000000.md",
            'title: "Shared Title"\ndate: "2026-03-01"',
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert len(catalog) == 1
        assert catalog[0].doc_id == "2026/03/life-index_2026-03-01_001.md"

    def test_title_map_no_ambiguity_after_filter(self, data_dir: Path) -> None:
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001.md",
            'title: "Shared Title"\ndate: "2026-03-01"',
        )
        _write_revision(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001_20260416_000000_000000.md",
            'title: "Shared Title"\ndate: "2026-03-01"',
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        title_map = build_title_to_doc_ids(catalog)
        assert len(title_map["Shared Title"]) == 1

    def test_original_preserved_when_revision_exists(self, data_dir: Path) -> None:
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001.md",
            'title: "Original"\ndate: "2026-03-01"',
        )
        _write_revision(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001_20260416_000000_000000.md",
            'title: "Original"\ndate: "2026-03-01"',
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert len(catalog) == 1
        assert catalog[0].title == "Original"
        assert catalog[0].date == "2026-03-01"

    def test_multiple_revisions_all_excluded(self, data_dir: Path) -> None:
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001.md",
            'title: "Test"\ndate: "2026-03-01"',
        )
        _write_revision(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001_20260413_120000_000000.md",
            'title: "Test"\ndate: "2026-03-01"',
        )
        _write_revision(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001_20260413_130000_111111.md",
            'title: "Test"\ndate: "2026-03-01"',
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert len(catalog) == 1

    def test_no_revisions_still_works(self, data_dir: Path) -> None:
        _write_journal(
            data_dir,
            "2026",
            "03",
            "life-index_2026-03-01_001.md",
            'title: "Solo"\ndate: "2026-03-01"',
        )
        catalog = collect_eval_doc_catalog(data_dir=data_dir)
        assert len(catalog) == 1
        assert catalog[0].doc_id == "2026/03/life-index_2026-03-01_001.md"


# ---------------------------------------------------------------------------
# 5. build_title_to_doc_ids
# ---------------------------------------------------------------------------


class TestBuildTitleToDocIds:
    def test_unique_titles(self) -> None:
        catalog = [
            _sample_record(
                title="Alpha",
                doc_id="2026/01/life-index_2026-01-01_001.md",
            ),
            _sample_record(
                title="Beta",
                doc_id="2026/01/life-index_2026-01-02_001.md",
            ),
        ]
        mapping = build_title_to_doc_ids(catalog)
        assert len(mapping["Alpha"]) == 1
        assert len(mapping["Beta"]) == 1

    def test_duplicate_titles(self) -> None:
        catalog = [
            _sample_record(
                title="Same Title",
                doc_id="2026/01/life-index_2026-01-01_001.md",
            ),
            _sample_record(
                title="Same Title",
                doc_id="2026/01/life-index_2026-01-02_001.md",
            ),
        ]
        mapping = build_title_to_doc_ids(catalog)
        assert len(mapping["Same Title"]) == 2
        assert mapping["Same Title"] == [
            "2026/01/life-index_2026-01-01_001.md",
            "2026/01/life-index_2026-01-02_001.md",
        ]

    def test_empty_catalog(self) -> None:
        assert build_title_to_doc_ids([]) == {}


# ---------------------------------------------------------------------------
# 6. detect_doc_id_collisions
# ---------------------------------------------------------------------------


class TestDetectDocIdCollisions:
    def test_no_collisions(self) -> None:
        catalog = [
            _sample_record(
                doc_id="2026/01/life-index_2026-01-01_001.md",
            ),
            _sample_record(
                doc_id="2026/01/life-index_2026-01-02_001.md",
            ),
        ]
        assert detect_doc_id_collisions(catalog) == {}

    def test_duplicate_doc_id(self) -> None:
        catalog = [
            _sample_record(
                doc_id="2026/01/life-index_2026-01-01_001.md",
            ),
            _sample_record(
                doc_id="2026/01/life-index_2026-01-01_001.md",
            ),
        ]
        collisions = detect_doc_id_collisions(catalog)
        assert len(collisions) == 1
        assert "2026/01/life-index_2026-01-01_001.md" in collisions
        assert len(collisions["2026/01/life-index_2026-01-01_001.md"]) == 2

    def test_empty_catalog(self) -> None:
        assert detect_doc_id_collisions([]) == {}
