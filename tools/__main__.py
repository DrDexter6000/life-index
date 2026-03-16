#!/usr/bin/env python3
"""
Life Index - Unified CLI Entry Point
统一命令行入口

Usage:
    life-index <command> [options]
    python -m tools <command> [options]

Commands:
    write     Write a journal entry
    search    Search journals
    edit      Edit a journal entry
    weather   Query weather information
    index     Build/rebuild search index
    abstract  Generate monthly/yearly summaries
    backup    Backup journal data
"""

import sys


def main() -> None:
    """Unified CLI entry point"""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    subcmd = sys.argv[1]

    # Map subcommands to __main__ module paths
    # Each submodule has its own __main__.py with a main() function
    cmd_map = {
        "write": "tools.write_journal.__main__",
        "search": "tools.search_journals.__main__",
        "edit": "tools.edit_journal.__main__",
        "weather": "tools.query_weather.__main__",
        "index": "tools.build_index.__main__",
        "abstract": "tools.generate_abstract.__main__",
        "backup": "tools.backup.__main__",
    }

    if subcmd in cmd_map:
        # Rewrite argv so the submodule's argparse works correctly
        # Keep the original argv[0] for proper error messages
        sys.argv = [f"life-index {subcmd}"] + sys.argv[2:]

        # Import and run the submodule's main()
        module = __import__(cmd_map[subcmd], fromlist=["main"])
        module.main()
    elif subcmd in ("--help", "-h", "help"):
        print_usage()
    else:
        print(f"Unknown command: {subcmd}")
        print_usage()
        sys.exit(1)


def print_usage() -> None:
    """Print usage information"""
    print("Usage: life-index <command> [options]")
    print()
    print("Commands:")
    print("  write     Write a journal entry")
    print("  search    Search journals")
    print("  edit      Edit a journal entry")
    print("  weather   Query weather information")
    print("  index     Build/rebuild search index")
    print("  abstract  Generate monthly/yearly summaries")
    print("  backup    Backup journal data")
    print()
    print("Run 'life-index <command> --help' for command-specific options.")
    print()
    print("Developer mode:")
    print("  python -m tools.write_journal --data '{...}'")
    print("  python -m tools.search_journals --query '关键词'")


if __name__ == "__main__":
    main()
