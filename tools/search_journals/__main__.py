#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - CLI Entry Point
双管道并行检索日志（关键词管道 ∥ 语义管道 → RRF 融合）
"""

# ── Encoding protection (R10 fix) ──────────────────────────────────────
# MUST run before any imports that might trigger torch/transformers output.
# On Windows, torch emits GBK-encoded bytes to stderr which corrupts
# subprocess output when the parent process reads with encoding='utf-8'.
from ._bootstrap import ensure_utf8_io

ensure_utf8_io()

import argparse
import json
import sys
from importlib import import_module

from .core import hierarchical_search
from ..lib.config import ensure_dirs
from ..lib.paths import get_journals_dir, get_user_data_dir
from ..lib.trace import Trace


def _emit_json(payload: dict, *, include_events: bool = True) -> None:
    """Print JSON safely across Windows console encodings."""
    if include_events:
        # Attach piggyback events before emitting
        from ..lib.events import detect_events
        from ..lib.event_detectors import register_all_detectors

        register_all_detectors()
        context = {"journals_dir": get_journals_dir(), "data_dir": get_user_data_dir()}
        events = detect_events(context=context)
        payload["events"] = [e.to_dict() for e in events]

    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text)


def main() -> None:
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Life Index - Search Journals Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m tools.search_journals --query "重构"
    python -m tools.search_journals --query "重构" --level 3
    python -m tools.search_journals --topic work --project Life-Index
    python -m tools.search_journals --date-from 2026-01-01 --date-to 2026-03-04
    python -m tools.search_journals --query "学习笔记" --no-semantic
        """,
    )

    parser.add_argument("--query", help="搜索关键词")
    parser.add_argument("--topic", help="按主题过滤 (如 work, learn, life)")
    parser.add_argument("--year", type=int, help="L0 prefilter: restrict to year")
    parser.add_argument(
        "--month", type=int, help="L0 prefilter: restrict to month (requires --year)"
    )
    parser.add_argument("--project", help="按项目过滤")
    parser.add_argument("--tags", help="按标签过滤（逗号分隔多个）")
    parser.add_argument("--mood", help="按心情过滤（逗号分隔多个）")
    parser.add_argument("--people", help="按人物过滤（逗号分隔多个）")
    parser.add_argument("--date-from", dest="date_from", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--date-to", dest="date_to", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--location", help="按地点过滤")
    parser.add_argument("--weather", help="按天气过滤")
    parser.add_argument(
        "--level",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="搜索层级：1=索引, 2=元数据, 3=双管道并行 (默认: 3)",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="禁用 FTS 索引（回退到文件扫描，默认启用 FTS）",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="禁用语义搜索（默认启用）",
    )
    parser.add_argument(
        "--semantic-policy",
        choices=["fallback", "hybrid"],
        default="fallback",
        help="语义搜索策略: fallback=仅零结果时启用, hybrid=并行融合 (默认: fallback)",
    )
    parser.add_argument(
        "--semantic-weight",
        type=float,
        default=1.0,
        help="语义搜索权重 (默认: 1.0)",
    )
    parser.add_argument(
        "--fts-weight",
        type=float,
        default=1.0,
        help="FTS 搜索权重 (默认: 1.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="返回结果数量限制",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="结果偏移量（分页起始位置，默认: 0）",
    )
    parser.add_argument(
        "--read-top",
        type=int,
        default=0,
        help="读取前 N 条结果的完整正文（Task 1.2.3，默认: 0 不读取）",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="输出搜索评分详情（Task 2.1）",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="输出最近搜索行为诊断摘要并退出",
    )
    parser.add_argument(
        "--diagnose-days",
        type=int,
        default=7,
        help="诊断回看天数（默认: 7）",
    )

    args = parser.parse_args()
    ensure_dirs()

    if args.diagnose:
        diagnose_search = import_module("tools.lib.search_diagnose").diagnose_search
        _emit_json(diagnose_search(days=args.diagnose_days), include_events=False)
        sys.exit(0)

    # 解析列表参数（支持全角逗号）
    tags = (
        [t.strip() for t in args.tags.replace("，", ",").split(",") if t.strip()]
        if args.tags
        else None
    )
    mood = (
        [m.strip() for m in args.mood.replace("，", ",").split(",") if m.strip()]
        if args.mood
        else None
    )
    people = (
        [p.strip() for p in args.people.replace("，", ",").split(",") if p.strip()]
        if args.people
        else None
    )

    # 执行搜索
    with Trace("search") as trace:
        with trace.step("hierarchical_search"):
            result = hierarchical_search(
                query=args.query,
                topic=args.topic,
                project=args.project,
                tags=tags,
                mood=mood,
                people=people,
                date_from=args.date_from,
                date_to=args.date_to,
                location=args.location,
                weather=args.weather,
                year=args.year,
                month=args.month,
                level=args.level,
                use_index=not args.no_index,
                semantic=not args.no_semantic,
                semantic_weight=args.semantic_weight,
                fts_weight=args.fts_weight,
                explain=args.explain,  # Task 2.1
                semantic_policy=args.semantic_policy,
            )

    # Phase 2 (Task 3): Presentation-layer slicing with offset + limit
    if "merged_results" in result:
        all_results = result["merged_results"]
        total_available = result.get("total_available", len(all_results))

        # Apply offset
        if args.offset and args.offset > 0:
            all_results = all_results[args.offset :]

        # Apply limit (if specified, overrides the default MAX_RESULTS_DEFAULT truncation)
        if args.limit:
            all_results = all_results[: args.limit]

        result["merged_results"] = all_results
        result["total_found"] = len(all_results)
        result["total_available"] = total_available
        result["has_more"] = (args.offset + len(all_results)) < total_available

    # Task 1.2.3: Read full content for top N results
    if args.read_top > 0 and result.get("success") and result.get("merged_results"):
        from pathlib import Path
        from ..lib.paths import get_journals_dir

        _journals_dir = get_journals_dir()

        top_n = min(args.read_top, len(result["merged_results"]))
        for i in range(top_n):
            item = result["merged_results"][i]
            path = item.get("path", "")

            if path:
                # Construct full path
                if path.startswith("Journals/"):
                    full_path = _journals_dir.parent / path
                else:
                    full_path = Path(path)

                # Read full content
                try:
                    if full_path.exists():
                        content = full_path.read_text(encoding="utf-8")
                        # Extract body (after frontmatter)
                        if content.startswith("---"):
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                item["full_content"] = parts[2].strip()
                            else:
                                item["full_content"] = content
                        else:
                            item["full_content"] = content
                    else:
                        item["full_content"] = None
                except Exception as e:
                    item["full_content"] = None
                    item["read_error"] = str(e)

    # 输出结果
    result["_trace"] = trace.to_dict()
    _emit_json(result)

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
