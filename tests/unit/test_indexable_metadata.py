#!/usr/bin/env python3
"""The shared "what is indexable metadata" rule and the shared date rule.

Both derived per-fragment stores — the FTS row builder and the metadata cache —
read frontmatter through ``frontmatter.normalize_indexable_metadata``. This file
pins the rule itself and proves both stores obey it: a malformed field costs only
that field, one malformed fragment must never make a store raise, and every
reader dates a fragment by the one date rule.
"""

import sqlite3
from pathlib import Path

import pytest

from tools.lib.frontmatter import (
    INDEXABLE_LIST_FIELDS,
    INDEXABLE_SCALAR_FIELDS,
    empty_indexable_metadata,
    frontmatter_is_unreadable,
    indexable_date,
    normalize_indexable_metadata,
    parse_frontmatter,
)

SCALAR_FIELD = INDEXABLE_SCALAR_FIELDS[0]
LIST_FIELD = INDEXABLE_LIST_FIELDS[0]

NORMALIZED_KEYS = set(INDEXABLE_SCALAR_FIELDS) | set(INDEXABLE_LIST_FIELDS)

FRAGMENT = Path("Journals/2026/03/life-index_2026-03-04_001.md")


def _rel(journal: Path, data_dir: Path) -> str:
    return str(journal.relative_to(data_dir)).replace("\\", "/")


def _write_fragment(data_dir: Path, body: str, frontmatter: str | None) -> Path:
    month = data_dir / "Journals" / "2026" / "03"
    month.mkdir(parents=True, exist_ok=True)
    journal = month / FRAGMENT.name
    text = f"---\n{frontmatter}\n---\n\n{body}\n" if frontmatter is not None else f"{body}\n"
    journal.write_text(text, encoding="utf-8")
    return journal


def _fts_row(data_dir: Path, journal: Path) -> sqlite3.Row:
    conn = sqlite3.connect(str(data_dir / ".index" / "journals_fts.db"))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM journals WHERE path = ?", (_rel(journal, data_dir),)
        ).fetchone()
    finally:
        conn.close()


class TestRootRule:
    @pytest.mark.parametrize("root", [None, {}, [], ["a", "b"], "just a scalar", 42])
    def test_a_non_mapping_or_empty_root_is_unparsable(self, root):
        assert normalize_indexable_metadata(root) is None

    def test_a_non_empty_mapping_is_parsable_even_with_only_unknown_keys(self):
        result = normalize_indexable_metadata({"custom": {"nested": [1, 2]}})

        assert result is not None
        assert set(result) == NORMALIZED_KEYS
        assert result[SCALAR_FIELD] == ""
        assert result[LIST_FIELD] == []

    def test_every_indexable_field_defaults_to_its_empty_value(self):
        result = normalize_indexable_metadata({"unknown": "value"})

        assert result is not None
        assert all(result[key] == "" for key in INDEXABLE_SCALAR_FIELDS)
        assert all(result[key] == [] for key in INDEXABLE_LIST_FIELDS)
        assert result == empty_indexable_metadata()


class TestScalarFields:
    @pytest.mark.parametrize("field", INDEXABLE_SCALAR_FIELDS)
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, ""),
            ("text", "text"),
            ("2026-03-04", "2026-03-04"),
            (2024, "2024"),
            (3.5, "3.5"),
            (True, "True"),
            (False, "False"),
        ],
    )
    def test_scalar_values_become_text(self, field, value, expected):
        result = normalize_indexable_metadata({field: value})

        assert result is not None, f"{field}={value!r} must stay indexable"
        assert result[field] == expected

    @pytest.mark.parametrize("field", INDEXABLE_SCALAR_FIELDS)
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ({"nested": "value"}, "nested: value"),
            ([1, 2], "1, 2"),
            ([], ""),
            ([{"a": 1}, [2]], "a: 1, 2"),
            ({"a": [1, {"b": 2}]}, "a: 1, b: 2"),
        ],
    )
    def test_a_mapping_or_list_in_a_scalar_field_is_flattened(self, field, value, expected):
        result = normalize_indexable_metadata({field: value})

        assert result is not None, f"{field}={value!r} must stay indexable"
        assert result[field] == expected

    def test_non_string_keys_are_rendered_with_str(self):
        result = normalize_indexable_metadata({"title": {2024: "x", True: [1]}})

        assert result is not None
        assert result["title"] == "2024: x, True: 1"

    def test_flattening_a_recursive_value_never_raises(self):
        cyclic = []
        cyclic.append(cyclic)

        result = normalize_indexable_metadata({"title": cyclic, "topic": cyclic})

        assert result is not None
        assert result["title"] == ""
        assert result["topic"] == [""]

    @pytest.mark.parametrize("depth", [12, 5000])
    def test_a_leaf_stays_searchable_at_any_depth(self, depth):
        """No depth limit: a token nested deeper than any limit would be lost."""
        deep = "leaf"
        for _ in range(depth):
            deep = [deep]

        result = normalize_indexable_metadata({"title": deep, "tags": [deep]})

        assert result is not None
        assert result["title"] == "leaf"
        assert result["tags"] == ["leaf"]


