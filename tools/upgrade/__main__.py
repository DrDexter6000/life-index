from __future__ import annotations

import argparse
import json
import sys

from .core import PyPIReleaseProvider
from .core import apply_upgrade
from .core import build_upgrade_plan
from .core import detect_install_context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="life-index upgrade",
        description=(
            "Plan or apply a deterministic Life Index CLI upgrade for host agents. "
            "This is not a release publishing workflow."
        ),
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Build a read-only upgrade plan.")
    mode.add_argument("--apply", action="store_true", help="Run safe upgrade actions.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    context = detect_install_context()
    provider = PyPIReleaseProvider()
    if args.apply:
        payload = apply_upgrade(context=context, release_provider=provider)
    else:
        payload = build_upgrade_plan(context=context, release_provider=provider)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("success") is not False else 1


if __name__ == "__main__":
    sys.exit(main())
