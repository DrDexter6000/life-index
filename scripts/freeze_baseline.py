#!/usr/bin/env python3
"""Freeze a search eval baseline snapshot for Phase regression testing.

Usage:
    python scripts/freeze_baseline.py --phase phase2
    python scripts/freeze_baseline.py --phase phase3

Writes a JSON snapshot to .strategy/cli/Round_10_baselines/{phase}.json
containing full eval metrics + timestamp + git commit hash.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINES_DIR = PROJECT_ROOT / ".strategy" / "cli" / "Round_10_baselines"


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze eval baseline snapshot")
    parser.add_argument(
        "--phase", required=True, help="Phase label (e.g. phase2, phase3)"
    )
    args = parser.parse_args()

    sys.path.insert(0, str(PROJECT_ROOT))

    from tools.eval.run_eval import run_evaluation

    output_path = BASELINES_DIR / f"{args.phase}.json"

    print(f"Freezing baseline for '{args.phase}'...")
    result = run_evaluation(
        data_dir=None,  # use default test fixtures
        use_semantic=True,
        save_baseline=output_path,
    )

    metrics = result.get("metrics", {})
    print(f"  MRR@5:       {metrics.get('mrr_at_5', 0):.4f}")
    print(f"  Recall@5:    {metrics.get('recall_at_5', 0):.4f}")
    print(f"  Precision@5: {metrics.get('precision_at_5', 0):.4f}")
    print(f"  Failures:    {len(result.get('failures', []))}")
    print(f"  Total queries: {result.get('total_queries', 0)}")
    print(f"  Snapshot: {output_path}")


if __name__ == "__main__":
    main()
