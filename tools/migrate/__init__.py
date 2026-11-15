"""Schema migration scanner and executor for Life Index journals.

A file is rewritten for either of two independent reasons:

- ``needs_schema_migration``: its ``schema_version`` is below the target; and
- ``needs_id``: its stored entry ``id`` is missing (rules in
  ``tools/lib/entry_id.py`` and ``docs/ARCHITECTURE.md`` *Entry identity*).

Live entry files only (``journal_files.iter_journal_files``); revisions and
dot-directory files are never enumerated. The run is two passes: a census
that reads every file once and keeps only id strings (so duplicated stored
valid ids are known up front, whatever else is wrong with a file), then one
file at a time — read, plan, and for ``--apply`` replace **immediately**,
before the next file is read, so a file changed by an ordinary editor while
later files are being worked on is never overwritten with stale bytes. A
file that needs a rewrite gets one snapshot, the schema chain applied in
memory if needed, the id added if needed, **one** render, the shared
outgoing check, and **one** replace — never two rewrites (a crash between
them would change the bytes the legacy-id recipe hashes). A stored id that
is malformed, a valid id duplicated across files, and a prospective id that
collides with a stored or already-assigned id are never written: the file is
left exactly as it is and reported with the reason. On a file that needs
only an id, the rewrite may change nothing but the id — anything the
serializer would normalise away is refused as ``would_change_metadata``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.config import FILE_LOCK_TIMEOUT_REBUILD
from tools.lib.entry_id import classify_stored_entry_id, legacy_entry_id
from tools.lib.errors import ErrorCode, create_error_response
from tools.lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path
from tools.lib.frontmatter import (
    _same_value,
    frontmatter_rewrite_blocker,
    parse_frontmatter,
)
from tools.lib.journal_files import iter_journal_files
from tools.lib.journal_rewrite import (
    OutgoingJournalRefused,
    ensure_replaceable_journal,
    render_frontmatter_block,
    replace_journal_bytes,
    split_journal_bytes,
    verify_outgoing_journal,
)
from tools.lib.schema import SCHEMA_VERSION, MigrationResult, run_migration_chain

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

# The change recorded for a file whose one rewrite assigned its entry id.
_ASSIGNED_ID_CHANGE = "assigned entry id"


# ---------------------------------------------------------------------------
# Pass 1: the census (id strings only, no file bytes survive this pass)
# ---------------------------------------------------------------------------


def _census_valid_ids(journals_dir: Path) -> dict[str, list[str]]:
    """Map every stored valid entry id to the rel_paths that carry it.

    A file counts whatever else is wrong with it (an invalid
    ``schema_version``, a rewrite blocker): only files whose bytes cannot be
    read or parsed at all are absent. Nothing but the id strings and paths
    survive this pass.
    """
    ids: dict[str, list[str]] = {}
    for md_file in iter_journal_files(journals_dir):
        try:
            metadata, _body = parse_frontmatter(md_file.read_bytes().decode("utf-8"))
        except Exception:  # noqa: BLE001 - an unreadable file carries no id fact
            continue
        if classify_stored_entry_id(metadata.get("id")) != "valid":
            continue
        stored = str(metadata["id"])
        ids.setdefault(stored, []).append(md_file.relative_to(journals_dir.parent).as_posix())
    return ids


# ---------------------------------------------------------------------------
# Pass 2: one file at a time
# ---------------------------------------------------------------------------


@dataclass
class _FilePlan:
    """What the migration does with one file; discarded after the iteration.

    ``action`` is ``"migrate"`` (one rewrite is computed), ``"refused"``
    (the file is left exactly as it is, ``reason`` names the category), or
    ``"current"`` (it needs neither a schema step nor an id).
    """

    path: Path
    rel_path: str
    action: str
    reason: str | None = None
    detail: str | None = None
    current_version: Any = None
    missing_fields: list[str] | None = None
    needs_schema: bool = False
    needs_id: bool = False
    assigns_id: str | None = None
    new_bytes: bytes | None = None
    chain_result: MigrationResult | None = None


def _refuse(
    plan: _FilePlan,
    reason: str,
    detail: str | None = None,
) -> _FilePlan:
    plan.action = "refused"
    plan.reason = reason
    plan.detail = detail
    return plan


def _entry_rel_path(md_file: Path, journals_dir: Path) -> str:
    """The recipe's path: relative to the data directory, as POSIX text.

    ``relative_to(...).as_posix()`` and nothing else: no helper that rewrites
    backslashes, because on POSIX a backslash is a legal character in a
    directory name and two different locations must never hash alike.
    """
    return md_file.relative_to(journals_dir.parent).as_posix()


def _plan_one_file(
    md_file: Path,
    journals_dir: Path,
    target: int,
    census: dict[str, list[str]],
    assigned: dict[str, str],
) -> _FilePlan:
    """Compute what the migration does with one file; read it exactly once."""
    rel_path = _entry_rel_path(md_file, journals_dir)
    plan = _FilePlan(path=md_file, rel_path=rel_path, action="current")
    try:
        raw_bytes = md_file.read_bytes()
    except OSError as exc:
        return _refuse(plan, "unreadable", str(exc))

    try:
        split = split_journal_bytes(raw_bytes)
        if split is None:
            # The file reads like a v1 entry with no block at all: it is
            # counted as needing the migration it is refused (wrapping the
            # whole file in new frontmatter would change every body byte).
            plan.current_version = 1
            plan.missing_fields = sorted(EXPECTED_FIELDS)
            plan.needs_schema = True
            plan.needs_id = True
            return _refuse(plan, "no_frontmatter_block")
        content = raw_bytes.decode("utf-8")
        blocker = frontmatter_rewrite_blocker(content)
        if blocker == "unreadable":
            return _refuse(plan, "unreadable")
        metadata, body = parse_frontmatter(content)
    except Exception as exc:  # noqa: BLE001 - one unreadable file fails alone
        return _refuse(plan, "unreadable", str(exc))

    stored_id = metadata.get("id")
    id_state = classify_stored_entry_id(stored_id)
    plan.current_version = metadata.get("schema_version", 1)
    plan.missing_fields = sorted(EXPECTED_FIELDS - set(metadata.keys()))
    if id_state == "valid" and len(census.get(str(stored_id), [])) > 1:
        # A duplicated stored valid id is never changed on any carrier,
        # whatever else is wrong with the file.
        others = ", ".join(path for path in census[str(stored_id)] if path != rel_path)
        return _refuse(plan, "duplicate_id", f"also stored by {others}")
    if id_state == "malformed":
        # Never replaced: the file is left exactly as it is and reported.
        return _refuse(plan, "malformed_id")

    file_ver = plan.current_version
    try:
        plan.needs_schema = bool(file_ver < target)
    except TypeError as exc:
        # A ``schema_version`` that is not a number cannot be compared, so
        # the file is not migratable; it fails alone with its bytes kept.
        return _refuse(plan, "invalid_schema_version", f"{type(exc).__name__}: {exc}")
    plan.needs_id = id_state == "missing"

    if not plan.needs_schema and not plan.needs_id:
        return plan
    plan.action = "migrate"

    if blocker is not None:
        # Outdated or id-less, but the serializer cannot write this
        # frontmatter back without loss: the file needs a change it cannot get.
        return _refuse(plan, blocker)

    # The prospective rewrite: the chain in memory if needed, the id if
    # needed, one render — computed from this one snapshot, so the id recipe
    # always hashes the bytes as they were before this migration.
    final_metadata: dict[str, Any]
    if plan.needs_schema:
        try:
            result = run_migration_chain(metadata, content=body)
        except Exception as exc:  # noqa: BLE001 - one unmigratable file fails alone
            return _refuse(plan, "invalid_schema_version", f"{type(exc).__name__}: {exc}")
        plan.chain_result = result
        final_metadata = result.metadata
    else:
        final_metadata = dict(metadata)
    if plan.needs_id:
        prospective = legacy_entry_id(rel_path, raw_bytes)
        collision = census.get(prospective)
        if collision:
            return _refuse(
                plan,
                "duplicate_id",
                f"the id this migration would assign ({prospective}) is already"
                " stored by " + ", ".join(collision),
            )
        if prospective in assigned:
            return _refuse(
                plan,
                "duplicate_id",
                f"the id this migration would assign ({prospective}) was already"
                f" assigned in this run to {assigned[prospective]}",
            )
        plan.assigns_id = prospective
        final_metadata["id"] = prospective

    new_bytes = render_frontmatter_block(final_metadata) + split.suffix
    try:
        verify_outgoing_journal(raw_bytes, new_bytes, final_metadata, metadata_only=True)
    except OutgoingJournalRefused:
        return _refuse(plan, "outgoing_check_refused")

    if plan.needs_id and not plan.needs_schema:
        # The migration adds `id` and nothing else on a current-schema file:
        # the outgoing metadata, with the id removed, must equal the old
        # parsed metadata exactly (type-sensitive), or the serializer would
        # silently normalise other stored values away.
        rewritten, _rewritten_body = parse_frontmatter(new_bytes.decode("utf-8"))
        rewritten.pop("id", None)
        if not _same_value(rewritten, metadata):
            changed = [
                key
                for key in sorted(set(rewritten) | set(metadata))
                if key != "id"
                and (
                    key not in rewritten
                    or key not in metadata
                    or not _same_value(rewritten[key], metadata[key])
                )
            ]
            return _refuse(
                plan,
                "would_change_metadata",
                "fields that would change: " + ", ".join(changed),
            )

    try:
        ensure_replaceable_journal(md_file)
    except PermissionError as exc:
        return _refuse(plan, "not_replaceable", str(exc))
    plan.new_bytes = new_bytes
    return plan


@dataclass
class _FileRecord:
    """The small per-file report that survives one pass-2 iteration."""

    path: str
    rel_path: str
    action: str
    reason: str | None
    detail: str | None
    current_version: Any
    missing_fields: list[str]
    needs_schema: bool
    needs_id: bool
    assigns_id: str | None
    replace_error: str | None
    changes: list[str]
    needs_agent: list[str]


def _run_pass(
    journals_dir: Path,
    target: int,
    *,
    apply: bool,
) -> list[_FileRecord]:
    """Census, then one file at a time: plan, and for apply replace now.

    Each file is read and (for apply) replaced before the next file is read;
    only the small per-file record survives the iteration. ``assigned``
    accumulates the ids this run has assigned (planned for dry-run, written
    for apply) so a later prospective id cannot collide with an earlier one.
    """
    census = _census_valid_ids(journals_dir)
    assigned: dict[str, str] = {}
    records: list[_FileRecord] = []
    for md_file in iter_journal_files(journals_dir):
        plan = _plan_one_file(md_file, journals_dir, target, census, assigned)
        replace_error: str | None = None
        if apply and plan.action == "migrate":
            assert plan.new_bytes is not None
            try:
                replace_journal_bytes(plan.path, plan.new_bytes)
            except Exception as exc:  # noqa: BLE001 - one failed replace fails alone
                replace_error = str(exc)
        if plan.assigns_id is not None and plan.action == "migrate" and (replace_error is None):
            assigned[plan.assigns_id] = plan.rel_path
        changes: list[str] = (
            list(plan.chain_result.deterministic_changes) if plan.chain_result is not None else []
        )
        if plan.assigns_id is not None and replace_error is None:
            changes.append(_ASSIGNED_ID_CHANGE)
        records.append(
            _FileRecord(
                path=str(plan.path),
                rel_path=plan.rel_path,
                action=plan.action,
                reason=plan.reason,
                detail=plan.detail,
                current_version=plan.current_version,
                missing_fields=plan.missing_fields or [],
                needs_schema=plan.needs_schema,
                needs_id=plan.needs_id,
                assigns_id=plan.assigns_id,
                replace_error=replace_error,
                changes=changes,
                needs_agent=(
                    list(plan.chain_result.needs_agent) if plan.chain_result is not None else []
                ),
            )
        )
    return records


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _refusal_text(record: _FileRecord) -> str:
    """The one error text shape per refusal category; the file stays as it is."""
    if record.reason == "malformed_id":
        prefix = "the stored entry id is malformed (malformed_id) and is never replaced"
    elif record.reason == "duplicate_id":
        prefix = "the entry id is duplicated across files (duplicate_id) and is never changed"
    elif record.reason == "would_change_metadata":
        prefix = (
            "an id-only rewrite would change other stored values"
            " (would_change_metadata); the migration adds id and nothing else"
        )
    elif record.reason == "not_replaceable":
        prefix = "the journal cannot be replaced (not_replaceable: symlink or not writable)"
    elif record.reason == "outgoing_check_refused":
        prefix = "frontmatter rewrite blocked (outgoing_check_refused)"
    else:
        # unreadable, no_frontmatter_block, each rewrite-blocker reason and
        # invalid_schema_version all carry their reason code in parentheses.
        prefix = f"frontmatter rewrite blocked ({record.reason})"
    text = f"{prefix}; file left unchanged"
    if record.detail:
        text = f"{text}: {record.detail}"
    return text


def _outdated_entry(record: _FileRecord) -> dict[str, Any]:
    entry_record: dict[str, Any] = {
        "path": record.path,
        "current_version": record.current_version,
        "missing_fields": record.missing_fields,
        "needs_schema_migration": record.needs_schema,
        "needs_id": record.needs_id,
    }
    if record.action == "refused" and record.reason in {
        "no_frontmatter_block",
        "content_key_in_frontmatter",
        "not_round_trippable",
    }:
        entry_record["rewrite_blocker"] = record.reason
    return entry_record


def scan_journals(journals_dir: Path) -> dict[str, Any]:
    """Dry-run: plan the same rewrite ``--apply`` would do, publish nothing.

    Every file that will not be migrated is named with a reason
    (``refused_files``); files that need a rewrite (schema step and/or an
    entry id) are listed in ``outdated_files``. Nothing is written and no
    state is reserved: ``--apply`` re-reads and re-checks everything.
    """
    journals_dir = Path(journals_dir)
    if not journals_dir.exists():
        return {
            "total_scanned": 0,
            "version_distribution": {},
            "needs_migration": 0,
            "needs_id": 0,
            "outdated_files": [],
            "refused_files": [],
        }

    version_dist: dict[str, int] = {}
    outdated: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    total = 0
    needs_id_count = 0

    for record in _run_pass(journals_dir, SCHEMA_VERSION, apply=False):
        total += 1
        if record.reason == "unreadable":
            version_dist["unparseable"] = version_dist.get("unparseable", 0) + 1
        else:
            ver_key = str(record.current_version)
            version_dist[ver_key] = version_dist.get(ver_key, 0) + 1
        if record.needs_id:
            needs_id_count += 1
        if record.needs_schema or record.needs_id:
            outdated.append(_outdated_entry(record))
        if record.action == "refused":
            refused.append(
                {
                    "path": record.path,
                    "reason": record.reason,
                    "error": _refusal_text(record),
                }
            )

    return {
        "total_scanned": total,
        "version_distribution": version_dist,
        "needs_migration": len(outdated),
        "needs_id": needs_id_count,
        "outdated_files": outdated,
        "refused_files": refused,
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
            "needs_id": int,
            "assigned_ids": [{"path": str, "id": str}],
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
    assigned_ids: list[dict[str, str]] = []
    needs_id_count = 0

    for record in _run_pass(journals_dir, target, apply=True):
        if record.needs_id:
            needs_id_count += 1
        if record.action == "current":
            already_current += 1
            continue
        if record.action == "refused":
            failed.append({"path": record.path, "error": _refusal_text(record)})
            continue
        if record.replace_error is not None:
            failed.append({"path": record.path, "error": record.replace_error})
            continue

        # The one planned rewrite was replaced before the next file was read.
        migrated += 1
        if record.assigns_id is not None:
            assigned_ids.append({"path": record.path, "id": record.assigns_id})
        if record.changes:
            det_changes.append({"path": record.path, "changes": record.changes})
        if record.needs_agent:
            needs_agent_list.append(
                {
                    "path": record.path,
                    "items": record.needs_agent,
                }
            )

    return {
        "migrated_count": migrated,
        "already_current": already_current,
        "failed_count": len(failed),
        "failed_files": failed,
        "needs_agent": needs_agent_list,
        "deterministic_changes": det_changes,
        "needs_id": needs_id_count,
        "assigned_ids": assigned_ids,
    }


def _apply_empty() -> dict[str, Any]:
    return {
        "migrated_count": 0,
        "already_current": 0,
        "failed_count": 0,
        "failed_files": [],
        "needs_agent": [],
        "deterministic_changes": [],
        "needs_id": 0,
        "assigned_ids": [],
    }
