#!/usr/bin/env python3
"""Keep the packaged skill mirror (tools/_skill_artifacts) in step.

``SKILL.md`` and ``references/*.md`` at the repository root are the only
editable sources. ``tools/_skill_artifacts/`` is a byte-for-byte copy that
gets packaged into wheels. Running this script without arguments refreshes
the copy; ``--check`` reports (and fails on) any drift instead of writing.

The gate runs ``--check``; the drift is also pinned by
``tests/unit/test_bootstrap_manifest_packaging.py``. Standard library only.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_SKILL = REPO_ROOT / "SKILL.md"
ROOT_REFERENCES = REPO_ROOT / "references"
PACKAGED_ROOT = REPO_ROOT / "tools" / "_skill_artifacts"
PACKAGED_SKILL = PACKAGED_ROOT / "SKILL.md"
PACKAGED_REFERENCES = PACKAGED_ROOT / "references"


def source_files() -> dict[Path, Path]:
    """Map packaged destination -> root source for every mirrored file."""
    mirrored: dict[Path, Path] = {PACKAGED_SKILL: ROOT_SKILL}
    for reference in sorted(ROOT_REFERENCES.rglob("*.md")):
        destination = PACKAGED_REFERENCES / reference.relative_to(ROOT_REFERENCES)
        mirrored[destination] = reference
    return mirrored


def differences() -> list[str]:
    """Human-readable drift between the root sources and the packaged copy."""
    problems: list[str] = []
    for destination, source in source_files().items():
        if not destination.is_file():
            problems.append(f"missing from the packaged copy: {_rel(destination)}")
        elif destination.read_bytes() != source.read_bytes():
            problems.append(f"differs from the root source: {_rel(destination)}")
    for stray in sorted(stray_files()):
        problems.append(f"exists only in the packaged copy: {_rel(stray)}")
    return problems


def stray_files() -> list[Path]:
    """Packaged markdown files that have no root source anymore."""
    expected = set(source_files())
    return [path for path in sorted(PACKAGED_ROOT.rglob("*.md")) if path not in expected]


def refresh() -> int:
    """Copy every root source over the packaged mirror and drop strays."""
    for destination, source in source_files().items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    for stray in stray_files():
        stray.unlink()
    print(f"Refreshed {PACKAGED_ROOT.relative_to(REPO_ROOT)} from the root skill sources.")
    return 0


def check() -> int:
    problems = differences()
    if problems:
        print("Packaged skill artifacts are out of sync with the root sources:")
        for problem in problems:
            print(f"- {problem}")
        print("Refresh them with: python scripts/sync_skill_artifacts.py")
        return 1
    print("Packaged skill artifacts match the root skill sources.")
    return 0


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail (naming the files) when the copy differs or a file exists on only one side",
    )
    args = parser.parse_args(argv)
    return check() if args.check else refresh()


if __name__ == "__main__":
    raise SystemExit(main())
