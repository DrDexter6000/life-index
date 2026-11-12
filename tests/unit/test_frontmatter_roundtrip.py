#!/usr/bin/env python3
"""Frontmatter serialisation round-trip and byte-identity tests.

``format_frontmatter`` is the single writer for journal frontmatter, so two
properties are pinned here:

* every value it accepts survives ``parse_frontmatter(format_frontmatter(...))``;
* ordinary values keep the exact bytes the writer produced before the escaping
  bug was fixed (no format drift for existing journals).
"""

import json
from typing import Any, Dict, List, Tuple

import pytest

from tools.lib.frontmatter import FIELD_ORDER, format_frontmatter, parse_frontmatter


def _roundtrip(meta: Dict[str, Any]) -> Dict[str, Any]:
    parsed, body = parse_frontmatter(format_frontmatter(meta) + "\n\nbody\n")
    assert body == "body"
    return parsed


ROUNDTRIP_CASES = [
    # --- the four reported failures -----------------------------------------
    ("title_with_double_quote", {"title": 'He said "hi" to me'}),
    ("title_with_windows_path", {"title": "path C:\\temp\\new"}),
    ("title_with_newline", {"title": "line one\nline two"}),
    ("occurred_mapping", {"occurred": {"from": 2008, "to": None, "precision": "year"}}),
    # --- quote / backslash edge cases ---------------------------------------
    ("only_a_double_quote", {"title": '"'}),
    ("string_ending_in_backslash", {"title": "ends with \\"}),
    # --- strings that YAML would otherwise resolve to another type ----------
    ("string_true", {"summary": "true"}),
    ("string_null", {"summary": "null"}),
    ("string_number", {"summary": "123"}),
    ("string_date", {"summary": "2026-03-07"}),
    ("string_timestamp", {"summary": "2026-03-07T10:00:00+01:00"}),
    # --- whitespace / unicode / empty --------------------------------------
    ("leading_and_trailing_spaces", {"title": "  padded  "}),
    ("emoji_and_cjk", {"title": "今天心情不错 😀🎉"}),
    ("empty_string", {"title": ""}),
    # --- control characters that JSON leaves raw ---------------------------
    ("tab_and_newline", {"title": "a\tb\nc"}),
    ("del_and_c1_controls", {"title": "a\x7fb\x85c\x9fd"}),
    (
        "yaml_line_separators",
        {
            "title": "a\u2028 b\u2029 c",
            "details": {"plain": "p\u2028 q", "list": ["x\u2029 y"]},
        },
    ),
    # --- top-level scalars --------------------------------------------------
    (
        "top_level_scalars",
        {"count": 42, "rating": 3.14, "published": True, "draft": False},
    ),
    (
        "float_scalars",
        {
            "score": 1e20,
            "tiny": 1e-7,
            "negative": -0.5,
            "whole": 1.0,
            "huge": 1.7976931348623157e308,
        },
    ),
    ("infinite_floats", {"high": float("inf"), "low": float("-inf")}),
    (
        "floats_in_lists_and_mappings",
        {
            "values": [1e20, 1e-7, 2.5, 0.0],
            "details": {"big": 1e20, "small": 1e-7},
        },
    ),
    # --- mappings -----------------------------------------------------------
    (
        "nested_mapping",
        {
            "occurred": {
                "from": 2008,
                "to": None,
                "precision": "year",
                "all_day": True,
                "confidence": 0.75,
                "label": "2026-03-07T10:00:00+01:00",
                "enabled": "true",
                "count": "123",
                "tags": ["work", "2026-03-07"],
                "inner": {"level": 2, "note": 'he said "hi"', "missing": None},
                "empty_map": {},
                "empty_list": [],
                "items": [{"k": "v"}, {"n": 1}],
                "2026-03-07": "key that looks like a date",
                "true": "key that looks like a bool",
            }
        },
    ),
    (
        "nested_unicode_and_backslashes",
        {
            "details": {
                "title": '他说 "你好" 😀',
                "path": "C:\\temp\\new",
                "multi": "line one\nline two",
                "键": "值",
                "when": "2026-03-07",
            }
        },
    ),
    # --- lists stay inline JSON --------------------------------------------
    (
        "list_of_mappings_with_quotes",
        {
            "attachments": [
                {"note": 'he said "hi"', "n": 1},
                {"note": "back\\slash", "n": 2},
            ]
        },
    ),
    (
        "list_of_mixed_scalars",
        {
            "values": [
                "true",
                "null",
                "123",
                "2026-03-07",
                "2026-03-07T10:00:00+01:00",
                1,
                None,
                False,
                2.5,
            ]
        },
    ),
    # --- parser delimiters --------------------------------------------------
    ("string_with_triple_hyphen", {"title": "a---b", "details": {"note": "x---y"}}),
    ("title_is_only_triple_hyphen", {"title": "---"}),
    # --- date field ---------------------------------------------------------
    ("date_only", {"date": "2026-03-07"}),
    ("date_timestamp_with_offset", {"date": "2026-03-07T10:00:00+01:00"}),
    ("date_timestamp_in_zulu_form", {"date": "2026-03-07T10:00:00Z"}),
    ("date_empty_string", {"date": ""}),
    # --- None ---------------------------------------------------------------
    ("unknown_field_none", {"note": None}),
    ("known_field_none_is_omitted", {"title": "Test", "location": None}),
]


