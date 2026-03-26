#!/usr/bin/env python3
"""
Life Index - Edit Journal Tool - CLI Entry Point
编辑已存在的日志文件，支持 frontmatter 字段修改和正文编辑
"""

import argparse
import json
import sys
from pathlib import Path

from . import edit_journal
from ..lib.config import USER_DATA_DIR, ensure_dirs
from ..lib.logger import get_logger

logger = get_logger(__name__)


def _emit_json(payload: dict) -> None:
    """Print JSON safely across Windows console encodings."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        fallback_text = json.dumps(payload, ensure_ascii=True, indent=2)
        print(fallback_text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Life Index - Edit Journal Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
重要规则:
    修改地点时，必须同时提供新的天气。
    推荐顺序：先 query_weather；如果失败，可手动查询天气后，再一起传入 --set-location 和 --set-weather。

Examples:
    # 设置地点和天气
    python -m tools.edit_journal --journal "Journals/2026/03/life-index_2026-03-05_001.md" \\
        --set-location "Beijing, China" --set-weather "多云"

    # 追加正文内容
    python -m tools.edit_journal --journal "..." --append-content "下午还讨论了部署方案。"

    # 修改 topic（会触发索引重建）
    python -m tools.edit_journal --journal "..." --set-topic "learn"

    # 批量修改多个字段
    python -m tools.edit_journal --journal "..." \\
        --set-location "Shanghai, China" \\
        --set-mood "开心,兴奋" \\
        --set-project "New-Project"
        """,
    )

    parser.add_argument(
        "--journal", required=True, help="日志文件路径（相对或绝对路径）"
    )

    # Frontmatter 字段设置
    parser.add_argument("--set-title", help="设置标题")
    parser.add_argument("--set-date", help="设置日期")
    parser.add_argument("--set-location", help="设置地点")
    parser.add_argument("--set-weather", help="设置天气")
    parser.add_argument("--set-mood", help="设置心情（逗号分隔多个）")
    parser.add_argument("--set-people", help="设置人物（逗号分隔多个）")
    parser.add_argument("--set-tags", help="设置标签（逗号分隔多个）")
    parser.add_argument("--set-project", help="设置项目")
    parser.add_argument("--set-topic", help="设置主题（逗号分隔多个）")
    parser.add_argument("--set-abstract", help="设置摘要")

    # 内容编辑
    content_group = parser.add_mutually_exclusive_group()
    content_group.add_argument("--append-content", help="追加内容到正文末尾")
    content_group.add_argument(
        "--replace-content", help="替换整个正文内容（保留 frontmatter）"
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="模拟运行，不实际写入文件"
    )

    parser.add_argument("--verbose", action="store_true", help="输出详细日志")

    args = parser.parse_args()
    ensure_dirs()

    if args.verbose:
        logger.info("启用详细日志模式")

    # 解析日志路径
    journal_path = Path(args.journal)
    if not journal_path.is_absolute():
        # 尝试相对于用户数据目录解析
        base_dir = USER_DATA_DIR
        journal_path = base_dir / journal_path

    logger.debug(f"日志路径：{journal_path}")

    # 收集 frontmatter 更新
    frontmatter_updates = {}

    if args.set_title is not None:
        frontmatter_updates["title"] = args.set_title
    if args.set_date is not None:
        frontmatter_updates["date"] = args.set_date
    if args.set_location is not None:
        frontmatter_updates["location"] = args.set_location
    if args.set_weather is not None:
        frontmatter_updates["weather"] = args.set_weather
    if args.set_mood is not None:
        normalized = args.set_mood.replace("，", ",")
        frontmatter_updates["mood"] = [
            m.strip() for m in normalized.split(",") if m.strip()
        ]
    if args.set_people is not None:
        normalized = args.set_people.replace("，", ",")
        frontmatter_updates["people"] = [
            p.strip() for p in normalized.split(",") if p.strip()
        ]
    if args.set_tags is not None:
        normalized = args.set_tags.replace("，", ",")
        frontmatter_updates["tags"] = [
            t.strip() for t in normalized.split(",") if t.strip()
        ]
    if args.set_project is not None:
        frontmatter_updates["project"] = args.set_project
    if args.set_topic is not None:
        normalized = args.set_topic.replace("，", ",")
        frontmatter_updates["topic"] = [
            t.strip() for t in normalized.split(",") if t.strip()
        ]
    if args.set_abstract is not None:
        frontmatter_updates["abstract"] = args.set_abstract

    logger.debug(f"Frontmatter 更新：{list(frontmatter_updates.keys())}")

    # 执行编辑
    result = edit_journal(
        journal_path=journal_path,
        frontmatter_updates=frontmatter_updates,
        append_content=args.append_content,
        replace_content=args.replace_content,
        dry_run=args.dry_run,
    )

    # 输出结果（保持 JSON 输出到 stdout）
    _emit_json(result)

    if result["success"]:
        logger.info("工具执行成功")
    else:
        logger.error(f"工具执行失败：{result.get('error')}")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
