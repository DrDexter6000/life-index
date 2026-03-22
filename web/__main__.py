"""CLI entry point for `life-index serve`."""

import argparse
import json
import sys
from typing import Any, Optional

from tools.lib.errors import ErrorCode, create_error_response
from web.config import DEFAULT_HOST, DEFAULT_PORT


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the Life Index Web GUI server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", type=str, default=DEFAULT_HOST)
    parser.add_argument("--reload", action="store_true", default=False)
    return parser.parse_args(argv)


def check_deps() -> tuple[bool, Optional[dict[str, Any]]]:
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401

        return True, None
    except ImportError:
        return False, create_error_response(
            ErrorCode.WEB_DEPS_MISSING,
            "Web GUI dependencies not installed. Run: pip install life-index[web]",
        )


def main() -> None:
    args = parse_args()
    ok, error = check_deps()
    if not ok:
        print(json.dumps(error, ensure_ascii=False, indent=2))
        sys.exit(1)

    import uvicorn
    from web.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
