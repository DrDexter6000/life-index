#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - L1 Index
一级索引搜索模块（by-topic索引）
"""

import re
from pathlib import Path
from typing import Any, Dict, List

# 导入配置 (relative imports from tools/lib)
from ..lib.config import BY_TOPIC_DIR, USER_DATA_DIR, JOURNALS_DIR
from ..lib.path_contract import merge_journal_path_fields


def scan_all_indices() -> List[Dict[str, Any]]:
    """
    扫描所有索引文件（L1 层全索引浏览）

    Returns:
        所有索引条目合并后的列表
    """
    results: List[Dict[str, Any]] = []
    seen_paths: set[str] = set()

    if not BY_TOPIC_DIR.exists():
        return results

    # 扫描所有索引文件
    for index_file in BY_TOPIC_DIR.glob("*.md"):
        try:
            content = index_file.read_text(encoding="utf-8")
            # 解析索引条目: - [YYYY-MM-DD 标题](路径)
            pattern = r"- \[(\d{4}-\d{2}-\d{2})\] \[(.*?)\]\((.*?)\)"
            matches = re.findall(pattern, content)

            for date_str, title, path in matches:
                normalized = merge_journal_path_fields(
                    {
                        "date": date_str,
                        "title": title,
                        "source": "index:all",
                    },
                    USER_DATA_DIR / Path(path),
                    journals_dir=JOURNALS_DIR,
                    user_data_dir=USER_DATA_DIR,
                )
                if normalized["path"] not in seen_paths:
                    seen_paths.add(normalized["path"])
                    results.append(normalized)
        except (OSError, IOError):
            continue

    return results


def search_l1_index(query_type: str, query_value: str) -> List[Dict[str, Any]]:
    """
    L1: 索引层搜索 - 快速定位可能包含目标的日志

    Args:
        query_type: 'topic', 'project', 'tag'
        query_value: 查询值
    """
    results: List[Dict[str, Any]] = []

    if query_type == "topic":
        index_file = BY_TOPIC_DIR / f"主题_{query_value}.md"
    elif query_type == "project":
        index_file = BY_TOPIC_DIR / f"项目_{query_value}.md"
    elif query_type == "tag":
        index_file = BY_TOPIC_DIR / f"标签_{query_value}.md"
    else:
        return results

    if not index_file.exists():
        return results

    content = index_file.read_text(encoding="utf-8")

    # 解析索引条目: - [YYYY-MM-DD] [标题](路径)
    pattern = r"- \[(\d{4}-\d{2}-\d{2})\] \[(.*?)\]\((.*?)\)"
    matches = re.findall(pattern, content)

    for date_str, title, path in matches:
        results.append(
            merge_journal_path_fields(
                {
                    "date": date_str,
                    "title": title,
                    "source": f"index:{query_type}={query_value}",
                },
                USER_DATA_DIR / Path(path),
                journals_dir=JOURNALS_DIR,
                user_data_dir=USER_DATA_DIR,
            )
        )

    return results
