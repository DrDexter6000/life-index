"""CLI entry point for Life Index bootstrap detection."""

from __future__ import annotations

import argparse
import json
import os
import sys

from tools.bootstrap import build_bootstrap_result


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="life-index bootstrap",
        description=(
            "Detect Life Index install/data state. Read-only: no changes to data, "
            "venv, or checkouts."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    parser.add_argument(
        "--data-dir",
        default=None,
        help=(
            "Override Life Index data directory. Also sets LIFE_INDEX_DATA_DIR " "for this process."
        ),
    )
    parser.add_argument(
        "--checkout-path",
        default=None,
        help="Optional Life Index checkout path to assess.",
    )
    parser.add_argument(
        "--checkout-origin",
        choices=("discovered", "host_managed", "user_designated"),
        default="discovered",
        help=(
            "Authority for --checkout-path. Use host_managed only for an agent "
            "platform's official skill directory; use user_designated only after "
            "explicit user selection."
        ),
    )
    args = parser.parse_args()

    if args.data_dir:
        os.environ["LIFE_INDEX_DATA_DIR"] = args.data_dir

    result = build_bootstrap_result(
        data_dir=args.data_dir,
        checkout_path=args.checkout_path,
        checkout_origin=args.checkout_origin,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    print(f"Route:  {result['route']}")
    print(f"Reason: {result['route_reason']}")
    if result["needs_human"]:
        print()
        print("Needs human input:")
        for item in result["needs_human"]:
            print(f"  [{item['code']}] {item['message']}")
            print(f"  Action: {item['suggested_action']}")
    if result["safe_next_steps"]:
        print()
        print("Safe next steps:")
        for step in result["safe_next_steps"]:
            print(f"  {step}")
    sys.exit(0)


if __name__ == "__main__":
    main()
