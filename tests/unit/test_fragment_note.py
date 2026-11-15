#!/usr/bin/env python3
"""Unit tests for `fragment note` (tools/fragment/note.py, tools/lib/fragment_notes.py).

Every test runs against a temporary LIFE_INDEX_DATA_DIR; the real user data
directory is never touched. The numbered groups map to the work package's
required coverage:

1.  first note: byte-exact stored form across line-ending shapes;
2.  an original text that already contains a fake note block stays original;
3.  second and third notes; order kept; region stays well-formed;
4.  every refusal leaves the bytes unchanged and no temp file;
5.  replay: same input writes once; a different by/basis writes a new note;
6.  readers: headers, by, ids and quotes never leak; the corrected word is
    found where it must be;
7.  malformed region: original still returned, flagged, refused;
8.  `edit` and `migrate` on a file with notes;
9.  concurrency: two note processes both land; note against edit loses neither;
10. the guards are load-bearing (paired sabotage tests pin each one).
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools.edit_journal import edit_journal
from tools.entity.candidate_edges import extract_candidates_from_wikilinks
from tools.fragment.core import add_fragment
from tools.fragment.note import add_note_to_fragment
from tools.journal.__main__ import run_journal_get
from tools.lib.fragment_notes import (
    boundary_of,
    find_notes_region,
    insert_boundary_line,
    note_marker_prefix,
    render_note_block,
    split_fragment_notes,
    split_suffix_region,
)
from tools.lib.frontmatter import parse_frontmatter, parse_journal_file
from tools.lib.journal_rewrite import split_journal_bytes
from tools.maintenance.audit import _attachment_refs, _detect_links
from tools.verify.core import run_verify

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPRESSED = "2026-11-12T15:02:10+01:00"
HEX32 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    data = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data))
    return data


def _fragment(text="meeting was on Monday", expressed=EXPRESSED, **extra):
    result = add_fragment({"text": text, "expressed_at": expressed, **extra})
    assert result["success"], result
    return result


def _note(target, text, basis, by="host-agent", expect_id="auto", quote=None, **extra):
    """expect_id="auto" sends the target's own id; None omits the key."""
    payload = {"path": target["rel_path"], "text": text, "by": by}
    if expect_id == "auto":
        expect_id = target.get("id")
    if expect_id is not None:
        payload["expect_id"] = expect_id
    if quote is None:
        quote = "he said Monday"
    payload["based_on"] = [{"path": basis["rel_path"], "quote": quote}]
    payload.update(extra)
    return add_note_to_fragment(payload)


def _basis(data_dir):
    """A second fragment whose original text carries the quote used below."""
    return _fragment(text="he said Monday in the call", expressed="2026-11-12T16:02:10+01:00")


def _write_bytes(data_dir: Path, name: str, block_lines, suffix: bytes, join="\n") -> Path:
    """Hand-craft a fragment file: block lines + raw suffix bytes."""
    month = data_dir / "Journals" / "2026" / "11"
    month.mkdir(parents=True, exist_ok=True)
    block = join.join(block_lines) + join
    path = month / name
    path.write_bytes(block.encode("utf-8") + suffix)
    return path


def _rel(path: Path) -> str:
    return "Journals/2026/11/" + path.name


def _split(path: Path):
    raw = path.read_bytes()
    metadata, body = parse_frontmatter(raw.decode("utf-8"))
    return raw, metadata, body, split_fragment_notes(metadata, body)


def _no_temp_files(month_dir: Path) -> bool:
    return not [p for p in month_dir.iterdir() if ".tmp" in p.name or p.name.startswith(".")]


def _parse_cli_json(text: str):
    """Parse the JSON payload from CLI stdout (tokenizer noise may precede it)."""
    decoder = json.JSONDecoder()
    return decoder.raw_decode(text[text.index("{") :])[0]


# ---------------------------------------------------------------------------
# 1. First note: the exact stored bytes, across line-ending shapes
# ---------------------------------------------------------------------------


