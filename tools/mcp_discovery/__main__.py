"""Entry point for ``python -m tools.mcp_discovery``.

Currently a no-op stub. Future work: start a JSON-RPC 2.0 server on stdio
per the MCP specification (RFC-2026-05-25 section 3).
"""

from __future__ import annotations

import sys


def main() -> None:
    """Print a stub message. Real MCP JSON-RPC transport is future work."""
    print(
        "MCP discovery server stub. " "JSON-RPC 2.0 transport over stdio is not yet implemented.",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
