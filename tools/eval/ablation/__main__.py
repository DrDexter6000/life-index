#!/usr/bin/env python3
"""CLI entry point for graph ablation evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import run_ablation


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Life Index - Graph ablation evaluation")
    parser.add_argument(
        "--queries",
        type=Path,
        required=True,
        help="Path to ablation queries JSON fixture",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="stdout",
        help='Output destination: "stdout" (default) or a file path',
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Override data directory (sets LIFE_INDEX_DATA_DIR)",
    )
    args = parser.parse_args(argv)

    if not args.queries.exists():
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"Queries fixture not found: {args.queries}",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    # Set data directory if provided
    if args.data_dir:
        import os

        os.environ["LIFE_INDEX_DATA_DIR"] = str(args.data_dir)

    output = run_ablation(queries_path=args.queries)
    output["success"] = True

    text = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output == "stdout":
        try:
            print(text)
        except UnicodeEncodeError:
            print(json.dumps(output, ensure_ascii=True, indent=2))
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        print(json.dumps({"success": True, "output_file": str(output_path)}))


if __name__ == "__main__":
    main()
