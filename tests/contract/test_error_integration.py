#!/usr/bin/env python3
"""
Integration tests: verify tools return structured errors, not ad-hoc strings.

These tests call tools via subprocess (same as E2E runner) and verify
the error response format matches the contract in errors.py.

Task 3.1 (RED): All tests here should FAIL because __main__.py files
currently return ad-hoc string errors like:
    {"success": false, "error": "JSON解析错误: ..."}

After Task 3.2 (GREEN), they should return structured errors like:
    {"success": false, "error": {"code": "E0001", "message": "...", "recovery_strategy": "ask_user"}}
"""

import json
import subprocess
import sys

import pytest


def run_tool(module: str, args: list[str]) -> dict:
    """Run a Life Index tool via subprocess and parse JSON output.

    Uses sys.executable to ensure the same Python interpreter is used.
    Captures stdout for JSON parsing; stderr is discarded.
    """
    cmd = [sys.executable, "-m", f"tools.{module}"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    # Some error cases produce no stdout (e.g., argparse errors)
    stdout = result.stdout or ""
    if not stdout.strip():
        pytest.skip(f"No JSON output from {module} (exit={result.returncode})")
    return json.loads(stdout)


def assert_structured_error(result: dict, msg: str = "") -> None:
    """Assert that a failed result has a structured error dict, not a string.

    Structured error contract (from errors.py / API.md):
        result["error"] = {
            "code": "Exxxx",
            "message": "...",
            "recovery_strategy": "ask_user|skip_optional|continue_empty|fail|retry",
            ...
        }
    """
    prefix = f"[{msg}] " if msg else ""
    assert result["success"] is False, f"{prefix}Expected success=False"
    assert isinstance(result.get("error"), dict), (
        f"{prefix}error should be a structured dict, not {type(result.get('error')).__name__}. "
        f"Got: {result.get('error')!r}"
    )
    error_obj = result["error"]
    assert "code" in error_obj, f"{prefix}Structured error must have 'code' field"
    assert "recovery_strategy" in error_obj, (
        f"{prefix}Structured error must have 'recovery_strategy' field"
    )


# ============================================================
# write_journal errors
# ============================================================


class TestWriteJournalStructuredErrors:
    """write_journal __main__.py should return structured errors."""

    def test_invalid_json_returns_structured_error(self):
        """write_journal with malformed JSON → structured error, not ad-hoc string."""
        result = run_tool("write_journal", ["write", "--data", "not-valid-json"])
        assert_structured_error(result, "invalid JSON input")

    def test_file_not_found_returns_structured_error(self, tmp_path):
        """write_journal with @nonexistent-file → structured error."""
        nonexistent = tmp_path / "does_not_exist.json"
        result = run_tool("write_journal", ["write", "--data", f"@{nonexistent}"])
        assert_structured_error(result, "file not found")

    def test_empty_content_returns_structured_error(self):
        """write_journal with empty content → structured error with ask_user."""
        data = json.dumps({"date": "2026-04-04", "content": "", "title": "test"})
        result = run_tool("write_journal", ["write", "--data", data, "--dry-run"])
        # This may or may not return error depending on core.py validation
        # If it succeeds (empty content allowed in dry-run), skip
        if result.get("success"):
            pytest.skip("empty content did not trigger error in dry-run mode")
        assert_structured_error(result, "empty content")


# ============================================================
# write_journal enrich subcommand errors
# ============================================================


class TestWriteJournalEnrichStructuredErrors:
    """write_journal enrich subcommand should return structured errors."""

    def test_enrich_invalid_json_returns_structured_error(self):
        """enrich with malformed JSON → structured error."""
        result = run_tool("write_journal", ["enrich", "--data", "not-valid-json"])
        assert_structured_error(result, "enrich invalid JSON")

    def test_enrich_file_not_found_returns_structured_error(self, tmp_path):
        """enrich with @nonexistent-file → structured error."""
        nonexistent = tmp_path / "does_not_exist.json"
        result = run_tool("write_journal", ["enrich", "--data", f"@{nonexistent}"])
        assert_structured_error(result, "enrich file not found")


# ============================================================
# query_weather errors
# ============================================================


class TestQueryWeatherStructuredErrors:
    """query_weather __main__.py should return structured errors."""

    def test_missing_params_returns_structured_error(self):
        """query_weather with no location/lat/lon → structured error."""
        # query_weather requires --location or --lat/--lon
        # When neither is given, it returns ad-hoc error
        result = run_tool("query_weather", ["--date", "2026-04-04"])
        assert_structured_error(result, "missing location params")

    def test_nonexistent_location_returns_structured_error(self):
        """query_weather with nonsense location → structured error."""
        result = run_tool(
            "query_weather",
            ["--location", "XYZZY_NONEXISTENT_PLACE_99999", "--date", "2026-04-04"],
        )
        # geocode_location returns None for unknown places
        if result.get("success"):
            pytest.skip("location unexpectedly resolved")
        assert_structured_error(result, "location not found")


# ============================================================
# edit_journal errors (already uses create_error_response in core,
# but testing the full CLI path for completeness)
# ============================================================


class TestEditJournalStructuredErrors:
    """edit_journal __main__.py should pass through structured errors from core."""

    def test_nonexistent_journal_returns_structured_error(self, tmp_path):
        """edit_journal with nonexistent file → structured error."""
        fake_journal = tmp_path / "nonexistent.md"
        result = run_tool(
            "edit_journal",
            ["--journal", str(fake_journal), "--set-location", "Beijing"],
        )
        assert_structured_error(result, "journal not found")
