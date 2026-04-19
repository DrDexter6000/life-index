"""Schema migration scanner and executor for Life Index journals."""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any

from tools.lib.frontmatter import parse_frontmatter, format_frontmatter
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

# Only scan files matching this pattern.
_JOURNAL_PATTERN = re.compile(r"^life-index_\d{4}-\d{2}-\d{2}_\d+\.md$")


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

    for md_file in sorted(journals_dir.rglob("*.md")):
        if not _JOURNAL_PATTERN.match(md_file.name):
            continue

        total += 1
        try:
            content = md_file.read_text(encoding="utf-8")
            metadata, _body = parse_frontmatter(content)
        except Exception:
            logger.debug("Failed to parse %s during scan", md_file, exc_info=True)
            version_dist["unparseable"] = version_dist.get("unparseable", 0) + 1
            continue

        file_ver = metadata.get("schema_version", 1)
        ver_key = str(file_ver)
        version_dist[ver_key] = version_dist.get(ver_key, 0) + 1

        if file_ver < SCHEMA_VERSION:
            missing = sorted(EXPECTED_FIELDS - set(metadata.keys()))
            outdated.append(
                {
                    "path": str(md_file),
                    "current_version": file_ver,
                    "missing_fields": missing,
                }
            )

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

    migrated = 0
    already_current = 0
    failed: list[dict[str, str]] = []
    needs_agent_list: list[dict[str, Any]] = []
    det_changes: list[dict[str, Any]] = []

    for md_file in sorted(journals_dir.rglob("*.md")):
        if not _JOURNAL_PATTERN.match(md_file.name):
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
            metadata, body = parse_frontmatter(content)
        except Exception as exc:
            failed.append({"path": str(md_file), "error": str(exc)})
            continue

        file_ver = metadata.get("schema_version", 1)
        if file_ver >= target:
            already_current += 1
            continue

        # Run migration chain
        result = run_migration_chain(metadata, content=body)

        # Reconstruct the file with migrated frontmatter
        new_frontmatter = format_frontmatter(result.metadata)
        new_content = f"{new_frontmatter}\n\n{body}"

        # Atomic write: write to temp file, then rename
        try:
            fd, tmp_path = tempfile.mkstemp(
                suffix=".md",
                prefix=".migrate_",
                dir=md_file.parent,
            )
            try:
                with open(fd, "w", encoding="utf-8") as f:
                    f.write(new_content)
                Path(tmp_path).replace(md_file)
            except BaseException:
                Path(tmp_path).unlink(missing_ok=True)
                raise
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
