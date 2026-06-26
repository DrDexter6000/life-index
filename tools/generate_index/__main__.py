#!/usr/bin/env python3
"""
Life Index - Index Generator - CLI Entry Point
索引生成工具（月度/年度）
"""

import argparse
import json
import sys
from collections.abc import Iterator

from . import generate_monthly_abstract, generate_yearly_abstract, rebuild_index_tree
from ..lib.config import ensure_dirs
from ..lib.paths import get_journals_dir
from ..lib.logger import get_logger

logger = get_logger(__name__)


def _iter_journal_months(year: int | None = None) -> Iterator[tuple[int, int]]:
    journals_dir = get_journals_dir()
    if year is not None:
        year_dirs = [journals_dir / str(year)]
    else:
        year_dirs = (
            [
                path
                for path in sorted(journals_dir.iterdir())
                if path.is_dir() and path.name.isdigit()
            ]
            if journals_dir.exists()
            else []
        )

    for year_dir in year_dirs:
        if not year_dir.exists() or not year_dir.name.isdigit():
            continue
        year_value = int(year_dir.name)
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
            month = int(month_dir.name)
            if not 1 <= month <= 12:
                continue
            if any(month_dir.glob("life-index_*.md")):
                yield year_value, month


def _refresh_index_b_result(*, dry_run: bool) -> dict:
    """Refresh Index B alongside legacy generated indexes."""
    try:
        from ..index_tree.materialize import build_materialize_payload

        payload = build_materialize_payload(dry_run=dry_run, incremental=True)
        return {
            "type": "index-b",
            "success": True,
            "updated": not dry_run,
            "message": "Index B navigation refreshed",
            "index_b": payload,
        }
    except Exception as exc:
        return {
            "type": "index-b",
            "success": False,
            "updated": False,
            "message": f"Index B navigation refresh failed: {exc}",
            "error": str(exc),
        }


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

    # 批量生成所有有日志月份的月度索引
    python -m tools.generate_index --all-months

    # 批量生成指定年份的月度索引
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
        help="批量生成有日志月份的月度索引；与 --year 一起使用时限制到指定年份",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="预览模式：显示生成的内容但不写入文件"
    )

    parser.add_argument("--json", action="store_true", help="输出结果为 JSON 格式")
    parser.add_argument("--rebuild", action="store_true", help="重建全部索引树")

    args = parser.parse_args()
    ensure_dirs()

    # 验证参数
    if not args.rebuild and not args.month and not args.year and not args.all_months:
        parser.error("请指定 --month、--year 或 --all-months 参数")

    results = []

    if args.rebuild:
        logger.info("重建全部索引树")
        results.append(rebuild_index_tree(dry_run=args.dry_run))
        results.append(_refresh_index_b_result(dry_run=args.dry_run))

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

    # 批量生成月度摘要
    if args.all_months:
        scope = f"{args.year}年" if args.year else "所有年份"
        logger.info(f"批量生成{scope}有日志月份的月度摘要")
        month_pairs = list(_iter_journal_months(args.year))
        for year, month in month_pairs:
            result = generate_monthly_abstract(year, month, args.dry_run)
            results.append(result)
        if not month_pairs:
            message = f"{args.year}年没有可生成的日志月份" if args.year else "没有可生成的日志月份"
            logger.warning(message)
            results.append({"type": "monthly", "year": args.year, "message": message})
        results.append(_refresh_index_b_result(dry_run=args.dry_run))

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
