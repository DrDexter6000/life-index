#!/usr/bin/env python3
"""Measure jieba dual-mode tokenization asymmetry baseline (r₀).

Phase 0 of Round 16: produces two baseline files:
1. tests/golden/jieba_baseline.json — r₀ value (mean intersection ratio)
2. tests/golden/ranking_eval_baseline.json — current ranking eval score

This script is idempotent: same corpus + same jieba version → identical output.

Usage:
    python scripts/measure_jieba_baseline.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = PROJECT_ROOT / "tests" / "golden"
CORPUS_PATH = GOLDEN_DIR / "jieba_asymmetry_corpus.json"
JIEBA_BASELINE_PATH = GOLDEN_DIR / "jieba_baseline.json"
RANKING_BASELINE_PATH = GOLDEN_DIR / "ranking_eval_baseline.json"


def get_corpus_entries() -> list[dict[str, str]]:
    """Load the fixed corpus entries."""
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    return data["entries"]


def compute_r0(entries: list[dict[str, str]]) -> dict[str, Any]:
    """Compute r₀: mean intersection ratio of jieba.cut() vs jieba.cut_for_search().

    For each corpus entry:
    - tokens_index = set(jieba.cut(text))  — precise mode, used at index time
    - tokens_query = set(jieba.cut_for_search(text))  — search mode, used at query time
    - ratio = |tokens_index ∩ tokens_query| / |tokens_index ∪ tokens_query|

    r₀ = mean(ratio) across all entries.

    Returns dict with r0_mean, r0_std, r0_min, r0_max, per_entry_ratios, jieba_version.
    """
    import jieba
    import numpy as np

    jieba.initialize()

    ratios: list[float] = []
    per_entry: list[dict[str, Any]] = []

    for entry in entries:
        text = entry["text"]

        # Index mode: jieba.cut() — precise segmentation
        index_tokens = set(jieba.lcut(text))
        # Query mode: jieba.cut_for_search() — finer granularity
        query_tokens = set(jieba.lcut_for_search(text))

        # Jaccard-like intersection ratio
        union = index_tokens | query_tokens
        intersection = index_tokens & query_tokens

        ratio = len(intersection) / len(union) if union else 0.0
        ratios.append(ratio)

        per_entry.append(
            {
                "id": entry["id"],
                "category": entry["category"],
                "ratio": round(ratio, 6),
                "index_token_count": len(index_tokens),
                "query_token_count": len(query_tokens),
                "intersection_count": len(intersection),
                "union_count": len(union),
            }
        )

    ratios_arr = np.array(ratios)
    r0_mean = float(np.mean(ratios_arr))
    r0_std = float(np.std(ratios_arr, ddof=1)) if len(ratios_arr) > 1 else 0.0
    r0_min = float(np.min(ratios_arr))
    r0_max = float(np.max(ratios_arr))
    threshold = max(0.5, r0_mean - 0.05)

    return {
        "r0_mean": round(r0_mean, 6),
        "r0_std": round(r0_std, 6),
        "r0_min": round(r0_min, 6),
        "r0_max": round(r0_max, 6),
        "threshold": round(threshold, 6),
        "jieba_version": jieba.__version__,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "corpus_file": "tests/golden/jieba_asymmetry_corpus.json",
        "entries_count": len(entries),
        "threshold_formula": "max(0.5, r0 - 0.05)",
        "drift_alert_formula": "r < (r0 - 0.10) → alert; r < (r0 - 0.05) → note",
        "per_entry_ratios": per_entry,
    }


def compute_ranking_baseline() -> dict[str, Any]:
    """Run the existing eval harness to capture current ranking score.

    Uses golden_rejection_queries.yaml as the eval fixture, per Synthesis §10.3 (R3).
    """
    import jieba

    sys.path.insert(0, str(PROJECT_ROOT))

    # Import and run the eval
    from tools.eval.run_eval import run_evaluation

    # Run with default (test fixture) data, keyword judge mode
    result = run_evaluation(
        data_dir=None,
        use_semantic=False,
        judge="keyword",
    )

    metrics = result.get("metrics", {})

    # Use MRR@5 as the primary metric for ranking baseline
    # (matches Synthesis §10.3: |Δmetric| ≤ 2%)
    return {
        "metric_name": "mrr_at_5",
        "baseline_score": round(metrics.get("mrr_at_5", 0.0), 6),
        "mrr_at_5": round(metrics.get("mrr_at_5", 0.0), 6),
        "recall_at_5": round(metrics.get("recall_at_5", 0.0), 6),
        "precision_at_5": round(metrics.get("precision_at_5", 0.0), 6),
        "total_queries": result.get("total_queries", 0),
        "failures_count": len(result.get("failures", [])),
        "jieba_version": jieba.__version__,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "eval_fixture": "tools/eval/golden_queries.yaml",
        "judge_mode": "keyword",
        "semantic_enabled": False,
        "regression_threshold": "abs(delta) <= 0.02 (2%)",
    }


def main() -> None:
    """Run baseline measurements and write output files."""
    print("=" * 60)
    print("Round 16 Phase 0 — Baseline Measurement")
    print("=" * 60)

    # Ensure golden directory exists
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load corpus
    print("\n[1/3] Loading corpus...")
    entries = get_corpus_entries()
    print(f"  Loaded {len(entries)} entries from {CORPUS_PATH.name}")

    # 2. Compute r0
    print("\n[2/3] Computing r0 (jieba dual-mode asymmetry baseline)...")
    jieba_baseline = compute_r0(entries)

    print(f"  r0 mean:      {jieba_baseline['r0_mean']:.6f}")
    print(f"  r0 std:       {jieba_baseline['r0_std']:.6f}")
    print(f"  r0 min:       {jieba_baseline['r0_min']:.6f}")
    print(f"  r0 max:       {jieba_baseline['r0_max']:.6f}")
    print(f"  threshold:    {jieba_baseline['threshold']:.6f}")
    print(f"  jieba version: {jieba_baseline['jieba_version']}")

    # Sanity check
    if not (0.5 <= jieba_baseline["r0_mean"] <= 0.99):
        print(f"\n  WARNING: r0 = {jieba_baseline['r0_mean']:.4f} outside expected [0.5, 0.99].")
        print("  Corpus selection may need review.")

    # Write jieba baseline
    JIEBA_BASELINE_PATH.write_text(
        json.dumps(jieba_baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n  Written: {JIEBA_BASELINE_PATH.relative_to(PROJECT_ROOT)}")

    # 3. Compute ranking baseline
    print("\n[3/3] Computing ranking eval baseline...")
    ranking_baseline = compute_ranking_baseline()

    print(f"  metric:       {ranking_baseline['metric_name']}")
    print(f"  baseline:     {ranking_baseline['baseline_score']:.6f}")
    print(f"  queries:      {ranking_baseline['total_queries']}")
    print(f"  failures:     {ranking_baseline['failures_count']}")

    # Write ranking baseline
    RANKING_BASELINE_PATH.write_text(
        json.dumps(ranking_baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n  Written: {RANKING_BASELINE_PATH.relative_to(PROJECT_ROOT)}")

    print("\n" + "=" * 60)
    print("Phase 0 baseline measurement complete.")
    print("=" * 60)
    print(f"\nNext: Write ADR-020 with r0 = {jieba_baseline['r0_mean']:.4f}")


if __name__ == "__main__":
    main()
