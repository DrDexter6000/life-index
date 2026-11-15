#!/usr/bin/env python3
"""Correction tests for the G2 fragment-note package (second review round).

One class per review item:

1.  `write` (and the prepare→write path) refuses the reserved key
    `notes_boundary`; nothing is written;
2.  `generate_index.builder._entry_ref` labels from the original text, also
    when the original is empty and the note header would be the first line;
3.  a note `text` line starting with a note marker prefix is refused as
    invalid input before the lock;
5.  a valid boundary that leaked into the text above a damaged marker line
    makes the region malformed everywhere;
6.  a CRLF-converted region reads the same through `journal get`, `verify`
    and `fragment note`;
7.  header validation refuses what the writer never writes (bad `noted_at`,
    bad `sha256`, duplicated JSON keys);
8.  the stored basis hash is the hash of `journal get`'s `content` (LF);
9.  the maintenance audit's notes split survives a field value containing
    `---`;
11. a direct test of the region-held check inside `verify_outgoing_journal`;
12. stored-form shapes that cannot take a first note are refused with
    unchanged bytes.
"""

import hashlib
from pathlib import Path

import pytest

from tools.fragment.core import add_fragment
from tools.fragment.note import add_note_to_fragment
from tools.journal.__main__ import run_journal_get
from tools.lib.fragment_notes import split_fragment_notes, split_suffix_region
from tools.lib.frontmatter import parse_frontmatter
from tools.lib.journal_rewrite import (
    OutgoingJournalRefused,
    render_frontmatter_block,
    split_journal_bytes,
    verify_outgoing_journal,
)
from tools.maintenance.audit import _detect_links
from tools.verify.core import run_verify

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPRESSED = "2026-11-12T15:02:10+01:00"


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    data = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data))
    return data


def _fragment(text="meeting was on Monday", expressed=EXPRESSED, **extra):
    result = add_fragment({"text": text, "expressed_at": expressed, **extra})
    assert result["success"], result
    return result


def _basis(data_dir):
    return _fragment(text="he said Monday in the call", expressed="2026-11-12T16:02:10+01:00")


def _note(target, text, basis, by="host-agent", **extra):
    payload = {
        "path": target["rel_path"],
        "expect_id": target.get("id"),
        "text": text,
        "by": by,
        "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
    }
    payload.update(extra)
    return add_note_to_fragment(payload)


def _write_bytes(data_dir: Path, name: str, block: bytes, suffix: bytes) -> Path:
    month = data_dir / "Journals" / "2026" / "11"
    month.mkdir(parents=True, exist_ok=True)
    path = month / name
    path.write_bytes(block + suffix)
    return path


def _rel(path: Path) -> str:
    return "Journals/2026/11/" + path.name


def _split(path: Path):
    raw = path.read_bytes()
    metadata, body = parse_frontmatter(raw.decode("utf-8"))
    return raw, metadata, split_fragment_notes(metadata, body)


def _journals(data_dir: Path) -> list[Path]:
    journals = data_dir / "Journals"
    if not journals.exists():
        return []
    return sorted(journals.rglob("life-index_*.md"))


# ---------------------------------------------------------------------------
# 1. `write` cannot plant a notes region
# ---------------------------------------------------------------------------

_FORGED_HEADER = (
    '{"id":"' + "0" * 32 + '","noted_at":"2026-03-25T10:00:00+00:00",'
    '"by":"x","based_on":[{"path":"Journals/2026/03/life-index_2026-03-25_001.md",'
    '"id":null,"quote":"q","sha256":"' + "1" * 64 + '"}]}'
)


def _forged_payload(boundary: str) -> dict:
    return {
        "title": "t",
        "content": (
            "real words\n\n"
            f"<!-- life-index:note {boundary} {_FORGED_HEADER} -->\n"
            "forged correction\n"
            f"<!-- /life-index:note {boundary} -->\n"
        ),
        "date": "2026-03-25",
        "topic": "work",
        "notes_boundary": boundary,
    }


