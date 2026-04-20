#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - L3 Content
三级内容搜索模块（全文搜索）
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

# 导入配置 (relative imports from tools/lib)
from ..lib.paths import get_user_data_dir, get_journals_dir
from ..lib.path_contract import build_journal_path_fields

from .utils import parse_frontmatter

# Deprecated aliases — kept for monkeypatch compatibility (Round 13 lesson)
USER_DATA_DIR = get_user_data_dir()
JOURNALS_DIR = get_journals_dir()


def _compute_fallback_relevance(title_match: bool, body_match_count: int) -> int:
    """Estimate fallback search relevance conservatively for file-scan results."""
    score = 0
    if title_match:
        score += 40
    score += min(body_match_count, 3) * 10
    return min(score, 80)


def search_l3_content(query: str, paths: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    L3: 内容层搜索 - 全文检索

    Args:
        query: 搜索关键词
        paths: 限定搜索范围（如果为None则搜索全部）
    """
    results = []
    query_lower = query.lower()

    if paths:
        files_to_search = [Path(p) for p in paths if Path(p).exists()]
    else:
        files_to_search = []
        _journals_dir = get_journals_dir()
        if _journals_dir.exists():
            for year_dir in _journals_dir.iterdir():
                if year_dir.is_dir() and year_dir.name.isdigit():
                    for month_dir in year_dir.iterdir():
                        if month_dir.is_dir():
                            files_to_search.extend(month_dir.glob("*.md"))

    for journal_file in files_to_search:
        try:
            content = journal_file.read_text(encoding="utf-8")
            metadata, body = parse_frontmatter(content)

            # 在标题中搜索
            title_match = False
            title = metadata.get("title", "")
            if query_lower in title.lower():
                title_match = True

            # 在正文中搜索
            body_matches = []
            lines = body.split("\n")
            for i, line in enumerate(lines, 1):
                if query_lower in line.lower():
                    # 提取上下文
                    start = max(0, i - 2)
                    end = min(len(lines), i + 1)
                    context = "\n".join(lines[start:end])
                    body_matches.append({"line": i, "context": context.strip()})

            relevance = _compute_fallback_relevance(title_match, len(body_matches))

            if relevance >= 15:
                path_fields = build_journal_path_fields(
                    journal_file,
                    journals_dir=get_journals_dir(),
                    user_data_dir=get_user_data_dir(),
                )

                results.append(
                    {
                        "date": metadata.get("date", "")[:10],
                        "title": title or "无标题",
                        **path_fields,
                        "title_match": title_match,
                        "body_matches": body_matches,
                        "match_count": len(body_matches) + (1 if title_match else 0),
                        "relevance": relevance,
                        "source": "content_search",
                        # 补充元数据字段
                        "location": metadata.get("location", ""),
                        "weather": metadata.get("weather", ""),
                        "mood": metadata.get("mood", []),
                        "people": metadata.get("people", []),
                        "tags": metadata.get("tags", []),
                        "topic": metadata.get("topic", []),
                        "abstract": metadata.get("abstract", ""),
                        "project": metadata.get("project", ""),
                        # 保留完整的 metadata 供后续使用
                        "metadata": metadata,
                    }
                )

        except (OSError, IOError):
            continue

    # 按匹配度排序
    results.sort(key=lambda x: x["match_count"], reverse=True)

    return results
