#!/usr/bin/env python3

import json
from pathlib import Path


def test_write_journal_schema_declares_links_and_related_entries() -> None:
    schema = json.loads(
        (Path("tools/write_journal") / "schema.json").read_text(encoding="utf-8")
    )

    properties = schema["parameters"]["properties"]

    assert "links" in properties
    assert "related_entries" in properties


def test_write_journal_schema_declares_structured_confirmation_returns() -> None:
    schema = json.loads(
        (Path("tools/write_journal") / "schema.json").read_text(encoding="utf-8")
    )

    returns = schema["returns"]["properties"]
    assert returns["confirmation"]["type"] == "object"
    assert "properties" in returns["confirmation"]
    assert "location" in returns["confirmation"]["properties"]
    assert "related_candidates" in returns["confirmation"]["properties"]
    assert returns["related_candidates"]["type"] == "array"
    assert "items" in returns["related_candidates"]


def test_write_journal_schema_has_examples() -> None:
    schema = json.loads(
        (Path("tools/write_journal") / "schema.json").read_text(encoding="utf-8")
    )

    assert schema["examples"]


def test_edit_journal_schema_declares_links_and_related_entries_support() -> None:
    schema = json.loads(
        (Path("tools/edit_journal") / "schema.json").read_text(encoding="utf-8")
    )

    updates = schema["parameters"]["properties"]["updates"]
    assert updates["type"] == "object"
    assert "properties" in updates
    assert "links" in updates["properties"]
    assert "related_entries" in updates["properties"]


def test_valid_schema_passes_validation(tmp_path: Path) -> None:
    from tools.lib.schema_validator import validate_tool_schema

    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft-07/schema#",
                "name": "write_journal",
                "description": "写入日志",
                "version": "1.0.0",
                "parameters": {"type": "object", "properties": {}, "required": []},
                "returns": {"type": "object", "properties": {}},
                "examples": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    errors = validate_tool_schema(schema_path)

    assert errors == []


def test_missing_name_rejected(tmp_path: Path) -> None:
    from tools.lib.schema_validator import validate_tool_schema

    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft-07/schema#",
                "description": "写入日志",
                "version": "1.0.0",
                "parameters": {"type": "object", "properties": {}, "required": []},
                "returns": {"type": "object", "properties": {}},
                "examples": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    errors = validate_tool_schema(schema_path)

    assert any("name" in error for error in errors)


def test_missing_parameters_rejected(tmp_path: Path) -> None:
    from tools.lib.schema_validator import validate_tool_schema

    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft-07/schema#",
                "name": "write_journal",
                "description": "写入日志",
                "version": "1.0.0",
                "returns": {"type": "object", "properties": {}},
                "examples": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    errors = validate_tool_schema(schema_path)

    assert any("parameters" in error for error in errors)


def test_invalid_json_schema_rejected(tmp_path: Path) -> None:
    from tools.lib.schema_validator import validate_tool_schema

    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")

    errors = validate_tool_schema(schema_path)

    assert errors


def test_all_tool_schemas_exist() -> None:
    tool_dirs = [
        "tools/write_journal",
        "tools/write_journal/confirm",
        "tools/search_journals",
        "tools/edit_journal",
        "tools/generate_abstract",
        "tools/query_weather",
        "tools/build_index",
        "tools/backup",
        "tools/entity",
    ]

    missing = [path for path in tool_dirs if not (Path(path) / "schema.json").exists()]

    assert missing == []


def test_all_tool_schemas_valid() -> None:
    from tools.lib.schema_validator import validate_tool_schema

    tool_dirs = [
        "tools/write_journal",
        "tools/write_journal/confirm",
        "tools/search_journals",
        "tools/edit_journal",
        "tools/generate_abstract",
        "tools/query_weather",
        "tools/build_index",
        "tools/backup",
        "tools/entity",
    ]

    invalid: list[tuple[str, list[str]]] = []
    for path in tool_dirs:
        schema_path = Path(path) / "schema.json"
        errors = validate_tool_schema(schema_path)
        if errors:
            invalid.append((path, errors))

    assert invalid == []


def test_confirm_schema_declares_applied_and_ignored_feedback() -> None:
    schema = json.loads(
        (Path("tools/write_journal/confirm") / "schema.json").read_text(
            encoding="utf-8"
        )
    )

    params = schema["parameters"]["properties"]
    returns = schema["returns"]["properties"]

    assert "journal" in params
    assert "approve_related" in params
    assert "approve_related_id" in params
    assert "reject_related" in params
    assert "reject_related_id" in params
    assert "candidate_context" in params
    assert "applied_fields" in returns
    assert "ignored_fields" in returns
    assert "approved_related_entries" in returns
    assert "confirm_status" in returns
    assert "relation_summary" in returns
    assert "approved_candidate_ids" in returns
    assert "rejected_related_entries" in returns
    assert "rejected_candidate_ids" in returns
    assert "approval_summary" in returns
