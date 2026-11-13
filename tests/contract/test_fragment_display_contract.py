#!/usr/bin/env python3
"""Contract: an untitled fragment is valid and carries kind + display_label.

A fragment with no ``title`` (and no ``topic``) must (a) pass ``verify`` and
the maintenance data audit, (b) come back from ``search`` (cache path and
full-text path), ``timeline``, ``on-this-day`` and ``journal list`` with
``title == ""``, ``kind == "fragment"`` and the expected ``display_label``,
and (c) appear under its label in the generated indexes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATE = "2026-03-04"
BODY_FIRST_LINE = "今天在公园里散步，遇到了老朋友！"
# The token appears on two lines so the fallback content scan's relevance
# cut-off is cleared by body hits alone (no title to match).
BODY = (
    BODY_FIRST_LINE + "\n\nuniquedisplaytoken 第一段正文，没有标题。\nuniquedisplaytoken 第二段。"
)
LABEL = BODY_FIRST_LINE  # the first terminator cuts here and is kept
FILENAME = "life-index_2026-03-04_001.md"
REL_PATH = f"Journals/2026/03/{FILENAME}"

# (data dir, untitled fragment path) as built by the untitled_archive fixture
Archive = tuple[Path, Path]


def _write_untitled_fragment(data_dir: Path) -> Path:
    month_dir = data_dir / "Journals" / "2026" / "03"
    month_dir.mkdir(parents=True, exist_ok=True)
    path = month_dir / FILENAME
    path.write_text(
        f"---\ndate: {DATE}\n---\n\n{BODY}\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def untitled_archive(isolated_data_dir: Path) -> Archive:
    from tools.build_index import build_all

    path = _write_untitled_fragment(isolated_data_dir)
    build = build_all(incremental=False)
    assert build["success"] is True
    return isolated_data_dir, path


class TestValidationAndAudit:
    def test_untitled_fragment_is_not_flagged_by_verify(self, untitled_archive: Archive) -> None:
        from tools.verify.core import run_verify

        _data_dir, path = untitled_archive
        result = run_verify()

        by_name = {check["name"]: check for check in result["checks"]}
        for name in ("frontmatter_valid", "required_fields"):
            issues = [i for i in by_name[name]["issues"] if i.startswith(path.name)]
            assert issues == [], (name, issues)

    def test_untitled_fragment_is_not_flagged_by_the_data_audit(
        self, untitled_archive: Archive
    ) -> None:
        from tools.maintenance.audit import run_audit

        data_dir, _path = untitled_archive
        audit = run_audit(data_dir=data_dir, domains=["frontmatter"])

        frontmatter_issues = [
            issue for issue in audit["issues"] if issue["evidence"][0]["path"] == REL_PATH
        ]
        assert frontmatter_issues == []

    def test_fragment_without_date_is_still_flagged(self, isolated_data_dir: Path) -> None:
        from tools.maintenance.audit import run_audit

        month_dir = isolated_data_dir / "Journals" / "2026" / "03"
        month_dir.mkdir(parents=True, exist_ok=True)
        (month_dir / "life-index_2026-03-05_001.md").write_text(
            "---\ntitle: T\n---\n\nbody\n", encoding="utf-8"
        )

        audit = run_audit(data_dir=isolated_data_dir, domains=["frontmatter"])

        issue_ids = [issue["issue_id"] for issue in audit["issues"]]
        assert "frontmatter.missing_date:Journals/2026/03/life-index_2026-03-05_001.md" in (
            issue_ids
        )
        issue_types = {issue["type"] for issue in audit["issues"]}
        assert "missing_title" not in issue_types
        assert "missing_topic" not in issue_types


class TestSearchSurfaces:
    def test_cache_path_l2_result_carries_kind_and_label(self, untitled_archive: Archive) -> None:
        from tools.search_journals.l2_metadata import search_l2_metadata

        response = search_l2_metadata(date_from=DATE, date_to=DATE)

        assert len(response["results"]) == 1
        hit = response["results"][0]
        assert hit["title"] == ""
        assert hit["kind"] == "fragment"
        assert hit["display_label"] == LABEL

    def test_full_text_path_result_carries_kind_and_label(self, untitled_archive: Archive) -> None:
        from tools.search_journals.core import hierarchical_search

        response = hierarchical_search(query="uniquedisplaytoken", level=3)

        assert response["success"] is True
        merged = response["merged_results"]
        assert len(merged) == 1
        assert merged[0]["title"] == ""
        assert merged[0]["kind"] == "fragment"
        assert merged[0]["display_label"] == LABEL
        fts_hit = response["l3_results"][0]
        assert fts_hit["source"] == "fts_index"
        assert fts_hit["title"] == ""
        assert fts_hit["kind"] == "fragment"
        assert fts_hit["display_label"] == LABEL

    def test_fallback_content_scan_carries_kind_and_label(self, untitled_archive: Archive) -> None:
        from tools.search_journals.l3_content import search_l3_content

        results = search_l3_content("uniquedisplaytoken")

        assert len(results) == 1
        assert results[0]["title"] == ""
        assert results[0]["kind"] == "fragment"
        assert results[0]["display_label"] == LABEL

    def test_fts_result_without_cache_row_falls_back_to_file_name(
        self, untitled_archive: Archive
    ) -> None:
        from tools.lib.metadata_cache import get_display_labels_for_keys
        from tools.search_journals.utils import annotate_kind_and_display_label

        data_dir, path = untitled_archive
        missing_path = data_dir / "Journals" / "2026" / "03" / "life-index_2026-03-09_042.md"
        missing_path.parent.mkdir(parents=True, exist_ok=True)
        missing_path.write_text("---\ndate: 2026-03-09\n---\n\nbody\n", encoding="utf-8")

        assert get_display_labels_for_keys([str(missing_path).replace("\\", "/")]) == {}

        items = annotate_kind_and_display_label([{"path": str(missing_path)}])
        assert items[0]["kind"] == "fragment"
        assert items[0]["display_label"] == "life-index_2026-03-09_042"


class TestTimelineAndOnThisDay:
    def test_timeline_entry_carries_kind_and_label(self, untitled_archive: Archive) -> None:
        from tools.timeline.core import run_timeline

        result = run_timeline("2026-03", "2026-03")

        assert result["success"] is True
        assert len(result["entries"]) == 1
        entry = result["entries"][0]
        assert entry["title"] == ""
        assert entry["kind"] == "fragment"
        assert entry["display_label"] == LABEL

    def test_on_this_day_match_carries_kind_and_label(self, untitled_archive: Archive) -> None:
        from tools.on_this_day.core import run_on_this_day

        result = run_on_this_day(date_str="2027-03-04", years_back=1)

        assert result["success"] is True
        assert len(result["matches"]) == 1
        match = result["matches"][0]
        assert match["title"] == ""
        assert match["kind"] == "fragment"
        assert match["display_label"] == LABEL


class TestJournalList:
    def test_journal_list_item_carries_kind_and_label(self, untitled_archive: Archive) -> None:
        data_dir, _path = untitled_archive
        env = os.environ.copy()
        env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run(
            [sys.executable, "-m", "tools", "journal", "list", "--recent"],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            encoding="utf-8",
            cwd=str(PROJECT_ROOT),
        )
        assert proc.returncode == 0, proc.stderr

        payload = json.loads(proc.stdout)
        items = payload["data"]["items"]
        assert len(items) == 1
        assert items[0]["title"] == ""
        assert items[0]["kind"] == "fragment"
        assert items[0]["display_label"] == LABEL


class TestGeneratedIndexes:
    def test_month_index_prints_the_label(self, untitled_archive: Archive) -> None:
        from tools.generate_index import generate_monthly_index

        data_dir, _path = untitled_archive
        result = generate_monthly_index(year=2026, month=3)

        assert result["success"] is True
        content = (data_dir / "Journals" / "2026" / "03" / "index_2026-03.md").read_text(
            encoding="utf-8"
        )
        assert f"[{LABEL}]({FILENAME})" in content
        assert "无标题" not in content
        assert "未命名" not in content

    def test_by_topic_index_prints_the_label(self, untitled_archive: Archive) -> None:
        from tools.write_journal.index_updater import update_topic_index

        data_dir, path = untitled_archive
        updated = update_topic_index("life", path, {"date": DATE, "title": "", "content": BODY})

        assert updated, "by-topic index was not written"
        content = updated[0].read_text(encoding="utf-8")
        assert f"[{LABEL}](Journals/2026/03/{FILENAME})" in content
        assert "无标题" not in content

    def test_edit_writes_the_label_into_the_by_topic_line(self, untitled_archive: Archive) -> None:
        """Giving an untitled fragment a topic through edit prints its label, not a placeholder."""
        from tools.edit_journal import edit_journal
        from tools.lib.paths import get_by_topic_dir

        _data_dir, path = untitled_archive
        result = edit_journal(journal_path=path, frontmatter_updates={"topic": ["life"]})

        assert result["success"] is True, result
        index_text = "".join(
            index.read_text(encoding="utf-8") for index in get_by_topic_dir().glob("*life*.md")
        )
        assert f"[{LABEL}]({REL_PATH})" in index_text
        assert "无标题" not in index_text

    def test_navigation_index_entry_pointer_prints_the_label(
        self, untitled_archive: Archive
    ) -> None:
        from tools.index_tree.materialize import build_materialize_payload

        data_dir, _path = untitled_archive
        payload = build_materialize_payload(dry_run=False, incremental=False)

        assert payload["entry_count"] == 1
        month_doc = data_dir / ".life-index" / "index-b" / "Journals" / "2026" / "03" / "index.md"
        content = month_doc.read_text(encoding="utf-8")
        assert f"| {DATE} | {LABEL} | {REL_PATH} |" in content
