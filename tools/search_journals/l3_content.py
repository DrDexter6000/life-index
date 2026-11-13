#!/usr/bin/env python3
"""
Life Index - Search Journals Tool - L3 Content
三级内容搜索模块（全文搜索）
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

# 导入配置 (relative imports from tools/lib)
from ..lib.paths import get_user_data_dir, get_journals_dir
from ..lib.frontmatter import empty_indexable_metadata, normalize_indexable_metadata
from ..lib.journal_files import fragment_date_from_filename, iter_month_journal_files
from ..lib.path_contract import build_journal_path_fields
from ..lib.search_constants import (
    L3_TITLE_MATCH_BONUS,
    L3_BODY_MATCH_PER_HIT,
    L3_MAX_FALLBACK_SCORE,
    L3_MIN_FALLBACK_RELEVANCE,
)

from .utils import parse_frontmatter

# Deprecated aliases — kept for monkeypatch compatibility (Round 13 lesson)
USER_DATA_DIR = get_user_data_dir()
JOURNALS_DIR = get_journals_dir()


def _compute_fallback_relevance(title_match: bool, body_match_count: int) -> int:
    """Estimate fallback search relevance conservatively for file-scan results."""
    score = 0
    if title_match:
        score += L3_TITLE_MATCH_BONUS
    score += min(body_match_count, 3) * L3_BODY_MATCH_PER_HIT
    return min(score, L3_MAX_FALLBACK_SCORE)


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
                            files_to_search.extend(iter_month_journal_files(month_dir))

    for journal_file in files_to_search:
        try:
            # Bytes that are not UTF-8 are replaced, not fatal: the rest of the
            # file is still searchable text.
            content = journal_file.read_text(encoding="utf-8", errors="replace")
            metadata, body = parse_frontmatter(content)
            indexable = normalize_indexable_metadata(metadata)
            if indexable is None:
                # Same treatment as the fragment's FTS row: the whole file is
                # searchable text, no metadata, date from the filename.
                metadata, body = {}, content
                indexable = empty_indexable_metadata()
                indexable["date"] = fragment_date_from_filename(journal_file) or ""

            # 在标题中搜索
            title_match = False
            title = indexable["title"]
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

            if relevance >= L3_MIN_FALLBACK_RELEVANCE:
                path_fields = build_journal_path_fields(
                    journal_file,
                    journals_dir=get_journals_dir(),
                    user_data_dir=get_user_data_dir(),
                )

                results.append(
                    {
                        "date": indexable["date"][:10],
                        "title": title or "无标题",
                        **path_fields,
                        "title_match": title_match,
                        "body_matches": body_matches,
                        "match_count": len(body_matches) + (1 if title_match else 0),
                        "relevance": relevance,
                        "source": "content_search",
                        # 补充元数据字段
                        "location": indexable["location"],
                        "weather": indexable["weather"],
                        "mood": indexable["mood"],
                        "people": indexable["people"],
                        "tags": indexable["tags"],
                        "topic": indexable["topic"],
                        "abstract": indexable["abstract"],
                        "project": indexable["project"],
                        # 保留完整的 metadata 供后续使用
                        "metadata": metadata,
                    }
                )

        except (OSError, IOError):
            continue

    # 按匹配度排序
    results.sort(key=lambda x: x["match_count"], reverse=True)

    return results
