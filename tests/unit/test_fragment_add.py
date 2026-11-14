#!/usr/bin/env python3
"""Unit tests for `fragment add` (tools/fragment/core.py).

Every test runs against a temporary LIFE_INDEX_DATA_DIR; the real user data
directory is never touched. The numbered tests map to the work package's
required coverage:

1.  stored bytes: LF only, no BOM, no title line, exact field set;
2.  text round trip through `journal get` for the awkward texts;
3.  no default location, no weather, no network, `source_url` rejected;
4.  input validation: every rejected key and malformed field is named;
5.  `date` and folder derive from expressed_at's own wall clock;
6.  no overwrite when the allocated path is taken between allocation and publish;
7.  dedupe: retry, conflict, adjacent month, unreadable file, cache independence;
8.  attachments are all-or-nothing;
9.  fault injection before publish leaves nothing; after publish degrades honestly;
10. derived parity: FTS + metadata cache rows equal a full rebuild's;
11. `search` finds the fragment immediately with kind/display_label.
"""

import json
import re
import sqlite3
from pathlib import Path

import pytest

from tools.fragment.core import add_fragment
from tools.lib.frontmatter import parse_frontmatter

EXPRESSED = "2026-11-12T15:02:10+01:00"
HEX32 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    data = tmp_path / "Life-Index"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data))
    return data


def _fragments_on_disk(data_dir: Path) -> list[Path]:
    journals = data_dir / "Journals"
    if not journals.exists():
        return []
    return sorted(p for p in journals.rglob("life-index_*.md") if p.is_file())


def _read_stored(result: dict) -> tuple[dict, str]:
    raw = Path(result["journal_path"]).read_bytes()
    return parse_frontmatter(raw.decode("utf-8"))


def _side_effect(result: dict, name: str) -> dict:
    records = [r for r in result["side_effects"] if r["name"] == name]
    assert records, f"missing side effect {name}"
    return records[-1]


# ---------------------------------------------------------------------------
# 1. Stored bytes
# ---------------------------------------------------------------------------


class TestStoredBytes:
    def test_lf_no_bom_no_title_line_exact_fields(self, data_dir):
        result = add_fragment({"text": "第一行\r\n第二行\r尾部空白  ", "expressed_at": EXPRESSED})
        assert result["success"] is True
        raw = Path(result["journal_path"]).read_bytes()
        assert b"\r" not in raw, "stored bytes must be LF only"
        assert not raw.startswith(b"\xef\xbb\xbf"), "stored bytes must not carry a BOM"
        text = raw.decode("utf-8")
        assert text.endswith("\n") and not text.endswith("\n\n")
        metadata, body = parse_frontmatter(text)
        assert set(metadata) == {
            "schema_version",
            "kind",
            "id",
            "date",
            "expressed_at",
            "ingested_at",
        }, "frontmatter must hold exactly the six fixed fields when nothing else is supplied"
        assert metadata["schema_version"] == 3
        assert metadata["kind"] == "fragment"
        assert HEX32.match(metadata["id"])
        assert metadata["date"] == "2026-11-12T15:02:10"
        assert metadata["expressed_at"] == EXPRESSED
        assert not body.startswith("#"), "a fragment has no title line"
        assert body == "第一行\n第二行\n尾部空白"
        assert raw.decode("utf-8").split("---")[2].lstrip("\n").startswith("第一行")

    def test_crlf_and_cr_are_normalized_to_lf(self, data_dir):
        result = add_fragment({"text": "a\r\nb\rc\nd", "expressed_at": EXPRESSED})
        _metadata, body = _read_stored(result)
        assert body == "a\nb\nc\nd"

    def test_supplied_fields_plus_six_fixed_ones(self, data_dir):
        result = add_fragment(
            {
                "text": "记得这件事",
                "expressed_at": EXPRESSED,
                "occurred": {"from": "2026-11", "to": "2026-11-12", "precision": "month"},
                "source": {"channel": "whatsapp", "message_id": "mid-1"},
                "location": "江边",
                "place": {"lat": 29.5, "lon": 106.5, "from": "device"},
                "weather": "多云",
                "reply_to": [{"id": "abc", "version": 2, "quote": "原话"}],
            }
        )
        metadata, _body = _read_stored(result)
        assert set(metadata) == {
            "schema_version",
            "kind",
            "id",
            "date",
            "expressed_at",
            "ingested_at",
            "occurred",
            "source",
            "location",
            "place",
            "weather",
            "reply_to",
        }
        assert metadata["occurred"] == {
            "from": "2026-11",
            "to": "2026-11-12",
            "precision": "month",
        }
        assert metadata["source"] == {"channel": "whatsapp", "message_id": "mid-1"}
        assert metadata["place"]["lat"] == 29.5
        assert metadata["place"]["from"] == "device"
        assert metadata["reply_to"][0]["id"] == "abc"


# ---------------------------------------------------------------------------
# 2. Round trip through journal get
# ---------------------------------------------------------------------------

_AWKWARD_TEXTS = {
    "dashes": "开头\n---\n中间一行\n--- \n结尾",
    "leading_hash": "# 这不是标题，是用户的话",
    "yaml_lookalike": "key: value\n- 列表项\n另一个: [a, b]",
    "cjk_emoji": "今天和晴岚去了动物园 🦒，她说了「长脖子的动物最优雅」。",
}