@pytest.mark.parametrize(
    "case_id,meta", ROUNDTRIP_CASES, ids=[case_id for case_id, _meta in ROUNDTRIP_CASES]
)
def test_every_value_roundtrips(case_id: str, meta: Dict[str, Any]) -> None:
    parsed = _roundtrip(meta)

    expected_keys = {"schema_version"}
    for key, value in meta.items():
        if key in FIELD_ORDER and value is None:
            # Known-order None fields stay omitted (current behaviour).
            assert key not in parsed
            continue
        assert parsed[key] == value, f"{case_id}: {key!r} did not round-trip"
        expected_keys.add(key)

    # schema_version is always emitted; nothing else may be invented.
    assert set(parsed) == expected_keys


@pytest.mark.parametrize(
    "case_id,meta", ROUNDTRIP_CASES, ids=[case_id for case_id, _meta in ROUNDTRIP_CASES]
)
def test_formatting_is_stable(case_id: str, meta: Dict[str, Any]) -> None:
    first = format_frontmatter(meta)
    reparsed = _roundtrip(meta)
    assert format_frontmatter(reparsed) == first, f"{case_id}: formatting is not stable"


def test_nan_float_is_stable() -> None:
    text = format_frontmatter({"score": float("nan")})

    assert "score: .nan" in text
    parsed, _body = parse_frontmatter(text + "\n\nbody\n")
    assert parsed["score"] != parsed["score"]  # NaN never compares equal
    assert format_frontmatter(parsed) == text


def test_nested_timestamp_parses_as_string_not_datetime() -> None:
    content = (
        "---\n"
        'title: "Nested timestamps"\n'
        "occurred:\n"
        "  from: 2008-01-01\n"
        "  at: 2026-03-07T10:00:00+01:00\n"
        "flags: [2026-03-07, true]\n"
        "---\n"
        "\n"
        "body\n"
    )

    parsed, _body = parse_frontmatter(content)

    assert parsed["occurred"] == {
        "from": "2008-01-01",
        "at": "2026-03-07T10:00:00+01:00",
    }
    assert parsed["flags"] == ["2026-03-07", True]
    json.dumps(parsed)


def test_mapping_is_written_as_block_yaml() -> None:
    text = format_frontmatter(
        {
            "occurred": {
                "from": 2008,
                "to": None,
                "precision": "year",
                "note": "2026-03-07",
                "inner": {"depth": 2},
            }
        }
    )
    lines = text.split("\n")
    start = lines.index("occurred:")

    assert lines[start + 1] == "  from: 2008"
    assert lines[start + 2] == "  to: null"
    assert lines[start + 3] == "  precision: year"
    assert lines[start + 4] == '  note: "2026-03-07"'
    assert lines[start + 5] == "  inner:"
    assert lines[start + 6] == "    depth: 2"


# ---------------------------------------------------------------------------
# Byte identity for ordinary values
#
# Every expected string below was produced by the *unmodified*
# ``format_frontmatter`` before the escaping fix. They are literals on purpose:
# ordinary journals must not drift.
# ---------------------------------------------------------------------------

