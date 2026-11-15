#!/usr/bin/env python3
"""Tests for the one entry-id module (``tools/lib/entry_id.py``).

The legacy recipe is pinned with a literal vector so an accidental change to
the recipe (domain prefix, separator, hash input order, digest length) fails
a test instead of silently assigning different ids.
"""

from __future__ import annotations

from pathlib import Path

from tools.lib.entry_id import (
    classify_stored_entry_id,
    is_valid_entry_id,
    legacy_entry_id,
    new_entry_id,
)

# One fixed input whose derived id is pinned byte-for-byte below.
_VECTOR_REL_PATH = "Journals/2026/03/life-index_2026-03-07_001.md"
_VECTOR_BYTES = b'---\nschema_version: 3\ntitle: "T"\ndate: 2026-03-07\n---\n\nBody\n'
_VECTOR_ID = "7d3de494d96f4af70f8b2910bec58c72"


class TestRecipe:
    def test_a_fixed_input_gives_the_pinned_id(self) -> None:
        assert legacy_entry_id(_VECTOR_REL_PATH, _VECTOR_BYTES) == _VECTOR_ID

    def test_the_pinned_id_is_a_valid_entry_id(self) -> None:
        assert is_valid_entry_id(_VECTOR_ID)

    def test_same_bytes_at_another_path_differ(self) -> None:
        other = legacy_entry_id("Journals/2026/03/life-index_2026-03-07_002.md", _VECTOR_BYTES)
        assert other != _VECTOR_ID
        assert is_valid_entry_id(other)

    def test_one_changed_byte_differs(self) -> None:
        mutated = _VECTOR_BYTES[:-2] + b"x\n"
        assert mutated != _VECTOR_BYTES
        assert legacy_entry_id(_VECTOR_REL_PATH, mutated) != _VECTOR_ID

    def test_path_case_and_spelling_are_kept_verbatim(self) -> None:
        # rel_path is not normalised: a different case is a different input.
        upper = "Journals/2026/03/Life-Index_2026-03-07_001.md"
        assert legacy_entry_id(upper, _VECTOR_BYTES) != _VECTOR_ID

    def test_the_same_file_in_two_data_directories_gets_the_same_id(self, tmp_path: Path) -> None:
        def plant(root: Path) -> Path:
            month = root / "Journals" / "2026" / "03"
            month.mkdir(parents=True)
            target = month / "life-index_2026-03-07_001.md"
            target.write_bytes(_VECTOR_BYTES)
            return target

        first, second = plant(tmp_path / "archive-a"), plant(tmp_path / "archive-b")
        rel = "Journals/2026/03/" + first.name
        assert legacy_entry_id(rel, first.read_bytes()) == _VECTOR_ID
        assert legacy_entry_id(rel, second.read_bytes()) == _VECTOR_ID


class TestNewEntryId:
    def test_a_new_id_is_valid_and_unique(self) -> None:
        assert is_valid_entry_id(new_entry_id())
        assert new_entry_id() != new_entry_id()


class TestValidityRule:
    def test_valid_shapes(self) -> None:
        assert is_valid_entry_id("0" * 32)
        assert is_valid_entry_id("a" * 32)
        assert is_valid_entry_id("0123456789abcdef" * 2)

    def test_invalid_shapes(self) -> None:
        assert not is_valid_entry_id("A" * 32)  # uppercase
        assert not is_valid_entry_id("g" * 32)  # not hexadecimal
        assert not is_valid_entry_id("0" * 31)  # too short
        assert not is_valid_entry_id("0" * 33)  # too long
        assert not is_valid_entry_id("")
        assert not is_valid_entry_id(None)
        assert not is_valid_entry_id(1234)
        assert not is_valid_entry_id(["0" * 32])


class TestClassifier:
    def test_missing(self) -> None:
        assert classify_stored_entry_id(None) == "missing"
        assert classify_stored_entry_id("") == "missing"
        assert classify_stored_entry_id("   ") == "missing"

    def test_valid(self) -> None:
        assert classify_stored_entry_id("d" * 32) == "valid"

    def test_malformed(self) -> None:
        assert classify_stored_entry_id("D" * 32) == "malformed"
        assert classify_stored_entry_id("d" * 31) == "malformed"
        assert classify_stored_entry_id("not-an-id") == "malformed"
        assert classify_stored_entry_id(42) == "malformed"
        assert classify_stored_entry_id(["d" * 32]) == "malformed"