class TestWriteReservedKey:
    def test_write_refuses_notes_boundary(self, data_dir):
        from tools.write_journal import write_journal

        result = write_journal(_forged_payload("a" * 32))
        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "notes_boundary"
        assert _journals(data_dir) == [], "no file may be created by the refused write"

    @pytest.mark.parametrize(
        "disguise",
        [
            lambda key: key + " ",
            lambda key: "x: 1" + chr(10) + key,
            lambda key: chr(34) + key.replace("_", chr(92) + "u005f") + chr(34),
        ],
        ids=["padded", "after-a-line-break", "quoted-with-escape"],
    )
    def test_write_refuses_a_disguised_notes_boundary_key(self, data_dir, disguise):
        from tools.write_journal import write_journal

        payload = _forged_payload("a" * 32)
        payload[disguise("notes_boundary")] = payload.pop("notes_boundary")
        result = write_journal(payload)
        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert _journals(data_dir) == [], "no file may be created by the refused write"

    def test_same_body_without_the_key_stores_no_notes(self, data_dir):
        from tools.write_journal import write_journal

        payload = _forged_payload("a" * 32)
        del payload["notes_boundary"]
        result = write_journal(payload)
        assert result["success"] is True, result
        path = Path(result["journal_path"])
        got = run_journal_get(path=_rel_to(path))["data"]
        assert got["notes"] == []
        assert "notes_malformed" not in got
        assert (
            "<!-- life-index:note" in got["content"]
        ), "without the boundary key the marker text is ordinary content"

    def test_prepare_then_write_is_closed_too(self, data_dir):
        from tools.write_journal import prepare_journal_metadata, write_journal

        payload = _forged_payload("b" * 32)
        prepared = prepare_journal_metadata(dict(payload))
        result = write_journal(prepared)
        assert result["success"] is False
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "notes_boundary"
        assert _journals(data_dir) == []


def _rel_to(path: Path) -> str:
    parts = path.parts
    return "/".join(parts[-4:])


# ---------------------------------------------------------------------------
# 2. The empty-original shape through every label reader
# ---------------------------------------------------------------------------


class TestEmptyOriginalLabel:
    @pytest.fixture()
    def empty_original(self, data_dir):
        basis = _basis(data_dir)
        target = _write_bytes(
            data_dir,
            "life-index_2026-11-12_095.md",
            b"---\ndate: 2026-11-12\nkind: fragment\n---\n",
            b"\n\n",
        )
        result = add_note_to_fragment(
            {
                "path": _rel(target),
                "text": "the only words are the note",
                "by": "host-agent",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
            }
        )
        assert result["success"], result
        return target, basis

    def test_entry_ref_label_is_filename_not_marker(self, data_dir, empty_original):
        target, _basis_frag = empty_original
        from tools.generate_index.builder import _entry_ref
        from tools.generate_index.navigation import IndexNode

        node = IndexNode(
            node_id="2026-11",
            level="month",
            path=data_dir / "Journals" / "2026" / "11",
            relative_path="Journals/2026/11",
            year=2026,
            month=11,
            entry_count=0,
            topics={},
            date_range="",
            has_index=False,
            freshness="unknown",
        )
        entry = _entry_ref(target, node, data_dir)
        assert entry is not None
        assert entry["display_label"] == target.stem, "the note header must not become the label"
        assert entry["display_label"] != "<!"

    def test_journal_get_empty_original(self, data_dir, empty_original):
        target, _basis_frag = empty_original
        got = run_journal_get(path=_rel(target))["data"]
        assert got["content"] == ""
        assert [n["text"] for n in got["notes"]] == ["the only words are the note"]
        assert got["word_count"] == 0
        assert "notes_malformed" not in got


# ---------------------------------------------------------------------------
# 3. Marker-like lines in the note text
# ---------------------------------------------------------------------------


