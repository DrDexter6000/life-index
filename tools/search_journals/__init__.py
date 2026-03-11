#!/usr/bin/env python3
"""
Life Index - Search Journals Tool
分层级检索日志（L1索引→L2元数据→L3内容）

Usage:
    python -m search_journals --query "关键词"
    python -m search_journals --topic work --project LobsterAI
    python -m search_journals --date-from 2026-01-01 --date-to 2026-03-04
"""

import argparse
import json
import sys
from typing import List, Optional

from .core import hierarchical_search


def main() -> None:
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Life Index - Search Journals Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m search_journals --query "深度学习"
    python -m search_journals --topic work --project LobsterAI
    python -m search_journals --date-from 2026-01-01 --date-to 2026-03-04
    python -m search_journals --tags AI,Python --level 2
    python -m search_journals --location Lagos
        """,
    )

    parser.add_argument(
        "--query",
        "--keywords",
        dest="query",
        help="内容搜索关键词（支持 --query 或 --keywords）",
    )
    parser.add_argument("--topic", help="按主题过滤")
    parser.add_argument("--project", help="按项目过滤")
    parser.add_argument("--tags", help="按标签过滤（逗号分隔）")
    parser.add_argument("--date-from", help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--location", help="按地点过滤")
    parser.add_argument("--weather", help="按天气过滤")
    parser.add_argument("--mood", help="按心情过滤（逗号分隔多个）")
    parser.add_argument("--people", help="按人物过滤（逗号分隔多个）")
    parser.add_argument(
        "--level",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="搜索层级: 1=索引, 2=元数据, 3=全文 (默认: 3)",
    )
    parser.add_argument(
        "--use-index",
        action="store_true",
        help="使用 FTS 索引加速全文搜索（需要预先运行 build_index.py）",
    )
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="启用语义搜索（混合 BM25 + 向量相似度排序）",
    )
    parser.add_argument(
        "--semantic-weight",
        type=float,
        default=0.4,
        help="语义搜索权重（0-1，默认 0.4，需配合 --semantic）",
    )
    parser.add_argument(
        "--fts-weight",
        type=float,
        default=0.6,
        help="FTS 搜索权重（0-1，默认 0.6，需配合 --semantic）",
    )
    parser.add_argument("--limit", type=int, default=50, help="返回结果数量限制")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")

    args = parser.parse_args()

    # 解析标签
    tags = args.tags.split(",") if args.tags else None
    mood = args.mood.split(",") if args.mood else None
    people = args.people.split(",") if args.people else None

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
        use_index=args.use_index,
        semantic=args.semantic,
        semantic_weight=args.semantic_weight,
        fts_weight=args.fts_weight,
    )

    # 应用限制
    if "merged_results" in result:
        result["merged_results"] = result["merged_results"][: args.limit]
    elif result["l2_results"]:
        result["l2_results"] = result["l2_results"][: args.limit]
    elif result["l1_results"]:
        result["l1_results"] = result["l1_results"][: args.limit]

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
