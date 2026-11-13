"""Built-in event detectors for piggyback event system."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from tools.lib.events import Event, EventSeverity, register_detector
from tools.lib.frontmatter import parse_frontmatter
from tools.lib.journal_files import JournalFileStat, scan_journal_files

logger = __import__("logging").getLogger(__name__)

NO_JOURNAL_THRESHOLD_DAYS = 7
ENTITY_AUDIT_THRESHOLD_DAYS = 30
ENTITY_PROFILES_COMMAND = "life-index abstract --entities"
DERIVED_ENTITY_PROFILES_NOTE = (
    "Writes derived Entities/ profile docs only; entity_graph.yaml is not modified."
)
DERIVED_INDEX_NOTE = "Writes derived index artifacts only; source journals are not modified."
ENTITY_AUDIT_READ_NOTE = "Read-only entity audit/review/check command."

_JOURNAL_FILE_STAT_SCAN_KEY = "_journal_file_stat_scan"


def _fragment_stats(context: dict) -> list[JournalFileStat]:
    """Return this call's fragment stat scan, computing it on first use.

    ``EventRegistry.detect_all`` hands every detector the same per-call context
    copy, so the Journals tree is walked at most once per detection call and
    the memoized scan dies with the call.
    """
    cached = context.get(_JOURNAL_FILE_STAT_SCAN_KEY)
    if cached is not None:
        return cast(list[JournalFileStat], cached)
    journals_dir = context.get("journals_dir")
    stats = scan_journal_files(Path(journals_dir)) if journals_dir else []
    context[_JOURNAL_FILE_STAT_SCAN_KEY] = stats
    return stats


def _has_fragment_under(context: dict, directory: Path) -> bool:
    """Whether this call's scan holds a fragment at or below directory."""
    prefix = os.path.normcase(str(directory)) + os.sep
    return any(
        os.path.normcase(str(item.path)).startswith(prefix) for item in _fragment_stats(context)
    )


def check_no_journal_streak(context: dict) -> list[Event]:
    """Detect consecutive days without a journal entry."""
    journals_dir = context.get("journals_dir")
    if not journals_dir:
        return []
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return []

    # Find the most recent fragment journal by mtime
    newest_mtime = max((item.mtime for item in _fragment_stats(context)), default=0.0)

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
    """Detect months that have journals but no generated monthly index.

    The historical detector looked for a non-generated report file. The
    actionable artifact is the monthly index created by
    ``life-index abstract --month YYYY-MM``.
    """
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

        # Check if there are any journal (fragment) files in this month
        if not _has_fragment_under(context, month_dir):
            continue

        month_str = f"{year}-{month:02d}"
        artifact_name = f"index_{month_str}.md"
        artifact_path = month_dir / artifact_name
        if not artifact_path.exists():
            events.append(
                Event(
                    type="monthly_review_due",
                    severity=EventSeverity.INFO,
                    message=(
                        f"{year}年{month:02d}月月度索引尚未生成；"
                        f"运行 life-index abstract --month {month_str}"
                    ),
                    data={
                        "month": month_str,
                        "expected_artifact": artifact_name,
                        "suggested_command": f"life-index abstract --month {month_str}",
                        "side_effect": "write",
                        "side_effect_note": DERIVED_INDEX_NOTE,
                    },
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
                    "suggested_command": "life-index entity audit --json",
                    "side_effect": "read",
                    "side_effect_note": ENTITY_AUDIT_READ_NOTE,
                },
            )
        ]
    return []