BYTE_IDENTITY_CASES: List[Tuple[str, Dict[str, Any], str]] = [
    (
        "minimal_required_fields",
        {
            "title": "Test",
            "date": "2026-03-10",
        },
        ("---\n" "schema_version: 3\n" 'title: "Test"\n' "date: 2026-03-10\n" "---"),
    ),
    (
        "complete_fields",
        {
            "title": "Complete Test",
            "date": "2026-03-10T14:30:00",
            "location": "Beijing, China",
            "weather": "Sunny 25°C",
            "mood": ["happy", "productive"],
            "people": ["Alice", "Bob"],
            "tags": ["test", "demo"],
            "project": "Life-Index",
            "topic": ["work", "create"],
            "abstract": "Test abstract",
            "links": ["https://example.com"],
            "attachments": ["file1.txt", "file2.txt"],
        },
        (
            "---\n"
            "schema_version: 3\n"
            'title: "Complete Test"\n'
            "date: 2026-03-10T14:30:00\n"
            'location: "Beijing, China"\n'
            'weather: "Sunny 25°C"\n'
            'mood: ["happy", "productive"]\n'
            'people: ["Alice", "Bob"]\n'
            'tags: ["test", "demo"]\n'
            'project: "Life-Index"\n'
            'topic: ["work", "create"]\n'
            'abstract: "Test abstract"\n'
            'links: ["https://example.com"]\n'
            'attachments: ["file1.txt", "file2.txt"]\n'
            "---"
        ),
    ),
    (
        "all_field_order_fields",
        {
            "schema_version": 3,
            "title": "关于晴岚的事",
            "date": "2026-03-20T21:46:00+01:00",
            "location": "Lagos, Nigeria",
            "weather": "Sunny 32°C",
            "mood": ["happy"],
            "entities": ["Qinglan", "Tuantuan"],
            "people": ["Alice"],
            "tags": ["test"],
            "project": "Life-Index",
            "topic": ["work"],
            "summary": "摘要",
            "abstract": "旧摘要",
            "links": ["https://example.com"],
            "related_entries": ["Journals/2026/03/life-index_2026-03-10_001.md"],
            "attachments": [
                {
                    "filename": "photo.jpg",
                    "rel_path": "../../../attachments/2026/03/photo.jpg",
                    "description": "A nice photo",
                }
            ],
        },
        (
            "---\n"
            "schema_version: 3\n"
            'title: "关于晴岚的事"\n'
            "date: 2026-03-20T21:46:00+01:00\n"
            'location: "Lagos, Nigeria"\n'
            'weather: "Sunny 32°C"\n'
            'mood: ["happy"]\n'
            'entities: ["Qinglan", "Tuantuan"]\n'
            'people: ["Alice"]\n'
            'tags: ["test"]\n'
            'project: "Life-Index"\n'
            'topic: ["work"]\n'
            'summary: "摘要"\n'
            'abstract: "旧摘要"\n'
            'links: ["https://example.com"]\n'
            'related_entries: ["Journals/2026/03/life-index_2026-03-10_001.md"]\n'
            'attachments: [{"filename": "photo.jpg", '
            '"rel_path": "../../../attachments/2026/03/photo.jpg", '
            '"description": "A nice photo"}]\n'
            "---"
        ),
    ),
    (
        "legacy_fixture_shape",
        {
            "date": "2025-01-15",
            "location": "Beijing",
            "weather": "Sunny",
            "weight_kg": 72.5,
            "mood": ["calm"],
            "project": "Life-Index",
            "tags": ["dev"],
        },
        (
            "---\n"
            "schema_version: 3\n"
            "date: 2025-01-15\n"
            'location: "Beijing"\n'
            'weather: "Sunny"\n'
            'mood: ["calm"]\n'
            'tags: ["dev"]\n'
            'project: "Life-Index"\n'
            "weight_kg: 72.5\n"
            "---"
        ),
    ),
    (
        "edit_reserialised_journal",
        {
            "title": "Original Title",
            "date": "2026-03-14",
            "location": "Lagos, Nigeria",
            "weather": "Sunny 32°C",
            "mood": ["happy"],
            "tags": ["test"],
        },
        (
            "---\n"
            "schema_version: 3\n"
            'title: "Original Title"\n'
            "date: 2026-03-14\n"
            'location: "Lagos, Nigeria"\n'
            'weather: "Sunny 32°C"\n'
            'mood: ["happy"]\n'
            'tags: ["test"]\n'
            "---"
        ),
    ),
    (
        "chinese_daily_entry",
        {
            "title": "今天状态不错",
            "date": "2026-03-10T14:30:00",
            "location": "北京，中国",
            "weather": "晴天 25°C",
            "mood": ["开心", "充实"],
            "people": ["小明"],
            "tags": ["生活"],
            "topic": ["work", "生活"],
            "summary": "今天完成了写作任务。",
        },
        (
            "---\n"
            "schema_version: 3\n"
            'title: "今天状态不错"\n'
            "date: 2026-03-10T14:30:00\n"
            'location: "北京，中国"\n'
            'weather: "晴天 25°C"\n'
            'mood: ["开心", "充实"]\n'
            'people: ["小明"]\n'
            'tags: ["生活"]\n'
            'topic: ["work", "生活"]\n'
            'summary: "今天完成了写作任务。"\n'
            "---"
        ),
    ),
    (
        "scalar_extras_and_omitted_none",
        {
            "title": "Scalars",
            "date": "2026-03-10",
            "location": None,
            "published": True,
            "draft": False,
            "count": 42,
            "rating": 3.14,
        },
        (
            "---\n"
            "schema_version: 3\n"
            'title: "Scalars"\n'
            "date: 2026-03-10\n"
            "published: true\n"
            "draft: false\n"
            "count: 42\n"
            "rating: 3.14\n"
            "---"
        ),
    ),
    (
        "empty_values",
        {
            "title": "",
            "date": "2026-03-10",
            "location": "",
            "weather": "",
            "mood": [],
            "tags": [],
            "topic": [],
            "links": [],
            "attachments": [],
        },
        (
            "---\n"
            "schema_version: 3\n"
            'title: ""\n'
            "date: 2026-03-10\n"
            'location: ""\n'
            'weather: ""\n'
            "mood: []\n"
            "tags: []\n"
            "topic: []\n"
            "links: []\n"
            "attachments: []\n"
            "---"
        ),
    ),
    (
        "commas_and_urls",
        {
            "title": "London, United Kingdom — day one",
            "date": "2026-03-10",
            "location": "London, United Kingdom",
            "project": "Life-Index",
            "links": ["https://example.com/a?b=c&d=e", "https://example.org/x/y"],
            "related_entries": [
                "Journals/2026/03/life-index_2026-03-09_001.md",
                "Journals/2026/03/life-index_2026-03-08_001.md",
            ],
        },
        (
            "---\n"
            "schema_version: 3\n"
            'title: "London, United Kingdom — day one"\n'
            "date: 2026-03-10\n"
            'location: "London, United Kingdom"\n'
            'project: "Life-Index"\n'
            'links: ["https://example.com/a?b=c&d=e", "https://example.org/x/y"]\n'
            'related_entries: ["Journals/2026/03/life-index_2026-03-09_001.md", '
            '"Journals/2026/03/life-index_2026-03-08_001.md"]\n'
            "---"
        ),
    ),
    (
        "attachment_dicts",
        {
            "title": "With attachments",
            "date": "2026-03-10",
            "attachments": [
                {
                    "filename": "file.png",
                    "rel_path": "../../../attachments/2026/03/file.png",
                },
                {
                    "filename": "no_path.png",
                    "description": "No path",
                },
            ],
        },
        (
            "---\n"
            "schema_version: 3\n"
            'title: "With attachments"\n'
            "date: 2026-03-10\n"
            'attachments: [{"filename": "file.png", '
            '"rel_path": "../../../attachments/2026/03/file.png"}, '
            '{"filename": "no_path.png", "description": "No path"}]\n'
            "---"
        ),
    ),
]


@pytest.mark.parametrize(
    "case_id,meta,expected",
    BYTE_IDENTITY_CASES,
    ids=[case_id for case_id, _meta, _expected in BYTE_IDENTITY_CASES],
)
def test_ordinary_values_stay_byte_identical(
    case_id: str, meta: Dict[str, Any], expected: str
) -> None:
    assert format_frontmatter(meta) == expected


def test_byte_identity_cases_cover_field_order() -> None:
    covered = set()
    for _case_id, meta, _expected in BYTE_IDENTITY_CASES:
        covered.update(meta)

    assert set(FIELD_ORDER) <= covered
