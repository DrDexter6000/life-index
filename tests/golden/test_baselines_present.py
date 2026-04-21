"""Phase 0 baseline presence tests — RED → GREEN cycle.

These tests verify that Round 16 Phase 0 has produced the required baseline
artifacts before any Package B or C work can proceed.

Round 16 Synthesis §10.2 (R1):
- jieba golden threshold = max(0.5, r₀ - 0.05), where r₀ is measured baseline
- corpus must be fixed (20 entries, 5 categories) for reproducibility
- jieba version must be exact-pinned in pyproject.toml
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden"
CORPUS_PATH = GOLDEN_DIR / "jieba_asymmetry_corpus.json"
RANKING_BASELINE_PATH = GOLDEN_DIR / "ranking_eval_baseline.json"
JIEBA_BASELINE_PATH = GOLDEN_DIR / "jieba_baseline.json"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
ADR_PATH = PROJECT_ROOT / "docs" / "adr" / "ADR-020-jieba-asymmetry-baseline.md"

REQUIRED_CATEGORIES = {"family", "work", "health", "emotion", "location"}
ENTRIES_PER_CATEGORY = 4
TOTAL_ENTRIES = 20


def test_jieba_asymmetry_corpus_exists_and_has_20_entries() -> None:
    """Phase 0 must produce a fixed corpus with 20 entries across 5 categories."""
    assert (
        CORPUS_PATH.exists()
    ), f"Phase 0 must produce corpus at {CORPUS_PATH.relative_to(PROJECT_ROOT)}"
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    assert "entries" in data, "Corpus must have 'entries' key"
    entries = data["entries"]
    assert len(entries) == TOTAL_ENTRIES, f"Expected {TOTAL_ENTRIES} entries, got {len(entries)}"

    # Verify categories coverage
    categories = {e["category"] for e in entries}
    assert (
        categories == REQUIRED_CATEGORIES
    ), f"Expected categories {REQUIRED_CATEGORIES}, got {categories}"

    # Verify each entry has required fields
    for entry in entries:
        assert "id" in entry, f"Entry missing 'id': {entry}"
        assert "text" in entry, f"Entry missing 'text': {entry}"
        assert "category" in entry, f"Entry missing 'category': {entry}"
        assert len(entry["text"]) > 5, f"Entry {entry['id']} text too short: {entry['text']!r}"

    # Verify each category has exactly 4 entries
    from collections import Counter

    cat_counts = Counter(e["category"] for e in entries)
    for cat in REQUIRED_CATEGORIES:
        assert (
            cat_counts[cat] == ENTRIES_PER_CATEGORY
        ), f"Category {cat!r}: expected {ENTRIES_PER_CATEGORY}, got {cat_counts[cat]}"


def test_jieba_baseline_json_exists_with_metrics() -> None:
    """Phase 0 must produce jieba_baseline.json with r₀ measurement."""
    assert (
        JIEBA_BASELINE_PATH.exists()
    ), f"Phase 0 must produce baseline at {JIEBA_BASELINE_PATH.relative_to(PROJECT_ROOT)}"
    data = json.loads(JIEBA_BASELINE_PATH.read_text(encoding="utf-8"))

    assert "r0_mean" in data, "Baseline must contain 'r0_mean'"
    assert "r0_std" in data, "Baseline must contain 'r0_std'"
    assert "r0_min" in data, "Baseline must contain 'r0_min'"
    assert "r0_max" in data, "Baseline must contain 'r0_max'"
    assert "jieba_version" in data, "Baseline must contain 'jieba_version'"
    assert "threshold" in data, "Baseline must contain 'threshold'"
    assert "measured_at" in data, "Baseline must contain 'measured_at'"
    assert "per_entry_ratios" in data, "Baseline must contain 'per_entry_ratios'"

    # Sanity check: r₀ should be in reasonable range
    r0 = data["r0_mean"]
    assert 0.5 <= r0 <= 0.99, (
        f"r₀ sanity check failed: {r0:.4f} outside [0.5, 0.99]. " "Corpus selection may have bias."
    )

    # Verify threshold formula: max(0.5, r₀ - 0.05)
    expected_threshold = max(0.5, r0 - 0.05)
    assert (
        abs(data["threshold"] - expected_threshold) < 1e-6
    ), f"Threshold mismatch: expected {expected_threshold:.6f}, got {data['threshold']:.6f}"

    # Verify jieba version is exact
    assert data["jieba_version"] == "0.42.1", f"Unexpected jieba version: {data['jieba_version']}"

    # Verify per-entry ratios count
    assert (
        len(data["per_entry_ratios"]) == TOTAL_ENTRIES
    ), f"Expected {TOTAL_ENTRIES} per-entry ratios, got {len(data['per_entry_ratios'])}"


def test_ranking_eval_baseline_exists() -> None:
    """Phase 0 must produce ranking_eval_baseline.json for Package C gate."""
    assert (
        RANKING_BASELINE_PATH.exists()
    ), f"Phase 0 must produce baseline at {RANKING_BASELINE_PATH.relative_to(PROJECT_ROOT)}"
    data = json.loads(RANKING_BASELINE_PATH.read_text(encoding="utf-8"))

    # Required fields per Synthesis §10.3 (R3)
    assert "metric_name" in data, "Must contain 'metric_name'"
    assert "baseline_score" in data, "Must contain 'baseline_score'"
    assert "jieba_version" in data, "Must contain 'jieba_version'"
    assert "measured_at" in data, "Must contain 'measured_at'"

    # Score must be a valid float
    score = data["baseline_score"]
    assert isinstance(score, (int, float)), f"baseline_score must be numeric, got {type(score)}"
    assert 0.0 <= score <= 1.0, f"baseline_score out of range [0, 1]: {score}"


def test_jieba_version_exact_pinned() -> None:
    """jieba must be exact-pinned (==X.Y.Z) in pyproject.toml, not >=."""
    assert PYPROJECT_PATH.exists()
    with PYPROJECT_PATH.open("rb") as f:
        pyproject = tomllib.load(f)

    deps = pyproject.get("project", {}).get("dependencies", [])
    jieba_dep = next((d for d in deps if d.strip().startswith("jieba")), None)
    assert jieba_dep is not None, "No jieba dependency found in pyproject.toml"

    # Must use == (exact pin), not >= or ~= or bare name
    assert "==" in jieba_dep, f"jieba must be exact-pinned with ==, got: {jieba_dep!r}"
    # Must not use >= or ~=
    assert (
        ">=" not in jieba_dep and "~=" not in jieba_dep
    ), f"jieba must use exact pin (==), not >= or ~=, got: {jieba_dep!r}"

    # Verify it's pinned to 0.42.1
    assert "0.42.1" in jieba_dep, f"jieba must be pinned to 0.42.1, got: {jieba_dep!r}"


def test_adr_020_exists_with_baseline_values() -> None:
    """ADR-020 must exist and contain r₀ value + threshold formula."""
    assert ADR_PATH.exists(), f"ADR-020 must exist at {ADR_PATH.relative_to(PROJECT_ROOT)}"
    content = ADR_PATH.read_text(encoding="utf-8")

    # Must contain the baseline formula
    assert (
        "max(0.5" in content or "max(0.5" in content
    ), "ADR-020 must contain the threshold formula: max(0.5, r₀-0.05)"

    # Must contain a concrete r₀ value (pattern: r₀ = X.XXXX or r0 = X.XXXX)
    assert re.search(
        r"r[₀0]\s*[=:]\s*\d+\.\d+", content
    ), "ADR-020 must contain a concrete r₀ value (e.g., 'r₀ = 0.78')"