class TestFirstNoteBytes:
    def _assert_first_note_shape(self, data_dir, path, basis, expect_id=None):
        old = path.read_bytes()
        old_split = split_journal_bytes(old)
        assert old_split is not None
        payload = {
            "path": _rel(path),
            "text": "It was Tuesday, not Monday",
            "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
            "by": "host-agent",
        }
        if expect_id is not None:
            payload["expect_id"] = expect_id
        result = add_note_to_fragment(payload)
        assert result["success"], result
        new = path.read_bytes()
        new_split = split_journal_bytes(new)
        assert new_split is not None

        # (b) the old suffix is a byte prefix of the new suffix.
        assert new_split.suffix.startswith(old_split.suffix)

        # (a) the new block is the old block with exactly one inserted line.
        assert new_split.frontmatter_block != old_split.frontmatter_block
        old_stripped = (
            old_split.frontmatter_block[:-1]
            if old_split.frontmatter_block.endswith(b"\n")
            else old_split.frontmatter_block
        )
        new_stripped = (
            new_split.frontmatter_block[:-1]
            if new_split.frontmatter_block.endswith(b"\n")
            else new_split.frontmatter_block
        )
        old_head, _old_close = old_stripped.rsplit(b"\n", 1)
        new_head, _new_close = new_stripped.rsplit(b"\n", 1)
        assert new_head.startswith(old_head + b"\n")
        inserted = new_head[len(old_head) + 1 :] + b"\n"
        assert inserted.count(b"\n") == 1

        # the reader's metadata gained exactly notes_boundary (a valid one)
        old_metadata, _old_body = parse_frontmatter(old.decode("utf-8"))
        new_metadata, _new_body = parse_frontmatter(new.decode("utf-8"))
        boundary = new_metadata.get("notes_boundary")
        assert isinstance(boundary, str) and HEX32.fullmatch(boundary)
        assert set(new_metadata) == set(old_metadata) | {"notes_boundary"}
        for key, value in old_metadata.items():
            assert new_metadata[key] == value

        # the appended region: separator per the rule, then the note block
        appended = new_split.suffix[len(old_split.suffix) :]
        separator = b"\n" if old.endswith(b"\n") else b"\n\n"
        assert appended.startswith(separator)
        block = appended[len(separator) :]
        assert block.startswith(
            f"<!-- life-index:note {boundary} ".encode("utf-8")
        ), "the note block must follow the marker grammar"
        assert block.endswith(f"<!-- /life-index:note {boundary} -->\n".encode("utf-8"))
        assert b"\r" not in block, "the notes region is LF only"

        # the reader keeps the original text and sees exactly one note
        _raw, _metadata, _body, notes_split = _split(path)
        assert notes_split.original_text == parse_frontmatter(old.decode("utf-8"))[1]
        assert len(notes_split.notes) == 1
        assert notes_split.notes[0].text == "It was Tuesday, not Monday"
        assert not notes_split.malformed

    def test_lf_fragment_from_add(self, data_dir):
        target = _fragment()
        self._assert_first_note_shape(
            data_dir, Path(target["journal_path"]), _basis(data_dir), expect_id=target["id"]
        )

    def test_lf_hand_written(self, data_dir):
        basis = _basis(data_dir)
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "title: plain", "---", "", "meeting was on Monday"],
            b"",
        )
        self._assert_first_note_shape(data_dir, path, basis)

    def test_crlf_file(self, data_dir):
        basis = _basis(data_dir)
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "---", "", "meeting was on Monday"],
            b"",
            join="\r\n",
        )
        old = path.read_bytes()
        self._assert_first_note_shape(data_dir, path, basis)
        new = path.read_bytes()
        # the inserted line uses the closing delimiter's line ending (CRLF)
        new_split = split_journal_bytes(new)
        boundary = parse_frontmatter(new.decode("utf-8"))[0]["notes_boundary"]
        line = f'notes_boundary: "{boundary}"\r\n'.encode("utf-8")
        assert line in new_split.frontmatter_block
        assert b"\r\n" in new_split.suffix.split(b"<!-- life-index:note")[0]
        assert old.split(b"---\r\n")[-1] in new  # original bytes ride along verbatim

    def test_mixed_line_endings(self, data_dir):
        basis = _basis(data_dir)
        month = data_dir / "Journals" / "2026" / "11"
        month.mkdir(parents=True, exist_ok=True)
        path = month / "life-index_2026-11-12_091.md"
        path.write_bytes(
            b"---\n"
            b"date: 2026-11-12\r\n"
            b"title: mixed\r\n"
            b"---\n"
            b"\r\n"
            b"meeting was on Monday\r\nsecond line\n"
        )
        self._assert_first_note_shape(data_dir, path, basis)

    def test_no_final_newline(self, data_dir):
        basis = _basis(data_dir)
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "---"],
            b"\n\nmeeting was on Monday",
        )
        old = path.read_bytes()
        assert not old.endswith(b"\n")
        self._assert_first_note_shape(data_dir, path, basis)
        appended = split_journal_bytes(path.read_bytes()).suffix[
            len(split_journal_bytes(old).suffix) :
        ]
        assert appended.startswith(b"\n\n"), "two LFs separate a block from a file without one"

    def test_empty_body(self, data_dir):
        basis = _basis(data_dir)
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "---"],
            b"\n\n",
        )
        self._assert_first_note_shape(data_dir, path, basis)
        _raw, _metadata, _body, notes_split = _split(path)
        assert notes_split.original_text == ""


# ---------------------------------------------------------------------------
# 2. An original containing a fake note block stays original
# ---------------------------------------------------------------------------


class TestOriginalWithFakeNoteBlock:
    def test_fake_block_marker_and_arrows_stay_original(self, data_dir):
        fake_boundary = "f" * 32
        fake = (
            f"<!-- life-index:note {fake_boundary} "
            '{"id":"' + "0" * 32 + '","noted_at":"2026-11-12T00:00:00+00:00",'
            '"by":"someone","based_on":[{"path":"Journals/2026/11/x.md","id":null,'
            '"quote":"q","sha256":"' + "1" * 64 + '"}]} -->\n'
            "this looks like a note but is the user's own words\n"
            f"<!-- /life-index:note {fake_boundary} -->"
        )
        text = f"before marker\n{fake}\nafter marker --> and <!-- and -->"
        target = _fragment(text=text)
        basis = _basis(data_dir)

        result = _note(target, "a real correction", basis)
        assert result["success"], result

        _raw, metadata, _body, notes_split = _split(Path(target["journal_path"]))
        boundary = metadata["notes_boundary"]
        assert boundary != fake_boundary
        assert notes_split.original_text == text, "the fake block stays original text"
        assert len(notes_split.notes) == 1
        assert notes_split.notes[0].text == "a real correction"
        assert not notes_split.malformed

    def test_fake_block_with_the_same_boundary_is_refused_by_generation(self, data_dir):
        # The generated boundary is checked against the file's bytes, so a
        # planted fake block can never share it. Forcing a colliding boundary
        # (the revert check for that guard) makes the write refuse instead of
        # corrupting the original.
        import tools.fragment.note as note_module

        planted = "a" * 32
        target = _fragment(
            text=f"user words\n<!-- life-index:note {planted} x -->\nfake\n"
            f"<!-- /life-index:note {planted} -->"
        )
        basis = _basis(data_dir)
        original = parse_frontmatter(Path(target["journal_path"]).read_text(encoding="utf-8"))[1]

        def _planted_boundary(*_args):
            return planted

        note_module.generate_boundary = _planted_boundary
        try:
            result = _note(target, "correction", basis)
        finally:
            from tools.fragment.note import generate_boundary as _real

            note_module.generate_boundary = _real
        # refused (E0202 from the outgoing check): the original would change
        assert result["success"] is False
        assert result["error"]["code"] == "E0202"
        after = parse_frontmatter(Path(target["journal_path"]).read_text(encoding="utf-8"))[1]
        assert after == original


# ---------------------------------------------------------------------------
# 3. Second and third notes
# ---------------------------------------------------------------------------