class TestListFields:
    @pytest.mark.parametrize("field", INDEXABLE_LIST_FIELDS)
    def test_a_list_keeps_each_item_as_text(self, field):
        result = normalize_indexable_metadata({field: ["alpha", 2, True]})

        assert result is not None
        assert result[field] == ["alpha", "2", "True"]

    @pytest.mark.parametrize("field", INDEXABLE_LIST_FIELDS)
    def test_a_scalar_becomes_a_one_item_list(self, field):
        result = normalize_indexable_metadata({field: "alpha"})

        assert result is not None
        assert result[field] == ["alpha"]

    @pytest.mark.parametrize("field", INDEXABLE_LIST_FIELDS)
    def test_none_becomes_an_empty_list(self, field):
        result = normalize_indexable_metadata({field: None})

        assert result is not None
        assert result[field] == []

    @pytest.mark.parametrize("field", INDEXABLE_LIST_FIELDS)
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ({"nested": "value"}, ["nested: value"]),
            ([{"nested": "value"}], ["nested: value"]),
            ([["nested"]], ["nested"]),
            ([{"url": "https://example.com"}], ["url: https://example.com"]),
            ({"url": "https://example.com"}, ["url: https://example.com"]),
            ([{"a": [1, 2]}, None], ["a: 1, 2", ""]),
        ],
    )
    def test_a_mapping_or_a_nested_item_becomes_flattened_text(self, field, value, expected):
        result = normalize_indexable_metadata({field: value})

        assert result is not None
        assert result[field] == expected

    @pytest.mark.parametrize("field", INDEXABLE_LIST_FIELDS)
    @pytest.mark.parametrize("value", ["scalar", 7, True])
    def test_a_scalar_list_field_is_one_item(self, field, value):
        result = normalize_indexable_metadata({field: value})

        assert result is not None
        assert result[field] == [str(value)]

    def test_unknown_keys_never_make_a_file_unparsable(self):
        result = normalize_indexable_metadata(
            {
                "title": "kept",
                "topic": ["life"],
                "schema_version": "2.1.0",
                "attachments": [{"filename": "a.png"}],
                "entities": {"x": ["y"]},
            }
        )

        assert result is not None
        assert result["title"] == "kept"
        assert result["topic"] == ["life"]
        assert "attachments" not in result
        assert "entities" not in result


class TestParseFrontmatterStaysReadable:
    """Malformed documents never escape the parser as an exception."""

    @pytest.mark.parametrize(
        "frontmatter",
        [
            "- a\n- b",
            "just a scalar",
            "title: T\ndate: 2026-99-99",
            "title: [unterminated",
            "title: T\ncustom: &a [*a]",
        ],
    )
    def test_unreadable_documents_still_yield_the_body(self, frontmatter):
        metadata, body = parse_frontmatter(f"---\n{frontmatter}\n---\n\nthe body\n")

        assert metadata == {}
        assert body == "the body"

    def test_a_list_root_does_not_raise_from_the_legacy_content_merge(self):
        metadata, body = parse_frontmatter("---\n- a\n- b\n---\n\nbody\n")

        assert metadata == {}
        assert body == "body"

    def test_an_impossible_date_does_not_raise(self):
        metadata, body = parse_frontmatter("---\ntitle: T\ndate: 2026-99-99\n---\n\nbody\n")

        assert metadata == {}
        assert body == "body"

    def test_a_recursive_alias_is_unreadable(self):
        content = "---\ntitle: T\ncustom: &a [*a]\n---\n\nbody\n"

        metadata, body = parse_frontmatter(content)

        assert metadata == {}
        assert body == "body"
        assert frontmatter_is_unreadable(content) is True

    def test_every_returned_string_is_utf8_encodable(self):
        content = '---\nlocation: "\\uD800"\n"\\uDC00key": value\n---\n\nbody\n'

        metadata, body = parse_frontmatter(content)

        assert metadata["location"] == "\ufffd"
        assert metadata["\ufffdkey"] == "value"
        assert body == "body"
        for value in metadata.values():
            assert isinstance(value, str)
            value.encode("utf-8")


