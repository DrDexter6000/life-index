#!/usr/bin/env python3
"""The shared "what is indexable metadata" rule (D1).

Both derived per-fragment stores — the FTS row builder and the metadata cache —
read frontmatter through ``frontmatter.normalize_indexable_metadata``. This file
pins the rule itself and proves both stores obey it: one malformed fragment must
never make a store raise, and a parsable fragment's stored values must have the
guaranteed types.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from tools.lib.frontmatter import (
    INDEXABLE_LIST_FIELDS,
    INDEXABLE_SCALAR_FIELDS,
    empty_indexable_metadata,
    normalize_indexable_metadata,
    parse_frontmatter,
)

SCALAR_FIELD = INDEXABLE_SCALAR_FIELDS[0]
LIST_FIELD = INDEXABLE_LIST_FIELDS[0]

NORMALIZED_KEYS = set(INDEXABLE_SCALAR_FIELDS) | set(INDEXABLE_LIST_FIELDS)


def _rel(journal: Path, data_dir: Path) -> str:
    return str(journal.relative_to(data_dir)).replace("\\", "/")


def _write_fragment(data_dir: Path, body: str, frontmatter: str | None) -> Path:
    month = data_dir / "Journals" / "2026" / "03"
    month.mkdir(parents=True, exist_ok=True)
    journal = month / "life-index_2026-03-04_001.md"
    text = f"---\n{frontmatter}\n---\n\n{body}\n" if frontmatter is not None else f"{body}\n"
    journal.write_text(text, encoding="utf-8")
    return journal


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
    @pytest.mark.parametrize("value", [{"nested": "value"}, [1, 2], []])
    def test_a_mapping_or_list_in_a_scalar_field_makes_the_frontmatter_unparsable(
        self, field, value
    ):
        assert normalize_indexable_metadata({field: value}) is None


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
        "value",
        [{"nested": "value"}, [{"nested": "value"}], [["nested"]]],
    )
    def test_a_mapping_or_a_mapping_item_makes_the_frontmatter_unparsable(self, field, value):
        assert normalize_indexable_metadata({field: value}) is None

    @pytest.mark.parametrize("field", INDEXABLE_LIST_FIELDS)
    @pytest.mark.parametrize("value", ["scalar", 7, True])
    def test_a_scalar_list_field_is_not_unparsable(self, field, value):
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
    """Violations of the rule never escape the parser as an exception."""

    @pytest.mark.parametrize(
        "frontmatter",
        [
            "- a\n- b",
            "just a scalar",
            "title: T\ndate: 2026-99-99",
            "title: [unterminated",
        ],
    )
    def test_unparsable_documents_still_yield_the_body(self, frontmatter):
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

        conn = sqlite3.connect(str(isolated_data_dir / ".index" / "journals_fts.db"))
        try:
            fts_row = conn.execute(
                "SELECT title, date, location, weather, project, topic, tags, mood, people "
                "FROM journals WHERE path = ?",
                (_rel(journal, isolated_data_dir),),
            ).fetchone()
        finally:
            conn.close()
        assert fts_row == (
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

    def test_fts_row_and_cache_row_agree_for_an_unparsable_file(self, isolated_data_dir):
        from tools.build_index import build_all
        from tools.lib.metadata_cache import get_all_cached_metadata

        journal = _write_fragment(
            isolated_data_dir,
            "unparsable body",
            "title: {nested: value}\ntopic: [life]",
        )
        assert build_all(incremental=False)["success"] is True

        conn = sqlite3.connect(str(isolated_data_dir / ".index" / "journals_fts.db"))
        try:
            title, content = conn.execute(
                "SELECT title, content FROM journals WHERE path = ?",
                (_rel(journal, isolated_data_dir),),
            ).fetchone()
        finally:
            conn.close()
        assert title == ""
        assert "unparsable" in content  # raw-text row over the whole file

        cached = next(
            item
            for item in get_all_cached_metadata()
            if item["rel_path"] == _rel(journal, isolated_data_dir)
        )
        assert cached["title"] == ""
        assert cached["date"] == ""
        assert cached["topic"] == []
        assert cached["tags"] == []
        json.dumps(cached["metadata"])  # JSON-safe: no dict leaked into a field