class TestMultipleNotes:
    def test_three_notes_keep_order_and_grammar(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        first = _note(target, "first correction", basis, by="a")
        second = _note(target, "second correction", basis, by="b")
        third = _note(target, "third correction", basis, by="c")
        for r in (first, second, third):
            assert r["success"], r
        assert (first["notes_count"], second["notes_count"], third["notes_count"]) == (1, 2, 3)

        _raw, _metadata, _body, notes_split = _split(Path(target["journal_path"]))
        assert [n.text for n in notes_split.notes] == [
            "first correction",
            "second correction",
            "third correction",
        ]
        assert [n.by for n in notes_split.notes] == ["a", "b", "c"]
        assert not notes_split.malformed
        raw = Path(target["journal_path"]).read_bytes()
        region = raw.decode("utf-8")
        # blocks separated by exactly one blank line
        marker = "\n<!-- life-index:note "
        assert region.count("\n\n<!-- life-index:note ") == 3
        assert marker in region


# ---------------------------------------------------------------------------
# 4. Refusals: bytes unchanged, no temp file
# ---------------------------------------------------------------------------


class TestRefusals:
    def _refused(self, data_dir, payload, code, reason=None):
        target = _fragment()
        basis = _basis(data_dir)
        path = Path(target["journal_path"])
        before = path.read_bytes()
        base = {
            "path": target["rel_path"],
            "expect_id": target["id"],
            "text": "correction",
            "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
            "by": "host-agent",
        }
        base.update(payload)
        if base.get("expect_id") is None:
            base.pop("expect_id", None)
        result = add_note_to_fragment(base)
        assert result["success"] is False, result
        assert result["error"]["code"] == code, result
        if reason is not None:
            assert result["error"]["details"].get("reason") == reason, result["error"]
        assert path.read_bytes() == before, "a refusal must not change one byte"
        assert _no_temp_files(path.parent)
        return result

    def test_unknown_top_level_key(self, data_dir):
        self._refused(data_dir, {"unknown_key": 1}, "E0001")

    def test_missing_text(self, data_dir):
        self._refused(data_dir, {"text": None}, "E0001")

    def test_blank_text(self, data_dir):
        self._refused(data_dir, {"text": "   "}, "E0001")

    def test_multiline_by(self, data_dir):
        self._refused(data_dir, {"by": "two\nlines"}, "E0001")

    def test_blank_by(self, data_dir):
        self._refused(data_dir, {"by": "  "}, "E0001")

    def test_bad_noted_at(self, data_dir):
        self._refused(data_dir, {"noted_at": "2026-11-12 15:00"}, "E0001")

    def test_noted_at_without_offset(self, data_dir):
        self._refused(data_dir, {"noted_at": "2026-11-12T15:00:00"}, "E0001")

    def test_absolute_path(self, data_dir):
        self._refused(data_dir, {"path": "/etc/passwd"}, "E0001")

    def test_traversal_path(self, data_dir):
        self._refused(data_dir, {"path": "Journals/2026/11/../../../x.md"}, "E0001")

    def test_non_fragment_name(self, data_dir):
        self._refused(data_dir, {"path": "Journals/2026/11/digest_x.md"}, "E0001")

    def test_revisions_path(self, data_dir):
        self._refused(
            data_dir,
            {"path": "Journals/2026/11/.revisions/life-index_2026-11-12_001.md"},
            "E0001",
        )

    def test_nonexistent_target(self, data_dir):
        target = _fragment()
        result = add_note_to_fragment(
            {
                "path": "Journals/2026/11/life-index_2020-01-01_001.md",
                "text": "x",
                "based_on": [{"path": target["rel_path"], "quote": "meeting"}],
                "by": "host-agent",
            }
        )
        assert result["error"]["code"] == "E0500"

    def test_symlink_target(self, data_dir, tmp_path_factory):
        target = _fragment()
        basis = _basis(data_dir)
        outside = tmp_path_factory.mktemp("outside") / "link.md"
        outside.write_bytes(Path(target["journal_path"]).read_bytes())
        month = Path(target["journal_path"]).parent
        link = month / "life-index_2026-11-12_099.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):  # pragma: no cover - platform
            pytest.skip("symlinks unavailable on this platform")
        result = add_note_to_fragment(
            {
                "path": _rel(link),
                "text": "x",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
                "by": "host-agent",
            }
        )
        assert result["error"]["code"] == "E0001"

    def test_expect_id_required_when_target_has_id(self, data_dir):
        self._refused(data_dir, {"expect_id": None}, "E0208", reason="expect_id_required")

    def test_expect_id_mismatch(self, data_dir):
        self._refused(data_dir, {"expect_id": "0" * 32}, "E0208", reason="expect_id_mismatch")

    def test_expect_id_on_target_without_id(self, data_dir):
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "---"],
            b"\n\nlegacy words",
        )
        basis = _basis(data_dir)
        result = add_note_to_fragment(
            {
                "path": _rel(path),
                "expect_id": "0" * 32,
                "text": "x",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
                "by": "host-agent",
            }
        )
        assert result["error"]["code"] == "E0208"
        assert result["error"]["details"]["reason"] == "expect_id_unexpected"

    def test_basis_id_mismatch(self, data_dir):
        self._refused(
            data_dir,
            {
                "based_on": [
                    {
                        "path": _basis(data_dir)["rel_path"],
                        "id": "0" * 32,
                        "quote": "he said Monday",
                    }
                ]
            },
            "E0208",
            reason="basis_id_mismatch",
        )

    def test_quote_not_in_original(self, data_dir):
        self._refused(
            data_dir,
            {"based_on": [{"path": _basis(data_dir)["rel_path"], "quote": "not there"}]},
            "E0208",
            reason="quote_not_found",
        )

    def test_quote_empty(self, data_dir):
        self._refused(
            data_dir, {"based_on": [{"path": _basis(data_dir)["rel_path"], "quote": ""}]}, "E0001"
        )

    def test_basis_unknown_key(self, data_dir):
        self._refused(
            data_dir,
            {
                "based_on": [
                    {"path": _basis(data_dir)["rel_path"], "quote": "he said Monday", "why": "x"}
                ]
            },
            "E0001",
        )

    def test_based_on_empty(self, data_dir):
        self._refused(data_dir, {"based_on": []}, "E0001")

    def test_based_on_not_a_list(self, data_dir):
        self._refused(data_dir, {"based_on": {"path": "x"}}, "E0001")

    def test_basis_nonexistent(self, data_dir):
        self._refused(
            data_dir,
            {"based_on": [{"path": "Journals/2026/11/life-index_2020-01-01_009.md", "quote": "x"}]},
            "E0500",
        )

    def test_quote_in_note_text_is_not_original(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first note words", basis)["success"]
        # the quote must occur in a basis ORIGINAL text; a note text is not one
        other = _fragment()
        assert _note(other, "quoted elsewhere", basis)["success"]
        result = _note(target, "second", other, quote="quoted elsewhere")
        assert result["error"]["code"] == "E0208"
        assert result["error"]["details"]["reason"] == "quote_not_found"

    def test_text_containing_boundary_refused(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first", basis)["success"]
        boundary = parse_frontmatter(Path(target["journal_path"]).read_text(encoding="utf-8"))[0][
            "notes_boundary"
        ]
        result = _note(target, f"contains {boundary} inside", basis)
        assert result["error"]["code"] == "E0001"

    def test_target_without_frontmatter_block(self, data_dir):
        month = data_dir / "Journals" / "2026" / "11"
        month.mkdir(parents=True, exist_ok=True)
        path = month / "life-index_2026-11-12_091.md"
        path.write_bytes("no frontmatter here\n".encode("utf-8"))
        basis = _basis(data_dir)
        result = add_note_to_fragment(
            {
                "path": _rel(path),
                "text": "x",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
                "by": "host-agent",
            }
        )
        assert result["error"]["code"] == "E0202"
        assert result["error"]["details"]["reason"] == "no_frontmatter_block"

    def test_target_unreadable_frontmatter(self, data_dir):
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "- a", "- b", "---"],
            b"\n\nbody",
        )
        basis = _basis(data_dir)
        result = add_note_to_fragment(
            {
                "path": _rel(path),
                "text": "x",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
                "by": "host-agent",
            }
        )
        assert result["error"]["code"] == "E0202"
        assert result["error"]["details"]["reason"] == "unreadable"

    def test_lock_timeout(self, data_dir, monkeypatch):
        from tools.lib.file_lock import FileLock, get_journals_lock_path

        target = _fragment()
        basis = _basis(data_dir)
        monkeypatch.setattr("tools.fragment.note.FILE_LOCK_TIMEOUT_DEFAULT", 0.05)
        with FileLock(get_journals_lock_path(), timeout=30.0):
            result = _note(target, "blocked", basis)
        assert result["error"]["code"] == "E0005"


