"""Tests for the public diff private-name scanner."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / ".github" / "scripts" / "check_public_diff_names.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_public_diff_names_for_tests", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _diff_for_added_line(text: str) -> str:
    return "\n".join(
        [
            "diff --git a/README.md b/README.md",
            "--- a/README.md",
            "+++ b/README.md",
            "@@ -417,0 +418 @@",
            f"+{text}",
        ]
    )


def test_public_gui_repo_markdown_link_is_allowed() -> None:
    gui_repo = "life-index" + "-gui"
    public_url = "https://github.com/DrDexter6000/" + gui_repo
    diff = _diff_for_added_line(f"公开 GUI 仓库 [`{gui_repo}`]({public_url})。")

    assert CHECKER.scan_diff_text(diff) == []


def test_gui_workshop_variant_still_fails() -> None:
    gui_repo = "life-index" + "-gui"
    private_workshop = gui_repo + "-workshop"
    diff = _diff_for_added_line("private repo: " + private_workshop)

    violations = CHECKER.scan_diff_text(diff)

    assert len(violations) == 1
    assert violations[0].term == gui_repo


def test_gui_underscore_variant_still_fails() -> None:
    private_name = "life-index" + "_gui"
    diff = _diff_for_added_line("private repo: " + private_name)

    violations = CHECKER.scan_diff_text(diff)

    assert len(violations) == 1
    assert violations[0].term == private_name


def test_host_bridge_sandbox_variant_still_fails() -> None:
    private_name = "host" + "-bridge" + "-sandbox"
    diff = _diff_for_added_line("private repo: " + private_name)

    violations = CHECKER.scan_diff_text(diff)

    assert len(violations) == 1
    assert violations[0].term == private_name
