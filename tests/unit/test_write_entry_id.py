#!/usr/bin/env python3
"""Tests for the durable entry id on the `write` path (H1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.lib.entry_id import is_valid_entry_id
from tools.lib.frontmatter import parse_frontmatter
from tools.write_journal.core import write_journal


def _payload(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "date": "2026-03-07",
        "title": "Entry id journal",
        "content": "The journal body.",
        "topic": ["work"],
        "location": "Test City",
        "weather": "Sunny",
    }
    payload.update(extra)
    return payload


def _journals(isolated_data_dir: Path) -> list[Path]:
    return list((isolated_data_dir / "Journals").rglob("life-index_*.md"))


class TestWriteAssignsId:
    def test_write_returns_and_stores_a_valid_id(self, isolated_data_dir: Path) -> None:
        result = write_journal(_payload())

        assert result["success"] is True, result
        assert is_valid_entry_id(result["id"])
        metadata, _body = parse_frontmatter(Path(result["journal_path"]).read_text("utf-8"))
        assert metadata["id"] == result["id"]

    def test_two_writes_get_different_ids(self, isolated_data_dir: Path) -> None:
        first = write_journal(_payload())
        second = write_journal(_payload(title="Second journal"))

        assert first["success"] and second["success"]
        assert is_valid_entry_id(first["id"])
        assert is_valid_entry_id(second["id"])
        assert first["id"] != second["id"]

    def test_dry_run_returns_null_and_writes_nothing(self, isolated_data_dir: Path) -> None:
        result = write_journal(_payload(), dry_run=True)

        assert result["success"] is True, result
        assert result["id"] is None
        assert _journals(isolated_data_dir) == [], "dry run must not commit a journal"

    def test_a_degraded_post_commit_outcome_still_returns_the_id(
        self, isolated_data_dir: Path, monkeypatch: Any
    ) -> None:
        # A projection failure inside the commit helper — after the journal
        # file is committed, before the helper returns — must still return
        # the id, and it must be the id stored in the published file.
        from tools.write_journal import core as write_core

        def failing_projection(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("post-commit projection exploded")

        monkeypatch.setattr(
            write_core, "_update_postcommit_derived_projections", failing_projection
        )
        result = write_journal(_payload())

        assert result["success"] is True, result
        assert result["write_outcome"] == "success_degraded"
        assert is_valid_entry_id(result["id"])
        metadata, _body = parse_frontmatter(Path(result["journal_path"]).read_text("utf-8"))
        assert (
            result["id"] == metadata["id"]
        ), "the returned id must be the id stored in the published file"


class TestWriteKeyRule:
    """Payload keys that become frontmatter keys follow the one shared rule."""

    @pytest.mark.parametrize(
        "bad_key",
        [
            "extra: null\n---\nforged",
            "padded ",
            " padded",
            "with:colon",
            "",
            2024,
        ],
        ids=[
            "closing-delimiter",
            "trailing-space",
            "leading-space",
            "colon",
            "empty",
            "non-string",
        ],
    )
    def test_an_unwritable_payload_key_is_refused_and_named(
        self, isolated_data_dir: Path, bad_key: Any
    ) -> None:
        from tools.write_journal import write_journal as write

        payload = _payload()
        payload[bad_key] = "x"
        result = write(payload)

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == (
            bad_key if isinstance(bad_key, str) else repr(bad_key)
        )
        assert _journals(isolated_data_dir) == [], "no file may be created by the refused write"

    def test_the_delimiter_key_cannot_push_the_id_into_the_body(
        self, isolated_data_dir: Path
    ) -> None:
        """The reproduced shape: a key spanning a ``---`` line used to push
        the generated id into the body while the write reported success with
        a returned id that was never stored."""
        from tools.write_journal import write_journal as write

        result = write(_payload(**{"extra: null\n---\nforged": "x"}))

        assert result["success"] is False, result
        assert result["error"]["details"]["field"] == "extra: null\n---\nforged"
        assert _journals(isolated_data_dir) == []


class TestWriteReadsBackTheStoredId:
    def test_a_render_without_the_generated_id_is_refused(
        self, isolated_data_dir: Path, monkeypatch: Any
    ) -> None:
        """If the final rendered journal does not read back with the
        generated id, nothing is published (belt and braces behind the key
        rule)."""
        from tools.lib.frontmatter import format_journal_content

        from tools.write_journal import core as write_core

        def render_without_id(payload: dict[str, Any]) -> str:
            return format_journal_content(
                {key: value for key, value in payload.items() if key != "id"}
            )

        monkeypatch.setattr(write_core, "format_content", render_without_id)
        result = write_core.write_journal(_payload())

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "id"
        assert _journals(isolated_data_dir) == []


class TestCallerDictionaryNeverGainsId:
    def test_dry_run_then_real_write_with_the_same_dictionary(
        self, isolated_data_dir: Path
    ) -> None:
        from tools.write_journal import write_journal as write

        payload = _payload()
        preview = write(payload, dry_run=True)
        assert preview["success"] is True, preview
        assert "id" not in payload, "the caller's dictionary never gains id"

        committed = write(payload)
        assert committed["success"] is True, committed
        assert is_valid_entry_id(committed["id"])
        assert "id" not in payload


class TestWriteRefusesCallerSuppliedId:
    def test_a_supplied_id_is_refused(self, isolated_data_dir: Path) -> None:
        result = write_journal(_payload(id="a" * 32))

        assert result["success"] is False, result
        assert result["error"]["code"] == "E0001"
        assert result["error"]["details"]["field"] == "id"
        assert _journals(isolated_data_dir) == [], "no file may be created by the refused write"

    def test_clearing_or_nulling_via_the_key_is_refused_too(self, isolated_data_dir: Path) -> None:
        for supplied in ("", None):
            result = write_journal(_payload(id=supplied))
            assert result["success"] is False, result
            assert result["error"]["details"]["field"] == "id"


class TestRenderFailureStillSurfaces:
    def test_a_render_failure_without_attachments_is_reported_not_swallowed(
        self, isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import tools.write_journal.core as core

        def broken_render(_data: dict[str, Any]) -> str:
            raise ValueError("render failed")

        monkeypatch.setattr(core, "format_content", broken_render)

        result = write_journal(_payload())

        assert result["success"] is False, result
        assert "render failed" in str(result.get("error"))
        assert _journals(isolated_data_dir) == []
