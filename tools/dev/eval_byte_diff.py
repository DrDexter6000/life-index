#!/usr/bin/env python3
"""Compare two evaluation JSON outputs, excluding known non-deterministic fields.

Usage:
    python tools/dev/eval_byte_diff.py <path_a> <path_b>

Exit code 0 when no meaningful differences are found.
Exit code 1 when differences remain.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Fields whose values are expected to differ across runs.
DEFAULT_EXCLUDE = [
    "eval_run_timestamp",
    "hostname",
    "process_id",
    "eval_duration_ms",
    "timestamp",  # human-readable isoformat timestamp
]


def _deep_diff(
    a: Any,
    b: Any,
    path: str = "root",
    exclude: set[str] | None = None,
) -> list[str]:
    """Recursively compare *a* and *b*, collecting differences."""
    if exclude is None:
        exclude = set(DEFAULT_EXCLUDE)

    differences: list[str] = []

    if isinstance(a, dict) and isinstance(b, dict):
        keys = set(a.keys()) | set(b.keys())
        for key in sorted(keys):
            if key in exclude:
                continue
            if key not in a:
                differences.append(f"{path}.{key}: missing in A")
            elif key not in b:
                differences.append(f"{path}.{key}: missing in B")
            else:
                differences.extend(_deep_diff(a[key], b[key], f"{path}.{key}", exclude))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            differences.append(f"{path}: list length {len(a)} vs {len(b)}")
        else:
            for i, (item_a, item_b) in enumerate(zip(a, b)):
                differences.extend(_deep_diff(item_a, item_b, f"{path}[{i}]", exclude))
    elif a != b:
        differences.append(f"{path}: {a!r} != {b!r}")

    return differences


def main() -> int:
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <file_a> <file_b>", file=sys.stderr)
        return 2

    path_a = Path(sys.argv[1])
    path_b = Path(sys.argv[2])

    if not path_a.exists():
        print(f"File not found: {path_a}", file=sys.stderr)
        return 2
    if not path_b.exists():
        print(f"File not found: {path_b}", file=sys.stderr)
        return 2

    data_a = json.loads(path_a.read_text(encoding="utf-8"))
    data_b = json.loads(path_b.read_text(encoding="utf-8"))

    # Unwrap "success" envelope if present (run_eval.py main block writes it)
    if isinstance(data_a, dict) and "data" in data_a:
        data_a = data_a["data"]
    if isinstance(data_b, dict) and "data" in data_b:
        data_b = data_b["data"]

    diffs = _deep_diff(data_a, data_b, exclude=set(DEFAULT_EXCLUDE))

    if not diffs:
        print(f"0 differences (excluding {DEFAULT_EXCLUDE})")
        return 0

    print(f"{len(diffs)} differences (excluding {DEFAULT_EXCLUDE}):")
    for d in diffs:
        print(f"  - {d}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
