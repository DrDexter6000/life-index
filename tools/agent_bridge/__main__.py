from __future__ import annotations

import argparse
import json
import sys

from tools.agent_bridge.handoff import handoff_search


def _print_help() -> None:
    print("usage: agent-bridge probe --json [--no-network] [--timeout SECONDS]")
    print("       agent-bridge --query QUERY [--in-context]")
    print()
    print("Commands:")
    print("  probe       Check endpoint/model/ack/token without sending journal evidence")
    print()
    print("Options:")
    print("  --json       Emit JSON output for probe")
    print("  --no-network Skip endpoint/model HTTP checks")
    print("  --timeout    HTTP timeout in seconds for probe checks")
    print("  --query      Legacy handoff query path; may send smart-search evidence")
    print("  --in-context Force in-context agent mode for handoff/probe resolution")


def _probe(argv: list[str]) -> int:
    from tools.agent_bridge.probe import probe_agent_bridge

    p = argparse.ArgumentParser(prog="agent-bridge probe")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-network", action="store_true")
    p.add_argument("--timeout", type=float, default=1.5)
    p.add_argument("--in-context", action="store_true")
    args = p.parse_args(argv)
    if not args.json:
        p.error("--json is required")
    result = probe_agent_bridge(
        network=not args.no_network,
        timeout=args.timeout,
        in_context_agent=args.in_context,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _handoff(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="agent-bridge")
    p.add_argument("--query", required=True)
    p.add_argument("--in-context", action="store_true")
    args = p.parse_args(argv)
    env = handoff_search(args.query, in_context_agent=args.in_context)
    print(json.dumps(env, ensure_ascii=False))
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("--help", "-h", "help"):
        _print_help()
        return 0
    if argv[0] == "probe":
        return _probe(argv[1:])
    return _handoff(argv)


if __name__ == "__main__":
    raise SystemExit(main())
