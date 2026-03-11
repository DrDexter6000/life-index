#!/usr/bin/env python3
"""
Life Index - Write Journal Tool
写入日志并自动维护索引体系

Usage:
    python -m write_journal --data '{"title": "...", "content": "...", ...}'
    python -m write_journal --data @input.json
    python -m write_journal --dry-run --data '...'
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Import modules
from .core import write_journal


def main() -> None:
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Life Index - Write Journal Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m write_journal --data '{"date":"2026-03-04","title":"测试","content":"内容"}'
    python -m write_journal --data @input.json --dry-run
    python -m write_journal --verbose --data '{...}'
        """,
    )

    parser.add_argument(
        "--data", required=True, help="JSON数据，或 @文件路径 (如 @input.json)"
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="模拟运行，不实际写入文件"
    )

    parser.add_argument("--verbose", action="store_true", help="输出详细日志")

    args = parser.parse_args()

    # 解析输入数据
    try:
        if args.data.startswith("@"):
            # 从文件读取
            file_path = args.data[1:]
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            # 直接解析JSON
            data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(
            json.dumps(
                {"success": False, "error": f"JSON解析错误: {e}"},
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)
    except FileNotFoundError:
        print(
            json.dumps(
                {"success": False, "error": f"文件未找到: {args.data[1:]}"},
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    if args.verbose:
        print(
            f"[INFO] 输入数据: {json.dumps(data, ensure_ascii=False)}", file=sys.stderr
        )

    # 执行写入
    result = write_journal(data, dry_run=args.dry_run)

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 返回码
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
