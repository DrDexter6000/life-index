#!/usr/bin/env python3
"""Fail when PR-added files are outside the public surface allowlist."""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALLOWLIST = REPO_ROOT / ".github" / "public-surface.allowlist"


def _normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def parse_allowlist(text: str) -> tuple[str, ...]:
    patterns: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(_normalize_path(line))
    return tuple(patterns)


def _load_allowlist(path: Path) -> tuple[str, ...]:
    if not path.exists():
        print(f"Public surface allowlist missing: {path}", file=sys.stderr)
        raise SystemExit(2)
    return parse_allowlist(path.read_text(encoding="utf-8"))


def _is_allowed(path: str, allowlist: tuple[str, ...]) -> bool:
    normalized = _normalize_path(path)
    for pattern in allowlist:
        if pattern.startswith("!") and fnmatch.fnmatchcase(normalized, pattern[1:]):
            return False
    return any(
        fnmatch.fnmatchcase(normalized, pattern)
        for pattern in allowlist
        if not pattern.startswith("!")
    )


def find_disallowed_paths(paths: list[str], allowlist: tuple[str, ...]) -> list[str]:
    disallowed: list[str] = []
    for path in paths:
        normalized = _normalize_path(path)
        if normalized and not _is_allowed(normalized, allowlist):
            disallowed.append(normalized)
    return disallowed


def _default_base() -> str:
    if os.environ.get("PUBLIC_SURFACE_BASE"):
        return os.environ["PUBLIC_SURFACE_BASE"]
    if os.environ.get("GITHUB_BASE_REF"):
        return f"origin/{os.environ['GITHUB_BASE_REF']}"
    return "origin/main"


def _git_added_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=A",
            f"{base}...{head}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode)
    return [line for line in result.stdout.splitlines() if line.strip()]


def _paths_from_file(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _print_violations(paths: list[str]) -> None:
    print("Public surface allowlist check failed.")
    print("New public paths are not allowlisted:")
    for path in paths:
        print(f"- {path}")
    print(
        "If the path is truly public, add the narrowest pattern to "
        ".github/public-surface.allowlist in this PR. Otherwise, keep it out "
        "of the public repository."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None, help="Base ref for git diff; default origin/main")
    parser.add_argument("--head", default="HEAD", help="Head ref for git diff; default HEAD")
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST,
        help="Allowlist file; default .github/public-surface.allowlist",
    )
    parser.add_argument(
        "--paths-file",
        type=Path,
        help="Read added paths from this newline-delimited file instead of git",
    )
    args = parser.parse_args(argv)

    allowlist = _load_allowlist(args.allowlist)
    if args.paths_file:
        paths = _paths_from_file(args.paths_file)
    else:
        paths = _git_added_paths(args.base or _default_base(), args.head)

    violations = find_disallowed_paths(paths, allowlist)
    if violations:
        _print_violations(violations)
        return 1

    print("Public surface allowlist check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
