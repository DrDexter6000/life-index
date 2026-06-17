from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "check_public_diff_names.py"


def _private_report_dir_name() -> str:
    return "." + "agent" + "-reports"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_public_diff_names", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.blocker
def test_scanner_flags_added_private_report_dir_fixture() -> None:
    checker = _load_checker()
    diff = "\n".join(
        [
            "diff --git a/docs/runbook.md b/docs/runbook.md",
            "+++ b/docs/runbook.md",
            "@@ -1,0 +1,1 @@",
            "+state file lives under " + _private_report_dir_name() + "/server.json",
        ]
    )

    violations = checker.scan_diff_text(diff)

    assert len(violations) == 1
    assert violations[0].path == "docs/runbook.md"
    assert violations[0].line == 1
    assert violations[0].term == _private_report_dir_name()


@pytest.mark.blocker
def test_scanner_allows_clean_added_lines_and_ignores_headers() -> None:
    checker = _load_checker()
    diff = "\n".join(
        [
            "diff --git a/docs/runbook.md b/docs/runbook.md",
            "+++ b/docs/runbook.md",
            "@@ -1,0 +1,2 @@",
            "+state file lives under $PWD/.life-index-smoke/server.json",
            "+public docs stay product-generic",
        ]
    )

    assert checker.scan_diff_text(diff) == []


@pytest.mark.blocker
def test_cli_diff_file_exits_nonzero_for_violation_and_zero_for_clean(tmp_path: Path) -> None:
    dirty_diff = tmp_path / "dirty.diff"
    dirty_diff.write_text(
        "\n".join(
            [
                "diff --git a/README.md b/README.md",
                "+++ b/README.md",
                "@@ -1,0 +1,1 @@",
                "+debug path: " + _private_report_dir_name() + "/smoke",
            ]
        ),
        encoding="utf-8",
    )
    clean_diff = tmp_path / "clean.diff"
    clean_diff.write_text(
        "\n".join(
            [
                "diff --git a/README.md b/README.md",
                "+++ b/README.md",
                "@@ -1,0 +1,1 @@",
                "+debug path: $PWD/.life-index-smoke/server.json",
            ]
        ),
        encoding="utf-8",
    )

    dirty = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--diff-file", str(dirty_diff)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    clean = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--diff-file", str(clean_diff)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert dirty.returncode == 1
    assert _private_report_dir_name() in dirty.stdout
    assert clean.returncode == 0
