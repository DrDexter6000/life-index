"""Phase 6-A: Search constants lint compliance test.

CHARTER 4.3 requires all numeric thresholds in search_journals/
to be managed constants in search_constants.py.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LINT_SCRIPT = REPO_ROOT / "tools" / "eval" / "search_constants_lint.py"


def test_no_unmanaged_numeric_literals():
    """search_journals/ must not contain bare numeric thresholds (CHARTER 4.3)."""
    result = subprocess.run(
        [sys.executable, str(LINT_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"Lint found violations:\n{result.stdout}\n{result.stderr}"


def test_semantic_absolute_floor_is_alias():
    """SEMANTIC_ABSOLUTE_FLOOR must equal SEMANTIC_MIN_SIMILARITY (deprecated synonym)."""
    from tools.lib.search_constants import (
        SEMANTIC_ABSOLUTE_FLOOR,
        SEMANTIC_MIN_SIMILARITY,
    )

    assert SEMANTIC_ABSOLUTE_FLOOR == SEMANTIC_MIN_SIMILARITY


def test_total_exports_count():
    """Track total exported constants count (should not grow without review)."""
    from tools.lib.search_constants import __all__

    # Post Phase 6-A: 43 exports (SEMANTIC_ABSOLUTE_FLOOR kept as alias)
    # Post Round 19 Phase 1-D C1-fuzzy: +4 fuzzy typo constants
    # If this grows beyond 50, a new constant was added — review it.
    assert len(__all__) <= 50, (
        f"__all__ has {len(__all__)} exports (max 50). "
        "New constants must be reviewed for synonym merging."
    )