# ---------------------------------------------------------------------------
# 5. Replay
# ---------------------------------------------------------------------------


class TestReplay:
    def test_same_input_writes_once(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        first = _note(target, "It was Tuesday", basis)
        assert first["success"] and first["deduplicated"] is False
        path = Path(target["journal_path"])
        bytes_after_first = path.read_bytes()
        mtime_after_first = path.stat().st_mtime_ns

        time.sleep(0.01)
        second = _note(target, "It was Tuesday", basis)
        assert second["success"] is True
        assert second["deduplicated"] is True
        assert second["note"] == first["note"], "the stored note's real fields come back"
        assert second["notes_count"] == 1
        assert path.read_bytes() == bytes_after_first
        assert path.stat().st_mtime_ns == mtime_after_first

    def test_replay_refreshes_derived_rows(self, data_dir, monkeypatch):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "It was Tuesday", basis)["success"]

        from tools.lib import metadata_cache

        conn = metadata_cache.init_metadata_cache()
        try:
            metadata_cache.invalidate_cache(Path(target["journal_path"]))
        finally:
            conn.close()

        second = _note(target, "It was Tuesday", basis)
        assert second["deduplicated"] is True
        cache = metadata_cache.get_or_update_metadata(Path(target["journal_path"]))
        assert cache is not None, "a replay heals a failed cache row"

    def test_different_by_is_another_note(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "It was Tuesday", basis, by="a")["success"]
        result = _note(target, "It was Tuesday", basis, by="b")
        assert result["success"] is True and result["deduplicated"] is False
        assert result["notes_count"] == 2

    def test_different_basis_is_another_note(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        other = _fragment(text="other basis words", expressed="2026-11-12T17:02:10+01:00")
        assert _note(target, "It was Tuesday", basis)["success"]
        result = _note(target, "It was Tuesday", other, quote="other basis words")
        assert result["success"] is True and result["deduplicated"] is False
        assert result["notes_count"] == 2

    def test_different_quote_is_another_note(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "It was Tuesday", basis, quote="he said Monday")["success"]
        result = _note(target, "It was Tuesday", basis, quote="in the call")
        assert result["deduplicated"] is False


# ---------------------------------------------------------------------------
# 6. Readers
# ---------------------------------------------------------------------------


class TestReaders:
    @pytest.fixture()
    def noted(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "It was Tuesday, not Monday", basis)["success"]
        assert _note(target, "room was B2", basis, by="user")["success"]
        return target, basis

    def test_journal_get(self, data_dir, noted):
        target, _basis_frag = noted
        got = run_journal_get(path=target["rel_path"])["data"]
        assert got["content"] == "meeting was on Monday"
        assert [n["text"] for n in got["notes"]] == ["It was Tuesday, not Monday", "room was B2"]
        assert all(n["by"] and n["id"] and n["noted_at"] for n in got["notes"])
        assert "notes_malformed" not in got
        # word count from the original only
        from tools.lib.chinese_tokenizer import count_cjk_words

        assert got["word_count"] == count_cjk_words("meeting was on Monday")

    def test_journal_list_word_count_and_label(self, data_dir, noted):
        target, _basis_frag = noted
        from tools.journal.__main__ import _journal_summary

        summary = _journal_summary(Path(target["journal_path"]))
        assert summary["word_count"] == 4, "word count from the original text only"
        assert summary["display_label"] == "meeting was on Monday"
        assert "Tuesday" not in summary["display_label"]

    def test_metadata_cache_row(self, data_dir, noted):
        target, _basis_frag = noted
        from tools.lib.metadata_cache import upsert_journal_cache_row

        row = upsert_journal_cache_row(Path(target["journal_path"]), data_dir / "Journals")
        assert row is not None
        from tools.lib.chinese_tokenizer import count_cjk_words

        assert row["word_count"] == count_cjk_words("meeting was on Monday")
        assert row["display_label"] == "meeting was on Monday"

    def test_fts_indexes_note_text_not_headers(self, data_dir, noted):
        target, _basis_frag = noted
        from tools.lib.fts_update import read_journal_document

        doc, _signature, unparsable = read_journal_document(
            Path(target["journal_path"]), data_dir / "Journals", data_dir
        )
        assert not unparsable
        content = doc["content"]
        assert "Tuesday" in content and "B2" in content
        for leaked in ("host-agent", "sha256", "he said Monday", "life-index:note"):
            assert leaked not in content, f"{leaked} leaked into the FTS row"

    def test_fts_search_finds_corrected_word(self, data_dir, noted):
        target, _basis_frag = noted
        from tools.search_journals.core import hierarchical_search

        def paths(query):
            result = hierarchical_search(query=query, level=3)
            return [Path(m.get("path", "")).as_posix() for m in result.get("merged_results", [])]

        assert any(p.endswith(target["rel_path"]) for p in paths("Tuesday"))
        assert any(p.endswith(target["rel_path"]) for p in paths("B2"))
        assert any(p.endswith(target["rel_path"]) for p in paths("Monday"))
        assert not any(p.endswith(target["rel_path"]) for p in paths("host-agent"))
        assert not any(p.endswith(target["rel_path"]) for p in paths("sha256"))

    def test_l3_content_search(self, data_dir):
        # two hits clear L3's fallback relevance floor; the note text is
        # searched exactly like the original text
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(
            target, "It was Tuesday, not Monday." + chr(10) + "The Tuesday session", basis
        )["success"]
        from tools.search_journals.l3_content import search_l3_content

        hits = search_l3_content("Tuesday")
        match = next(h for h in hits if h.get("rel_path") == target["rel_path"])
        assert match["display_label"] == "meeting was on Monday"
        contexts = " ".join(m["context"] for m in match["body_matches"])
        assert "Tuesday" in contexts
        assert "host-agent" not in contexts

        # by/headers are never searchable text: not even a direct hit
        assert not search_l3_content("host-agent")
        assert not search_l3_content("sha256")

    def test_index_tree_content_terms(self, data_dir, noted):
        target, _basis_frag = noted
        from tools.index_tree.core import _content_text
        from tools.index_tree.materialize import IndexBEntry

        entry = IndexBEntry(
            rel_path=target["rel_path"],
            year="2026",
            month="11",
            date="2026-11-12",
            title="",
            display_label="meeting was on Monday",
            metadata={},
        )
        text = _content_text(entry)
        assert "Tuesday" in text and "B2" in text
        assert "life-index:note" not in text
        assert "host-agent" not in text

    def test_index_tree_materialize_label(self, data_dir, noted):
        target, _basis_frag = noted
        from tools.index_tree.materialize import _collect_entries_with_scan

        entries, facts = _collect_entries_with_scan("2026-01", "2026-12")
        assert facts["scanned"]
        match = next(e for e in entries if e.rel_path == target["rel_path"])
        assert match.display_label == "meeting was on Monday"

    def test_aggregate_body_carries_note_text(self, data_dir, noted):
        target, _basis_frag = noted
        from tools.aggregate.core import _parse_journal_file
        from datetime import date

        entry, outcome = _parse_journal_file(
            Path(target["journal_path"]),
            date(2026, 1, 1),
            date(2026, 12, 31),
            data_dir / "Journals",
        )
        assert outcome == "parsed"
        assert entry is not None
        assert "Tuesday" in entry["body"] and "B2" in entry["body"]
        assert "life-index:note" not in entry["body"]
        assert "host-agent" not in entry["body"]

    def test_search_read_top(self, data_dir, noted):
        target, _basis_frag = noted
        env = dict(os.environ)
        env["LIFE_INDEX_DATA_DIR"] = str(data_dir)
        env["PYTHONUTF8"] = "1"
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.search_journals",
                "--query",
                "Monday",
                "--level",
                "3",
                "--read-top",
                "5",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        payload = _parse_cli_json(proc.stdout)
        top = [
            item
            for item in payload.get("merged_results", [])
            if str(item.get("path", "")).replace("\\", "/").endswith(target["rel_path"])
        ]
        assert top, "the noted fragment must be among the results"
        item = top[0]
        assert item["full_content"] == "meeting was on Monday"
        assert [n["text"] for n in item["notes"]] == ["It was Tuesday, not Monday", "room was B2"]
        assert "notes_malformed" not in item

    def test_fragment_add_dedupe_compares_original_only(self, data_dir):
        keyed = add_fragment(
            {
                "text": "unique words for dedupe",
                "expressed_at": EXPRESSED,
                "source": {"channel": "chat", "message_id": "m1"},
            }
        )
        assert keyed["success"]
        basis = _basis(data_dir)
        assert _note(keyed, "corrected words", basis)["success"]

        retry = add_fragment(
            {
                "text": "unique words for dedupe",
                "expressed_at": EXPRESSED,
                "source": {"channel": "chat", "message_id": "m1"},
            }
        )
        assert retry["success"] is True
        assert retry["deduplicated"] is True, "notes never take part in the comparison"

        conflict = add_fragment(
            {
                "text": "unique words for dedupe, changed",
                "expressed_at": EXPRESSED,
                "source": {"channel": "chat", "message_id": "m1"},
            }
        )
        assert conflict["success"] is False
        assert conflict["error"]["code"] == "E0206"

        # the note's own text is not the stored body either
        as_body = add_fragment(
            {
                "text": "corrected words",
                "expressed_at": EXPRESSED,
                "source": {"channel": "chat", "message_id": "m1"},
            }
        )
        assert as_body["success"] is False
        assert as_body["error"]["code"] == "E0206"

    def test_entity_candidates_original_only(self, data_dir):
        target = _fragment(text="plans for [[ProjectX]] soon")
        basis = _basis(data_dir)
        assert _note(target, "[[WrongEntity]] belongs to the note", basis)["success"]
        journals = [parse_journal_file(Path(target["journal_path"]))]
        candidates = extract_candidates_from_wikilinks(journals, data_dir / "Journals")
        targets = {c["target"] for c in candidates}
        assert "ProjectX" in targets
        assert "WrongEntity" not in targets

    def test_verify_attachment_scan_original_only(self, data_dir):
        month = data_dir / "Journals" / "2026" / "11"
        month.mkdir(parents=True, exist_ok=True)
        target = _fragment(text="see ![photo](attachments/2026/11/real.jpg)")
        basis = _basis(data_dir)
        assert _note(target, "also ![other](attachments/2026/11/note.jpg)", basis)["success"]
        from tools.verify.core import run_verify as _rv

        result = _rv()
        attachment_issues = next(c for c in result["checks"] if c["name"] == "attachment_refs")
        assert attachment_issues["status"] == "warning"
        assert len(attachment_issues["issues"]) == 1, "only the original's reference counts"
        assert "real.jpg" in attachment_issues["issues"][0]
        assert not any("note.jpg" in i for i in attachment_issues["issues"])

    def test_maintenance_audit_original_only(self, data_dir):
        target = _fragment(text="look at [the plan](Journals/2026/11/missing-target.md)")
        basis = _basis(data_dir)
        assert _note(target, "note link [broken](Journals/2026/11/note-only.md)", basis)["success"]
        issues = _detect_links(data_dir)
        evidence = [i["issue_id"] for i in issues]
        assert any(target["rel_path"] in p for p in evidence), "the original's link is audited"
        assert not any("note-only.md" in p for p in evidence), "note links are not audited"

    def test_maintenance_attachment_refs_original_only(self, data_dir):
        target = _fragment(text="![real](attachments/2026/11/real.jpg)")
        basis = _basis(data_dir)
        assert _note(target, "![note](attachments/2026/11/note.jpg)", basis)["success"]
        refs = _attachment_refs(data_dir)
        assert any("real.jpg" in r for r in refs)
        assert not any("note.jpg" in r for r in refs)

    def test_timeline_label_from_original(self, data_dir, noted):
        target, _basis_frag = noted
        from tools.timeline.core import run_timeline

        result = run_timeline("2026-11", "2026-11")
        entry = next(
            e for e in result["entries"] if e["path"].replace("\\", "/") == target["rel_path"]
        )
        assert entry["display_label"] == "meeting was on Monday"


# ---------------------------------------------------------------------------
# 7. Malformed notes region
# ---------------------------------------------------------------------------


def _damage(path: Path, how: str) -> None:
    raw = path.read_bytes().decode("utf-8")
    boundary = parse_frontmatter(raw)[0]["notes_boundary"]
    close = f"<!-- /life-index:note {boundary} -->"
    lines = raw.split("\n")
    if how == "truncate":
        # remove the close line of the last block
        for index in range(len(lines) - 1, -1, -1):
            if lines[index] == close:
                del lines[index]
                break
    elif how == "wrong_close_boundary":
        for index in range(len(lines) - 1, -1, -1):
            if lines[index] == close:
                lines[index] = f"<!-- /life-index:note {'0' * 32} -->"
                break
    elif how == "junk_between":
        first_close = next(i for i, line in enumerate(lines) if line == close)
        lines.insert(first_close + 1, "junk line between blocks")
    else:  # pragma: no cover
        raise ValueError(how)
    path.write_bytes("\n".join(lines).encode("utf-8"))


class TestMalformedRegion:
    @pytest.mark.parametrize("how", ["truncate", "wrong_close_boundary", "junk_between"])
    def test_original_still_returned_and_flagged(self, data_dir, how):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first note", basis)["success"]
        assert _note(target, "second note", basis, by="user")["success"]
        path = Path(target["journal_path"])
        _damage(path, how)

        _raw, _metadata, _body, notes_split = _split(path)
        assert notes_split.original_text == "meeting was on Monday"
        assert notes_split.malformed is True

    @pytest.mark.parametrize("how", ["truncate", "wrong_close_boundary", "junk_between"])
    def test_journal_get_flags_malformed(self, data_dir, how):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first note", basis)["success"]
        assert _note(target, "second note", basis, by="user")["success"]
        _damage(Path(target["journal_path"]), how)
        got = run_journal_get(path=target["rel_path"])["data"]
        assert got["content"] == "meeting was on Monday"
        assert got["notes_malformed"] is True

    @pytest.mark.parametrize("how", ["truncate", "wrong_close_boundary", "junk_between"])
    def test_verify_reports_it(self, data_dir, how):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first note", basis)["success"]
        assert _note(target, "second note", basis, by="user")["success"]
        path = Path(target["journal_path"])
        _damage(path, how)
        result = run_verify()
        frontmatter = next(c for c in result["checks"] if c["name"] == "frontmatter_valid")
        assert frontmatter["status"] == "warning"
        assert any("malformed notes region" in i for i in frontmatter["issues"])
        # six checks: the five historical ones plus the entry_ids identity check
        assert len(result["checks"]) == 6, "no new check slot: folded into frontmatter_valid"

    def test_well_formed_region_is_not_an_issue(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "fine", basis)["success"]
        result = run_verify()
        assert result["success"] is True
        frontmatter = next(c for c in result["checks"] if c["name"] == "frontmatter_valid")
        assert not any("notes region" in i for i in frontmatter["issues"])

    @pytest.mark.parametrize("how", ["truncate", "wrong_close_boundary", "junk_between"])
    def test_fragment_note_refuses_after_damage(self, data_dir, how):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first note", basis)["success"]
        assert _note(target, "second note", basis, by="user")["success"]
        path = Path(target["journal_path"])
        _damage(path, how)
        before = path.read_bytes()
        result = _note(target, "third note", basis)
        assert result["error"]["code"] == "E0209"
        assert path.read_bytes() == before
        assert _no_temp_files(path.parent)


# ---------------------------------------------------------------------------
# 8. edit and migrate with notes
# ---------------------------------------------------------------------------


class TestEditAndMigrateWithNotes:
    @pytest.fixture()
    def noted(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "It was Tuesday", basis)["success"]
        return target

    def test_metadata_edit_keeps_boundary_and_region(self, data_dir, noted):
        path = Path(noted["journal_path"])
        before = path.read_bytes()
        suffix_before = split_journal_bytes(before).suffix
        result = edit_journal(path, {"weather": "sunny"})
        assert result["success"], result
        after = path.read_bytes()
        assert split_journal_bytes(after).suffix == suffix_before, "region rides along verbatim"
        metadata, body = parse_frontmatter(after.decode("utf-8"))
        assert metadata["notes_boundary"]
        assert split_fragment_notes(metadata, body).original_text == "meeting was on Monday"

    def test_migrate_keeps_boundary_and_region(self, data_dir, noted):
        from tools.lib.schema import SCHEMA_VERSION
        from tools.migrate import apply_migrations

        path = Path(noted["journal_path"])
        # force a real migration: age the file's schema_version
        raw = path.read_bytes().decode("utf-8")
        aged = raw.replace("schema_version: 3", "schema_version: 1", 1)
        assert aged != raw
        path.write_bytes(aged.encode("utf-8"))
        suffix_before = split_journal_bytes(path.read_bytes()).suffix

        result = apply_migrations(data_dir / "Journals", SCHEMA_VERSION)
        assert result.get("failed_count") == 0, result
        assert any(
            change.get("path", "").endswith(path.name)
            for change in result.get("deterministic_changes", [])
        ), "the aged file must actually have been migrated"

        after = path.read_bytes()
        assert split_journal_bytes(after).suffix == suffix_before, "region survives migration"
        metadata, body = parse_frontmatter(after.decode("utf-8"))
        assert metadata["notes_boundary"]
        notes = split_fragment_notes(metadata, body)
        assert notes.original_text == "meeting was on Monday"
        assert len(notes.notes) == 1 and not notes.malformed

    def test_edit_notes_boundary_refused_on_new_form_fragment(self, data_dir, noted):
        result = edit_journal(Path(noted["journal_path"]), {"notes_boundary": "0" * 32})
        assert result["error"]["code"] == "E0505"
        assert result["error"]["details"]["field"] == "notes_boundary"

    def test_edit_notes_boundary_refused_on_legacy_file(self, data_dir):
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "---"],
            b"\n\nlegacy words",
        )
        result = edit_journal(path, {"notes_boundary": "0" * 32})
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "notes_boundary"

    def test_legacy_content_edit_keeps_region_verbatim(self, data_dir):
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "---"],
            b"\n\nlegacy original words",
        )
        basis = _basis(data_dir)
        assert add_note_to_fragment(
            {
                "path": _rel(path),
                "text": "a correction",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
                "by": "host-agent",
            }
        )["success"]
        before = path.read_bytes()
        region_before = split_suffix_region(
            split_journal_bytes(before).suffix,
            parse_frontmatter(before.decode("utf-8"))[0]["notes_boundary"],
        )[1]

        result = edit_journal(path, {}, replace_content="brand new words")
        assert result["success"], result
        assert result["content_modified"] is True

        after = path.read_bytes()
        boundary = parse_frontmatter(after.decode("utf-8"))[0]["notes_boundary"]
        region_after = split_suffix_region(split_journal_bytes(after).suffix, boundary)[1]
        assert region_after == region_before, "the notes region bytes are identical"
        metadata, body = parse_frontmatter(after.decode("utf-8"))
        split = split_fragment_notes(metadata, body)
        assert split.original_text == "brand new words"
        assert len(split.notes) == 1

    def test_legacy_append_content_applies_to_original(self, data_dir):
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "---"],
            b"\n\nlegacy original words",
        )
        basis = _basis(data_dir)
        assert add_note_to_fragment(
            {
                "path": _rel(path),
                "text": "a correction",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
                "by": "host-agent",
            }
        )["success"]
        result = edit_journal(path, {}, append_content="appended words")
        assert result["success"], result
        metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        split = split_fragment_notes(metadata, body)
        assert split.original_text == "legacy original words\n\nappended words"
        assert len(split.notes) == 1 and not split.malformed

    def test_supplied_content_with_boundary_refused(self, data_dir):
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            ["---", "date: 2026-11-12", "---"],
            b"\n\nlegacy original words",
        )
        basis = _basis(data_dir)
        assert add_note_to_fragment(
            {
                "path": _rel(path),
                "text": "a correction",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
                "by": "host-agent",
            }
        )["success"]
        boundary = parse_frontmatter(path.read_text(encoding="utf-8"))[0]["notes_boundary"]
        before = path.read_bytes()
        result = edit_journal(path, {}, append_content=f"no {boundary} forging")
        assert result["error"]["code"] == "E0001"
        assert path.read_bytes() == before

    def test_new_form_fragment_content_edit_still_refused(self, data_dir, noted):
        result = edit_journal(Path(noted["journal_path"]), {}, append_content="x")
        assert result["error"]["code"] == "E0505"