class TestMarkerPrefixLinesInText:
    def _refused(self, data_dir, text):
        target = _fragment()
        basis = _basis(data_dir)
        path = Path(target["journal_path"])
        before = path.read_bytes()
        result = _note(target, text, basis)
        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "text"
        assert path.read_bytes() == before

    def test_open_prefix_at_start(self, data_dir):
        self._refused(data_dir, "<!-- life-index:note " + "0" * 32 + " x -->\nwords")

    def test_close_prefix_at_start(self, data_dir):
        self._refused(data_dir, "<!-- /life-index:note " + "0" * 32 + " -->\nwords")

    def test_open_prefix_on_later_line(self, data_dir):
        self._refused(data_dir, "words\n<!-- life-index:note something else")

    def test_close_prefix_on_later_line(self, data_dir):
        self._refused(data_dir, "words\nmore\n<!-- /life-index:note xxx")

    def test_same_string_mid_line_is_accepted(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        result = _note(
            target, "see <!-- life-index:note here --> and <!-- /life-index:note -->", basis
        )
        assert result["success"], result
        _raw, _metadata, notes_split = _split(Path(target["journal_path"]))
        assert notes_split.notes[0].text.startswith("see <!--")
        assert not notes_split.malformed


# ---------------------------------------------------------------------------
# 5. A damaged first marker leaks the boundary into the original text
# ---------------------------------------------------------------------------


class TestDamagedFirstMarker:
    def _noted_then_damaged(self, data_dir, damage):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first note words", basis)["success"]
        assert _note(target, "second note words", basis, by="user")["success"]
        path = Path(target["journal_path"])
        damage(path)
        return target, path

    @staticmethod
    def _damage_first_marker(path: Path) -> None:
        raw = path.read_bytes()
        damaged = raw.replace(b"life-index:note ", b"life-index:notX ", 1)
        assert damaged != raw
        path.write_bytes(damaged)

    @staticmethod
    def _damage_second_header(path: Path) -> None:
        raw = path.read_bytes().decode("utf-8")
        marker = "<!-- life-index:note "
        first = raw.find(marker)
        second = raw.find(marker, first + 1)
        assert second > first > -1, "the file must hold two note blocks"
        path.write_bytes(
            (raw[:second] + "<!-- life-index:notX " + raw[second + len(marker) :]).encode("utf-8")
        )

    def test_reproduction_boundary_leak_is_malformed_everywhere(self, data_dir):
        target, path = self._noted_then_damaged(data_dir, self._damage_first_marker)

        # journal get: the leak line is not original text, the region is flagged
        got = run_journal_get(path=target["rel_path"])["data"]
        assert got["notes_malformed"] is True
        assert (
            got["content"] == "meeting was on Monday"
        ), "everything after the leak line is untrusted"
        assert [n["text"] for n in got["notes"]] == [
            "second note words"
        ], "an intact later block still parses, best-effort, with the damage flagged"

        # verify reports it
        result = run_verify()
        frontmatter = next(c for c in result["checks"] if c["name"] == "frontmatter_valid")
        assert any("malformed notes region" in i for i in frontmatter["issues"])

        # fragment note refuses
        basis = _basis(data_dir)
        before = path.read_bytes()
        refusal = _note(target, "third note", basis)
        assert refusal["error"]["code"] == "E0209"
        assert path.read_bytes() == before

    def test_boundary_leak_inside_original_text(self, data_dir):
        # the marker line intact, but the boundary value appears above it
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first note words", basis)["success"]
        path = Path(target["journal_path"])
        boundary = parse_frontmatter(path.read_text(encoding="utf-8"))[0]["notes_boundary"]
        raw = path.read_bytes().decode("utf-8")
        marker_line = next(
            line for line in raw.split("\n") if line.startswith("<!-- life-index:note ")
        )
        head = raw[: raw.index(marker_line)]
        leaked = (
            head
            + f"leak {boundary} here\n"
            + marker_line
            + raw[raw.index(marker_line) + len(marker_line) :]
        )
        path.write_bytes(leaked.encode("utf-8"))

        _raw, _metadata, notes_split = _split(path)
        assert notes_split.malformed is True
        assert (
            notes_split.original_text
            == "meeting was on Monday\n\nleak here".replace("\n\nleak here", "")
            or notes_split.original_text == "meeting was on Monday"
        ), notes_split.original_text

    def test_damaged_header_in_second_block(self, data_dir):
        target, path = self._noted_then_damaged(data_dir, self._damage_second_header)
        _raw, _metadata, notes_split = _split(path)
        assert notes_split.malformed is True
        assert [n.text for n in notes_split.notes] == [
            "first note words"
        ], "the intact first block still parses; the damaged one does not"

    def test_boundary_without_any_region_is_not_malformed(self, data_dir):
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_091.md",
            b'---\ndate: 2026-11-12\nnotes_boundary: "' + b"c" * 32 + b'"\n---\n',
            b"\n\njust words",
        )
        _raw, _metadata, notes_split = _split(path)
        assert notes_split.malformed is False
        assert notes_split.notes == ()
        assert notes_split.original_text == "just words"


# ---------------------------------------------------------------------------
# 6. A CRLF-converted region reads the same everywhere
# ---------------------------------------------------------------------------


class TestCrlfRegionAgreement:
    def test_get_verify_and_note_agree(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "first note words", basis)["success"]
        path = Path(target["journal_path"])
        lf_notes = run_journal_get(path=target["rel_path"])["data"]["notes"]

        # what a Windows editor does on save
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

        got = run_journal_get(path=target["rel_path"])["data"]
        assert got["notes"] == lf_notes, "journal get reads the same notes"
        assert got["content"] == "meeting was on Monday"
        assert "notes_malformed" not in got

        result = run_verify()
        frontmatter = next(c for c in result["checks"] if c["name"] == "frontmatter_valid")
        assert not any("notes region" in i for i in frontmatter["issues"])

        second = _note(target, "second note words", basis, by="user")
        assert second["success"], second
        after = run_journal_get(path=target["rel_path"])["data"]
        assert [n["text"] for n in after["notes"]] == [
            "first note words",
            "second note words",
        ], "old notes read back unchanged"
        assert "notes_malformed" not in after
        appended = path.read_bytes().split(b"<!-- life-index:note ")[-1]
        assert b"\r" not in appended, "the appended block is LF as today"


