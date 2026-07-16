"""Entrypoint for the optional generic MCP projection."""

from __future__ import annotations

from .server import run_stdio


def main() -> None:
    """Run the optional SDK-managed stdio projection."""
    run_stdio()


if __name__ == "__main__":
    main()
