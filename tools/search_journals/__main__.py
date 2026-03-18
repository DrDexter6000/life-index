#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - CLI Entry Point
双管道并行检索日志（关键词管道 ∥ 语义管道 → RRF 融合）
"""

import argparse
import json
import sys

from .core import hierarchical_search
from ..lib.config import ensure_dirs


def _emit_json(payload: dict) -> None:
    """Print JSON safely across Windows console encodings."""
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
        "--semantic-weight",
        type=float,
        default=0.4,
        help="语义搜索权重 (默认: 0.4)",
    )
    parser.add_argument(
        "--fts-weight",
        type=float,
        default=0.6,
        help="FTS 搜索权重 (默认: 0.6)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="返回结果数量限制",
    )

    args = parser.parse_args()
    ensure_dirs()

    # 解析列表参数
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    mood = [m.strip() for m in args.mood.split(",") if m.strip()] if args.mood else None
    people = (
        [p.strip() for p in args.people.split(",") if p.strip()]
        if args.people
        else None
    )

    # 执行搜索
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
        level=args.level,
        use_index=not args.no_index,
        semantic=not args.no_semantic,
        semantic_weight=args.semantic_weight,
        fts_weight=args.fts_weight,
    )

    # 应用 limit
    if args.limit and "merged_results" in result:
        result["merged_results"] = result["merged_results"][: args.limit]
        result["total_found"] = len(result["merged_results"])

    # 输出结果
    _emit_json(result)

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
