"""Schema migration scanner and executor for Life Index journals."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from tools.lib.config import FILE_LOCK_TIMEOUT_REBUILD
from tools.lib.errors import ErrorCode, create_error_response
from tools.lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path
from tools.lib.frontmatter import (
    frontmatter_rewrite_blocker,
    parse_frontmatter,
)
from tools.lib.journal_files import iter_journal_files
from tools.lib.journal_rewrite import (
    OutgoingJournalRefused,
    render_frontmatter_block,
    replace_journal_bytes,
    split_journal_bytes,
    verify_outgoing_journal,
)
from tools.lib.schema import SCHEMA_VERSION, run_migration_chain

logger = logging.getLogger(__name__)

# Fields expected in the current schema version.
EXPECTED_FIELDS: set[str] = {
    "schema_version",
    "title",
    "date",
    "location",
    "weather",
    "mood",
    "entities",
    "people",
    "tags",
    "project",
    "topic",
    "abstract",
    "summary",
    "links",
    "related_entries",
    "attachments",
}

# ---------------------------------------------------------------------------
# Scan (dry-run)
# ---------------------------------------------------------------------------


def scan_journals(journals_dir: Path) -> dict[str, Any]:
    """Scan all journal files and return a schema version distribution report.

    Returns:
        {
            "total_scanned": int,
            "version_distribution": {"1": int, ...},
            "needs_migration": int,
            "outdated_files": [
                {"path": str, "current_version": int, "missing_fields": [str]},
            ],
        }
    """
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return _empty_report()

    version_dist: dict[str, int] = {}
    outdated: list[dict[str, Any]] = []
    total = 0

    for md_file in iter_journal_files(journals_dir):
        total += 1
        try:
            content = md_file.read_text(encoding="utf-8")
            if split_journal_bytes(content.encode("utf-8")) is None:
                # --apply refuses to rewrite a file without a frontmatter
                # block at all; report the same reason dry-run would hit.
                no_block = True
                reason: str | None = None
            else:
                no_block = False
                reason = frontmatter_rewrite_blocker(content)
            if reason == "unreadable":
                version_dist["unparseable"] = version_dist.get("unparseable", 0) + 1
                continue
            metadata, _body = parse_frontmatter(content)
        except Exception:
            logger.debug("Failed to parse %s during scan", md_file, exc_info=True)
            version_dist["unparseable"] = version_dist.get("unparseable", 0) + 1
            continue

        file_ver = metadata.get("schema_version", 1)
        ver_key = str(file_ver)
        version_dist[ver_key] = version_dist.get(ver_key, 0) + 1

        try:
            outdated_file = file_ver < SCHEMA_VERSION
        except TypeError:
            # A ``schema_version`` that is not a number is counted above under
            # its own text; it cannot be compared, so it is not migratable.
            continue

        if outdated_file:
            missing = sorted(EXPECTED_FIELDS - set(metadata.keys()))
            entry: dict[str, Any] = {
                "path": str(md_file),
                "current_version": file_ver,
                "missing_fields": missing,
            }
            if reason is not None or no_block:
                # Readable and outdated, but --apply will refuse to rewrite it.
                entry["rewrite_blocker"] = (
                    "no_frontmatter_block" if no_block else (reason or "unreadable")
                )
            outdated.append(entry)

    return {
        "total_scanned": total,
        "version_distribution": version_dist,
        "needs_migration": len(outdated),
        "outdated_files": outdated,
    }


def _empty_report() -> dict[str, Any]:
    return {
        "total_scanned": 0,
        "version_distribution": {},
        "needs_migration": 0,
        "outdated_files": [],
    }


# ---------------------------------------------------------------------------
# Apply (deterministic migration)
# ---------------------------------------------------------------------------


def apply_migrations(
    journals_dir: Path,
    target_version: int | None = None,
) -> dict[str, Any]:
    """Execute deterministic migrations on all outdated journals.

    The whole batch runs inside the journals lock: every file is re-read
    inside that lock and rewritten through the shared primitive
    (``tools/lib/journal_rewrite.py``), so a concurrent journals writer that
    follows the lock protocol serializes with the migration instead of being
    clobbered by it.

    Returns:
        {
            "migrated_count": int,
            "already_current": int,
            "failed_count": int,
            "failed_files": [{"path": str, "error": str}],
            "needs_agent": [{"path": str, "items": [str]}],
            "deterministic_changes": [{"path": str, "changes": [str]}],
        }
    """
    target = target_version or SCHEMA_VERSION
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return _apply_empty()

    lock = FileLock(get_journals_lock_path(), timeout=FILE_LOCK_TIMEOUT_REBUILD)
    try:
        with lock:
            return _apply_migrations_locked(journals_dir, target)
    except LockTimeoutError as exc:
        # Nothing was read or written; report the empty report plus the
        # structured lock-timeout envelope.
        logger.error("无法获取 journals 写入锁，迁移未执行：%s", exc)
        report = _apply_empty()
        report.update(
            create_error_response(
                ErrorCode.LOCK_TIMEOUT,
                f"无法获取 journals 写入锁，迁移未执行：{exc}",
                {
                    "lock_path": str(get_journals_lock_path()),
                    "timeout": FILE_LOCK_TIMEOUT_REBUILD,
                },
                "等待几秒后重试，或检查是否有其他进程正在写入日志",
            )
        )
        return report


def _apply_migrations_locked(journals_dir: Path, target: int) -> dict[str, Any]:
    """Run the migration loop; the caller already holds the journals lock."""
    migrated = 0
    already_current = 0
    failed: list[dict[str, str]] = []
    needs_agent_list: list[dict[str, Any]] = []
    det_changes: list[dict[str, Any]] = []

    for md_file in iter_journal_files(journals_dir):
        try:
            # Read inside the lock; these bytes decide the rewrite.
            raw_bytes = md_file.read_bytes()
            split = split_journal_bytes(raw_bytes)
            if split is None:
                failed.append(
                    {
                        "path": str(md_file),
                        "error": (
                            "frontmatter rewrite blocked (no_frontmatter_block);"
                            " file left unchanged"
                        ),
                    }
                )
                continue
            content = raw_bytes.decode("utf-8")
            reason = frontmatter_rewrite_blocker(content)
            blocked = {
                "path": str(md_file),
                "error": f"frontmatter rewrite blocked ({reason}); file left unchanged",
            }
            if reason == "unreadable":
                # No readable mapping, so not even the version is known. Report
                # it like a parse failure and keep the bytes.
                failed.append(blocked)
                continue
            metadata, body = parse_frontmatter(content)
        except Exception as exc:
            failed.append({"path": str(md_file), "error": str(exc)})
            continue

        # Everything computed from this one file's content stays inside the
        # per-file failure boundary: a ``schema_version`` that is not a number
        # fails this file only and leaves its bytes unchanged.
        try:
            file_ver = metadata.get("schema_version", 1)
            if file_ver >= target:
                already_current += 1
                continue

            if reason is not None:
                # Outdated, but the serializer cannot write this frontmatter
                # back without loss: the file needs a migration it cannot get.
                failed.append(blocked)
                continue

            # Run migration chain
            result = run_migration_chain(metadata, content=body)
        except Exception as exc:
            failed.append({"path": str(md_file), "error": f"{type(exc).__name__}: {exc}"})
            continue

        # Rewrite through the shared atomic primitive: the migrated
        # frontmatter block (LF) plus the original suffix bytes verbatim,
        # committed only after the outgoing file passes its read-back check.
        try:
            new_bytes = render_frontmatter_block(result.metadata) + split.suffix
            verify_outgoing_journal(raw_bytes, new_bytes, result.metadata, metadata_only=True)
            replace_journal_bytes(md_file, new_bytes)
        except OutgoingJournalRefused:
            failed.append(
                {
                    "path": str(md_file),
                    "error": (
                        "frontmatter rewrite blocked (not_round_trippable);" " file left unchanged"
                    ),
                }
            )
            continue
        except Exception as exc:
            failed.append({"path": str(md_file), "error": str(exc)})
            continue

        migrated += 1

        if result.deterministic_changes:
            det_changes.append(
                {
                    "path": str(md_file),
                    "changes": result.deterministic_changes,
                }
            )
        if result.needs_agent:
            needs_agent_list.append(
                {
                    "path": str(md_file),
                    "items": result.needs_agent,
                }
            )

    return {
        "migrated_count": migrated,
        "already_current": already_current,
        "failed_count": len(failed),
        "failed_files": failed,
        "needs_agent": needs_agent_list,
        "deterministic_changes": det_changes,
    }


def _apply_empty() -> dict[str, Any]:
    return {
        "migrated_count": 0,
        "already_current": 0,
        "failed_count": 0,
        "failed_files": [],
        "needs_agent": [],
        "deterministic_changes": [],
    }