# ---------------------------------------------------------------------------
# 7. Header validation refuses what the writer never writes
# ---------------------------------------------------------------------------


def _damage_header_field(path: Path, old: str, new: str) -> None:
    raw = path.read_bytes().decode("utf-8")
    assert old in raw, old
    path.write_bytes(raw.replace(old, new, 1).encode("utf-8"))


class TestHeaderValidation:
    def _noted(self, data_dir):
        target = _fragment()
        basis = _basis(data_dir)
        assert _note(target, "note words", basis)["success"]
        return Path(target["journal_path"])

    def test_noted_at_must_be_an_offset_datetime(self, data_dir):
        path = self._noted(data_dir)
        good = _split(path)[2].notes[0].noted_at
        _damage_header_field(path, f'"noted_at":"{good}"', '"noted_at":"not-a-date"')
        assert _split(path)[2].malformed is True

    def test_sha256_must_be_64_lowercase_hex(self, data_dir):
        path = self._noted(data_dir)
        raw = path.read_bytes().decode("utf-8")
        good = split_fragment_notes(*parse_frontmatter(raw)).notes[0].based_on[0]["sha256"]
        _damage_header_field(path, good, "not-a-hash")
        assert _split(path)[2].malformed is True

    def test_duplicated_header_key(self, data_dir):
        path = self._noted(data_dir)
        _damage_header_field(path, '"by":"host-agent"', '"by":"host-agent","by":"other"')
        _raw, _metadata, notes_split = _split(path)
        assert notes_split.malformed is True

    def test_duplicated_basis_key(self, data_dir):
        path = self._noted(data_dir)
        raw = path.read_bytes().decode("utf-8")
        sha = split_fragment_notes(*parse_frontmatter(raw)).notes[0].based_on[0]["sha256"]
        _damage_header_field(path, f'"sha256":"{sha}"', f'"sha256":"{sha}","sha256":"{sha}"')
        _raw, _metadata, notes_split = _split(path)
        assert notes_split.malformed is True


# ---------------------------------------------------------------------------
# 8. The basis hash is the hash of journal get's content
# ---------------------------------------------------------------------------


class TestBasisHashMatchesReader:
    def test_crlf_basis_hashes_lf_content(self, data_dir):
        basis_file = _write_bytes(
            data_dir,
            "life-index_2026-11-12_092.md",
            b"---\ndate: 2026-11-12\r\nkind: fragment\r\n---\r\n",
            b"\r\nhe said Monday in the call\r\nsecond line\r\n",
        )
        target = _fragment()
        result = add_note_to_fragment(
            {
                "path": target["rel_path"],
                "expect_id": target["id"],
                "text": "correction",
                "by": "host-agent",
                "based_on": [{"path": _rel(basis_file), "quote": "he said Monday"}],
            }
        )
        assert result["success"], result
        stored = result["note"]["based_on"][0]["sha256"]
        content = run_journal_get(path=_rel(basis_file))["data"]["content"]
        assert content == "he said Monday in the call\nsecond line", "journal get serves LF text"
        assert stored == hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 9. The maintenance audit's notes split survives `---` inside a value
# ---------------------------------------------------------------------------


class TestMaintenanceNotesSplit:
    def test_message_id_with_dashes_does_not_hide_the_region(self, data_dir):
        keyed = add_fragment(
            {
                "text": "see [the plan](Journals/2026/11/missing-target.md)",
                "expressed_at": EXPRESSED,
                "source": {"channel": "chat", "message_id": "prefix---suffix"},
            }
        )
        assert keyed["success"], keyed
        target = add_fragment({"text": "plain words", "expressed_at": "2026-11-12T17:02:10+01:00"})
        assert target["success"], target
        noted = add_note_to_fragment(
            {
                "path": keyed["rel_path"],
                "expect_id": keyed["id"],
                "text": "note link [broken](Journals/2026/11/note-only.md)",
                "by": "host-agent",
                "based_on": [{"path": target["rel_path"], "quote": "plain words"}],
            }
        )
        assert noted["success"], noted

        issues = _detect_links(data_dir)
        evidence = [i["issue_id"] for i in issues]
        assert any(keyed["rel_path"] in p for p in evidence), "the original's link is audited"
        assert not any(
            "note-only.md" in p for p in evidence
        ), "the notes region stays hidden despite --- inside a field value"