class TestFrontmatterIsUnreadable:
    @pytest.mark.parametrize(
        "content",
        [
            "---\n- a\n- b\n---\n\nbody\n",
            "---\njust a scalar\n---\n\nbody\n",
            "---\ntitle: [unterminated\n---\n\nbody\n",
            "---\ntitle: T\ncustom: &a [*a]\n---\n\nbody\n",
            # a falsy root that is not a mapping is still text the user wrote
            "---\nfalse\n---\n\nbody\n",
            "---\n0\n---\n\nbody\n",
            "---\n[]\n---\n\nbody\n",
            '---\n""\n---\n\nbody\n',
            # a recursive reference hidden in tuples (``!!pairs``)
            "---\ntitle: T\ncustom: &a !!pairs [x: *a]\n---\n\nbody\n",
            "---\ntitle: T\ncontent: &a [*a]\n---\n\nbody\n",
        ],
    )
    def test_a_present_block_without_a_mapping_is_unreadable(self, content):
        assert frontmatter_is_unreadable(content) is True

    @pytest.mark.parametrize(
        "content",
        [
            "no frontmatter at all\n",
            "---\n---\n\nbody\n",
            "---\ntitle: T\ndate: 2026-03-04\n---\n\nbody\n",
            '---\ntitle: T\ncontent: "line one\nline two\n---\n\nbody\n',
        ],
    )
    def test_a_readable_or_absent_block_is_not_unreadable(self, content):
        assert frontmatter_is_unreadable(content) is False

    def test_the_legacy_content_recovery_is_still_readable(self):
        content = '---\ntitle: T\ncontent: "line one\nline two\n---\n\nbody\n'

        metadata, body = parse_frontmatter(content)

        assert metadata == {"title": "T"}
        assert "line one" in body


class TestDateRule:
    @pytest.mark.parametrize(
        ("frontmatter_date", "expected"),
        [
            ("2026-03-08", "2026-03-08"),
            ("2026-03-08T10:00:00", "2026-03-08"),
            # Shape only: no calendar check.
            ("2026-99-99", "2026-99-99"),
            ("20260311", "2026-03-04"),
            ("2026-3-8", "2026-03-04"),
            ("[2026]", "2026-03-04"),
            (None, "2026-03-04"),
        ],
    )
    def test_frontmatter_date_then_filename(self, frontmatter_date, expected):
        indexable = normalize_indexable_metadata({"date": frontmatter_date})

        assert indexable is not None
        assert indexable_date(indexable, FRAGMENT) == expected

    def test_a_non_canonical_filename_has_no_fallback_date(self):
        indexable = empty_indexable_metadata()

        assert indexable_date(indexable, Path("notes.md")) == ""

    def test_the_fts_row_and_the_cache_row_use_the_same_fallback_date(self, isolated_data_dir):
        from tools.build_index import build_all
        from tools.lib.metadata_cache import get_all_cached_metadata

        journal = _write_fragment(
            isolated_data_dir,
            "dateword",
            "title: T\ndate: 20260311",
        )
        assert build_all(incremental=False)["success"] is True

        row = _fts_row(isolated_data_dir, journal)
        cached = next(
            item
            for item in get_all_cached_metadata()
            if item["rel_path"] == _rel(journal, isolated_data_dir)
        )

        assert row["date"] == "2026-03-04"
        assert cached["date"] == row["date"]

    def test_the_fallback_scan_uses_the_same_fallback_date(self, isolated_data_dir):
        from tools.search_journals.l3_content import search_l3_content

        journal = _write_fragment(
            isolated_data_dir,
            "dateword first hit\ndateword second hit",
            "title: T\ndate: [2026]",
        )

        results = search_l3_content("dateword")

        hit = next(
            item
            for item in results
            if str(item["path"]).replace("\\", "/") == str(journal).replace("\\", "/")
        )
        assert hit["date"] == "2026-03-04"


