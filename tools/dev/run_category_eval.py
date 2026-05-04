#!/usr/bin/env python3
"""Run eval and report category failure rates."""

from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, ".")
from tools.eval.run_eval import run_evaluation


def main() -> None:
    result = run_evaluation(save_baseline=None)
    per_query = result["per_query"]

    by_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "fail": 0})
    for q in per_query:
        cat = q.get("category", "unknown")
        by_cat[cat]["total"] += 1
        if not q.get("pass", False):
            by_cat[cat]["fail"] += 1

    print("Category failure rates:")
    for cat, stats in sorted(
        by_cat.items(), key=lambda x: x[1]["fail"] / x[1]["total"], reverse=True
    ):
        rate = stats["fail"] / stats["total"] * 100
        print(f"  {cat:20s}: {stats['fail']}/{stats['total']} ({rate:.0f}%)")

    total_f = len(result["failures"])
    total_q = result["total_queries"]
    print(f"\nOverall: {total_f}/{total_q} ({total_f / total_q * 100:.0f}%)")
    print(f"\nMetrics: {result['metrics']}")


if __name__ == "__main__":
    main()
