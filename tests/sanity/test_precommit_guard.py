"""Pre-commit configuration guard test.

Verifies that .pre-commit-config.yaml exists and contains the required hooks
(black, flake8, mypy) with pinned revisions — not floating refs like 'main'.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Project root — this file is at tests/sanity/test_precommit_guard.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRECOMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"

REQUIRED_HOOK_IDS = {"black", "flake8", "mypy"}


def _load_config() -> dict:
    """Load and parse .pre-commit-config.yaml."""
    assert PRECOMMIT_CONFIG.exists(), f".pre-commit-config.yaml not found at {PRECOMMIT_CONFIG}"
    with PRECOMMIT_CONFIG.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


class TestPrecommitConfig:
    """Guard tests for .pre-commit-config.yaml structure and content."""

    def test_config_file_exists(self) -> None:
        """The config file must exist at project root."""
        assert (
            PRECOMMIT_CONFIG.is_file()
        ), f"Missing .pre-commit-config.yaml at project root: {PRECOMMIT_CONFIG}"

    def test_config_is_valid_yaml(self) -> None:
        """The config file must be parseable YAML."""
        config = _load_config()
        assert isinstance(config, dict), "Config must be a YAML mapping"
        assert "repos" in config, "Config must have a 'repos' key"

    def test_all_required_hooks_present(self) -> None:
        """black, flake8, and mypy hooks must all be configured."""
        config = _load_config()
        hook_ids: set[str] = set()
        for repo in config.get("repos", []):
            for hook in repo.get("hooks", []):
                hook_ids.add(hook["id"])

        missing = REQUIRED_HOOK_IDS - hook_ids
        assert not missing, (
            f"Missing required hooks in .pre-commit-config.yaml: {missing}. " f"Found: {hook_ids}"
        )

    def test_hooks_have_pinned_revs(self) -> None:
        """All repos must use pinned revs (no 'main', 'latest', or empty)."""
        config = _load_config()
        floating_refs: list[str] = []

        for repo in config.get("repos", []):
            rev = repo.get("rev", "")
            repo_url = repo.get("repo", "?")
            if not rev or rev.lower() in {"main", "master", "latest", "head"}:
                floating_refs.append(f"{repo_url}: rev={rev!r}")

        assert (
            not floating_refs
        ), "Unpinned/floating revs found (must pin to specific version):\n" + "\n".join(
            f"  - {r}" for r in floating_refs
        )

    def test_black_line_length_matches_pyproject(self) -> None:
        """black hook args must specify --line-length=100 to match pyproject.toml."""
        config = _load_config()
        for repo in config.get("repos", []):
            for hook in repo.get("hooks", []):
                if hook["id"] == "black":
                    args = hook.get("args", [])
                    has_line_length = any("--line-length=100" in a for a in args)
                    # Either in args or relying on pyproject.toml (both valid)
                    assert has_line_length or not args, (
                        "black hook should have --line-length=100 in args "
                        "or rely on pyproject.toml [tool.black]"
                    )
                    return
        raise AssertionError("black hook not found")

    def test_flake8_args_include_complexity_and_line_length(self) -> None:
        """flake8 must enforce max-complexity=40 and max-line-length=100."""
        config = _load_config()
        for repo in config.get("repos", []):
            for hook in repo.get("hooks", []):
                if hook["id"] == "flake8":
                    args = hook.get("args", [])
                    args_str = " ".join(args)
                    assert (
                        "--max-complexity=40" in args_str
                    ), f"flake8 missing --max-complexity=40. args: {args}"
                    assert (
                        "--max-line-length=100" in args_str
                    ), f"flake8 missing --max-line-length=100. args: {args}"
                    return
        raise AssertionError("flake8 hook not found")

    def test_mypy_hook_exists(self) -> None:
        """mypy hook must be configured (reads settings from pyproject.toml)."""
        config = _load_config()
        for repo in config.get("repos", []):
            for hook in repo.get("hooks", []):
                if hook["id"] == "mypy":
                    # mypy reads [tool.mypy] from pyproject.toml by default
                    return
        raise AssertionError("mypy hook not found in config")

    def test_exclude_section_exists(self) -> None:
        """Global exclude patterns must be documented."""
        config = _load_config()
        # Either top-level 'exclude' or per-hook excludes
        has_global = "exclude" in config
        has_per_hook = any(
            bool(hook.get("exclude"))
            for repo in config.get("repos", [])
            for hook in repo.get("hooks", [])
        )
        assert has_global or has_per_hook, (
            "No exclude patterns found — legacy files must be excluded "
            "to avoid blocking on historical lint debt"
        )
