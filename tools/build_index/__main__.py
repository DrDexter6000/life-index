#!/usr/bin/env python3
"""
Life Index - Build Index Tool - CLI Entry Point
索引构建工具（FTS only）
"""

import argparse
import json
import sys

from . import build_all, show_stats, check_index
from ..lib.config import ensure_dirs
from ..lib.metadata_cache import get_cache_stats
from ..lib.observability import build_provenance_envelope
from ..lib.trace import Trace


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Life Index - Build Search Index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Daily incremental update (default)
    python -m tools.build_index

    # Full rebuild (monthly maintenance)
    python -m tools.build_index --rebuild

    # Only FTS index
    python -m tools.build_index --fts-only

    # View statistics
    python -m tools.build_index --stats

    # Check index consistency (read-only diagnostic)
    python -m tools.build_index --check
        """,
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Full rebuild (delete and recreate all indexes)",
    )

    parser.add_argument("--fts-only", action="store_true", help="Only update FTS index")

    parser.add_argument(
        "--vec-only",
        action="store_true",
        help="Deprecated no-op: vector index is no longer built",
    )

    parser.add_argument(
        "--with-semantic",
        action="store_true",
        help="Deprecated no-op: semantic/vector index is no longer built",
    )

    parser.add_argument("--stats", action="store_true", help="Show index statistics")

    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    parser.add_argument(
        "--explain",
        action="store_true",
        help="Output build diagnostics as JSON",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="Check index consistency (read-only diagnostic)",
    )

    parser.add_argument(
        "--cache-dry-run",
        action="store_true",
        help="Report cache invalidation status without writing (read-only)",
    )

    args = parser.parse_args()

    if args.check:
        result = check_index()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if not result["healthy"]:
            sys.exit(1)
        return

    if args.cache_dry_run:
        from ..lib.metadata_cache import evaluate_cache_state

        state = evaluate_cache_state()
        result = {
            "success": True,
            "dry_run": True,
            "cache_version": state,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    ensure_dirs()

    if args.stats:
        show_stats()
        return

    effective_fts_only = True

    # 执行索引构建
    with Trace("index") as trace:
        with trace.step("build_all"):
            result = build_all(
                incremental=not args.rebuild,
                fts_only=effective_fts_only,
                vec_only=args.vec_only,
            )

    if args.with_semantic:
        result.setdefault("warnings", []).append(
            "deprecated_noop: --with-semantic is accepted but ignored; index builds FTS only."
        )

    result["_trace"] = trace.to_dict()

    if result["success"]:
        try:
            from ..lib.metadata_cache import write_cache_version

            write_cache_version()
        except Exception:
            pass

    if args.explain:
        latency_ms: dict[str, float] = {
            "total": round(result["duration_seconds"] * 1000, 2),
        }
        fts_data = result.get("fts") or {}
        if isinstance(fts_data, dict) and "duration_seconds" in fts_data:
            latency_ms["fts"] = round(fts_data["duration_seconds"] * 1000, 2)
        input_count = 0
        if isinstance(fts_data, dict):
            input_count += fts_data.get("added", 0) + fts_data.get("updated", 0)

        cache_stats = get_cache_stats()
        result["diagnostics"] = {
            "input_count": input_count,
            "filter_drops": {},
            "cache_hits": cache_stats.get("total_entries", 0),
            "cache_misses": 0,
            "latency_ms": latency_ms,
            "fallback_path": None,
        }

    if args.explain or args.json:
        provenance_envelope = build_provenance_envelope(
            source_data=result,
            generator="index",
            params={
                "rebuild": args.rebuild,
                "fts_only": effective_fts_only,
                "vec_only": args.vec_only,
                "with_semantic": args.with_semantic,
            },
        )
        result["schema_version"] = provenance_envelope["schema_version"]
        result["provenance"] = provenance_envelope["provenance"]
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
