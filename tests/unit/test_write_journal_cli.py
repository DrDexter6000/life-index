#!/usr/bin/env python3

import sys
from unittest.mock import patch

import pytest

from tools.write_journal.__main__ import main


def test_write_journal_cli_confirm_subcommand_calls_apply_confirmation_updates(
    monkeypatch, tmp_path
) -> None:
    captured = {}

    def fake_apply_confirmation_updates(**kwargs):
        captured.update(kwargs)
        return {"success": True, "journal_path": str(kwargs["journal_path"])}

    monkeypatch.setattr(
        "tools.write_journal.__main__.apply_confirmation_updates",
        fake_apply_confirmation_updates,
        raising=False,
    )
    monkeypatch.setattr("tools.write_journal.__main__.ensure_dirs", lambda: None)
    monkeypatch.setattr("tools.write_journal.__main__._emit_json", lambda payload: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "write_journal",
            "confirm",
            "--journal",
            str(tmp_path / "journal.md"),
            "--location",
            "New City",
            "--weather",
            "New Weather",
            "--approve-related",
            "Journals/2026/03/a.md",
            "--approve-related",
            "Journals/2026/03/b.md",
            "--approve-related-id",
            "1",
            "--reject-related",
            "Journals/2026/03/c.md",
            "--reject-related-id",
            "2",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert captured["location"] == "New City"
    assert captured["weather"] == "New Weather"
    assert captured["approved_related_entries"] == [
        "Journals/2026/03/a.md",
        "Journals/2026/03/b.md",
    ]
    assert captured["approved_related_candidate_ids"] == [1]
    assert captured["rejected_related_entries"] == ["Journals/2026/03/c.md"]
    assert captured["rejected_related_candidate_ids"] == [2]


def test_unified_cli_routes_confirm_to_write_journal(monkeypatch) -> None:
    import tools.__main__ as tools_main

    class FakeModule:
        called = False

        @staticmethod
        def main():
            FakeModule.called = True

    monkeypatch.setattr(sys, "argv", ["life-index", "confirm", "--journal", "foo.md"])
    monkeypatch.setattr(
        tools_main, "__import__", lambda *args, **kwargs: FakeModule, raising=False
    )

    tools_main.main()

    assert FakeModule.called is True
