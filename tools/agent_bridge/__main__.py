from __future__ import annotations

import argparse
import json

from tools.agent_bridge.handoff import handoff_search


def main() -> int:
    p = argparse.ArgumentParser(prog="agent-bridge")
    p.add_argument("--query", required=True)
    p.add_argument("--in-context", action="store_true")
    args = p.parse_args()
    env = handoff_search(args.query, in_context_agent=args.in_context)
    print(json.dumps(env, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
