"""Built-in event detectors for piggyback event system."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from tools.lib.events import Event, EventSeverity, register_detector

logger = __import__("logging").getLogger(__name__)

NO_JOURNAL_THRESHOLD_DAYS = 7
ENTITY_AUDIT_THRESHOLD_DAYS = 30

_JOURNAL_PATTERN = __import__("re").compile(r"^life-index_\d{4}-\d{2}-\d{2}_\d+\.md$")


def check_no_journal_streak(context: dict) -> list[Event]:
    """Detect consecutive days without a journal entry."""
    journals_dir = context.get("journals_dir")
    if not journals_dir:
        return []
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return []

    # Find the most recent life-index_*.md by mtime
    newest_mtime = 0.0
    for md_file in journals_dir.rglob("*.md"):
        if not _JOURNAL_PATTERN.match(md_file.name):
            continue
        try:
            mtime = os.path.getmtime(md_file)
            if mtime > newest_mtime:
                newest_mtime = mtime
        except OSError:
            continue

    if newest_mtime == 0.0:
        return []

    days_since = (time.time() - newest_mtime) / 86400
    if days_since >= NO_JOURNAL_THRESHOLD_DAYS:
        return [
            Event(
                type="no_journal_streak",
                severity=EventSeverity.INFO,
                message=f"已连续{int(days_since)}天未记日志",
                data={"days": int(days_since)},
            )
        ]
    return []


def check_monthly_review_due(context: dict) -> list[Event]:
    """Detect months that have journals but no report file."""
    journals_dir = context.get("journals_dir")
    if not journals_dir:
        return []
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return []

    events: list[Event] = []
    now = datetime.now()

    # Check last 3 months
    for offset in range(1, 4):
        check_date = now - timedelta(days=offset * 30)
        year = check_date.year
        month = check_date.month
        month_dir = journals_dir / f"{year}" / f"{month:02d}"

        if not month_dir.exists():
            continue

        # Check if there are any journal files in this month
        has_journals = any(
            _JOURNAL_PATTERN.match(f.name) for f in month_dir.iterdir() if f.is_file()
        )
        if not has_journals:
            continue

        report_path = month_dir / f"report_{year}-{month:02d}.md"
        if not report_path.exists():
            month_str = f"{year}-{month:02d}"
            events.append(
                Event(
                    type="monthly_review_due",
                    severity=EventSeverity.INFO,
                    message=f"{check_date.year}年{check_date.month}月月度回顾尚未生成",
                    data={"month": month_str},
                )
            )

    return events


def check_entity_audit_due(context: dict) -> list[Event]:
    """Detect if entity_graph.yaml hasn't been modified in a long time."""
    data_dir = context.get("data_dir")
    if not data_dir:
        return []
    graph_path = Path(data_dir) / "entity_graph.yaml"
    if not graph_path.exists():
        return []

    try:
        mtime = os.path.getmtime(graph_path)
    except OSError:
        return []

    days_since = (time.time() - mtime) / 86400
    if days_since > ENTITY_AUDIT_THRESHOLD_DAYS:
        return [
            Event(
                type="entity_audit_due",
                severity=EventSeverity.LOW,
                message=f"Entity graph 已 {int(days_since)} 天未审计",
                data={
                    "days_since_last_audit": int(days_since),
                    "suggested_command": "life-index entity --audit",
                },
            )
        ]
    return []


def check_schema_migration_available(context: dict) -> list[Event]:
    """Detect journals with old schema version (lightweight check).

    Only checks the first few files in recent month dirs — avoids full scan.
    """
    journals_dir = context.get("journals_dir")
    if not journals_dir:
        return []
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return []

    from tools.lib.schema import SCHEMA_VERSION

    # Lightweight: check first 5 files in up to 3 most recent month dirs
    count = 0
    checked = 0
    for md_file in sorted(journals_dir.rglob("*.md"), reverse=True):
        if not _JOURNAL_PATTERN.match(md_file.name):
            continue
        if checked >= 10:
            break
        checked += 1
        try:
            content = md_file.read_text(encoding="utf-8")
            # Quick frontmatter scan — avoid full YAML parse
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    fm = content[3:end]
                    for line in fm.splitlines():
                        if line.strip().startswith("schema_version:"):
                            val = line.split(":", 1)[1].strip()
                            try:
                                if int(float(val)) < SCHEMA_VERSION:
                                    count += 1
                            except (ValueError, TypeError):
                                pass
                            break
        except Exception:
            continue

    if count > 0:
        return [
            Event(
                type="schema_migration_available",
                severity=EventSeverity.INFO,
                message=f"发现 {count} 篇旧格式日志，可运行 life-index migrate --apply",
                data={"outdated_count": count},
            )
        ]
    return []


def check_index_stale(context: dict) -> list[Event]:
    """Detect if journal files are newer than the search index."""
    data_dir = context.get("data_dir")
    journals_dir = context.get("journals_dir")
    if not data_dir or not journals_dir:
        return []

    data_dir = Path(data_dir)
    journals_dir = Path(journals_dir)

    fts_db = data_dir / ".index" / "journals_fts.db"
    if not fts_db.exists():
        return []

    try:
        index_mtime = os.path.getmtime(fts_db)
    except OSError:
        return []

    # Find newest journal file
    newest_journal_mtime = 0.0
    if journals_dir.exists():
        for md_file in journals_dir.rglob("*.md"):
            if not _JOURNAL_PATTERN.match(md_file.name):
                continue
            try:
                mtime = os.path.getmtime(md_file)
                if mtime > newest_journal_mtime:
                    newest_journal_mtime = mtime
            except OSError:
                continue

    if newest_journal_mtime > index_mtime:
        return [
            Event(
                type="index_stale",
                severity=EventSeverity.LOW,
                message="索引可能已过时，建议运行 life-index index",
            )
        ]
    return []


def register_all_detectors() -> None:
    """Register all built-in detectors into the global registry."""
    register_detector("no_journal_streak", check_no_journal_streak)
    register_detector("monthly_review_due", check_monthly_review_due)
    register_detector("entity_audit_due", check_entity_audit_due)
    register_detector("schema_migration_available", check_schema_migration_available)
    register_detector("index_stale", check_index_stale)
