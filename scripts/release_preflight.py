#!/usr/bin/env python3
"""Deterministic release checks reused by the manual PyPI workflow.

This tool validates repository-owned release metadata without rewriting it.  The
optional PyPI query is deliberately isolated behind a callable seam so tests do
not require the network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

PYPI_JSON_URL = "https://pypi.org/pypi/life-index/json"
PYPI_TIMEOUT_SECONDS = 5.0
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
KNOWN_USED_HEADING = "Known PyPI-used versions:"


class ReleasePreflightError(ValueError):
    """A release candidate is not safe to publish."""


def _read_pyproject_version(root: Path) -> str:
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            value = tomllib.load(handle)["project"]["version"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ReleasePreflightError("pyproject version is unreadable") from exc
    if not isinstance(value, str):
        raise ReleasePreflightError("pyproject version is not a string")
    return value


def _read_manifest_version(path: Path) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))["repo_version"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ReleasePreflightError(f"manifest version is unreadable: {path.name}") from exc
    if not isinstance(value, str):
        raise ReleasePreflightError(f"manifest version is not a string: {path.name}")
    return value


def validate_version_surfaces(root: Path) -> str:
    """Require the package and both shipped bootstrap manifests to agree."""

    versions = {
        "pyproject.toml": _read_pyproject_version(root),
        "bootstrap-manifest.json": _read_manifest_version(root / "bootstrap-manifest.json"),
        "tools/bootstrap-manifest.json": _read_manifest_version(
            root / "tools" / "bootstrap-manifest.json"
        ),
    }
    if len(set(versions.values())) != 1:
        rendered = ", ".join(f"{name}={value}" for name, value in sorted(versions.items()))
        raise ReleasePreflightError(f"version surfaces disagree: {rendered}")
    version = next(iter(versions.values()))
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ReleasePreflightError(f"release version is not MAJOR.MINOR.PATCH: {version}")
    return version


def known_used_versions(root: Path) -> set[str]:
    """Read the immutable repository history of unavailable PyPI versions."""

    try:
        document = (root / "docs" / "VERSIONING.md").read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleasePreflightError("known-used history is unreadable") from exc
    if KNOWN_USED_HEADING not in document:
        raise ReleasePreflightError("known-used history heading is missing")
    tail = document.split(KNOWN_USED_HEADING, 1)[1]
    match = re.search(r"```text\s*(?P<versions>.*?)\s*```", tail, flags=re.DOTALL)
    if match is None:
        raise ReleasePreflightError("known-used history block is missing")
    versions = {line.strip() for line in match.group("versions").splitlines() if line.strip()}
    if not versions or any(VERSION_PATTERN.fullmatch(version) is None for version in versions):
        raise ReleasePreflightError("known-used history contains an invalid version")
    return versions


def _pypi_release_versions(payload: object) -> set[str]:
    if not isinstance(payload, Mapping):
        raise ReleasePreflightError("PyPI response is not an object")
    releases = payload.get("releases")
    if not isinstance(releases, Mapping):
        raise ReleasePreflightError("PyPI response does not include releases")
    return {str(version) for version in releases}


def fetch_pypi_payload() -> dict[str, Any]:
    """Fetch the current PyPI availability view only when the workflow asks."""

    request = Request(PYPI_JSON_URL, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=PYPI_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ReleasePreflightError("PyPI availability check failed") from exc
    if not isinstance(payload, dict):
        raise ReleasePreflightError("PyPI response is not an object")
    return payload


def validate_release_candidate(
    root: Path,
    *,
    fetch_pypi_payload: Callable[[], object] = fetch_pypi_payload,
) -> str:
    """Validate repository history first, then reject a currently used PyPI target."""

    target = validate_version_surfaces(root)
    if target in known_used_versions(root):
        raise ReleasePreflightError(f"release target is in immutable known-used history: {target}")
    if target in _pypi_release_versions(fetch_pypi_payload()):
        raise ReleasePreflightError(f"release target is already present on PyPI: {target}")
    return target


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Life Index release candidate.")
    parser.add_argument("command", choices=("validate-version", "check-pypi"))
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to this script's parent)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        if args.command == "validate-version":
            target = validate_version_surfaces(root)
            if target in known_used_versions(root):
                raise ReleasePreflightError(
                    f"release target is in immutable known-used history: {target}"
                )
        else:
            target = validate_release_candidate(root)
    except ReleasePreflightError as exc:
        print(f"release preflight failed: {exc}", file=sys.stderr)
        return 2
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
