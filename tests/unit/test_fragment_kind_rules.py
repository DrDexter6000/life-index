#!/usr/bin/env python3
"""Unit tests for per-kind required fields and the accepted date shapes."""

from __future__ import annotations

import pytest

from tools.lib.journal_files import JournalFileKind
from tools.lib.schema import get_required_fields, validate_metadata


class TestPerKindRequiredFields:
    def test_default_kind_is_the_fragment_rule(self) -> None:
        assert get_required_fields() == ["date"]

    def test_fragment_requires_only_date(self) -> None:
        assert get_required_fields(JournalFileKind.FRAGMENT) == ["date"]

    @pytest.mark.parametrize(
        "kind",
        [
            JournalFileKind.DIGEST,
            JournalFileKind.DERIVED_INDEX,
            JournalFileKind.UNKNOWN,
        ],
    )
    def test_kinds_without_a_rule_raise(self, kind: JournalFileKind) -> None:
        with pytest.raises(ValueError):
            get_required_fields(kind)

    def test_unknown_kind_text_raises(self) -> None:
        with pytest.raises(ValueError):
            get_required_fields("bogus")  # type: ignore[arg-type]

    def test_validate_metadata_default_accepts_untitled_fragment(self) -> None:
        issues = validate_metadata({"date": "2026-03-04"})
        assert [i for i in issues if i["level"] == "error"] == []

    def test_validate_metadata_flags_missing_date_only(self) -> None:
        issues = validate_metadata({"title": "x"})
        errors = [i for i in issues if i["level"] == "error"]
        assert len(errors) == 1
        assert errors[0]["field"] == "date"

    def test_validate_metadata_fragment_kind_matches_default(self) -> None:
        assert validate_metadata({"date": "2026-03-04"}, JournalFileKind.FRAGMENT) == (
            validate_metadata({"date": "2026-03-04"})
        )


class TestDateShapes:
    @pytest.mark.parametrize(
        "date_value",
        [
            "2026-03-07",
            "2026-03-07T19:43:02",
            "2026-03-07 19:43:02",
            "2026-03-07T19:43:02.123",
            "2026-03-07 19:43:02.123456",
            "2026-03-07T19:43:02Z",
            "2026-03-07T19:43:02+01:00",
            "2026-03-07 19:43:02-05:00",
            "2026-03-07T19:43:02.5+02:00",
        ],
    )
    def test_accepted_shapes_carry_no_date_warning(self, date_value: str) -> None:
        issues = validate_metadata({"date": date_value})
        assert not [i for i in issues if i["field"] == "date"]

    @pytest.mark.parametrize(
        "date_value",
        [
            "invalid-date",
            "20260307",
            "2026-3-7",
            "2026-03-07T19:43",  # no seconds
            "2026-03-07T19:43:02+0100",  # zone without colon
            "2026-03-07X19:43:02",  # neither T nor space
            "2026-03-07  19:43:02",  # two spaces
            "2026-03-07T19:43:02 UTC",  # named zone
        ],
    )
    def test_rejected_shapes_carry_a_date_warning(self, date_value: str) -> None:
        issues = validate_metadata({"date": date_value})
        assert any(i["field"] == "date" and i["level"] == "warning" for i in issues)

    def test_empty_date_is_a_missing_field_not_a_shape_warning(self) -> None:
        issues = validate_metadata({"date": ""})
        assert [i["field"] for i in issues if i["level"] == "error"] == ["date"]
        assert not [i for i in issues if i["field"] == "date" and i["level"] == "warning"]
