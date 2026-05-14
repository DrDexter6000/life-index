#!/usr/bin/env python3
"""Internal read-only Index Tree node enumeration for Life Index.

Provides IndexNode dataclass and enumerate_index_nodes() helper for navigating
the existing root/year/month Index Tree. This is an internal helper, not a
public CLI/API contract.
"""

from __future__ import annotations

import datetime
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

from ..lib.frontmatter import parse_frontmatter
from ..lib.paths import get_journals_dir, get_user_data_dir
from . import _aggregate_counts


@dataclass(frozen=True)
class IndexNode:
    node_id: str
    level: str
    path: Path
    relative_path: str
    year: Optional[int]
    month: Optional[int]
    entry_count: int
    topics: Dict[str, int]
    date_range: str
    has_index: bool
    freshness: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["path"] = str(self.path)
        return d


_VALID_LEVELS = {"root", "year", "month", "all"}


def build_month_node_ref(year_str: str, month_str: str) -> Optional[Dict[str, str]]:
    try:
        if len(year_str) != 4:
            return None
        year_int = int(year_str)
        month_int = int(month_str)
        if not (1 <= month_int <= 12):
            return None
    except (ValueError, IndexError):
        return None
    year = f"{year_int:04d}"
    month = f"{month_int:02d}"
    return {
        "type": "month",
        "node_id": f"month:{year}-{month}",
        "id": f"Journals/{year}/{month}",
        "path": f"Journals/{year}/{month}/index_{year}-{month}.md",
    }


def _parse_index_frontmatter(file_path: Path) -> dict:
    return _parse_file_frontmatter(file_path)


def _parse_file_frontmatter(file_path: Path) -> dict:
    if not file_path.exists():
        return {}
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            if handle.readline().strip() != "---":
                return {}
            lines: list[str] = []
            for line in handle:
                if line.strip() == "---":
                    metadata, _ = parse_frontmatter("---\n" + "".join(lines) + "---\n")
                    return metadata
                lines.append(line)
    except (OSError, UnicodeDecodeError):
        return {}
    return {}


def _collect_month_journals_from_dir(month_dir: Path) -> list[dict]:
    journals = []
    for journal_file in sorted(month_dir.glob("life-index_*.md")):
        metadata = _parse_file_frontmatter(journal_file)
        if metadata:
            journals.append(metadata)
    return journals


def _collect_year_journals_from_dir(year_dir: Path) -> list[dict]:
    journals = []
    for month_dir in sorted(year_dir.iterdir()):
        if not month_dir.is_dir() or not month_dir.name.isdigit():
            continue
        for journal_file in sorted(month_dir.glob("life-index_*.md")):
            metadata = _parse_file_frontmatter(journal_file)
            if metadata:
                journals.append(metadata)
    return journals


def _max_journal_mtime(scope_dir: Path) -> Optional[float]:
    max_mtime: Optional[float] = None
    for journal_file in scope_dir.rglob("life-index_*.md"):
        try:
            mtime = journal_file.stat().st_mtime
            if max_mtime is None or mtime > max_mtime:
                max_mtime = mtime
        except OSError:
            continue
    return max_mtime


def _compute_freshness(
    index_path: Path,
    scope_dir: Path,
    entry_count: int,
) -> str:
    if entry_count == 0:
        return "empty"
    if not index_path.exists():
        return "missing_index"
    try:
        idx_mtime = index_path.stat().st_mtime
    except OSError:
        return "missing_index"
    max_j = _max_journal_mtime(scope_dir)
    if max_j is not None and max_j > idx_mtime:
        return "stale"
    return "fresh"


def _build_root_node() -> IndexNode:
    user_data_dir = get_user_data_dir()
    journals_dir = get_journals_dir()
    index_path = user_data_dir / "INDEX.md"

    fm = _parse_index_frontmatter(index_path)
    if fm:
        entry_count = int(fm.get("total_entries", 0) or 0)
        date_range = str(fm.get("date_range", ""))
        has_index = True
    else:
        all_journals = []
        if journals_dir.exists():
            for year_dir in sorted(journals_dir.iterdir()):
                if year_dir.is_dir() and year_dir.name.isdigit():
                    all_journals.extend(_collect_year_journals_from_dir(year_dir))
        entry_count = len(all_journals)
        date_range = ""
        has_index = False

    freshness = _compute_freshness(index_path, journals_dir, entry_count)

    return IndexNode(
        node_id="root",
        level="root",
        path=index_path,
        relative_path="INDEX.md",
        year=None,
        month=None,
        entry_count=entry_count,
        topics={},
        date_range=date_range,
        has_index=has_index,
        freshness=freshness,
    )


