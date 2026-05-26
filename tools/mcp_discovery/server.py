"""MCP Discovery Server core (RFC-2026-05-25).

Three meta-tools for MCP-compatible Agent discovery of Life Index CLI
capabilities. This is a read-only discovery overlay: no data path, no LLM,
no dynamic plugin registry.

Target: <=200 LOC for the server core.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MANIFEST_PATH = Path(__file__).parent / "capabilities.json"
_manifest: list[dict[str, str]] | None = None


def _load_manifest() -> list[dict[str, str]]:
    """Load and cache the static capabilities manifest."""
    global _manifest
    if _manifest is None:
        raw = _MANIFEST_PATH.read_text(encoding="utf-8")
        _manifest = json.loads(raw)
    return _manifest


def list_capabilities() -> list[dict[str, str]]:
    """Return all CLI capabilities with names and one-line descriptions.

    Returns a list of dicts, each with 'name' and 'description'.
    Full parameter schemas are not included; use describe_tool(name).
    """
    return _load_manifest()


def describe_tool(name: str) -> dict[str, str]:
    """Return the manifest entry for a known tool.

    Raises:
        KeyError: if *name* is not found in the capabilities manifest.
    """
    for entry in _load_manifest():
        if entry["name"] == name:
            return dict(entry)
    raise KeyError(f"Unknown tool: {name!r}")


def invoke_tool(name: str, args: dict[str, Any] | None = None) -> None:
    """Invoke a CLI tool via subprocess.

    NOT IMPLEMENTED: this stub raises NotImplementedError.
    Full CLI passthrough subprocess execution is future work per RFC section 3.
    The MCP server will eventually call ``life-index <name>`` as a
    subprocess and return the CLI JSON output unchanged.
    """
    raise NotImplementedError(
        f"invoke_tool({name!r}) is not implemented in this stub. "
        "Full CLI passthrough subprocess execution is future work."
    )
