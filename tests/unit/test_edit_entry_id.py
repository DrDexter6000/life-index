#!/usr/bin/env python3
"""Tests for `edit` never changing a stored entry id (H1).

Setting, replacing, clearing or removing ``id`` through ``edit`` is refused
on every file; every other rewrite keeps the stored id byte-for-value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.edit_journal import edit_journal
from tools.fragment.core import add_fragment
from tools.fragment.note import add_note_to_fragment
from tools.lib.frontmatter import parse_frontmatter

EXPRESSED = "2026-11-12T15:02:10+01:00"
STORED_ID = "0123456789abcdef0123456789abcdef"


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    data = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data))
    return data


def _legacy_journal(data_dir: Path, *, with_id: bool = True) -> Path:
    month = data_dir / "Journals" / "2026" / "03"
    month.mkdir(parents=True, exist_ok=True)
    path = month / "life-index_2026-03-07_001.md"
    id_line = f'id: "{STORED_ID}"\n' if with_id else ""
    path.write_bytes(
        (
            "---\n"
            'title: "Legacy"\n'
            "date: 2026-03-07\n"
            'weather: "Sunny"\n'
            'location: "Test City"\n'
            f"{id_line}"
            "---\n\n"
            "Legacy body.\n"
        ).encode("utf-8")
    )
    return path


def _stored_id(path: Path) -> str | None:
    metadata, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return metadata.get("id")


class TestEditRefusesIdUpdates:
    def test_setting_id_on_a_legacy_journal_is_refused(self, data_dir):
        path = _legacy_journal(data_dir)
        before = path.read_bytes()

        result = edit_journal(path, {"id": "b" * 32})

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "id"
        assert path.read_bytes() == before

    @pytest.mark.parametrize("cleared", ["", None], ids=["empty-string", "null"])
    def test_clearing_or_removing_id_on_a_legacy_journal_is_refused(self, data_dir, cleared):
        path = _legacy_journal(data_dir)
        before = path.read_bytes()

        result = edit_journal(path, {"id": cleared})

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "id"
        assert path.read_bytes() == before

    def test_setting_id_to_the_same_value_is_refused_too(self, data_dir):
        path = _legacy_journal(data_dir)
        before = path.read_bytes()

        result = edit_journal(path, {"id": STORED_ID})

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert path.read_bytes() == before

    def test_setting_id_on_a_new_form_fragment_is_refused_with_E0505(self, data_dir):
        fragment = add_fragment({"text": "the user's words", "expressed_at": EXPRESSED})
        assert fragment["success"], fragment
        path = Path(fragment["journal_path"])
        before = path.read_bytes()

        result = edit_journal(path, {"id": "b" * 32})

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0505"
        assert result["error"]["details"]["field"] == "id"
        assert path.read_bytes() == before

    def test_clearing_id_on_a_new_form_fragment_is_refused_with_E0505(self, data_dir):
        fragment = add_fragment({"text": "the user's words", "expressed_at": EXPRESSED})
        assert fragment["success"], fragment
        path = Path(fragment["journal_path"])

        result = edit_journal(path, {"id": ""})

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0505"
        assert result["error"]["details"]["field"] == "id"

    def test_a_file_without_an_id_cannot_gain_one_through_edit(self, data_dir):
        path = _legacy_journal(data_dir, with_id=False)

        result = edit_journal(path, {"id": "b" * 32})

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "id"


class TestOtherRewritesKeepTheId:
    def test_an_ordinary_metadata_edit_keeps_the_id(self, data_dir):
        path = _legacy_journal(data_dir)

        result = edit_journal(path, {"weather": "Cloudy"})

        assert result["success"] is True, result
        assert _stored_id(path) == STORED_ID

    def test_a_content_edit_keeps_the_id(self, data_dir):
        path = _legacy_journal(data_dir)

        result = edit_journal(path, {}, replace_content="Rewritten body.")

        assert result["success"] is True, result
        assert result["content_modified"] is True
        assert _stored_id(path) == STORED_ID
        assert "Rewritten body." in path.read_text(encoding="utf-8")

    def test_a_fragment_note_keeps_the_id(self, data_dir):
        basis = add_fragment({"text": "he said Monday in the call", "expressed_at": EXPRESSED})
        target = add_fragment({"text": "meeting was on Monday", "expressed_at": EXPRESSED})
        assert basis["success"] and target["success"], (basis, target)

        note = add_note_to_fragment(
            {
                "path": target["rel_path"],
                "expect_id": target["id"],
                "text": "it was Tuesday, not Monday",
                "by": "host-agent",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
            }
        )
        assert note["success"], note
        assert _stored_id(Path(target["journal_path"])) == target["id"]

    def test_a_migration_keeps_a_stored_id(self, data_dir):
        from tools.migrate import apply_migrations

        # The fixture carries no schema_version (read as v1), so the
        # migration has chain work to do; the stored id rides along untouched.
        path = _legacy_journal(data_dir)

        result = apply_migrations(data_dir / "Journals")

        assert result["failed_count"] == 0, result
        assert result["migrated_count"] == 1
        assert _stored_id(path) == STORED_ID
