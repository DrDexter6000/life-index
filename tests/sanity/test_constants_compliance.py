"""CHARTER §4.3 compliance: no bare thresholds in search subsystem."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_DIR = REPO_ROOT / "tools" / "search_journals"
CONSTANTS_FILE = REPO_ROOT / "tools" / "lib" / "search_constants.py"

# These files should import ALL thresholds from search_constants
FILES_THAT_MUST_IMPORT = [
    "confidence.py",
    "title_promotion.py",
    "l3_content.py",
    "keyword_pipeline.py",
]


def test_no_bare_numeric_thresholds():
    """confidence.py must not contain bare >= 70, >= 55, etc.

    After migration, comparisons should use named constants like
    '>= CONFIDENCE_HIGH_FTS' — bare numeric literals must be gone.
    """
    conf = SEARCH_DIR / "confidence.py"
    text = conf.read_text(encoding="utf-8")
    for bare_val in [">= 70", ">= 55", ">= 0.018", ">= 50", ">= 45", ">= 0.010"]:
        assert (
            bare_val not in text
        ), f"Bare threshold '{bare_val}' still in confidence.py — must use named constant"


def test_constants_exported():
    """All new constants must be in __all__."""
    text = CONSTANTS_FILE.read_text(encoding="utf-8")
    required = [
        "CONFIDENCE_HIGH_FTS",
        "CONFIDENCE_HIGH_SEMANTIC",
        "CONFIDENCE_HIGH_RRF",
        "CONFIDENCE_MEDIUM_FTS",
        "CONFIDENCE_MEDIUM_SEMANTIC",
        "CONFIDENCE_MEDIUM_RRF",
        "TITLE_PROMOTION_MULTIPLIER",
        "TITLE_PROMOTION_COVERAGE_THRESHOLD",
        "TITLE_PROMOTION_MIN_QUERY_CHARS",
        "L3_TITLE_MATCH_BONUS",
        "L3_BODY_MATCH_PER_HIT",
        "L3_MAX_FALLBACK_SCORE",
        "L3_MIN_FALLBACK_RELEVANCE",
        "KEYWORD_TOKEN_HIT_RATIO",
    ]
    for name in required:
        assert name in text, f"{name} not found in search_constants.py"


def test_files_import_from_constants():
    """Each file must import its constants from search_constants."""
    for fname in FILES_THAT_MUST_IMPORT:
        fpath = SEARCH_DIR / fname
        text = fpath.read_text(encoding="utf-8")
        assert "search_constants" in text, f"{fname} does not import from search_constants"
