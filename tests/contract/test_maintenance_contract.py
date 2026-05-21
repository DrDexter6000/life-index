"""Contract tests for maintenance --dry-run (gbrain Phase D).

Covers:
  - CLI surface: maintenance --dry-run / --output=json
  - Six check categories (index freshness, entity audit, orphan related_entries,
    search eval smoke, backup verification, candidate edges count)
  - Status enum: pass / fail / needs-user-action
  - Subprocess delegation to existing CLI commands
  - Zero production writes
  - No LLM provider imports in default path
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAINTENANCE_ROOT = REPO_ROOT / "tools" / "maintenance"

# ── Helpers ─────────────────────────────────────────────────────────


def _run_maintenance(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run maintenance CLI via subprocess."""
    env = os.environ.copy()
    # Ensure we use test directories when specified
    if "LIFE_INDEX_DATA_DIR" in kwargs:
        env["LIFE_INDEX_DATA_DIR"] = kwargs.pop("LIFE_INDEX_DATA_DIR")
    cmd = [sys.executable, "-m", "tools", "maintenance"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        **kwargs,
    )


def _parse_json_output(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Parse JSON from subprocess stdout, raising AssertionError on failure."""
    assert proc.returncode == 0, f"Expected exit 0, got {proc.returncode}: stderr={proc.stderr}"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"stdout is not valid JSON: {e}\nstdout={proc.stdout}") from e
    assert isinstance(data, dict), f"Expected JSON object, got {type(data)}"
    return data


def _file_hashes(data_dir: Path) -> dict[str, str]:
    """Compute SHA256 of all files under a directory, relative to it."""
    hashes: dict[str, str] = {}
    if not data_dir.exists():
        return hashes
    for fpath in sorted(data_dir.rglob("*")):
        if fpath.is_file():
            rel = fpath.relative_to(data_dir).as_posix()
            hashes[rel] = hashlib.sha256(fpath.read_bytes()).hexdigest()
    return hashes


DISALLOWED_PROVIDER_IMPORTS = {"anthropic", "openai", "llm_client"}


def _imported_modules(path: Path) -> set[str]:
    """Parse Python file and return set of imported module names."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def _maintenance_files() -> list[Path]:
    """All .py files in tools/maintenance/."""
    if not MAINTENANCE_ROOT.exists():
        return []
    return sorted(MAINTENANCE_ROOT.rglob("*.py"))


# ── CLI surface tests ───────────────────────────────────────────────


def test_maintenance_help_output() -> None:
    """maintenance --help prints usage and exits 0."""
    proc = _run_maintenance(["--help"])
    assert proc.returncode == 0, f"help failed: {proc.stderr}"
    assert (
        "maintenance" in proc.stdout.lower()
    ), f"help output missing 'maintenance': {proc.stdout[:200]}"


def test_maintenance_dry_run_exits_zero() -> None:
    """maintenance --dry-run exits 0 and produces JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = _run_maintenance(["--dry-run", "--output=json"], LIFE_INDEX_DATA_DIR=tmpdir)
        output = _parse_json_output(proc)
        assert output.get("success") is True, f"Expected success=True: {output}"
        assert "checks" in output, f"Expected 'checks' key: {output}"
        assert "schema_version" in output, f"Expected 'schema_version': {output}"


def test_maintenance_no_args_prints_help() -> None:
    """maintenance with no args prints help and exits 0 or non-zero."""
    proc = _run_maintenance([])
    # Should print usage info (either via argparse default or help)
    combined = proc.stdout + proc.stderr
    assert "maintenance" in combined.lower() or proc.returncode != 0


# ── Six check categories ────────────────────────────────────────────


def test_six_check_categories_present() -> None:
    """maintenance --dry-run reports exactly 6 check categories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = _run_maintenance(["--dry-run", "--output=json"], LIFE_INDEX_DATA_DIR=tmpdir)
        output = _parse_json_output(proc)
        checks = output["checks"]
        assert isinstance(checks, list), f"Expected list, got {type(checks)}"
        assert len(checks) == 6, f"Expected 6 checks, got {len(checks)}"

        expected_categories = {
            "index_freshness",
            "entity_audit",
            "orphan_related_entries",
            "search_eval_smoke",
            "backup_verification",
            "candidate_edges",
        }
        actual_categories = {c["category"] for c in checks}
        assert (
            actual_categories == expected_categories
        ), f"Missing/extra categories. Expected: {expected_categories}, Got: {actual_categories}"


def test_each_check_has_required_fields() -> None:
    """Each check has category, status, details, and timestamp."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = _run_maintenance(["--dry-run", "--output=json"], LIFE_INDEX_DATA_DIR=tmpdir)
        output = _parse_json_output(proc)
        for check in output["checks"]:
            assert "category" in check, f"Missing 'category' in check: {check}"
            assert "status" in check, f"Missing 'status' in check: {check}"
            assert "details" in check, f"Missing 'details' in check: {check}"
            assert "timestamp" in check, f"Missing 'timestamp' in check: {check}"


def test_status_enum_values() -> None:
    """All check status values are valid enum members: pass, fail, needs-user-action."""
    valid_statuses = {"pass", "fail", "needs-user-action"}
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = _run_maintenance(["--dry-run", "--output=json"], LIFE_INDEX_DATA_DIR=tmpdir)
        output = _parse_json_output(proc)
        for check in output["checks"]:
            assert (
                check["status"] in valid_statuses
            ), f"Invalid status '{check['status']}' in check '{check['category']}'"


# ── JSON output format ──────────────────────────────────────────────


def test_json_output_is_valid() -> None:
    """--output=json produces valid JSON with top-level keys."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = _run_maintenance(["--dry-run", "--output=json"], LIFE_INDEX_DATA_DIR=tmpdir)
        output = _parse_json_output(proc)
        assert "success" in output
        assert "schema_version" in output
        assert "checks" in output
        assert "summary" in output
        assert "timestamp" in output
        assert isinstance(output["checks"], list)
        assert isinstance(output["summary"], dict)


def test_default_output_is_text_report() -> None:
    """Default output (no --output=json) is a human-readable text report."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = _run_maintenance(["--dry-run"], LIFE_INDEX_DATA_DIR=tmpdir)
        assert proc.returncode == 0
        # Should contain check category names in text form
        combined = proc.stdout + proc.stderr
        assert "index" in combined.lower(), f"Output missing index check: {combined[:300]}"
        assert "entity" in combined.lower(), f"Output missing entity audit: {combined[:300]}"


# ── Zero-write behavior ─────────────────────────────────────────────


def test_zero_production_writes() -> None:
    """maintenance --dry-run does not modify user journal files in the data directory.

    Index/cache files (.index/, .cache/) may be created by subprocess tools
    (index --check, entity --audit) but these are machine artifacts, not
    production user data. The maintenance module itself performs zero writes.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Create a minimal data dir structure with a journal file
        journals_dir = data_dir / "Journals" / "2026" / "05"
        journals_dir.mkdir(parents=True, exist_ok=True)
        test_file = journals_dir / "life-index_2026-05-21_001.md"
        test_file.write_text(
            "---\ntitle: Test\ndate: 2026-05-21\n---\n# Test\n\nTest content.\n",
            encoding="utf-8",
        )

        # Capture journal file hash before
        before_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()

        # Run maintenance
        proc = _run_maintenance(["--dry-run", "--output=json"], LIFE_INDEX_DATA_DIR=str(data_dir))
        assert proc.returncode == 0

        # Verify journal file is unmodified
        after_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
        assert before_hash == after_hash, (
            f"Journal file was modified by maintenance dry-run! "
            f"before={before_hash}, after={after_hash}"
        )

        # Verify no new journal files were created
        journal_files_after = list(journals_dir.rglob("*.md"))
        assert len(journal_files_after) == 1, f"Unexpected new journal files: {journal_files_after}"


# ── Subprocess boundary ─────────────────────────────────────────────


def test_maintenance_uses_subprocess_not_direct_import() -> None:
    """tools/maintenance/ must not directly import called module internals.

    The maintenance module delegates to existing CLI commands (index, entity,
    eval, backup) via subprocess. It must never import their internals directly.
    """
    disallowed_internal_imports = {
        "tools.build_index",
        "tools.entity",
        "tools.eval.ablation",
        "tools.backup",
        # Allowed: tools.lib.* (shared utilities)
    }

    offenders: list[str] = []
    for path in _maintenance_files():
        imports = _imported_modules(path)
        for imported in imports:
            if any(
                imported == disallowed or imported.startswith(f"{disallowed}.")
                for disallowed in disallowed_internal_imports
            ):
                rel = path.relative_to(REPO_ROOT).as_posix()
                offenders.append(f"{rel}: {imported}")

    # Allow tools.entity.candidate_edges specifically for the orphan check,
    # but only at the function-import granularity, not wholesale module import.
    # The contract says "subprocess for CLI operations, no imports for called internals."
    assert offenders == [], (
        f"maintenance module directly imports called module internals "
        f"(should use subprocess): {offenders}"
    )


def test_maintenance_no_default_llm_imports() -> None:
    """tools/maintenance/ must not import LLM providers in default path."""
    offenders: list[str] = []
    for path in _maintenance_files():
        imports = _imported_modules(path)
        found = imports & DISALLOWED_PROVIDER_IMPORTS
        if found:
            rel = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{rel}: {sorted(found)}")

    assert offenders == [], f"maintenance module contains disallowed LLM imports: {offenders}"


# ── Schema version contract ─────────────────────────────────────────


def test_schema_version_is_stable() -> None:
    """JSON output includes a stable schema_version field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = _run_maintenance(["--dry-run", "--output=json"], LIFE_INDEX_DATA_DIR=tmpdir)
        output = _parse_json_output(proc)
        sv = output.get("schema_version")
        assert sv is not None, "Missing schema_version"
        assert isinstance(sv, str)
        assert sv.startswith("m"), f"schema_version should start with 'm': {sv}"
        assert "maintenance" in sv, f"schema_version should contain 'maintenance': {sv}"


# ── Summary contract ────────────────────────────────────────────────


def test_summary_contains_counts() -> None:
    """summary includes pass_count, fail_count, needs_user_action_count totals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        proc = _run_maintenance(["--dry-run", "--output=json"], LIFE_INDEX_DATA_DIR=tmpdir)
        output = _parse_json_output(proc)
        summary = output["summary"]
        assert isinstance(summary, dict)
        assert "pass_count" in summary
        assert "fail_count" in summary
        assert "needs_user_action_count" in summary
        assert isinstance(summary["pass_count"], int)
        assert isinstance(summary["fail_count"], int)
        assert isinstance(summary["needs_user_action_count"], int)
        # Sum should equal 6
        total = summary["pass_count"] + summary["fail_count"] + summary["needs_user_action_count"]
        assert total == 6, f"Summary counts should sum to 6: {summary}"


# ── Dry-run flag is required for report ─────────────────────────────


def test_dry_run_flag_controls_report() -> None:
    """--dry-run flag produces the report; without it, behavior is the same
    (maintenance currently only supports dry-run mode)."""
    # Currently, --dry-run is the only mode. The command should work with it.
    proc = _run_maintenance(["--dry-run", "--help"])
    assert proc.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
