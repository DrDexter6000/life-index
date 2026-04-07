#!/usr/bin/env python3
"""Life Index index generation utilities."""

import calendar
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from ..lib.config import JOURNALS_DIR, USER_DATA_DIR
from ..lib.errors import ErrorCode, create_error_response
from ..lib.frontmatter import parse_journal_file
from ..lib.logger import get_logger

logger = get_logger(__name__)


def parse_frontmatter(file_path: Path) -> Dict[str, Any]:
    """Parse journal frontmatter via shared SSOT parser."""
    result = parse_journal_file(file_path)
    if "_error" in result:
        return {}
    return result


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    return []


def _frontmatter_names(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key in value.keys()]
    return [str(item) for item in _ensure_list(value) if item]


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _frontmatter_value(value: Any) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, dict):
        items = ", ".join(f"{key}: {value[key]}" for key in value)
        return f"{{{items}}}"
    if isinstance(value, list):
        return f"[{', '.join(str(item) for item in value)}]"
    return str(value)


def _build_frontmatter(data: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in data.items():
        lines.append(f"{key}: {_frontmatter_value(value)}")
    lines.append("---")
    return "\n".join(lines)


def _extract_date_prefix(date_value: Any) -> str:
    if isinstance(date_value, str) and len(date_value) >= 10:
        return date_value[:10]
    return ""


def _relative_link(path_value: str) -> str:
    return path_value[2:] if path_value.startswith("./") else path_value


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _aggregate_counts(journals: list[Dict[str, Any]], field: str) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for journal in journals:
        counter.update(str(item) for item in _ensure_list(journal.get(field)) if item)
    return dict(counter.most_common())


def _aggregate_scalar_counts(
    journals: list[Dict[str, Any]], field: str
) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for journal in journals:
        value = journal.get(field)
        if isinstance(value, str) and value:
            counter.update([value])
    return dict(counter.most_common())


def _aggregate_unique(journals: list[Dict[str, Any]], field: str) -> list[str]:
    values: list[str] = []
    for journal in journals:
        values.extend(str(item) for item in _ensure_list(journal.get(field)) if item)
    return _unique_preserve_order(values)


def _aggregate_scalar_unique(journals: list[Dict[str, Any]], field: str) -> list[str]:
    values = [str(journal.get(field)) for journal in journals if journal.get(field)]
    return _unique_preserve_order(values)


def _aggregate_month_metadata(
    year: int, month: int, journals: list[Dict[str, Any]]
) -> Dict[str, Any]:
    return {
        "year": year,
        "month": month,
        "entries": len(journals),
        "topics": _aggregate_counts(journals, "topic"),
        "moods": _aggregate_counts(journals, "mood"),
        "locations": _aggregate_scalar_unique(journals, "location"),
        "people": _aggregate_unique(journals, "people"),
        "notable_tags": _aggregate_unique(journals, "tags"),
        "date_range": f"{year}-{month:02d}-01 — {year}-{month:02d}-{_last_day(year, month):02d}",
    }


def _month_row(journal: Dict[str, Any]) -> str:
    date_text = _extract_date_prefix(journal.get("date"))
    day = date_text[5:] if date_text else "--"
    title = journal.get("title") or journal.get("file") or "未命名"
    link = _relative_link(journal.get("path", ""))
    topics = ", ".join(str(item) for item in _ensure_list(journal.get("topic"))) or "—"
    moods = ", ".join(str(item) for item in _ensure_list(journal.get("mood"))) or "—"
    location = str(journal.get("location") or "—")
    people = ", ".join(str(item) for item in _ensure_list(journal.get("people"))) or "—"
    return f"| {day} | [{title}]({link}) | {topics} | {moods} | {location} | {people} |"


def _parse_index_frontmatter(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        return {}
    return parse_frontmatter(file_path) or {}


def _read_month_summary(
    year: int, month_dir: Path
) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    month = month_dir.name
    index_path = month_dir / f"index_{year}-{month}.md"
    metadata = _parse_index_frontmatter(index_path)
    if metadata:
        summary = {
            "month": month,
            "entries": int(metadata.get("entries", 0) or 0),
            "moods": _frontmatter_names(metadata.get("moods")),
            "locations": _frontmatter_names(metadata.get("locations")),
            "notable_tags": _frontmatter_names(metadata.get("notable_tags")),
            "relative_path": f"{month}/index_{year}-{month}.md",
        }
        return [], summary

    journals = []
    for journal_file in sorted(month_dir.glob("life-index_*.md")):
        metadata = parse_frontmatter(journal_file)
        if metadata:
            journals.append(
                {
                    "file": journal_file.name,
                    "path": f"./{month}/{journal_file.name}",
                    "month": month,
                    "date": metadata.get("date", ""),
                    "title": metadata.get("title", journal_file.stem),
                    "tags": _ensure_list(metadata.get("tags")),
                    "project": metadata.get("project", ""),
                    "topic": _ensure_list(metadata.get("topic")),
                    "mood": _ensure_list(metadata.get("mood")),
                    "people": _ensure_list(metadata.get("people")),
                    "location": metadata.get("location", ""),
                    "abstract": metadata.get("abstract", ""),
                }
            )
    summary = {
        "month": month,
        "entries": len(journals),
        "moods": list(_aggregate_counts(journals, "mood").keys()),
        "locations": _aggregate_scalar_unique(journals, "location"),
        "notable_tags": _aggregate_unique(journals, "tags"),
        "relative_path": f"{month}/index_{year}-{month}.md",
    }
    return journals, summary


def _read_year_summary(year_dir: Path) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    year = int(year_dir.name)
    index_path = year_dir / f"index_{year}.md"
    metadata = _parse_index_frontmatter(index_path)
    if metadata:
        summary = {
            "year": year,
            "entries": int(metadata.get("entries", 0) or 0),
            "locations": _frontmatter_names(metadata.get("locations")),
            "topics": _frontmatter_names(metadata.get("topics")),
            "relative_path": f"Journals/{year}/index_{year}.md",
        }
        return [], summary

    journals = collect_year_journals(year)
    summary = {
        "year": year,
        "entries": len(journals),
        "locations": _aggregate_scalar_unique(journals, "location"),
        "topics": list(_aggregate_counts(journals, "topic").keys()),
        "relative_path": f"Journals/{year}/index_{year}.md",
    }
    return journals, summary


def _count_topic_entries(topic_name: str) -> int:
    count = 0
    for year_dir in sorted(JOURNALS_DIR.iterdir()) if JOURNALS_DIR.exists() else []:
        if not year_dir.is_dir():
            continue
        year = int(year_dir.name)
        journals = collect_year_journals(year)
        for journal in journals:
            if topic_name in {str(item) for item in _ensure_list(journal.get("topic"))}:
                count += 1
    return count


def collect_month_journals(year: int, month: int) -> list[Dict[str, Any]]:
    """Collect all journals in a given month."""
    journals: list[Dict[str, Any]] = []
    month_dir = JOURNALS_DIR / str(year) / f"{month:02d}"

    if not month_dir.exists():
        logger.debug(f"目录不存在：{month_dir}")
        return journals

    for journal_file in sorted(month_dir.glob("life-index_*.md")):
        metadata = parse_frontmatter(journal_file)
        if metadata:
            journals.append(
                {
                    "file": journal_file.name,
                    "path": f"./{journal_file.name}",
                    "date": metadata.get("date", ""),
                    "title": metadata.get("title", journal_file.stem),
                    "tags": _ensure_list(metadata.get("tags")),
                    "project": metadata.get("project", ""),
                    "topic": _ensure_list(metadata.get("topic")),
                    "mood": _ensure_list(metadata.get("mood")),
                    "people": _ensure_list(metadata.get("people")),
                    "location": metadata.get("location", ""),
                    "abstract": metadata.get("abstract", ""),
                }
            )

    return journals


def collect_year_journals(year: int) -> list[Dict[str, Any]]:
    """Collect all journals in a given year."""
    journals: list[Dict[str, Any]] = []
    year_dir = JOURNALS_DIR / str(year)

    if not year_dir.exists():
        logger.debug(f"目录不存在：{year_dir}")
        return journals

    for month_dir in sorted(year_dir.iterdir()):
        if not month_dir.is_dir() or not month_dir.name.isdigit():
            continue
        for journal_file in sorted(month_dir.glob("life-index_*.md")):
            metadata = parse_frontmatter(journal_file)
            if metadata:
                journals.append(
                    {
                        "file": journal_file.name,
                        "path": f"./{month_dir.name}/{journal_file.name}",
                        "month": month_dir.name,
                        "date": metadata.get("date", ""),
                        "title": metadata.get("title", journal_file.stem),
                        "tags": _ensure_list(metadata.get("tags")),
                        "project": metadata.get("project", ""),
                        "topic": _ensure_list(metadata.get("topic")),
                        "mood": _ensure_list(metadata.get("mood")),
                        "people": _ensure_list(metadata.get("people")),
                        "location": metadata.get("location", ""),
                        "abstract": metadata.get("abstract", ""),
                    }
                )

    return journals


def generate_monthly_index_content(
    year: int, month: int, journals: list[Dict[str, Any]]
) -> str:
    """Generate monthly index markdown."""
    metadata = _aggregate_month_metadata(year, month, journals)
    lines = [
        _build_frontmatter(metadata),
        "",
        f"# {year}-{month:02d} 月度索引",
        "",
        "## 条目列表",
        "",
        "| 日期 | 标题 | 主题 | 情绪 | 地点 | 人物 |",
        "|------|------|------|------|------|------|",
    ]

    for journal in sorted(journals, key=lambda item: str(item.get("date", ""))):
        lines.append(_month_row(journal))

    if not journals:
        lines.append("| — | — | — | — | — | — |")

    lines.extend(
        [
            "",
            "## 月度回顾",
            "",
            "> *(由月度报告填写——`generate_index` 不生成此段)*",
            "",
            "---",
            f"*Total: {len(journals)} entries · "
            f"Last updated: {datetime.now().strftime('%Y-%m-%d')}*",
        ]
    )
    return "\n".join(lines)


def generate_yearly_index_content(
    year: int,
    journals: list[Dict[str, Any]],
    monthly_summaries: list[Dict[str, Any]],
    total_entries: Optional[int] = None,
) -> str:
    """Generate yearly index markdown."""
    entry_total = total_entries if total_entries is not None else len(journals)
    metadata = {
        "year": year,
        "entries": entry_total,
        "topics": _aggregate_counts(journals, "topic"),
        "moods": _aggregate_counts(journals, "mood"),
        "locations": _aggregate_scalar_unique(journals, "location"),
        "people": _aggregate_unique(journals, "people"),
        "notable_tags": _aggregate_unique(journals, "tags"),
    }
    lines = [
        _build_frontmatter(metadata),
        "",
        f"# {year} 年度索引",
        "",
        "## 月度总览",
        "",
        "| 月份 | 条目 | 全部情绪 | 全部地点 | 全部标签 |",
        "|------|------|---------|---------|---------|",
    ]

    for summary in sorted(monthly_summaries, key=lambda item: item["month"]):
        month = summary["month"]
        moods = ", ".join(summary.get("moods", [])) or "—"
        locations = ", ".join(summary.get("locations", [])) or "—"
        tags = ", ".join(summary.get("notable_tags", [])) or "—"
        lines.append(
            f"| [{month}]({summary['relative_path']}) "
            f"| {summary['entries']} | {moods} | {locations} | {tags} |"
        )

    if not monthly_summaries:
        lines.append("| — | 0 | — | — | — |")

    lines.extend(
        [
            "",
            "## 年度回顾",
            "",
            "> *(由年度报告填写——`generate_index` 不生成此段)*",
            "",
            "---",
            f"*Total: {entry_total} entries*",
        ]
    )
    return "\n".join(lines)


def generate_root_index_content(
    *,
    yearly_summaries: list[Dict[str, Any]],
    topic_summaries: list[Dict[str, Any]],
    total_entries: int,
    date_range: str,
) -> str:
    """Generate root INDEX markdown."""
    lines = [
        _build_frontmatter({"total_entries": total_entries, "date_range": date_range}),
        "",
        "# Life Index",
        "",
        "> 个人人生日志系统 · 始于 2025",
        "",
        "## 日志总览",
        "",
        "| 年份 | 条目 | 全部地点 | 全部主题 |",
        "|------|------|---------|---------|",
    ]
    for summary in sorted(
        yearly_summaries, key=lambda item: item["year"], reverse=True
    ):
        locations = ", ".join(summary.get("locations", [])) or "—"
        topics = ", ".join(summary.get("topics", [])) or "—"
        lines.append(
            f"| [{summary['year']}]({summary['relative_path']}) "
            f"| {summary['entries']} | {locations} | {topics} |"
        )

    lines.extend(["", "## 主题维度", ""])
    for topic in sorted(topic_summaries, key=lambda item: item["name"]):
        lines.append(
            f"- [{topic['file']}](by-topic/{topic['file']}) · {topic['name']} · ({topic['count']})"
        )

    lines.extend(
        [
            "",
            "---",
            f"*Last updated: {datetime.now().strftime('%Y-%m-%d')} "
            f"· Total entries: {total_entries}*",
        ]
    )
    return "\n".join(lines)


def generate_monthly_index(
    year: int, month: int, dry_run: bool = False
) -> Dict[str, Any]:
    """Generate monthly index file."""
    result: Dict[str, Any] = {
        "success": False,
        "type": "monthly",
        "year": year,
        "month": month,
        "output_path": None,
        "journal_count": 0,
        "updated": False,
        "error": None,
    }

    try:
        month_dir = JOURNALS_DIR / str(year) / f"{month:02d}"
        output_path = month_dir / f"index_{year}-{month:02d}.md"
        journals = collect_month_journals(year, month)
        result["journal_count"] = len(journals)

        if not journals:
            result["success"] = True
            result["message"] = f"{year}年{month:02d}月没有日志记录"
            return result

        content = generate_monthly_index_content(year, month, journals)
        result["output_path"] = str(output_path)

        if dry_run:
            result["success"] = True
            result["message"] = f"[预览] 将生成月度索引：{output_path}"
            return result

        month_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        result["updated"] = True
        result["success"] = True
        result["message"] = f"月度索引已保存：{output_path}"
    except (IOError, OSError) as e:
        logger.error(f"写入月度索引失败：{e}")
        return create_error_response(
            ErrorCode.WRITE_FAILED,
            f"写入月度索引失败：{e}",
            {"year": year, "month": month},
            "请检查目录权限或磁盘空间",
        )

    return result


def generate_yearly_index(year: int, dry_run: bool = False) -> Dict[str, Any]:
    """Generate yearly index file."""
    result: Dict[str, Any] = {
        "success": False,
        "type": "yearly",
        "year": year,
        "output_path": None,
        "journal_count": 0,
        "updated": False,
        "error": None,
    }

    try:
        year_dir = JOURNALS_DIR / str(year)
        output_path = year_dir / f"index_{year}.md"
        journals: list[Dict[str, Any]] = []
        monthly_summaries: list[Dict[str, Any]] = []

        if year_dir.exists():
            for month_dir in sorted(year_dir.iterdir()):
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue
                fallback_journals, summary = _read_month_summary(year, month_dir)
                journals.extend(fallback_journals)
                monthly_summaries.append(summary)

        result["journal_count"] = sum(
            summary["entries"] for summary in monthly_summaries
        )

        if result["journal_count"] == 0:
            result["success"] = True
            result["message"] = f"{year}年没有日志记录"
            return result

        content = generate_yearly_index_content(
            year, journals, monthly_summaries, total_entries=result["journal_count"]
        )
        result["output_path"] = str(output_path)

        if dry_run:
            result["success"] = True
            result["message"] = f"[预览] 将生成年度索引：{output_path}"
            return result

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        result["updated"] = True
        result["success"] = True
        result["message"] = f"年度索引已保存：{output_path}"
    except (IOError, OSError) as e:
        logger.error(f"写入年度索引失败：{e}")
        return create_error_response(
            ErrorCode.WRITE_FAILED,
            f"写入年度索引失败：{e}",
            {"year": year},
            "请检查目录权限或磁盘空间",
        )

    return result


def generate_root_index(dry_run: bool = False) -> Dict[str, Any]:
    """Generate root INDEX.md file."""
    result: Dict[str, Any] = {
        "success": False,
        "type": "root",
        "output_path": None,
        "journal_count": 0,
        "updated": False,
        "error": None,
    }

    try:
        output_path = USER_DATA_DIR / "INDEX.md"
        yearly_summaries: list[Dict[str, Any]] = []
        fallback_journals: list[Dict[str, Any]] = []

        if JOURNALS_DIR.exists():
            for year_dir in sorted(JOURNALS_DIR.iterdir(), reverse=True):
                if not year_dir.is_dir() or not year_dir.name.isdigit():
                    continue
                journals, summary = _read_year_summary(year_dir)
                fallback_journals.extend(journals)
                yearly_summaries.append(summary)

        total_entries = sum(summary["entries"] for summary in yearly_summaries)
        result["journal_count"] = total_entries
        if total_entries == 0:
            result["success"] = True
            result["message"] = "没有日志记录"
            return result

        years = sorted((summary["year"] for summary in yearly_summaries))
        date_range = f"{years[0]}-01 — {years[-1]}-12"
        if years:
            latest_year = years[-1]
            latest_year_dir = JOURNALS_DIR / str(latest_year)
            month_names = (
                sorted(
                    month_dir.name
                    for month_dir in latest_year_dir.iterdir()
                    if month_dir.is_dir() and month_dir.name.isdigit()
                )
                if latest_year_dir.exists()
                else []
            )
            if month_names:
                date_range = f"{years[0]}-01 — {latest_year}-{month_names[-1]}"

        by_topic_dir = USER_DATA_DIR / "by-topic"
        topic_summaries: list[Dict[str, Any]] = []
        if by_topic_dir.exists():
            for topic_file in sorted(by_topic_dir.glob("主题_*.md")):
                topic_name = topic_file.stem.replace("主题_", "")
                count = _count_topic_entries(topic_name)
                topic_summaries.append(
                    {"name": topic_name, "file": topic_file.name, "count": count}
                )

        content = generate_root_index_content(
            yearly_summaries=yearly_summaries,
            topic_summaries=topic_summaries,
            total_entries=total_entries,
            date_range=date_range,
        )
        result["output_path"] = str(output_path)

        if dry_run:
            result["success"] = True
            result["message"] = f"[预览] 将生成根索引：{output_path}"
            return result

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        result["updated"] = True
        result["success"] = True
        result["message"] = f"根索引已保存：{output_path}"
    except (IOError, OSError) as e:
        logger.error(f"写入根索引失败：{e}")
        return create_error_response(
            ErrorCode.WRITE_FAILED,
            f"写入根索引失败：{e}",
            {},
            "请检查目录权限或磁盘空间",
        )

    return result


def rebuild_index_tree(dry_run: bool = False) -> Dict[str, Any]:
    """Rebuild monthly, yearly, and root indexes from journal files."""
    report: Dict[str, Any] = {
        "monthly_indexes_rebuilt": 0,
        "yearly_indexes_rebuilt": 0,
        "root_index_rebuilt": False,
        "errors": [],
    }

    if not JOURNALS_DIR.exists():
        root_result = generate_root_index(dry_run=dry_run)
        report["root_index_rebuilt"] = bool(root_result.get("success"))
        if not root_result.get("success"):
            report["errors"].append(root_result)
        return report

    years_with_journals: set[int] = set()

    for year_dir in sorted(JOURNALS_DIR.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue

        year = int(year_dir.name)
        year_has_journals = False
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue

            month = int(month_dir.name)
            if not any(month_dir.glob("life-index_*.md")):
                continue

            year_has_journals = True
            monthly_result = generate_monthly_index(year, month, dry_run=dry_run)
            if monthly_result.get("success"):
                report["monthly_indexes_rebuilt"] += 1
            else:
                report["errors"].append(monthly_result)

        if year_has_journals:
            years_with_journals.add(year)

    for year in sorted(years_with_journals):
        yearly_result = generate_yearly_index(year, dry_run=dry_run)
        if yearly_result.get("success"):
            report["yearly_indexes_rebuilt"] += 1
        else:
            report["errors"].append(yearly_result)

    root_result = generate_root_index(dry_run=dry_run)
    report["root_index_rebuilt"] = bool(root_result.get("success"))
    if not root_result.get("success"):
        report["errors"].append(root_result)

    return report


generate_monthly_abstract_content = generate_monthly_index_content
generate_yearly_abstract_content = generate_yearly_index_content
generate_monthly_abstract = generate_monthly_index
generate_yearly_abstract = generate_yearly_index


__all__ = [
    "parse_frontmatter",
    "collect_month_journals",
    "collect_year_journals",
    "generate_monthly_index_content",
    "generate_yearly_index_content",
    "generate_root_index_content",
    "generate_monthly_index",
    "generate_yearly_index",
    "generate_root_index",
    "rebuild_index_tree",
    "generate_monthly_abstract_content",
    "generate_yearly_abstract_content",
    "generate_monthly_abstract",
    "generate_yearly_abstract",
]