class TestBothDerivedStoresUseTheSameRule:
    def test_fts_row_and_cache_row_agree_for_a_parsable_scalar_file(self, isolated_data_dir):
        from tools.build_index import build_all
        from tools.lib.metadata_cache import get_all_cached_metadata

        journal = _write_fragment(
            isolated_data_dir,
            "scalar body",
            "title: 2024\ndate: 2026-03-04\nlocation: 42\nweather: true\n"
            "project: 3.5\ntopic: life\ntags: alpha, beta\nmood: calm\npeople: Alice",
        )
        assert build_all(incremental=False)["success"] is True

        row = _fts_row(isolated_data_dir, journal)
        assert (
            row["title"],
            row["date"],
            row["location"],
            row["weather"],
            row["project"],
            row["topic"],
            row["tags"],
            row["mood"],
            row["people"],
        ) == (
            "2024",
            "2026-03-04",
            "42",
            "True",
            "3.5",
            "life",
            "alpha, beta",
            "calm",
            "Alice",
        )

        cached = next(
            item
            for item in get_all_cached_metadata()
            if item["rel_path"] == _rel(journal, isolated_data_dir)
        )
        assert cached["title"] == "2024"
        assert cached["date"] == "2026-03-04"
        assert cached["weather"] == "True"
        assert cached["topic"] == ["life"]
        assert cached["tags"] == ["alpha, beta"]
        assert cached["mood"] == ["calm"]
        assert cached["people"] == ["Alice"]

    def test_a_malformed_field_costs_only_that_field(self, isolated_data_dir):
        from tools.build_index import build_all
        from tools.lib.metadata_cache import get_all_cached_metadata
        from tools.search_journals.core import hierarchical_search

        journal = _write_fragment(
            isolated_data_dir,
            "reviewbodytoken",
            "title: Review Title\ndate: 2026-03-04\ntopic: [work]\n"
            "links:\n  - url: https://example.com",
        )
        assert build_all(incremental=False)["success"] is True

        row = _fts_row(isolated_data_dir, journal)
        assert row["title"] == "Review Title"
        assert row["topic"] == "work"
        assert row["date"] == "2026-03-04"

        cached = next(
            item
            for item in get_all_cached_metadata()
            if item["rel_path"] == _rel(journal, isolated_data_dir)
        )
        assert cached["title"] == "Review Title"
        assert cached["topic"] == ["work"]
        assert cached["date"] == "2026-03-04"
        assert cached["links"] == ["url: https://example.com"]

        response = hierarchical_search(query="Review Title", level=3)
        assert response["success"] is True
        hits = {
            str(item.get("path") or "").replace("\\", "/")
            for item in (response.get("merged_results") or [])
        }
        assert str(journal).replace("\\", "/") in hits

    def test_fts_row_and_cache_row_agree_for_an_unparsable_file(self, isolated_data_dir):
        from tools.build_index import build_all
        from tools.lib.metadata_cache import get_all_cached_metadata

        journal = _write_fragment(
            isolated_data_dir,
            "unparsable body",
            "- a\n- b",
        )
        assert build_all(incremental=False)["success"] is True

        row = _fts_row(isolated_data_dir, journal)
        assert row["title"] == ""
        assert row["date"] == "2026-03-04"  # from the filename
        assert "unparsable" in row["content"]  # raw-text row over the whole file

        cached = next(
            item
            for item in get_all_cached_metadata()
            if item["rel_path"] == _rel(journal, isolated_data_dir)
        )
        assert cached["title"] == ""
        assert cached["date"] == row["date"]
        assert cached["topic"] == []
        assert cached["tags"] == []

    def test_a_frontmatter_with_only_a_private_key_dates_like_the_fts_row(self, isolated_data_dir):
        from tools.build_index import build_all
        from tools.lib.metadata_cache import get_all_cached_metadata

        journal = _write_fragment(isolated_data_dir, "privatekeybody", "_custom: x")
        assert build_all(incremental=False)["success"] is True

        row = _fts_row(isolated_data_dir, journal)
        cached = next(
            item
            for item in get_all_cached_metadata()
            if item["rel_path"] == _rel(journal, isolated_data_dir)
        )

        # The mapping is readable (it only has an ignored key), so the date
        # falls back to the filename in both stores — never one empty and one
        # filled.
        assert row["date"] == "2026-03-04"
        assert cached["date"] == row["date"]

    def test_a_recursive_alias_is_indexed_as_raw_text(self, isolated_data_dir):
        from tools.build_index import build_all

        journal = _write_fragment(
            isolated_data_dir,
            "recursivebodytoken",
            "title: T\ndate: 2026-03-04\ncustom: &a [*a]",
        )

        result = build_all(incremental=False)

        assert result["success"] is True
        assert result["fts"]["unparsable_paths"] == [_rel(journal, isolated_data_dir)]
        row = _fts_row(isolated_data_dir, journal)
        assert row["title"] == ""
        assert "recursivebodytoken" in row["content"]

    def test_a_lone_surrogate_is_stored_as_replacement_character(self, isolated_data_dir):
        from tools.build_index import build_all
        from tools.lib.metadata_cache import get_all_cached_metadata

        journal = _write_fragment(
            isolated_data_dir,
            "surrogatebody",
            'title: S\ndate: 2026-03-04\nlocation: "\\uD800"',
        )

        result = build_all(incremental=False)

        assert result["success"] is True
        row = _fts_row(isolated_data_dir, journal)
        assert row["location"] == "\ufffd"
        cached = next(
            item
            for item in get_all_cached_metadata()
            if item["rel_path"] == _rel(journal, isolated_data_dir)
        )
        assert cached["location"] == "\ufffd"