def check_entity_profiles_stale(context: dict) -> list[Event]:
    """Detect missing or stale generated entity profile documents."""
    data_dir = context.get("data_dir")
    if not data_dir:
        return []
    data_dir = Path(data_dir)
    graph_path = data_dir / "entity_graph.yaml"
    if not graph_path.exists():
        return []

    try:
        from tools.generate_index.entity_profiles import entity_graph_source_hash
        from tools.lib.entity_graph import load_entity_graph

        entities = load_entity_graph(graph_path)
    except Exception:
        return []

    if not any(entity.get("status", "confirmed") == "confirmed" for entity in entities):
        return []

    index_path = data_dir / "Entities" / "index.md"
    current_hash = entity_graph_source_hash(graph_path)
    profile_hash = None
    reason = "missing_profiles"
    if index_path.exists():
        try:
            metadata, _body = parse_frontmatter(index_path.read_text(encoding="utf-8"))
            raw_hash = metadata.get("source_hash")
            profile_hash = raw_hash if isinstance(raw_hash, str) else None
        except OSError:
            profile_hash = None
        reason = "source_hash_mismatch" if profile_hash else "missing_source_hash"

    if profile_hash == current_hash:
        return []

    return [
        Event(
            type="entity_profiles_stale",
            severity=EventSeverity.INFO,
            message=("Entity profile docs are stale or missing; run " f"{ENTITY_PROFILES_COMMAND}"),
            data={
                "reason": reason,
                "current_source_hash": current_hash,
                "profile_source_hash": profile_hash,
                "expected_artifact": "Entities/index.md",
                "suggested_command": ENTITY_PROFILES_COMMAND,
                "side_effect": "write",
                "side_effect_note": DERIVED_ENTITY_PROFILES_NOTE,
            },
        )
    ]


def check_schema_migration_available(context: dict) -> list[Event]:
    """Detect journals with old schema version (lightweight check).

    Checks only the newest ten fragment files from this call's shared scan —
    avoids reading the whole archive.
    """
    journals_dir = context.get("journals_dir")
    if not journals_dir:
        return []
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return []

    from tools.lib.schema import SCHEMA_VERSION

    # Lightweight: check the newest ten fragment files from the shared scan
    count = 0
    for journal_stat in reversed(_fragment_stats(context)[-10:]):
        md_file = journal_stat.path
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
    """Detect if search index is stale.

    Staleness is decided by the same per-fragment signature rule the search
    preflight uses (``fts_update.inspect_fts_index``): a live fragment with no
    FTS row, a missing or mismatching ``(mtime, size)`` signature, or a row
    for a vanished file. The former "newest journal mtime vs database file
    mtime" comparison is gone — the database file is written by every
    write-through and cannot prove archive coverage.

    Schema/tokenizer/dictionary version mismatches are still a separate
    rebuild signal.
    """
    data_dir = context.get("data_dir")
    journals_dir = context.get("journals_dir")
    if not data_dir or not journals_dir:
        return []

    data_dir = Path(data_dir)
    journals_dir = Path(journals_dir)

    fts_db = data_dir / ".index" / "journals_fts.db"
    if not fts_db.exists():
        return []

    from tools.lib.fts_update import inspect_fts_db

    report = inspect_fts_db(fts_db, journals_dir, data_dir, live=_fragment_stats(context))
    if not report.current:
        return [
            Event(
                type="index_stale",
                severity=EventSeverity.LOW,
                message="索引与日志文件不一致，建议运行 life-index index",
                data={
                    "reason": "signature_mismatch",
                    "suggested_command": "life-index index",
                    "signature_state": report.to_dict(),
                    "side_effect": "write",
                    "side_effect_note": DERIVED_INDEX_NOTE,
                },
            )
        ]

    # --- Signals 2 & 3: version / dict hash mismatch ---
    try:
        from tools.lib.search_index import check_needs_rebuild

        import sqlite3

        conn = sqlite3.connect(str(fts_db))
        try:
            needs_rebuild = check_needs_rebuild(conn)
        finally:
            conn.close()

        if needs_rebuild:
            return [
                Event(
                    type="index_stale",
                    severity=EventSeverity.LOW,
                    message="索引 schema/分词器已变更，建议运行 life-index index --rebuild",
                    data={
                        "reason": "version_mismatch",
                        "suggested_command": "life-index index --rebuild",
                        "side_effect": "write",
                        "side_effect_note": DERIVED_INDEX_NOTE,
                    },
                )
            ]
    except Exception:
        pass  # Non-critical — don't block the event pipeline

    return []


def register_all_detectors() -> None:
    """Register all built-in detectors into the global registry."""
    register_detector("no_journal_streak", check_no_journal_streak)
    register_detector("monthly_review_due", check_monthly_review_due)
    register_detector("entity_audit_due", check_entity_audit_due)
    register_detector("entity_profiles_stale", check_entity_profiles_stale)
    register_detector("schema_migration_available", check_schema_migration_available)
    register_detector("index_stale", check_index_stale)