# ---------------------------------------------------------------------------
# 9. Concurrency
# ---------------------------------------------------------------------------


def _run_note_cli(rel_path, text, basis_rel, by, expect_id=None):
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    payload = {
        "path": rel_path,
        "text": text,
        "by": by,
        "based_on": [{"path": basis_rel, "quote": "he said Monday"}],
    }
    if expect_id is not None:
        payload["expect_id"] = expect_id
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tools.fragment",
            "note",
            "--data",
            json.dumps(payload),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


class TestConcurrency:
    def test_two_note_processes_both_land(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        first = _run_note_cli(
            target["rel_path"], "note from A", basis["rel_path"], "a", target["id"]
        )
        second = _run_note_cli(
            target["rel_path"], "note from B", basis["rel_path"], "b", target["id"]
        )
        out_a, err_a = first.communicate(timeout=120)
        out_b, err_b = second.communicate(timeout=120)
        assert first.returncode == 0, (out_a, err_a)
        assert second.returncode == 0, (out_b, err_b)
        payload_a = _parse_cli_json(out_a)
        payload_b = _parse_cli_json(out_b)
        assert payload_a["success"] and payload_b["success"]

        _raw, metadata, body, notes_split = _split(Path(target["journal_path"]))
        assert len(notes_split.notes) == 2, "both notes landed"
        assert not notes_split.malformed
        assert {n.text for n in notes_split.notes} == {"note from A", "note from B"}
        assert notes_split.original_text == "meeting was on Monday"

    def test_note_against_edit_loses_neither(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        path = Path(target["journal_path"])

        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        note_proc = _run_note_cli(
            target["rel_path"], "concurrent note", basis["rel_path"], "a", target["id"]
        )
        edit_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "tools.edit_journal",
                "--journal",
                str(path),
                "--set-weather",
                "sunny",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=str(REPO_ROOT),
        )
        out_note, err_note = note_proc.communicate(timeout=120)
        out_edit, err_edit = edit_proc.communicate(timeout=120)
        assert note_proc.returncode == 0, (out_note, err_note)
        assert _parse_cli_json(out_note)["success"]
        assert edit_proc.returncode == 0, (out_edit, err_edit)
        assert _parse_cli_json(out_edit)["success"]

        metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        notes_split = split_fragment_notes(metadata, body)
        assert len(notes_split.notes) == 1, "the note survived the edit"
        assert metadata.get("weather") == "sunny", "the edit survived the note"
        assert notes_split.original_text == "meeting was on Monday"
        assert not notes_split.malformed


# ---------------------------------------------------------------------------
# 10. The guards are load-bearing
# ---------------------------------------------------------------------------


class TestGuards:
    def test_outgoing_check_refuses_a_lost_boundary_line(self, data_dir, monkeypatch):
        """Without the inserted line the file would lose notes_boundary.

        Pins `verify_outgoing_note_append`: sabotage the block insertion and
        the write must be refused (E0202), with the bytes unchanged.
        """
        import tools.fragment.note as note_module

        target = _fragment()
        basis = _basis(data_dir)
        path = Path(target["journal_path"])
        before = path.read_bytes()

        monkeypatch.setattr(note_module, "insert_boundary_line", lambda block, boundary: block)
        result = _note(target, "correction", basis)
        assert result["success"] is False
        assert result["error"]["code"] == "E0202"
        assert path.read_bytes() == before

    def test_boundary_generation_check_is_deterministic(self, monkeypatch):
        """`generate_boundary` retries past a candidate the file already holds.

        The randomness source itself is forced to offer a colliding candidate
        first, so this pins the generation check deterministically: with the
        collision check removed, the planted candidate would be returned.
        """
        import secrets

        import tools.lib.fragment_notes as notes_module

        planted = "7" * 32
        calls = {"n": 0}
        real_token_hex = secrets.token_hex

        def _token_hex(nbytes):
            calls["n"] += 1
            if calls["n"] == 1:
                return planted
            return real_token_hex(nbytes)

        monkeypatch.setattr(notes_module.secrets, "token_hex", _token_hex)
        raw = f"some words containing {planted} inside".encode("utf-8")
        boundary = notes_module.generate_boundary(raw)
        assert boundary != planted, "a candidate the file holds must be retried past"
        assert boundary.encode("ascii") not in raw
        assert calls["n"] >= 2

    def test_reader_splitter_is_load_bearing(self, data_dir, monkeypatch):
        """If `journal get` stopped splitting, notes would leak into content.

        Pins the shared splitter at one reader: with it monkeypatched away the
        get-test's assertions fail; the sabotage variant asserts the leak
        would be visible (content changes), proving the test can see it.
        """
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "It was Tuesday", basis)["success"]

        import tools.journal.__main__ as journal_main

        got = run_journal_get(path=target["rel_path"])["data"]
        assert got["content"] == "meeting was on Monday"
        assert [n["text"] for n in got["notes"]] == ["It was Tuesday"]

        class _NoSplit:
            def __init__(self, metadata, body):
                self.original_text = body
                self.notes = ()
                self.malformed = False

        monkeypatch.setattr(journal_main, "split_fragment_notes", _NoSplit)
        leaked = run_journal_get(path=target["rel_path"])["data"]
        assert leaked["content"] != got["content"], (
            "without the splitter the note region leaks into content — "
            "the reader test above can see the difference"
        )