class TestEveryYamlCollectionType:
    """``yaml.safe_load`` also builds tuples (``!!pairs``/``!!omap``) and sets."""

    def test_a_set_renders_in_one_order_whatever_the_hash_seed(self):
        result = normalize_indexable_metadata(
            {"title": {"gamma", "alpha", "beta"}, "tags": {"zeta", "eta"}}
        )

        assert result is not None
        assert result["title"] == "alpha, beta, gamma"
        assert result["tags"] == ["eta", "zeta"]

    def test_pairs_are_flattened_like_a_list(self):
        metadata, _body = parse_frontmatter("---\ntitle: !!pairs [x: one, y: two]\n---\n\nb\n")

        result = normalize_indexable_metadata(metadata)

        assert result is not None
        assert result["title"] == "x, one, y, two"

    def test_a_lone_surrogate_inside_pairs_is_replaced(self):
        metadata, _body = parse_frontmatter(
            '---\ntitle: !!pairs [x: "\\uD800"]\ntags: !!set {"\\uD800 tag": null}\n---\n\nb\n'
        )

        result = normalize_indexable_metadata(metadata)

        assert result is not None
        assert result["title"] == "x, \ufffd"
        assert result["tags"] == ["\ufffd tag"]

    def test_an_integer_too_long_for_decimal_text_does_not_raise(self):
        huge = int("f" * 6000, 16)

        result = normalize_indexable_metadata({"title": huge, "tags": [huge]})

        assert result is not None
        assert result["title"] == hex(huge)
        assert result["tags"] == [hex(huge)]

    def test_binary_is_decoded_not_repr(self):
        result = normalize_indexable_metadata({"title": b"hello \xff"})

        assert result is not None
        assert result["title"] == "hello \ufffd"


class TestLegacyContentKey:
    def test_a_content_value_that_is_not_text_stays_in_the_metadata(self):
        metadata, body = parse_frontmatter(
            "---\ntitle: T\ncontent: [irreplaceabletoken]\n---\n\nbody\n"
        )

        assert metadata == {"title": "T", "content": ["irreplaceabletoken"]}
        assert body == "body"

    def test_legacy_content_with_a_lone_surrogate_gives_an_encodable_body(self):
        metadata, body = parse_frontmatter(
            '---\ntitle: T\ncontent: "\\uD800 legacy text"\n---\n\nbody\n'
        )

        assert metadata == {"title": "T"}
        assert body.encode("utf-8").decode("utf-8") == "\ufffd legacy text\n\nbody"


