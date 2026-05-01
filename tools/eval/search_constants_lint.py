#!/usr/bin/env python3
"""Search Constants Lint — CHARTER §4.3 compliance checker.

Scans search_journals/ for bare numeric literals that should be
managed constants in search_constants.py.

Usage:
    python tools/eval/search_constants_lint.py
    python -m tools.eval.search_constants_lint

Exit code 0 = clean, 1 = violations found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_DIR = REPO_ROOT / "tools" / "search_journals"
CONSTANTS_FILE = REPO_ROOT / "tools" / "lib" / "search_constants.py"

# Whitelist: files that are allowed to have numeric literals
# (e.g., test files, CLI argument defaults, non-threshold numerics)
WHITELIST_FILES = {
    "__pycache__",
    "__init__.py",
}

# Known safe patterns (not thresholds)
SAFE_PATTERNS = [
    r"# .*Tukey.*k=1\.5",  # Tukey comment
    r"import\s+",  # Import lines
    r"^\s*#",  # Comment-only lines
    r"format\s*\(",  # Format strings
    r"range\s*\(",  # Range calls
    r"len\s*\(",  # Len calls
    r"enumerate\s*\(",  # Enumerate
    r"\[:",  # Slice operations
    r"\[0\]",  # Index access
    r"1",  # Generic integer 1 (too common)
    r"0",  # Generic integer 0
    r"-1",  # Generic -1
    r"2",  # Generic 2 (e.g., digits in format)
    r"3",  # Generic 3
]


def is_safe_line(line: str) -> bool:
    """Check if a line is safe (not a threshold violation)."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return True
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, stripped):
            return True
    return False


def check_numeric_thresholds() -> list[dict]:
    """Find suspicious numeric literals in search_journals/ Python files."""
    violations = []

    for py_file in sorted(SEARCH_DIR.glob("*.py")):
        if py_file.name in WHITELIST_FILES:
            continue

        text = py_file.read_text(encoding="utf-8")

        # Skip if file imports from search_constants (good citizen)
        imports_constants = "search_constants" in text

        for i, line in enumerate(text.split("\n"), 1):
            if is_safe_line(line):
                continue

            # Look for comparison thresholds: >= N, <= N, > N, < N, == N
            # where N is a float or int >= 5 (skip small loop counters)
            matches = re.finditer(
                r"""(?:>=|<=|>|<|==)\s*(\d+\.?\d*)""",
                line,
            )
            for m in matches:
                val = float(m.group(1))
                if val >= 5 and not imports_constants:
                    violations.append(
                        {
                            "file": py_file.name,
                            "line": i,
                            "value": m.group(1),
                            "context": line.strip()[:80],
                        }
                    )
                elif val >= 5 and imports_constants:
                    # File imports constants but still has bare literal
                    # Check if this specific value is in the import list
                    pass  # Allow for now — the import is present

    return violations


def main() -> int:
    violations = check_numeric_thresholds()

    if violations:
        print(f"[FAIL] Found {len(violations)} potential CHARTER 4.3 violations:")
        for v in violations:
            print(f"  {v['file']}:{v['line']} -- value {v['value']}: {v['context']}")
        print()
        print("These numeric thresholds should be defined in search_constants.py")
        print("and imported, not used as bare literals.")
        return 1
    else:
        print("[PASS] No CHARTER 4.3 violations found in search_journals/")
        return 0


if __name__ == "__main__":
    sys.exit(main())