# ---------------------------------------------------------------------------
# fragment_notes unit tests (the one grammar)
# ---------------------------------------------------------------------------


class TestFragmentNotesGrammar:
    def test_escape_sequences_are_built_not_literal(self):
        source = (REPO_ROOT / "tools/lib/fragment_notes.py").read_text(encoding="utf-8")
        for literal in ("\\u003c", "\\u003e"):
            assert (
                literal not in source
            ), "escapes must be built from character codes, not written as literals"

    def test_header_escapes_angle_brackets(self):
        note = {
            "id": "b" * 32,
            "noted_at": "2026-11-12T15:02:10+01:00",
            "by": "someone <me>",
            "based_on": [
                {"path": "Journals/a.md", "id": None, "quote": "x <y> -->", "sha256": "c" * 64}
            ],
        }
        header = render_note_block("d" * 32, note, "text with <angle> and -->")
        header_line = header.decode("utf-8").split("\n")[0]
        inner = header_line[: -len(" -->")]
        assert "-->" not in inner, "an escaped header can never close the comment early"
        assert "u003c" in header_line and "u003e" in header_line
        # and it parses back
        metadata = {"notes_boundary": "d" * 32}
        split = split_fragment_notes(metadata, header.decode("utf-8"))
        assert not split.malformed
        assert split.notes[0].by == "someone <me>"

    def test_boundary_of_rejects_invalid_values(self):
        for bad in (None, 123, "XYZ", "a" * 33, "A" * 32, "", ["a" * 32]):
            assert boundary_of({"notes_boundary": bad}) is None
        assert boundary_of({"notes_boundary": "a" * 32}) == "a" * 32
        assert boundary_of({}) is None
        assert boundary_of("not a mapping") is None

    def test_no_boundary_whole_body_is_original(self):
        text = "<!-- life-index:note " + "a" * 32 + " x -->\nlooks like a note"
        split = split_fragment_notes({}, text)
        assert split.original_text == text
        assert split.notes == () and not split.malformed

    def test_find_notes_region_on_raw_text(self):
        boundary = "e" * 32
        prefix = note_marker_prefix(boundary)
        text = f"line one\nline two\n{prefix}{{}} -->\nnote\n"
        start = find_notes_region(text, boundary)
        assert text[start:].startswith(prefix)

    def test_insert_boundary_line_requires_full_line(self):
        block = b"---\nkey: value\n---"
        out = insert_boundary_line(block, "a" * 32)
        assert out == b'---\nkey: value\nnotes_boundary: "' + b"a" * 32 + b'"\n---'

    def test_insert_boundary_line_keeps_crlf(self):
        block = b"---\r\nkey: value\r\n---\r\n"
        out = insert_boundary_line(block, "a" * 32)
        assert out.endswith(b'notes_boundary: "' + b"a" * 32 + b'"\r\n---\r\n')

    def test_split_suffix_region(self):
        boundary = "f" * 32
        prefix = note_marker_prefix(boundary).encode("utf-8")
        suffix = (
            b"original\n\n"
            + prefix
            + b"{}\nnote\n"
            + b"<!-- /life-index:note "
            + (boundary.encode())
            + b" -->\n"
        )
        original, region = split_suffix_region(suffix, boundary)
        assert original == b"original\n\n"
        assert region.startswith(prefix)
