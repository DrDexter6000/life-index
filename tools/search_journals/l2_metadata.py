#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - L2 Metadata
二级元数据搜索模块（frontmatter扫描）
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# 导入配置
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.config import JOURNALS_DIR, USER_DATA_DIR

from .utils import parse_frontmatter


def search_l2_metadata(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    location: Optional[str] = None,
    weather: Optional[str] = None,
    topic: Optional[str] = None,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    mood: Optional[List[str]] = None,
    people: Optional[List[str]] = None,
    query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    L2: 元数据层搜索 - 扫描所有日志的 frontmatter

    Args:
        query: 当指定 query 时，额外过滤 title/abstract/tags 包含该关键词的日志
    """
    results = []

    if not JOURNALS_DIR.exists():
        return results

    # 遍历所有日志文件
    for year_dir in JOURNALS_DIR.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue

        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue

            for journal_file in month_dir.glob("*.md"):
                try:
                    content = journal_file.read_text(encoding="utf-8")
                    metadata, body = parse_frontmatter(content)

                    if not metadata:
                        continue

                    # 日期过滤
                    file_date = metadata.get("date", "")[:10]
                    if date_from and file_date < date_from:
                        continue
                    if date_to and file_date > date_to:
                        continue

                    # 地点过滤
                    if (
                        location
                        and location.lower() not in metadata.get("location", "").lower()
                    ):
                        continue

                    # 天气过滤
                    if (
                        weather
                        and weather.lower() not in metadata.get("weather", "").lower()
                    ):
                        continue

                    # Topic过滤（支持数组或字符串）
                    if topic:
                        file_topics = metadata.get("topic", [])
                        if isinstance(file_topics, str):
                            file_topics = [file_topics]
                        if topic not in file_topics:
                            continue

                    # Project过滤（支持数组或字符串）
                    if project:
                        file_projects = metadata.get("project", [])
                        if isinstance(file_projects, str):
                            file_projects = [file_projects]
                        if project not in file_projects:
                            continue

                    # Tags过滤
                    if tags:
                        file_tags = metadata.get("tags", [])
                        if not isinstance(file_tags, list):
                            file_tags = [file_tags]
                        if not any(tag in file_tags for tag in tags):
                            continue

                    # Mood过滤
                    if mood:
                        file_moods = metadata.get("mood", [])
                        if isinstance(file_moods, str):
                            file_moods = [file_moods]
                        if not isinstance(file_moods, list):
                            file_moods = []
                        if not any(m in file_moods for m in mood):
                            continue

                    # People过滤
                    if people:
                        file_people = metadata.get("people", [])
                        if isinstance(file_people, str):
                            file_people = [file_people]
                        if not isinstance(file_people, list):
                            file_people = []
                        if not any(p in file_people for p in people):
                            continue

                    # Query 过滤：当指定 query 时，要求元数据包含该关键词
                    if query:
                        query_lower = query.lower()
                        title = metadata.get("title", "").lower()
                        abstract = (
                            metadata.get("abstract", "").lower()
                            if isinstance(metadata.get("abstract"), str)
                            else ""
                        )
                        file_tags = metadata.get("tags", [])
                        tags_str = (
                            " ".join(file_tags).lower()
                            if isinstance(file_tags, list)
                            else str(file_tags).lower()
                        )

                        # 检查 title/abstract/tags 是否包含 query
                        if (
                            query_lower not in title
                            and query_lower not in abstract
                            and query_lower not in tags_str
                        ):
                            continue  # 元数据不匹配，跳过

                    # 匹配成功
                    try:
                        rel_path = os.path.relpath(journal_file, USER_DATA_DIR).replace(
                            "\\", "/"
                        )
                    except ValueError:
                        rel_path = str(journal_file).replace("\\", "/")

                    results.append(
                        {
                            "date": file_date,
                            "title": metadata.get("title", "无标题"),
                            "path": str(journal_file),
                            "rel_path": rel_path,
                            "metadata": metadata,
                            "source": "metadata_scan",
                        }
                    )

                except Exception as e:
                    continue

    return results