class TestRoundTripThroughJournalGet:
    @pytest.mark.parametrize("name", sorted(_AWKWARD_TEXTS))
    def test_reads_back_equal(self, data_dir, name):
        from tools.journal.__main__ import run_journal_get

        result = add_fragment({"text": _AWKWARD_TEXTS[name], "expressed_at": EXPRESSED})
        assert result["success"] is True
        got = run_journal_get(path=result["rel_path"])
        assert got["success"] is True
        assert got["data"]["content"] == _AWKWARD_TEXTS[name]
        assert got["data"]["metadata"]["kind"] == "fragment"

    def test_text_is_never_rewritten_by_a_reread(self, data_dir):
        """Read bytes == what journal get returns: stored form is idempotent."""
        from tools.journal.__main__ import run_journal_get

        text = "---\n看起来像 frontmatter\n---\n正文"
        result = add_fragment({"text": text, "expressed_at": EXPRESSED})
        raw = Path(result["journal_path"]).read_bytes().decode("utf-8")
        _metadata, body = parse_frontmatter(raw)
        got = run_journal_get(path=result["rel_path"])
        assert body == got["data"]["content"] == text


# ---------------------------------------------------------------------------
# 3. No default location, no weather, no network
# ---------------------------------------------------------------------------


class TestNoDefaultsNoNetwork:
    def test_no_location_default_no_weather_no_network(self, data_dir, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("fragment add must never touch the network")

        monkeypatch.setattr("tools.write_journal.weather.query_weather_for_location", _boom)
        monkeypatch.setattr("tools.write_journal.core.query_weather_for_location", _boom)
        monkeypatch.setattr("tools.lib.url_download.download_url", _boom)
        monkeypatch.setattr("tools.write_journal.attachments.download_attachment_from_url", _boom)

        result = add_fragment({"text": "没有地点与天气", "expressed_at": EXPRESSED})
        assert result["success"] is True
        metadata, _body = _read_stored(result)
        assert "location" not in metadata
        assert "weather" not in metadata

    def test_blank_location_is_rejected_not_defaulted(self, data_dir):
        result = add_fragment({"text": "x", "location": "   "})
        assert result["success"] is False
        assert result["error"]["code"] == "E0001"
        assert "location" in result["error"]["message"]

    def test_source_url_attachment_rejected(self, data_dir):
        result = add_fragment(
            {
                "text": "看看这张图",
                "attachments": [{"source_url": "https://example.com/p.png"}],
            }
        )
        assert result["success"] is False
        assert result["error"]["code"] == "E0001"
        assert "source_url" in result["error"]["message"]
        assert "never touches the network" in result["error"]["message"]
        assert _fragments_on_disk(data_dir) == []


# ---------------------------------------------------------------------------
# 4. Input validation
# ---------------------------------------------------------------------------


def _error_of(payload: dict) -> dict:
    result = add_fragment(payload)
    assert result["success"] is False, f"expected rejection, got: {result}"
    assert result["error"]["code"] == "E0001"
    return result["error"]


class TestValidation:
    @pytest.mark.parametrize(
        "key", ["title", "topic", "people", "mood", "tags", "abstract", "project", "content"]
    )
    def test_fragment_only_keys_rejected_with_reason(self, data_dir, key):
        payload = {"text": "x", key: "value"}
        error = _error_of(payload)
        assert key in error["message"]
        assert "fragment holds only the user" in error["message"]

    def test_unknown_key_is_named(self, data_dir):
        error = _error_of({"text": "x", "serendipity": 1})
        assert "serendipity" in error["message"]

    def test_text_required(self, data_dir):
        assert "text" in _error_of({})["message"]

    def test_text_must_be_a_string(self, data_dir):
        assert "text" in _error_of({"text": 42})["message"]

    def test_text_blank_after_trim_rejected(self, data_dir):
        error = _error_of({"text": "  \n\t "})
        assert "text" in error["message"]

    def test_expressed_at_without_offset_rejected(self, data_dir):
        error = _error_of({"text": "x", "expressed_at": "2026-11-12T15:02:10"})
        assert "expressed_at" in error["message"]
        assert "offset" in error["message"]

    def test_expressed_at_impossible_date_rejected(self, data_dir):
        error = _error_of({"text": "x", "expressed_at": "2026-02-30T10:00:00+00:00"})
        assert "expressed_at" in error["message"]

    def test_expressed_at_garbage_rejected(self, data_dir):
        assert (
            "expressed_at"
            in _error_of({"text": "x", "expressed_at": "not-a-date+01:00"})["message"]
        )

    def test_occurred_missing_bound(self, data_dir):
        error = _error_of({"text": "x", "occurred": {"to": "2026", "precision": "year"}})
        assert "occurred.from" in error["message"]

    def test_occurred_bad_precision(self, data_dir):
        error = _error_of(
            {"text": "x", "occurred": {"from": "2026", "to": "2026", "precision": "hour"}}
        )
        assert "occurred.precision" in error["message"]

    def test_occurred_impossible_month(self, data_dir):
        error = _error_of(
            {"text": "x", "occurred": {"from": "2026-13", "to": "2027", "precision": "month"}}
        )
        assert "occurred.from" in error["message"]

    def test_occurred_unknown_inner_key(self, data_dir):
        error = _error_of(
            {
                "text": "x",
                "occurred": {"from": "2026", "to": "2026", "precision": "year", "era": "ce"},
            }
        )
        assert "era" in error["message"]

    def test_source_blank_string_rejected_not_treated_as_absent(self, data_dir):
        error = _error_of({"text": "x", "source": {"channel": "  "}})
        assert "source.channel" in error["message"]

    def test_source_unknown_key(self, data_dir):
        error = _error_of({"text": "x", "source": {"channel": "c", "extra": 1}})
        assert "extra" in error["message"]

    def test_location_multiline_rejected(self, data_dir):
        error = _error_of({"text": "x", "location": "第一行\n第二行"})
        assert "location" in error["message"]

    def test_place_lat_out_of_range(self, data_dir):
        error = _error_of({"text": "x", "place": {"lat": 91.0, "lon": 0.0, "from": "device"}})
        assert "place.lat" in error["message"]

    def test_place_missing_from(self, data_dir):
        error = _error_of({"text": "x", "place": {"lat": 1.0, "lon": 2.0}})
        assert "place.from" in error["message"]

    def test_place_bad_provenance(self, data_dir):
        error = _error_of({"text": "x", "place": {"lat": 1.0, "lon": 2.0, "from": "guessed"}})
        assert "place.from" in error["message"]

    def test_place_bad_carried_from(self, data_dir):
        error = _error_of(
            {
                "text": "x",
                "place": {"lat": 1.0, "lon": 2.0, "from": "carried", "carried_from": "  "},
            }
        )
        assert "place.carried_from" in error["message"]

    def test_place_carried_from_accepts_a_fragment_id_without_lookup(self, data_dir):
        fragment_id = "fragment-id-that-need-not-exist"
        result = add_fragment(
            {
                "text": "x",
                "place": {
                    "lat": 1.0,
                    "lon": 2.0,
                    "from": "carried",
                    "carried_from": fragment_id,
                },
            }
        )
        assert result["success"] is True
        metadata, _body = _read_stored(result)
        assert metadata["place"]["carried_from"] == fragment_id

    def test_place_observed_at_needs_offset(self, data_dir):
        error = _error_of(
            {
                "text": "x",
                "place": {
                    "lat": 1.0,
                    "lon": 2.0,
                    "from": "device",
                    "observed_at": "2026-11-12T10:00:00",
                },
            }
        )
        assert "place.observed_at" in error["message"]

    def test_weather_blank_rejected(self, data_dir):
        assert "weather" in _error_of({"text": "x", "weather": ""})["message"]

    def test_reply_to_requires_id(self, data_dir):
        error = _error_of({"text": "x", "reply_to": [{"version": 1}]})
        assert "reply_to[0].id" in error["message"]

    def test_reply_to_blank_id_rejected(self, data_dir):
        error = _error_of({"text": "x", "reply_to": [{"id": " "}]})
        assert "reply_to[0].id" in error["message"]

    def test_reply_to_bad_version_type(self, data_dir):
        error = _error_of({"text": "x", "reply_to": [{"id": "a", "version": 1.5}]})
        assert "reply_to[0].version" in error["message"]

    def test_reply_to_unknown_key(self, data_dir):
        error = _error_of({"text": "x", "reply_to": [{"id": "a", "note": "n"}]})
        assert "note" in error["message"]

    def test_attachment_missing_source_path(self, data_dir):
        error = _error_of({"text": "x", "attachments": [{"description": "d"}]})
        assert "attachments[0].source_path" in error["message"]

    def test_attachment_directory_rejected(self, data_dir, tmp_path):
        directory = tmp_path / "a-directory"
        directory.mkdir()
        error = _error_of({"text": "x", "attachments": [{"source_path": str(directory)}]})
        assert "attachments[0].source_path" in error["message"]

    def test_non_object_input_rejected(self, data_dir):
        result = add_fragment(["not", "an", "object"])  # type: ignore[arg-type]
        assert result["success"] is False
        assert result["error"]["code"] == "E0001"


# ---------------------------------------------------------------------------
# 5. date / folder derive from expressed_at's own wall clock
# ---------------------------------------------------------------------------


class TestWallClockDerivation:
    def test_offset_far_from_machine_zone_around_midnight(self, data_dir):
        # Wall clock 2026-11-13T01:30 in +13:00; in UTC (and most machine
        # zones) that moment is still 2026-11-12. The fragment must land on
        # its own calendar day, 2026-11-13.
        result = add_fragment({"text": "夜里的原话", "expressed_at": "2026-11-13T01:30:00+13:00"})
        assert result["success"] is True
        assert (
            result["journal_path"]
            .replace("\\", "/")
            .endswith("Journals/2026/11/life-index_2026-11-13_001.md")
        )
        metadata, _body = _read_stored(result)
        assert metadata["date"] == "2026-11-13T01:30:00"
        assert metadata["expressed_at"] == "2026-11-13T01:30:00+13:00"

    def test_month_boundary_not_rolled_by_machine_zone(self, data_dir):
        # Wall clock 2026-12-31T23:00 in -05:00 is 2027-01-01 in UTC: the
        # fragment still belongs to 2026-12.
        result = add_fragment({"text": "跨年原话", "expressed_at": "2026-12-31T23:00:00-05:00"})
        assert result["success"] is True
        assert (
            result["journal_path"]
            .replace("\\", "/")
            .endswith("Journals/2026/12/life-index_2026-12-31_001.md")
        )
        metadata, _body = _read_stored(result)
        assert metadata["date"] == "2026-12-31T23:00:00"

    def test_default_expressed_at_is_local_with_offset(self, data_dir):
        from datetime import datetime, timedelta

        before = datetime.now().astimezone()
        result = add_fragment({"text": "现在"})
        after = datetime.now().astimezone()
        assert result["success"] is True
        stored = datetime.fromisoformat(result["expressed_at"])
        assert stored.tzinfo is not None
        # Seconds precision truncates, so allow one second of slack at the
        # lower bound.
        assert before - timedelta(seconds=1) <= stored <= after


# ---------------------------------------------------------------------------
# 6. Publish never overwrites
# ---------------------------------------------------------------------------


class TestNoOverwrite:
    def test_file_appearing_at_allocated_path_is_not_replaced(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core

        original = fragment_core._generate_journal_path
        decoy_bytes = b"decoy journal written by a racing importer\n"

        def racing_allocator(date_str, timer):
            journal_path, month_dir, year, month = original(date_str, timer)
            # The import pipeline publishes without the journals lock: a file
            # appears at the path we just allocated, after allocation.
            month_dir.mkdir(parents=True, exist_ok=True)
            journal_path.write_bytes(decoy_bytes)
            return journal_path, month_dir, year, month

        monkeypatch.setattr(fragment_core, "_generate_journal_path", racing_allocator)

        result = add_fragment({"text": "撞路径的碎片", "expressed_at": EXPRESSED})
        assert result["success"] is True
        decoy = data_dir / "Journals" / "2026" / "11" / "life-index_2026-11-12_001.md"
        assert decoy.read_bytes() == decoy_bytes, "the racing writer's bytes must survive"
        assert (
            result["journal_path"].replace("\\", "/").endswith("life-index_2026-11-12_002.md")
        ), "the fragment must land on the next sequence number"
        metadata, body = _read_stored(result)
        assert body == "撞路径的碎片"


# ---------------------------------------------------------------------------
# 7. Dedupe
# ---------------------------------------------------------------------------


class TestDedupe:
    def _stored_with_key(self, data_dir, text="同一句话", expressed=EXPRESSED, key="mid-1"):
        result = add_fragment(
            {
                "text": text,
                "expressed_at": expressed,
                "source": {"channel": "walk", "message_id": key},
            }
        )
        assert result["success"] is True
        return result

    def test_same_key_same_text_returns_first_and_writes_nothing(self, data_dir):
        first = self._stored_with_key(data_dir)
        before = _fragments_on_disk(data_dir)
        second = add_fragment(
            {
                "text": "同一句话",
                "expressed_at": "2026-11-12T20:00:00+01:00",
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )
        assert second["success"] is True
        assert second["deduplicated"] is True
        assert second["id"] == first["id"]
        assert second["rel_path"] == first["rel_path"]
        assert second["journal_path"] == first["journal_path"]
        assert _fragments_on_disk(data_dir) == before
        commit = _side_effect(second, "journal_commit")
        assert commit["status"] == "skipped"
        assert commit["reason"] == "already stored"

    @pytest.mark.parametrize(
        "message_id",
        [
            "a\u0085b",
            "a\u2028b",
            "a\u007fb",
            "a\u0001b",
            "a\nb",
            'a"b',
            "消息-1",
            "12345",
        ],
    )
    def test_message_ids_with_yaml_escapes_still_deduplicate(self, data_dir, message_id):
        payload = {
            "text": "特殊 message id 也去重",
            "expressed_at": EXPRESSED,
            "source": {"channel": "walk", "message_id": message_id},
        }
        first = add_fragment(payload)
        second = add_fragment(payload)

        assert first["success"] is True
        assert second["success"] is True
        assert second["deduplicated"] is True
        assert second["id"] == first["id"]
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_same_key_crlf_stored_body_is_deduplicated(self, data_dir):
        first = self._stored_with_key(data_dir, text="同一句话\n第二行")
        journal_path = Path(first["journal_path"])
        journal_path.write_bytes(journal_path.read_bytes().replace(b"\n", b"\r\n"))
        before = journal_path.read_bytes()

        second = add_fragment(
            {
                "text": "同一句话\n第二行",
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )

        assert second["success"] is True
        assert second["deduplicated"] is True
        assert second["id"] == first["id"]
        assert journal_path.read_bytes() == before
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_deduplicated_result_lists_stored_attachments_and_writes_nothing(
        self, data_dir, tmp_path
    ):
        source = tmp_path / "keyed.png"
        source.write_bytes(b"keyed-image")
        payload = {
            "text": "带附件的同一句原话",
            "expressed_at": EXPRESSED,
            "source": {"channel": "walk", "message_id": "mid-with-attachment"},
            "attachments": [{"source_path": str(source), "description": "照片"}],
        }
        first = add_fragment(payload)
        assert first["success"] is True
        assert first["attachments"]
        before = {
            path.relative_to(data_dir): path.read_bytes()
            for path in data_dir.rglob("*")
            if path.is_file()
        }

        second = add_fragment(payload)

        assert second["success"] is True
        assert second["deduplicated"] is True
        assert second["attachments"] == first["attachments"]
        after = {
            path.relative_to(data_dir): path.read_bytes()
            for path in data_dir.rglob("*")
            if path.is_file()
        }
        assert after == before

    def test_same_key_different_text_conflicts(self, data_dir):
        first = self._stored_with_key(data_dir)
        result = add_fragment(
            {
                "text": "不同的正文",
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )
        assert result["success"] is False
        assert result["error"]["code"] == "E0206"
        existing = result["error"]["details"]["existing"]
        assert existing == [{"id": first["id"], "rel_path": first["rel_path"]}]
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_same_key_stored_file_without_id_conflicts_instead_of_deduplicating(self, data_dir):
        first = self._stored_with_key(data_dir)
        journal_path = Path(first["journal_path"])
        lines = journal_path.read_text(encoding="utf-8").splitlines(keepends=True)
        journal_path.write_text(
            "".join(
                line
                for line in lines
                if not line.startswith(("id:", "expressed_at:", "ingested_at:"))
            ),
            encoding="utf-8",
            newline="\n",
        )
        before = journal_path.read_bytes()

        result = add_fragment(
            {
                "text": "同一句话",
                "expressed_at": EXPRESSED,
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )

        assert result["success"] is False
        assert result["error"]["code"] == "E0206"
        assert "has no fragment id" in result["error"]["message"]
        assert first["rel_path"] in result["error"]["message"]
        assert result["error"]["details"]["existing"] == [{"id": "", "rel_path": first["rel_path"]}]
        assert journal_path.read_bytes() == before
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_multiple_matches_conflict_listing_all(self, data_dir):
        self._stored_with_key(data_dir, text="版本甲")
        # A same-key duplicate planted by hand (a tool-external copy).
        month_dir = data_dir / "Journals" / "2026" / "11"
        planted = month_dir / "life-index_2026-11-12_099.md"
        planted.write_text(
            "---\nkind: fragment\nid: planted\ndate: 2026-11-12T15:02:10\n"
            "expressed_at: 2026-11-12T15:02:10+01:00\ningested_at: 2026-11-12T15:02:11+01:00\n"
            "source:\n  channel: walk\n  message_id: mid-1\n---\n\n版本乙\n",
            encoding="utf-8",
        )
        result = add_fragment(
            {
                "text": "版本甲",
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )
        assert result["success"] is False
        assert result["error"]["code"] == "E0206"
        assert len(result["error"]["details"]["existing"]) == 2
        assert _fragments_on_disk(data_dir).count(planted) == 1
        assert planted.read_text(encoding="utf-8").endswith("版本乙\n")

    def test_adjacent_month_retry_is_found(self, data_dir):
        self._stored_with_key(data_dir, expressed="2026-10-31T23:30:00+02:00")
        result = add_fragment(
            {
                "text": "同一句话",
                "expressed_at": "2026-11-01T00:10:00+02:00",
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )
        assert result["success"] is True
        assert result["deduplicated"] is True
        assert result["dedupe_check"] == "complete"
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_year_boundary_retry_is_found(self, data_dir):
        self._stored_with_key(data_dir, expressed="2025-12-31T23:30:00+01:00")
        result = add_fragment(
            {
                "text": "同一句话",
                "expressed_at": "2026-01-01T00:10:00+01:00",
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )
        assert result["deduplicated"] is True

    def test_unreadable_file_yields_incomplete_and_still_writes(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core

        original_iter = fragment_core.iter_month_journal_files
        ghost = data_dir / "Journals" / "2026" / "11" / "life-index_2026-11-12_050.md"
        ghost.parent.mkdir(parents=True)

        def iter_with_unreadable_file(month_dir):
            yield from original_iter(month_dir)
            if month_dir.name == "11":
                yield ghost  # exists in the listing, unreadable on read

        monkeypatch.setattr(fragment_core, "iter_month_journal_files", iter_with_unreadable_file)
        result = add_fragment(
            {
                "text": "窗口里有读不出的文件",
                "expressed_at": EXPRESSED,
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )
        assert result["success"] is True, "the user's words are not refused"
        assert result["dedupe_check"] == "incomplete"
        assert result["dedupe_unreadable_count"] == 1
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_unlistable_window_directory_is_incomplete_and_still_writes(
        self, data_dir, monkeypatch
    ):
        from tools.fragment import core as fragment_core

        blocked = data_dir / "Journals" / "2026" / "10"
        blocked.mkdir(parents=True)
        original_scandir = fragment_core.os.scandir

        def refusing_scandir(path):
            if Path(path) == blocked:
                raise PermissionError("directory listing denied")
            return original_scandir(path)

        monkeypatch.setattr(fragment_core.os, "scandir", refusing_scandir)
        result = add_fragment(
            {
                "text": "相邻月目录不可读",
                "expressed_at": EXPRESSED,
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )

        assert result["success"] is True
        assert result["dedupe_check"] == "incomplete"
        assert result["dedupe_unreadable_count"] == 1
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_invalid_utf8_is_incomplete_and_still_writes(self, data_dir):
        month_dir = data_dir / "Journals" / "2026" / "11"
        month_dir.mkdir(parents=True)
        (month_dir / "life-index_2026-11-11_001.md").write_bytes(
            b"---\nkind: fragment\nsource:\n  channel: walk\n  message_id: mid-1\n---\n\n\xff"
        )

        result = add_fragment(
            {
                "text": "窗口里有非法 UTF-8",
                "expressed_at": EXPRESSED,
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )

        assert result["success"] is True
        assert result["dedupe_check"] == "incomplete"
        assert result["dedupe_unreadable_count"] == 1
        assert len(_fragments_on_disk(data_dir)) == 2

    def test_broken_frontmatter_is_incomplete_and_still_writes(self, data_dir):
        first = self._stored_with_key(data_dir)
        journal_path = Path(first["journal_path"])
        original = journal_path.read_bytes()
        broken = original.replace(b'kind: "fragment"', b"kind: [fragment", 1)
        assert broken != original
        journal_path.write_bytes(broken)

        result = add_fragment(
            {
                "text": "同一句话",
                "expressed_at": EXPRESSED,
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )

        assert result["success"] is True
        assert result["deduplicated"] is False
        assert result["dedupe_check"] == "incomplete"
        assert result["dedupe_unreadable_count"] == 1
        assert len(_fragments_on_disk(data_dir)) == 2

    def test_dedupe_does_not_depend_on_metadata_cache(self, data_dir):
        first = self._stored_with_key(data_dir)
        import shutil

        shutil.rmtree(data_dir / ".index", ignore_errors=True)
        shutil.rmtree(data_dir / ".cache", ignore_errors=True)
        result = add_fragment(
            {
                "text": "同一句话",
                "source": {"channel": "walk", "message_id": "mid-1"},
            }
        )
        assert result["success"] is True
        assert result["deduplicated"] is True
        assert result["id"] == first["id"]
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_no_key_means_not_requested(self, data_dir):
        result = add_fragment({"text": "没有来源键", "expressed_at": EXPRESSED})
        assert result["dedupe_check"] == "not_requested"


# ---------------------------------------------------------------------------
# 8. Attachments are all-or-nothing
# ---------------------------------------------------------------------------


class TestAttachments:
    def _attachment_file(self, tmp_path, name, content=b"photo-bytes"):
        source = tmp_path / name
        source.write_bytes(content)
        return source

    def test_one_missing_among_two_commits_nothing(self, data_dir, tmp_path):
        good = self._attachment_file(tmp_path, "good.png")
        missing = tmp_path / "missing.png"
        result = add_fragment(
            {
                "text": "两张图",
                "expressed_at": EXPRESSED,
                "attachments": [
                    {"source_path": str(good), "description": "在"},
                    {"source_path": str(missing), "description": "缺"},
                ],
            }
        )
        assert result["success"] is False
        assert result["error"]["code"] == "E0205"
        assert "missing.png" in result["error"]["message"]
        assert _fragments_on_disk(data_dir) == [], "no journal file"
        attachments_root = data_dir / "attachments"
        assert not attachments_root.exists() or not any(
            attachments_root.rglob("good.png")
        ), "no orphan attachment"
        assert not any(
            p.name.startswith(".write-stage-") for p in attachments_root.rglob("*")
        ), "no staging leftover"

    def test_successful_attachment_is_stored_and_recorded(self, data_dir, tmp_path):
        source = self._attachment_file(tmp_path, "pic.jpg", b"jpeg-bytes")
        result = add_fragment(
            {
                "text": "带图的原话",
                "expressed_at": EXPRESSED,
                "attachments": [{"source_path": str(source), "description": "照片"}],
            }
        )
        assert result["success"] is True
        assert result["attachments"] == ["../../../attachments/2026/11/pic.jpg"]
        stored = data_dir / "attachments" / "2026" / "11" / "pic.jpg"
        assert stored.read_bytes() == b"jpeg-bytes"
        metadata, _body = _read_stored(result)
        assert metadata["attachments"][0]["rel_path"] == "../../../attachments/2026/11/pic.jpg"
        assert _side_effect(result, "attachments")["status"] == "complete"


# ---------------------------------------------------------------------------
# 9. Fault injection
# ---------------------------------------------------------------------------


def _no_leftovers(data_dir) -> None:
    journals = data_dir / "Journals"
    attachments = data_dir / "attachments"
    assert _fragments_on_disk(data_dir) == [], "no journal file"
    if journals.exists():
        leftovers = [p for p in journals.rglob("*") if p.is_file() and p.suffix == ".tmp"] + [
            p for p in journals.rglob(".fragment-*")
        ]
        assert leftovers == [], f"temp leftovers: {leftovers}"
    if attachments.exists():
        staging = [p for p in attachments.rglob(".write-stage-*")]
        assert staging == [], f"staging leftovers: {staging}"


class TestFaultInjection:
    def test_failure_at_stage_leaves_nothing(self, data_dir, tmp_path, monkeypatch):
        from tools.fragment import core as fragment_core

        source = tmp_path / "a.png"
        source.write_bytes(b"x")

        def failing_stage(*args, **kwargs):
            raise OSError("disk full during staging")

        monkeypatch.setattr(fragment_core, "stage_attachments", failing_stage)
        result = add_fragment(
            {
                "text": "故障注入：stage",
                "expressed_at": EXPRESSED,
                "attachments": [{"source_path": str(source)}],
            }
        )
        assert result["success"] is False
        assert result["error"]["code"] == "E0200"
        _no_leftovers(data_dir)

    def test_failure_at_temp_write_leaves_nothing(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core

        def failing_temp(*args, **kwargs):
            raise OSError("disk full during temp write")

        monkeypatch.setattr(fragment_core, "_write_temp_bytes", failing_temp)
        result = add_fragment({"text": "故障注入：temp", "expressed_at": EXPRESSED})
        assert result["success"] is False
        assert result["error"]["code"] == "E0200"
        assert _side_effect(result, "journal_stage")["status"] == "failed"
        _no_leftovers(data_dir)

    def test_fsync_failure_in_real_temp_helper_removes_file(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core

        def failing_fsync(fd):
            raise OSError("fsync failed")

        monkeypatch.setattr(fragment_core.os, "fsync", failing_fsync)
        result = add_fragment({"text": "fsync 故障不能留下原文", "expressed_at": EXPRESSED})

        assert result["success"] is False
        assert result["error"]["code"] == "E0200"
        assert _side_effect(result, "journal_stage")["status"] == "failed"
        _no_leftovers(data_dir)

    def test_fsync_is_called_before_journal_hard_link(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core

        events = []
        original_fsync = fragment_core.os.fsync
        original_link = fragment_core.os.link

        def recording_fsync(fd):
            events.append("fsync")
            return original_fsync(fd)

        def recording_link(source, target):
            events.append("link")
            return original_link(source, target)

        monkeypatch.setattr(fragment_core.os, "fsync", recording_fsync)
        monkeypatch.setattr(fragment_core.os, "link", recording_link)
        result = add_fragment({"text": "先 fsync 再发布", "expressed_at": EXPRESSED})

        assert result["success"] is True
        assert "fsync" in events
        assert "link" in events
        assert events.index("fsync") < events.index("link")

    def test_failure_at_publish_leaves_nothing(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core

        def failing_publish(temp_path, final_path):
            raise FileExistsError(str(final_path))

        monkeypatch.setattr(fragment_core, "_publish_create_only", failing_publish)
        result = add_fragment({"text": "故障注入：publish", "expressed_at": EXPRESSED})
        assert result["success"] is False
        assert result["error"]["code"] == "E0207"
        assert _side_effect(result, "journal_commit")["status"] == "failed"
        _no_leftovers(data_dir)

    def test_journal_hard_link_refusal_is_clear_and_named_journal_commit(
        self, data_dir, monkeypatch
    ):
        from tools.fragment import core as fragment_core

        def refusing_link(source, target):
            raise OSError(1, "Incorrect function")

        monkeypatch.setattr(fragment_core.os, "link", refusing_link)
        result = add_fragment({"text": "硬链接失败", "expressed_at": EXPRESSED})

        assert result["success"] is False
        assert result["error"]["code"] == "E0200"
        message = result["error"]["message"]
        assert "refused a hard link" in message
        assert "without overwriting" in message
        assert "nothing was written" in message
        assert result["error"]["details"]["os_error"] == "[Errno 1] Incorrect function"
        assert _side_effect(result, "journal_commit")["status"] == "failed"
        assert not any(
            record["name"] == "attachments" and record["status"] == "failed"
            for record in result["side_effects"]
        )
        _no_leftovers(data_dir)

    def test_post_link_identity_check_failure_cannot_compensate_commit(
        self, data_dir, tmp_path, monkeypatch
    ):
        from tools.fragment import core as fragment_core

        source = tmp_path / "committed.png"
        source.write_bytes(b"committed-image")
        original_identity = getattr(fragment_core, "_file_identity", None)

        def failing_identity(path):
            if Path(path).suffix == ".md":
                raise PermissionError("post-link stat denied")
            assert original_identity is not None
            return original_identity(path)

        monkeypatch.setattr(fragment_core, "_file_identity", failing_identity, raising=False)
        result = add_fragment(
            {
                "text": "链接成功后不能再回滚附件",
                "expressed_at": EXPRESSED,
                "attachments": [{"source_path": str(source)}],
            }
        )

        assert result["success"] is True
        assert result["id"]
        assert Path(result["journal_path"]).is_file()
        assert (data_dir / "attachments" / "2026" / "11" / "committed.png").is_file()

    def test_journal_link_failure_compensates_all_published_attachments(
        self, data_dir, tmp_path, monkeypatch
    ):
        from tools.fragment import core as fragment_core

        first = tmp_path / "first.png"
        second = tmp_path / "second.txt"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        original_link = fragment_core.os.link

        def failing_journal_link(source, target):
            if Path(target).suffix == ".md":
                raise OSError("journal hard link refused")
            return original_link(source, target)

        monkeypatch.setattr(fragment_core.os, "link", failing_journal_link)
        result = add_fragment(
            {
                "text": "日志发布失败要清理两个附件",
                "expressed_at": EXPRESSED,
                "attachments": [{"source_path": str(first)}, {"source_path": str(second)}],
            }
        )

        assert result["success"] is False
        assert result["error"]["code"] == "E0200"
        _no_leftovers(data_dir)
        attachments_root = data_dir / "attachments"
        assert not attachments_root.exists() or not any(
            path.is_file() for path in attachments_root.rglob("*")
        )

    def test_attachment_publish_failure_keeps_attachments_side_effect_name(
        self, data_dir, tmp_path, monkeypatch
    ):
        from tools.fragment import core as fragment_core

        source = tmp_path / "attachment.png"
        source.write_bytes(b"image")

        def failing_attachment_publish(staging):
            raise OSError("attachment publish failed")

        monkeypatch.setattr(fragment_core, "publish_staged_attachments", failing_attachment_publish)
        result = add_fragment(
            {
                "text": "附件发布失败",
                "expressed_at": EXPRESSED,
                "attachments": [{"source_path": str(source)}],
            }
        )

        assert result["success"] is False
        assert result["error"]["code"] == "E0200"
        assert _side_effect(result, "attachments")["status"] == "failed"
        assert not any(
            record["name"] == "journal_commit" and record["status"] == "failed"
            for record in result["side_effects"]
        )
        _no_leftovers(data_dir)

    def test_temp_cleanup_failure_after_publish_preserves_identity_and_indexes(
        self, data_dir, monkeypatch
    ):
        from tools.search_journals import hierarchical_search

        original_unlink = Path.unlink

        def refusing_temp_unlink(path, *args, **kwargs):
            if path.name.startswith(".fragment-") and path.suffix == ".tmp":
                raise PermissionError("scanner holds the temporary file")
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", refusing_temp_unlink)
        result = add_fragment({"text": "扫描器锁住临时文件", "expressed_at": EXPRESSED})

        assert result["success"] is True
        assert result["write_outcome"] == "success_degraded"
        assert result["id"]
        assert result["journal_path"]
        assert result["rel_path"]
        assert Path(result["journal_path"]).is_file()
        leftovers = list(Path(result["journal_path"]).parent.glob(".fragment-*.tmp"))
        assert len(leftovers) == 1
        cleanup = _side_effect(result, "journal_cleanup")
        assert cleanup["status"] == "failed"
        assert cleanup["blocking"] is False
        assert str(leftovers[0]) in cleanup["error"]
        assert _side_effect(result, "metadata_cache_row")["status"] == "complete"
        assert _side_effect(result, "fts_row")["status"] == "complete"
        search = hierarchical_search(query="扫描器", level=3)
        assert any(
            item.get("rel_path") == result["rel_path"]
            for item in search.get("merged_results") or []
        )

    def test_failure_after_publish_keeps_fragment_and_degrades(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core

        def failing_fts(*args, **kwargs):
            raise RuntimeError("fts db locked")

        monkeypatch.setattr(fragment_core, "upsert_fts_row", failing_fts)
        result = add_fragment({"text": "故障注入：FTS", "expressed_at": EXPRESSED})
        assert result["success"] is True, "a committed fragment never fails"
        assert result["write_outcome"] == "success_degraded"
        assert _side_effect(result, "journal_commit")["status"] == "complete"
        assert _side_effect(result, "fts_row")["status"] == "failed"
        assert _side_effect(result, "fts_row")["recovery_strategy"] == "life-index index"
        assert _side_effect(result, "mark_pending")["status"] == "queued"
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_cache_failure_after_publish_keeps_fragment(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core

        def failing_cache(*args, **kwargs):
            raise RuntimeError("cache db locked")

        monkeypatch.setattr(fragment_core, "upsert_journal_cache_row", failing_cache)
        result = add_fragment({"text": "故障注入：cache", "expressed_at": EXPRESSED})
        assert result["success"] is True
        assert result["write_outcome"] == "success_degraded"
        assert _side_effect(result, "metadata_cache_row")["status"] == "failed"
        assert (
            _side_effect(result, "metadata_cache_row")["recovery_strategy"]
            == "life-index index --rebuild"
        )
        assert len(_fragments_on_disk(data_dir)) == 1

    def test_held_journals_lock_returns_timeout_and_writes_nothing(self, data_dir, monkeypatch):
        from tools.fragment import core as fragment_core
        from tools.lib.file_lock import FileLock, get_journals_lock_path

        monkeypatch.setattr(fragment_core, "FILE_LOCK_TIMEOUT_DEFAULT", 0.01)
        with FileLock(get_journals_lock_path(), timeout=0.2):
            result = add_fragment({"text": "锁被持有", "expressed_at": EXPRESSED})

        assert result["success"] is False
        assert result["error"]["code"] == "E0005"
        _no_leftovers(data_dir)


# ---------------------------------------------------------------------------
# 10. Derived parity with a full rebuild
# ---------------------------------------------------------------------------


def _fts_rows(data_dir: Path) -> list[tuple]:
    db = data_dir / ".index" / "journals_fts.db"
    conn = sqlite3.connect(str(db))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT path, title, content, date, location, weather, topic, "
            "project, tags, mood, people, file_hash "
            "FROM journals ORDER BY path"
        )
        return cursor.fetchall()
    finally:
        conn.close()


def _cache_rows(data_dir: Path) -> list[tuple]:
    db = data_dir / ".cache" / "metadata_cache.db"
    conn = sqlite3.connect(str(db))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT file_path, date, title, display_label, location, weather, topic, "
            "project, tags, mood, people, abstract, links, related_entries "
            "FROM metadata_cache ORDER BY file_path"
        )
        return cursor.fetchall()
    finally:
        conn.close()


class TestDerivedParity:
    def test_rows_after_n_adds_equal_rows_after_rebuild(self, data_dir):
        from tools.build_index import build_all

        for index in range(3):
            result = add_fragment(
                {
                    "text": f"第 {index} 条碎片，关键词 parity{index}",
                    "expressed_at": f"2026-11-1{index}T10:00:00+01:00",
                    "source": {"channel": "test", "message_id": f"m-{index}"},
                    "location": "江边" if index == 1 else None,
                }
            )
            assert result["success"] is True

        fts_before = _fts_rows(data_dir)
        cache_before = _cache_rows(data_dir)
        assert len(fts_before) == 3
        assert len(cache_before) == 3

        rebuild = build_all(incremental=False)
        assert rebuild["success"] is True

        assert _fts_rows(data_dir) == fts_before, "FTS rows must equal a rebuild's"
        assert _cache_rows(data_dir) == cache_before, "metadata-cache rows must equal a rebuild's"


# ---------------------------------------------------------------------------
# 11. search finds the fragment immediately
# ---------------------------------------------------------------------------


class TestSearchImmediately:
    def test_search_finds_fragment_with_kind_and_label(self, data_dir):
        from tools.search_journals import hierarchical_search

        result = add_fragment({"text": "傍晚在江边看到了白鹭掠过水面", "expressed_at": EXPRESSED})
        assert result["success"] is True
        search = hierarchical_search(query="白鹭", level=3)
        merged = search.get("merged_results") or []
        assert any(
            item.get("rel_path") == result["rel_path"]
            and item.get("kind") == "fragment"
            and item.get("display_label")
            for item in merged
        ), f"fragment not immediately searchable: {json.dumps(search)[:400]}"


# ---------------------------------------------------------------------------
# write stays untouched (spot check of the envelope contract fragment relies on)
# ---------------------------------------------------------------------------


class TestWriteUntouched:
    def test_write_still_appends_title_and_confirmation(self, data_dir):
        from tools.write_journal.core import write_journal

        result = write_journal(
            {"title": "普通日志", "content": "正文", "date": "2026-11-12", "topic": ["life"]}
        )
        assert result["success"] is True
        assert result["needs_confirmation"] is True
        raw = Path(result["journal_path"]).read_text(encoding="utf-8")
        assert "# 普通日志" in raw
