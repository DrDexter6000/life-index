#!/usr/bin/env python3
"""CLI entry point for search evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .run_eval import compare_against_baseline, run_evaluation


def _emit_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Life Index - Search evaluation")
    parser.add_argument("--data-dir", type=Path, help="Use a specific data directory")
    parser.add_argument(
        "--save-baseline", type=Path, help="Save current evaluation result to JSON"
    )
    parser.add_argument(
        "--compare-baseline",
        type=Path,
        help="Compare current evaluation with a saved baseline JSON",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the full JSON result instead of summary lines",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Disable semantic pipeline (default: disabled)",
    )
    parser.add_argument(
        "--judge",
        choices=("keyword", "llm"),
        default="keyword",
        help="Select keyword or llm judge mode",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Evaluate against real ~/Documents/Life-Index data",
    )
    args = parser.parse_args(argv)

    use_semantic = False

    if args.compare_baseline:
        comparison = compare_against_baseline(
            baseline_path=args.compare_baseline,
            data_dir=args.data_dir,
            use_semantic=use_semantic,
        )
        if args.json:
            payload = {"success": True, "data": comparison}
        else:
            payload = {
                "success": True,
                "data": {
                    "diff_lines": comparison["diff_lines"],
                    "diff": comparison["diff"],
                    "current_metrics": comparison["current"]["metrics"],
                    "recall_gaps": comparison["current"].get("recall_gaps", []),
                },
            }
        _emit_json(payload)
        return

    result = run_evaluation(
        data_dir=args.data_dir,
        save_baseline=args.save_baseline,
        use_semantic=use_semantic,
        judge=args.judge,
        live=args.live,
    )
    if args.json:
        payload = {"success": True, "data": result}
    else:
        payload = {
            "success": True,
            "data": {
                "summary_lines": result["summary_lines"],
                "metrics": result["metrics"],
                "total_queries": result["total_queries"],
                "failures": result["failures"],
            },
        }
    _emit_json(payload)


if __name__ == "__main__":
    main()