# ---------------------------------------------------------------------------
# 11. A direct test of the region-held check
# ---------------------------------------------------------------------------


class TestRegionHeldGuard:
    def test_changed_note_text_is_refused(self, data_dir):
        # a legacy file with one note, built through the real command
        basis = _basis(data_dir)
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_093.md",
            b"---\ndate: 2026-11-12\n---\n",
            b"\n\nlegacy original words",
        )
        result = add_note_to_fragment(
            {
                "path": _rel(path),
                "text": "first note words",
                "by": "host-agent",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
            }
        )
        assert result["success"], result

        old_bytes = path.read_bytes()
        old_metadata, _old_body = parse_frontmatter(old_bytes.decode("utf-8"))
        old_split = split_journal_bytes(old_bytes)
        boundary = old_metadata["notes_boundary"]
        _original_bytes, region_bytes = split_suffix_region(old_split.suffix, boundary)

        # a content edit whose computed body is right, but whose stored note
        # text was changed behind the computation's back
        tampered = region_bytes.replace(b"first note words", b"TAMPERED note words")
        assert tampered != region_bytes
        new_frontmatter = dict(old_metadata)
        new_body = "brand new words" + "\n\n" + tampered.decode("utf-8")
        new_bytes = render_frontmatter_block(new_frontmatter) + b"\n\n" + new_body.encode("utf-8")

        with pytest.raises(OutgoingJournalRefused):
            verify_outgoing_journal(
                old_bytes, new_bytes, new_frontmatter, metadata_only=False, computed_body=new_body
            )


# ---------------------------------------------------------------------------
# 12. Stored-form shapes that cannot take a first note
# ---------------------------------------------------------------------------


class TestShapesWithoutFirstNote:
    def _refused_shape(self, data_dir, block: bytes):
        basis = _basis(data_dir)
        path = _write_bytes(data_dir, "life-index_2026-11-12_094.md", block, b"\n\nlegacy words")
        before = path.read_bytes()
        result = add_note_to_fragment(
            {
                "path": _rel(path),
                "text": "correction",
                "by": "host-agent",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
            }
        )
        assert result["success"] is False, result
        assert result["error"]["code"] == "E0202"
        assert result["error"]["details"]["reason"] == "not_round_trippable"
        assert path.read_bytes() == before, "a refused shape keeps every byte"

    def test_block_scalar_last_field(self, data_dir):
        self._refused_shape(data_dir, b"---\ndate: 2026-11-12\nnote: |\n  kept words\n---\n")

    def test_root_flow_mapping(self, data_dir):
        self._refused_shape(data_dir, b"---\n{date: 2026-11-12, title: x}\n---\n")

    def test_document_end_marker(self, data_dir):
        self._refused_shape(data_dir, b"---\ndate: 2026-11-12\n...\n---\n")


# ---------------------------------------------------------------------------
# 10. The E0208 recovery names the right id for every expect_id_* reason
# ---------------------------------------------------------------------------


class TestExpectIdRecovery:
    def _refusal(self, data_dir, payload_extra):
        target = _fragment()
        basis = _basis(data_dir)
        path = Path(target["journal_path"])
        before = path.read_bytes()
        payload = {
            "path": target["rel_path"],
            "text": "correction",
            "by": "host-agent",
            "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
        }
        payload.update(payload_extra)
        result = add_note_to_fragment(payload)
        assert result["error"]["code"] == "E0208", result
        assert path.read_bytes() == before
        return result

    @pytest.mark.parametrize(
        "extra",
        [
            {},  # expect_id absent on an id-bearing target
            {"expect_id": "0" * 32},  # wrong id
        ],
    )
    def test_recovery_names_metadata_id(self, data_dir, extra):
        result = self._refusal(data_dir, extra)
        suggestion = result["error"]["suggestion"]
        assert "metadata.id" in suggestion
        assert "never the top-level path id" in suggestion

    def test_recovery_for_target_without_id(self, data_dir):
        _basis(data_dir)
        path = _write_bytes(
            data_dir,
            "life-index_2026-11-12_096.md",
            b"---\ndate: 2026-11-12\n---\n",
            b"\n\nlegacy words",
        )
        basis = _basis(data_dir)
        result = add_note_to_fragment(
            {
                "path": _rel(path),
                "expect_id": "0" * 32,
                "text": "correction",
                "by": "host-agent",
                "based_on": [{"path": basis["rel_path"], "quote": "he said Monday"}],
            }
        )
        assert result["error"]["code"] == "E0208"
        assert result["error"]["details"]["reason"] == "expect_id_unexpected"
        assert "metadata.id" in result["error"]["suggestion"]