def _build_year_nodes() -> list[IndexNode]:
    journals_dir = get_journals_dir()
    if not journals_dir.exists():
        return []

    nodes: list[IndexNode] = []
    for year_dir in sorted(journals_dir.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        year = int(year_dir.name)
        index_path = year_dir / f"index_{year}.md"

        fm = _parse_index_frontmatter(index_path)
        if fm:
            entry_count = int(fm.get("entries", 0) or 0)
            topics_raw = fm.get("topics", {})
            topics = (
                {str(k): int(v) for k, v in topics_raw.items()}
                if isinstance(topics_raw, dict)
                else {}
            )
            has_index = True
        else:
            journals = _collect_year_journals_from_dir(year_dir)
            entry_count = len(journals)
            topics = _aggregate_counts(journals, "topic")
            has_index = False

        if entry_count == 0:
            continue

        freshness = _compute_freshness(index_path, year_dir, entry_count)

        nodes.append(
            IndexNode(
                node_id=f"year:{year}",
                level="year",
                path=index_path,
                relative_path=f"Journals/{year}/index_{year}.md",
                year=year,
                month=None,
                entry_count=entry_count,
                topics=topics,
                date_range="",
                has_index=has_index,
                freshness=freshness,
            )
        )
    return nodes


def _build_month_nodes() -> list[IndexNode]:
    journals_dir = get_journals_dir()
    if not journals_dir.exists():
        return []

    nodes: list[IndexNode] = []
    for year_dir in sorted(journals_dir.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        year = int(year_dir.name)
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
            month = int(month_dir.name)
            index_path = month_dir / f"index_{year}-{month:02d}.md"

            fm = _parse_index_frontmatter(index_path)
            if fm:
                entry_count = int(fm.get("entries", 0) or 0)
                topics_raw = fm.get("topics", {})
                topics = (
                    {str(k): int(v) for k, v in topics_raw.items()}
                    if isinstance(topics_raw, dict)
                    else {}
                )
                date_range = str(fm.get("date_range", ""))
                has_index = True
            else:
                journals = _collect_month_journals_from_dir(month_dir)
                entry_count = len(journals)
                topics = _aggregate_counts(journals, "topic")
                date_range = f"{year}-{month:02d}"
                has_index = False

            if entry_count == 0:
                continue

            freshness = _compute_freshness(index_path, month_dir, entry_count)

            nodes.append(
                IndexNode(
                    node_id=f"month:{year}-{month:02d}",
                    level="month",
                    path=index_path,
                    relative_path=f"Journals/{year}/{month:02d}/index_{year}-{month:02d}.md",
                    year=year,
                    month=month,
                    entry_count=entry_count,
                    topics=topics,
                    date_range=date_range,
                    has_index=has_index,
                    freshness=freshness,
                )
            )
    return nodes


def enumerate_index_nodes(level: str = "all") -> list[IndexNode]:
    if level not in _VALID_LEVELS:
        raise ValueError(f"level must be one of {sorted(_VALID_LEVELS)}, got '{level}'")

    if level == "root":
        return [_build_root_node()]
    if level == "year":
        return _build_year_nodes()
    if level == "month":
        return _build_month_nodes()
    nodes = [_build_root_node()]
    nodes.extend(_build_year_nodes())
    nodes.extend(_build_month_nodes())
    return nodes


def check_index_tree_freshness(level: str = "all") -> dict:
    nodes = enumerate_index_nodes(level=level)
    issues: list[dict] = []
    for node in nodes:
        if node.freshness in ("stale", "missing_index"):
            issues.append(
                {
                    "node_id": node.node_id,
                    "level": node.level,
                    "freshness": node.freshness,
                    "relative_path": node.relative_path,
                }
            )
    all_empty = all(n.freshness == "empty" for n in nodes)
    if all_empty:
        return {"status": "empty_tree", "total_nodes": len(nodes), "issues": issues}
    return {
        "status": "all_fresh" if not issues else "has_issues",
        "total_nodes": len(nodes),
        "issues": issues,
    }


def index_node_ref_for_date(date_str: str) -> Optional[Dict[str, str]]:
    if not date_str or len(date_str) < 7:
        return None
    try:
        year = date_str[:4]
        month = date_str[5:7]
        return build_month_node_ref(year, month)
    except (ValueError, IndexError):
        return None


def index_node_refs_for_range(
    since: Optional[str | datetime.date],
    until: Optional[str | datetime.date],
) -> list[Dict[str, str]]:
    if since is None or until is None:
        return []
    try:
        if isinstance(since, datetime.date):
            start = since
        else:
            start = datetime.date.fromisoformat(since)
        if isinstance(until, datetime.date):
            end = until
        else:
            end = datetime.date.fromisoformat(until)
    except (ValueError, TypeError):
        return []
    if end < start:
        return []
    refs: list[Dict[str, str]] = []
    cursor_year = start.year
    cursor_month = start.month
    while (cursor_year, cursor_month) <= (end.year, end.month):
        ref = build_month_node_ref(f"{cursor_year:04d}", f"{cursor_month:02d}")
        if ref is not None:
            refs.append(ref)
        cursor_month += 1
        if cursor_month > 12:
            cursor_month = 1
            cursor_year += 1
    return refs