class TestNormalizationIsTotal:
    """Whatever a loader could hand over, the rule returns bindable text."""

    @staticmethod
    def _random_value(rng, depth: int):
        import datetime as dt

        leaves = [
            None,
            True,
            0,
            -7,
            3.5,
            float("nan"),
            float("inf"),
            "",
            "plain",
            "中文",
            "\ud800 lone",
            b"bytes \xff",
            dt.date(2026, 3, 4),
            dt.datetime(2026, 3, 4, 5, 6, 7),
            10**5000,
        ]
        if depth <= 0 or rng.random() < 0.4:
            return rng.choice(leaves)
        size = rng.randint(0, 3)
        kind = rng.choice(["dict", "list", "tuple", "set"])
        if kind == "dict":
            keys = [rng.choice(["k", 2024, True, None, 1.5, "\ud800key"]) for _ in range(size)]
            return {key: TestNormalizationIsTotal._random_value(rng, depth - 1) for key in keys}
        if kind == "set":
            return {rng.choice(["a", "b", 1, 2.5, None, ("t", 1)]) for _ in range(size)}
        items = [TestNormalizationIsTotal._random_value(rng, depth - 1) for _ in range(size)]
        return items if kind == "list" else tuple(items)

    def test_random_nested_values_never_raise_and_stay_bindable(self):
        import random

        rng = random.Random(20261113)
        fields = list(INDEXABLE_SCALAR_FIELDS) + list(INDEXABLE_LIST_FIELDS)
        for _ in range(400):
            metadata = {field: self._random_value(rng, 4) for field in fields}
            metadata[2024] = "ignored"

            result = normalize_indexable_metadata(metadata)

            assert result is not None
            assert result == normalize_indexable_metadata(metadata)
            for field in INDEXABLE_SCALAR_FIELDS:
                assert isinstance(result[field], str)
                result[field].encode("utf-8")
            for field in INDEXABLE_LIST_FIELDS:
                assert isinstance(result[field], list)
                for item in result[field]:
                    assert isinstance(item, str)
                    item.encode("utf-8")
            assert isinstance(indexable_date(result, FRAGMENT), str)

    def test_a_value_that_contains_itself_through_a_tuple_never_raises(self):
        inner: list = []
        inner.append(("x", inner))

        result = normalize_indexable_metadata({"title": inner, "tags": inner})

        assert result is not None
        assert result["title"] == "x, "


class TestUncachedReaderUsesTheSameRule:
    """The L2 reader that bypasses the cache returns what the cache would store."""

    def test_cached_and_uncached_readers_agree(self, isolated_data_dir):
        from tools.lib.metadata_cache import init_metadata_cache, parse_and_cache_journal
        from tools.search_journals.l2_metadata import _read_metadata_without_cache

        journal = _write_fragment(
            isolated_data_dir,
            "body",
            "title: 2024\ndate: 20260311\ntopic: work\ntags:\npeople: [{name: Ann}]",
        )

        uncached = _read_metadata_without_cache(journal)
        conn = init_metadata_cache()
        try:
            cached = parse_and_cache_journal(conn, journal)
        finally:
            conn.close()

        assert uncached is not None and cached is not None
        for field in ("date", "title", "topic", "tags", "people", "mood", "links"):
            assert uncached[field] == cached[field], field
        assert uncached["date"] == "2026-03-04"  # 20260311 is not a date: filename
        assert uncached["topic"] == ["work"]
        assert uncached["people"] == ["name: Ann"]

    def test_a_file_that_is_not_utf8_is_still_returned(self, isolated_data_dir):
        from tools.search_journals.l2_metadata import _read_metadata_without_cache

        journal = _write_fragment(isolated_data_dir, "body", "title: T")
        journal.write_bytes(b"---\ntitle: T\n---\n\nbody \xff\n")

        entry = _read_metadata_without_cache(journal)

        assert entry is not None
        assert entry["date"] == "2026-03-04"
        assert entry["title"] == ""
