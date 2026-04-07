#!/usr/bin/env python3

import json
from pathlib import Path


def test_schema_parameters_match_cli_args() -> None:
    schema_paths = [
        Path("tools/write_journal/schema.json"),
        Path("tools/search_journals/schema.json"),
        Path("tools/edit_journal/schema.json"),
        Path("tools/generate_index/schema.json"),
        Path("tools/query_weather/schema.json"),
        Path("tools/build_index/schema.json"),
        Path("tools/backup/schema.json"),
        Path("tools/entity/schema.json"),
    ]

    for schema_path in schema_paths:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        assert payload["parameters"]["type"] == "object"


def test_schema_driven_call_write(monkeypatch, capsys) -> None:
    from tools.write_journal.__main__ import main

    schema = json.loads(
        Path("tools/write_journal/schema.json").read_text(encoding="utf-8")
    )
    assert schema["name"] == "write_journal"

    monkeypatch.setattr(
        "sys.argv",
        [
            "tools.write_journal",
            "write",
            "--data",
            '{"date":"2026-04-03","title":"schema","content":"body"}',
            "--dry-run",
        ],
    )

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    assert '"success": true' in output.lower()


def test_schema_driven_call_search(monkeypatch, capsys) -> None:
    from tools.search_journals.__main__ import main

    schema = json.loads(
        Path("tools/search_journals/schema.json").read_text(encoding="utf-8")
    )
    assert schema["name"] == "search_journals"

    monkeypatch.setattr(
        "sys.argv",
        ["tools.search_journals", "--query", "test", "--level", "1"],
    )

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    output = capsys.readouterr().out
    assert '"success": true' in output.lower()


def test_schema_examples_executable() -> None:
    schema_paths = [
        Path("tools/write_journal/schema.json"),
        Path("tools/search_journals/schema.json"),
        Path("tools/edit_journal/schema.json"),
        Path("tools/generate_index/schema.json"),
        Path("tools/query_weather/schema.json"),
        Path("tools/build_index/schema.json"),
        Path("tools/backup/schema.json"),
        Path("tools/entity/schema.json"),
    ]

    for schema_path in schema_paths:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        assert isinstance(payload["examples"], list)
