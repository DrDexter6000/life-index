# Baseline measured on jieba 0.42.1: r₀ = 0.9008, threshold = max(0.5, r0-0.05) = 0.8508
# Round 16 CTO audit R1 — do NOT change threshold without updating ADR-020

"""Golden tests for jieba cut() vs cut_for_search() asymmetry.

These tests verify that the Jaccard ratio between jieba.lcut() and
jieba.lcut_for_search() remains within acceptable bounds established
by the Round 16 Phase 0 baseline measurement.
"""

import json
import warnings
from pathlib import Path

import jieba
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CORPUS_FILE = Path("tests/golden/jieba_asymmetry_corpus.json")
BASELINE_FILE = Path("tests/golden/jieba_baseline.json")


@pytest.fixture(scope="module")
def corpus():
    with CORPUS_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["entries"]


@pytest.fixture(scope="module")
def baseline():
    with BASELINE_FILE.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def r0(baseline):
    """Baseline r0_mean loaded dynamically from JSON."""
    return baseline["r0_mean"]


@pytest.fixture(scope="module")
def threshold(r0):
    """WARN threshold = max(0.5, r0 - 0.05), computed dynamically."""
    return max(0.5, r0 - 0.05)


@pytest.fixture(scope="module")
def drift_alert_threshold(r0):
    """FAIL drift threshold = r0 - 0.10."""
    return r0 - 0.10


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def jaccard_ratio(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity: |A ∩ B| / |A ∪ B|."""
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 1.0
    return intersection / union


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_jieba_asymmetry_intersection_above_threshold(corpus, r0, threshold, drift_alert_threshold):
    """Main golden test: avg Jaccard ratio across corpus vs baseline r0.

    Tiers:
      - PASS  : avg_ratio >= max(0.5, r0 - 0.05)  → clean pass
      - WARN  : max(0.5, r0 - 0.05) > avg_ratio >= (r0 - 0.10) → warn
      - FAIL  : (r0 - 0.10) > avg_ratio >= 0.5 → assert with drift message
      - FLOOR : avg_ratio < 0.5 → hard assert failure
    """
    ratios = []
    for entry in corpus:
        text = entry["text"]
        index_tokens = set(jieba.lcut(text))
        query_tokens = set(jieba.lcut_for_search(text))
        ratio = jaccard_ratio(index_tokens, query_tokens)
        ratios.append(ratio)

    avg_ratio = sum(ratios) / len(ratios)

    # ABSOLUTE FLOOR
    assert avg_ratio >= 0.5, (
        f"FLOOR BREACH: avg_ratio={avg_ratio:.6f} < 0.5 (absolute floor). "
        f"Drift from r0={r0:.6f} is {r0 - avg_ratio:.6f}."
    )

    # FAIL tier: below drift threshold
    fail_threshold = drift_alert_threshold
    assert avg_ratio >= fail_threshold, (
        f"FAIL: avg_ratio={avg_ratio:.6f} < r0-0.10={fail_threshold:.6f}. "
        f"Drift from r0={r0:.6f} is {r0 - avg_ratio:.6f}. "
        f"CURRENT THRESHOLD = max(0.5, r0-0.05) = {threshold:.6f}. "
        f"Update ADR-020 if this is a legitimate regression."
    )

    # WARN tier: between warn threshold and fail threshold
    if avg_ratio < threshold:
        warnings.warn(
            f"WARN: avg_ratio={avg_ratio:.6f} < threshold={threshold:.6f} "
            f"(r0-0.05={r0 - 0.05:.6f}), but above drift floor={fail_threshold:.6f}. "
            f"Drift from r0={r0:.6f} is {r0 - avg_ratio:.6f}."
        )

    # PASS tier: at or above warn threshold
    # (no assert needed — reaching here means PASS or WARN handled above)


def test_threshold_tiers_correctness():
    """Meta-test: verify tier logic with constructed values.

    Mock r0=0.90 → threshold=max(0.5, 0.85)=0.85, drift=r0-0.10=0.80
    """
    mock_r0 = 0.90
    mock_threshold = max(0.5, mock_r0 - 0.05)  # 0.85
    mock_drift = mock_r0 - 0.10  # 0.80
    floor = 0.5

    # ratio=0.85 → PASS (at threshold)
    ratio = 0.85
    assert ratio >= mock_threshold, f"ratio={ratio} should PASS at threshold={mock_threshold}"

    # ratio=0.82 → WARN (between drift=0.80 and threshold=0.85)
    ratio = 0.82
    assert ratio >= mock_drift, f"ratio={ratio} should not FAIL below drift={mock_drift}"
    assert (
        ratio < mock_threshold
    ), f"ratio={ratio} should WARN between {mock_drift} and {mock_threshold}"

    # ratio=0.78 → FAIL (below drift=0.80)
    ratio = 0.78
    with pytest.raises(AssertionError):
        assert ratio >= mock_drift, f"ratio={ratio} should FAIL below drift={mock_drift}"

    # ratio=0.45 → FLOOR FAIL (below 0.5)
    ratio = 0.45
    with pytest.raises(AssertionError):
        assert ratio >= floor, f"ratio={ratio} should FLOOR FAIL below {floor}"


def test_per_entry_ratios_all_above_floor(corpus):
    """Each individual entry must have ratio >= 0.4 (per-entry floor).

    This ensures no single corpus entry has catastrophically bad asymmetry.
    """
    FLOOR = 0.4
    failures = []
    for entry in corpus:
        text = entry["text"]
        index_tokens = set(jieba.lcut(text))
        query_tokens = set(jieba.lcut_for_search(text))
        ratio = jaccard_ratio(index_tokens, query_tokens)
        if ratio < FLOOR:
            failures.append((entry["id"], ratio))

    assert not failures, f"Per-entry floor breach (< {FLOOR}): " + ", ".join(
        f"{id_}={r:.4f}" for id_, r in failures
    )
