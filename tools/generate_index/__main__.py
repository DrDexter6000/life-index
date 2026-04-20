#!/usr/bin/env python3
"""
Life Index - Index Generator - CLI Entry Point
索引生成工具（月度/年度）
"""

import argparse
import json
import sys

from . import generate_monthly_abstract, generate_yearly_abstract, rebuild_index_tree
from ..lib.config import ensure_dirs
from ..lib.paths import get_journals_dir
from ..lib.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Life Index 索引生成工具（月度/年度）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 生成月度索引
    python -m tools.generate_index --month 2026-03
    python -m tools.generate_index --month 2026-03 --dry-run

    # 生成年度索引
    python -m tools.generate_index --year 2026
    python -m tools.generate_index --year 2026 --dry-run

    # 批量生成全年月度索引
    python -m tools.generate_index --year 2026 --all-months

    # 同时生成年度和指定月度索引
    python -m tools.generate_index --year 2026 --month 2026-03
        """,
    )

    parser.add_argument("--month", type=str, help="生成月度索引，格式: YYYY-MM (如 2026-03)")

    parser.add_argument("--year", type=int, help="生成年度索引，格式: YYYY (如 2026)")

    parser.add_argument(
        "--all-months",
        action="store_true",
        help="与 --year 一起使用，批量生成全年各月的月度索引",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="预览模式：显示生成的内容但不写入文件"
    )

    parser.add_argument("--json", action="store_true", help="输出结果为 JSON 格式")
    parser.add_argument("--rebuild", action="store_true", help="重建全部索引树")

    args = parser.parse_args()
    ensure_dirs()

    # 验证参数
    if not args.rebuild and not args.month and not args.year:
        parser.error("请指定 --month 或 --year 参数")

    results = []

    if args.rebuild:
        logger.info("重建全部索引树")
        results.append(rebuild_index_tree(dry_run=args.dry_run))

    # 生成月度摘要
    if args.month:
        try:
            year, month = map(int, args.month.split("-"))
            logger.info(f"生成月度摘要：{year}年{month:02d}月")
            result = generate_monthly_abstract(year, month, args.dry_run)
            results.append(result)
        except ValueError:
            logger.error("--month 参数格式应为 YYYY-MM (如 2026-03)")
            sys.exit(1)

    # 生成年度摘要
    if args.year and not args.all_months:
        logger.info(f"生成年度摘要：{args.year}年")
        result = generate_yearly_abstract(args.year, args.dry_run)
        results.append(result)

    # 批量生成全年月度摘要
    if args.year and args.all_months:
        logger.info(f"批量生成{args.year}年全年月度摘要")
        year_dir = get_journals_dir() / str(args.year)
        if year_dir.exists():
            for month_dir in sorted(year_dir.iterdir()):
                if month_dir.is_dir() and month_dir.name.isdigit():
                    month = int(month_dir.name)
                    result = generate_monthly_abstract(args.year, month, args.dry_run)
                    results.append(result)
        else:
            logger.warning(f"{args.year}年目录不存在")
            results.append(
                {
                    "type": "monthly",
                    "year": args.year,
                    "message": f"{args.year}年目录不存在",
                }
            )

    # 输出结果
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(result.get("message", ""))
            if result.get("journal_count") is not None:
                print(f"  日志数量: {result['journal_count']}")

    # 返回非零退出码如果有错误
    if any(not r.get("updated") and r.get("journal_count", 0) > 0 for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
