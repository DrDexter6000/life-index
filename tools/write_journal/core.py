#!/usr/bin/env python3
"""
Life Index - Write Journal Tool - Core
核心协调模块
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Sequence

from ..lib.config import (
    FILE_LOCK_TIMEOUT_DEFAULT,
    get_default_location,
    resolve_user_data_dir,
)
from ..lib.paths import get_journals_dir
from ..lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path
from ..lib.errors import ErrorCode, create_error_response
from ..lib.workflow_signals import (
    WriteOutcome,
    IndexStatus,
    SideEffectExecutionStatus,
    SideEffectsStatus,
    ConfirmStatus,
    derive_write_statuses,
)
from ..lib.entity_graph import load_entity_graph, resolve_entity
from ..lib.entity_schema import EntityGraphValidationError
from ..lib.entity_candidates import extract_entity_candidates
from ..lib.metadata_cache import (
    get_backlinked_by,
    get_all_cached_metadata,
    init_metadata_cache,
    replace_entry_relations,
)
from ..lib.path_contract import build_journal_path_fields
from ..lib.related_candidates import suggest_related_entries
from ..lib import content_analysis
from ..lib.timing import Timer
from ..lib.logger import get_logger
from .utils import (
    current_local_date_iso,
    extract_explicit_metadata_from_content as _extract_explicit_metadata_from_content,
    generate_filename,
    get_next_sequence,
    get_year_month,
)
from ..lib.frontmatter import format_journal_content as format_content
from .attachments import (
    AttachmentStaging,
    compensate_published_attachments,
    discard_attachment_staging,
    extract_file_paths_from_content,
    process_attachments,
    publish_staged_attachments,
    stage_attachments,
)
from .weather import query_weather_for_location, normalize_location
from .index_updater import (
    update_topic_index,
    update_project_index,
    update_tag_indices,
    update_monthly_abstract,
    refresh_index_b,
)
from ..lib.pending_writes import mark_pending
from ..entity.candidate_pool import capture_write_time_candidates

# 初始化日志器
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level private helpers (extracted from apply_confirmation_updates)
# ---------------------------------------------------------------------------

_CONFIRMATION_CANDIDATE_SNAPSHOT_FILE = "confirmation_candidates.json"


def _confirmation_snapshot_key(journal_path: Path) -> str:
    """Return the canonical key used for a journal confirmation snapshot."""
    return str(journal_path.resolve())


def _confirmation_snapshot_path(journal_path: Path) -> Path:
    """Store confirmation snapshots next to index state for this data tree."""
    resolved = journal_path.resolve()
    parts = list(resolved.parts)
    if "Journals" in parts:
        journals_index = parts.index("Journals")
        if journals_index > 0:
            data_dir = Path(*parts[:journals_index])
            return data_dir / ".index" / _CONFIRMATION_CANDIDATE_SNAPSHOT_FILE
    return resolved.parent / _CONFIRMATION_CANDIDATE_SNAPSHOT_FILE


def _candidate_snapshot(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only stable, public candidate fields needed by confirm."""
    snapshot: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue  # type: ignore[unreachable]
        rel_path = str(candidate.get("rel_path") or "").strip()
        if not rel_path:
            continue
        candidate_id = candidate.get("candidate_id")
        snapshot.append(
            {
                "candidate_id": candidate_id if isinstance(candidate_id, int) else None,
                "rel_path": rel_path,
                "title": str(candidate.get("title") or ""),
            }
        )
    return snapshot


def _write_confirmation_candidate_snapshot(
    journal_path: Path,
    candidates: list[dict[str, Any]],
) -> None:
    """Persist the write-time candidate_id -> rel_path snapshot for confirm."""
    snapshot = _candidate_snapshot(candidates)
    if not snapshot:
        return

    snapshot_path = _confirmation_snapshot_path(journal_path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    key = _confirmation_snapshot_key(journal_path)
    payload: dict[str, Any] = {"snapshots": {}}
    if snapshot_path.exists():
        try:
            existing = json.loads(snapshot_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("snapshots"), dict):
                payload = existing
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            payload = {"snapshots": {}}

    payload["snapshots"][key] = {
        "journal_path": key,
        "related_candidates": snapshot,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(snapshot_path.parent),
        prefix=f"{_CONFIRMATION_CANDIDATE_SNAPSHOT_FILE}.tmp",
    )
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(rendered)
        Path(tmp_path).replace(snapshot_path)
    except Exception:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _read_confirmation_candidate_snapshot(
    journal_path: Path,
) -> list[dict[str, Any]] | None:
    """Load the write-time confirmation candidate snapshot, if present."""
    snapshot_path = _confirmation_snapshot_path(journal_path)
    if not snapshot_path.exists():
        return None
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("snapshots"), dict):
        return None
    snapshot = payload["snapshots"].get(_confirmation_snapshot_key(journal_path))
    if not isinstance(snapshot, dict):
        return None
    candidates = snapshot.get("related_candidates")
    if not isinstance(candidates, list):
        return None
    return _candidate_snapshot(candidates)


def _has_candidate_id_refs(
    refs: Sequence[str | int] | None,
    candidate_ids: Sequence[int] | None,
) -> bool:
    """Return True when a confirm request uses unstable numeric references."""
    if candidate_ids:
        return True
    if not refs:
        return False
    for ref in refs:
        if isinstance(ref, int):
            return True
        if isinstance(ref, str) and ref.strip().isdigit():
            return True
    return False


def _confirmation_candidate_context(
    journal_path: Path,
    *,
    candidate_context: list[dict[str, Any]] | None,
    approved_related_entries: Sequence[str | int] | None,
    approved_related_candidate_ids: Sequence[int] | None,
    rejected_related_entries: Sequence[str | int] | None,
    rejected_related_candidate_ids: Sequence[int] | None,
) -> list[dict[str, Any]] | None:
    """Prefer write-time snapshot when confirm uses numeric candidate refs."""
    uses_candidate_ids = _has_candidate_id_refs(
        approved_related_entries,
        approved_related_candidate_ids,
    ) or _has_candidate_id_refs(
        rejected_related_entries,
        rejected_related_candidate_ids,
    )
    if not uses_candidate_ids:
        return candidate_context
    snapshot = _read_confirmation_candidate_snapshot(journal_path)
    return snapshot if snapshot is not None else candidate_context


def _normalize_candidate_context(
    candidates: list[dict[str, Any]],
) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build lookup dicts for candidate resolution by id and rel_path."""
    by_id: dict[int, dict[str, Any]] = {}
    by_rel_path: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue  # type: ignore[unreachable]
        rel_path = str(candidate.get("rel_path") or "").strip()
        if not rel_path:
            continue
        candidate_id = candidate.get("candidate_id")
        normalized_candidate = {
            "candidate_id": candidate_id,
            "rel_path": rel_path,
            "title": str(candidate.get("title") or ""),
        }
        if isinstance(candidate_id, int):
            by_id[candidate_id] = normalized_candidate
        by_rel_path[rel_path] = normalized_candidate
    return by_id, by_rel_path


def _resolve_candidate_refs(
    refs: Sequence[str | int] | None,
    *,
    candidate_ids: Sequence[int] | None = None,
    candidate_context: list[dict[str, Any]] | None = None,
) -> tuple[list[str], list[dict[str, Any]], list[int], dict[str, Any] | None]:
    """Resolve candidate references to rel_paths, candidates, and ids."""
    candidate_context = candidate_context or []
    by_id, by_rel_path = _normalize_candidate_context(candidate_context)
    resolved_rel_paths: list[str] = []
    resolved_candidates: list[dict[str, Any]] = []
    resolved_candidate_ids: list[int] = []
    seen_rel_paths: set[str] = set()

    combined_refs: list[str | int] = []
    if refs:
        combined_refs.extend(refs)
    if candidate_ids:
        combined_refs.extend(candidate_ids)

    for ref in combined_refs:
        candidate: dict[str, Any] | None = None
        if isinstance(ref, int):
            candidate = by_id.get(ref)
        elif isinstance(ref, str):
            normalized_ref = ref.strip()
            if not normalized_ref:
                continue
            if normalized_ref.isdigit():
                candidate = by_id.get(int(normalized_ref))
            else:
                candidate = by_rel_path.get(normalized_ref)
                if candidate is None:
                    candidate = {
                        "candidate_id": None,
                        "rel_path": normalized_ref,
                        "title": "",
                    }
        if candidate is None:
            return (
                [],
                [],
                [],
                create_error_response(
                    ErrorCode.INVALID_INPUT,
                    f"未知候选引用：{ref}",
                    {"candidate_reference": ref},
                    "请传入有效的 candidate_id 或 rel_path，并确保 candidate_context 与确认载荷一致",
                ),
            )

        rel_path = candidate["rel_path"]
        if rel_path in seen_rel_paths:
            continue
        seen_rel_paths.add(rel_path)
        resolved_rel_paths.append(rel_path)
        resolved_candidates.append(candidate)
        candidate_id = candidate.get("candidate_id")
        if isinstance(candidate_id, int):
            resolved_candidate_ids.append(candidate_id)

    return resolved_rel_paths, resolved_candidates, resolved_candidate_ids, None


def _build_approval_summary(
    *,
    approved_candidates: list[dict[str, Any]],
    rejected_candidates: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Build approval summary with candidate_id, rel_path, title."""

    def _summary_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "candidate_id": candidate.get("candidate_id"),
                "rel_path": candidate["rel_path"],
                "title": candidate.get("title") or "",
            }
            for candidate in candidates
        ]

    return {
        "approved": _summary_rows(approved_candidates),
        "rejected": _summary_rows(rejected_candidates),
    }


def _build_relation_summary(
    *,
    source_path: Path,
    approved_entries: list[str],
    applied_fields: list[str],
) -> dict[str, Any] | None:
    """Build relation summary with backlink info if related_entries was applied."""
    if "related_entries" not in applied_fields:
        return None

    metadata_conn = init_metadata_cache()
    try:
        source_fields = build_journal_path_fields(
            source_path,
            journals_dir=get_journals_dir(),
            user_data_dir=resolve_user_data_dir(),
        )
        source_rel_path = source_fields["rel_path"]
        source_backlinks = get_backlinked_by(metadata_conn, source_rel_path)
        approved_context = [
            {
                "rel_path": rel_path,
                "backlinked_by": get_backlinked_by(metadata_conn, rel_path),
            }
            for rel_path in approved_entries
        ]
        return {
            "source_entry": {
                "rel_path": source_rel_path,
                "related_entries": approved_entries,
                "backlinked_by": source_backlinks,
            },
            "approved_related_context": approved_context,
        }
    finally:
        metadata_conn.close()


def _derive_confirm_status(
    *, success: bool, requested_fields: list[str], applied_fields: list[str]
) -> str:
    """Derive confirm_status from success flag and field application results."""
    if not success:
        return ConfirmStatus.FAILED
    if not requested_fields or not applied_fields:
        return ConfirmStatus.NOOP
    if len(applied_fields) == len(requested_fields):
        return ConfirmStatus.COMPLETE
    return ConfirmStatus.PARTIAL


def _build_confirm_failure_envelope(
    *,
    journal_path_obj: Path,
    approved_related_entries: list[str] | None,
) -> dict[str, Any]:
    """Build the common error envelope for confirmation failures."""
    return {
        "journal_path": str(journal_path_obj),
        "confirm_status": ConfirmStatus.FAILED,
        "applied_fields": [],
        "ignored_fields": [],
        "approved_related_entries": [],
        "requested_related_entries": approved_related_entries or [],
        "approved_candidate_ids": [],
        "rejected_related_entries": [],
        "rejected_candidate_ids": [],
        "approval_summary": {"approved": [], "rejected": []},
        "relation_summary": None,
    }


def _field_was_applied(changes: dict[str, Any], field: str) -> bool:
    """Check if a field was actually changed in the edit result."""
    if field not in changes:
        return False
    change = changes.get(field)
    if not isinstance(change, dict):
        return True
    return change.get("old") != change.get("new")


def _enrich_confirm_result(
    *,
    result: Dict[str, Any],
    journal_path_obj: Path,
    resolved_approved_entries: list[str],
    resolved_rejected_entries: list[str],
    approved_candidates: list[dict[str, Any]],
    approved_candidate_ids: list[int],
    rejected_candidates: list[dict[str, Any]],
    rejected_candidate_ids: list[int],
    requested_fields: list[str],
) -> None:
    """Enrich the edit_journal result with confirmation metadata."""
    changes = result.get("changes", {}) if isinstance(result, dict) else {}
    applied_fields = [f for f in requested_fields if _field_was_applied(changes, f)]
    ignored_fields = [f for f in requested_fields if not _field_was_applied(changes, f)]

    if isinstance(result, dict):
        result["applied_fields"] = applied_fields
        result["ignored_fields"] = ignored_fields
        result["approved_related_entries"] = (
            resolved_approved_entries if "related_entries" in applied_fields else []
        )
        result["requested_related_entries"] = resolved_approved_entries
        approved_entries = result["approved_related_entries"]
        result["approved_candidate_ids"] = approved_candidate_ids
        result["rejected_related_entries"] = resolved_rejected_entries
        result["rejected_candidate_ids"] = rejected_candidate_ids
        result["approval_summary"] = _build_approval_summary(
            approved_candidates=approved_candidates,
            rejected_candidates=rejected_candidates,
        )
        result["confirm_status"] = _derive_confirm_status(
            success=bool(result.get("success")),
            requested_fields=requested_fields,
            applied_fields=applied_fields,
        )
        result["relation_summary"] = _build_relation_summary(
            source_path=journal_path_obj,
            approved_entries=approved_entries,
            applied_fields=applied_fields,
        )


def _build_frontmatter_updates(
    *,
    location: str | None,
    weather: str | None,
    resolved_approved_entries: list[str],
) -> tuple[Dict[str, Any], list[str]]:
    """Build frontmatter updates dict and track requested field names."""
    frontmatter_updates: Dict[str, Any] = {}
    requested_fields: list[str] = []
    if location is not None:
        frontmatter_updates["location"] = location
        requested_fields.append("location")
    if weather is not None:
        frontmatter_updates["weather"] = weather
        requested_fields.append("weather")
    if resolved_approved_entries:
        frontmatter_updates["add_related_entries"] = resolved_approved_entries
        requested_fields.append("related_entries")
    return frontmatter_updates, requested_fields


# ---------------------------------------------------------------------------
# Module-level private helpers (extracted from write_journal)
# ---------------------------------------------------------------------------


def _init_write_result() -> Dict[str, Any]:
    """Initialize the default result dict for write_journal."""
    return {
        "success": False,
        "write_outcome": WriteOutcome.FAILED,
        "journal_path": None,
        "updated_indices": [],
        "index_status": IndexStatus.NOT_STARTED,
        "side_effects_status": SideEffectsStatus.NOT_STARTED,
        "side_effects": [],
        "attachments_processed": [],
        "attachments_detected_count": 0,
        "attachments_processed_count": 0,
        "attachments_failed_count": 0,
        "location_used": "",
        "location_auto_filled": False,
        "weather_used": "",
        "weather_auto_filled": False,
        "needs_confirmation": False,
        "confirmation_message": "",
        "confirmation": {},
        "related_candidates": [],
        "new_entities_detected": [],
        "entity_candidates": [],
        "entity_candidate_pool": {},
        "error": None,
        "metrics": {},
    }


def _record_side_effect(
    result: Dict[str, Any],
    *,
    name: str,
    phase: str,
    status: SideEffectExecutionStatus,
    blocking: bool,
    error: str | None = None,
    recovery_strategy: str | None = None,
) -> None:
    """Append one machine-readable execution fact to the write result."""
    record: Dict[str, Any] = {
        "name": name,
        "phase": phase,
        "status": status,
        "blocking": blocking,
    }
    if error is not None:
        record["error"] = error
    if recovery_strategy is not None:
        record["recovery_strategy"] = recovery_strategy
    result["side_effects"].append(record)


def _update_side_effect_record(
    result: Dict[str, Any],
    *,
    name: str,
    status: SideEffectExecutionStatus,
    error: str | None = None,
    recovery_strategy: str | None = None,
    phase: str | None = None,
    blocking: bool | None = None,
) -> None:
    """Update the final state of an already-recorded side effect."""
    record = next(item for item in reversed(result["side_effects"]) if item["name"] == name)
    record["status"] = status
    if phase is not None:
        record["phase"] = phase
    if blocking is not None:
        record["blocking"] = blocking
    if error is None:
        record.pop("error", None)
    else:
        record["error"] = error
    if recovery_strategy is None:
        record.pop("recovery_strategy", None)
    else:
        record["recovery_strategy"] = recovery_strategy


def _resolve_location_and_weather(
    data: Dict[str, Any],
    result: Dict[str, Any],
    timer: Timer,
) -> tuple[str, str]:
    """Resolve location and weather from explicit metadata, user data, or auto-fill.

    Mutates result dict with location_used/location_auto_filled/weather_used/
    weather_auto_filled.  Returns (location, weather).
    """
    content = data.get("content", "")
    explicit_metadata = extract_explicit_metadata_from_content(content)
    # NOTE: data["content"] is NOT overwritten — user content is preserved 100%.

    # 第一层：用户提及为准
    # 第二层：自动填充
    location = explicit_metadata.get("location") or data.get("location", "").strip()
    if not location:
        location = get_default_location()
        result["location_auto_filled"] = True
        result["location_used"] = location
        location_for_weather = normalize_location(location)
    else:
        location_for_weather = normalize_location(location)
        result["location_used"] = location
    data["location"] = location

    weather = explicit_metadata.get("weather") or data.get("weather", "").strip()
    if not weather:
        logger.debug(f"查询天气：location={location_for_weather}")
        with timer.measure("weather_query"):
            queried_weather = query_weather_for_location(location_for_weather, data.get("date", ""))
        if queried_weather:
            weather = queried_weather
            result["weather_used"] = weather
            result["weather_auto_filled"] = True
            logger.info(f"天气查询成功：{weather}")
        else:
            weather = ""
            result["weather_used"] = ""
            logger.warning("天气查询失败，使用空值")
    else:
        result["weather_used"] = weather
        logger.debug(f"使用用户提供的天气：{weather}")

    data["weather"] = weather
    return location, weather


def _enrich_entities(
    data: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    """Enrich entity data and detect new entities."""
    try:
        entity_graph = load_entity_graph(resolve_user_data_dir() / "entity_graph.yaml")
    except EntityGraphValidationError as exc:
        logger.warning("Skipping entity graph enrichment due to invalid graph: %s", exc)
        entity_graph = []
    data["entities"] = content_analysis.match_entities(
        data.get("people"),
        data.get("location"),
        data.get("project"),
        entity_graph,
    )
    result["new_entities_detected"] = _detect_new_entities(data)
    result["entity_candidates"] = extract_entity_candidates(
        metadata=data,
        content=str(data.get("content", "")),
        graph=entity_graph,
    )


def _resolve_related_candidates(
    data: Dict[str, Any],
    result: Dict[str, Any],
    location: str,
    weather: str,
) -> None:
    """Find related entries and build initial confirmation payload."""
    metadata_conn = init_metadata_cache()
    try:
        candidate_entries = get_all_cached_metadata(metadata_conn)
    finally:
        metadata_conn.close()
    current_entry = {
        "date": data.get("date"),
        "topic": data.get("topic"),
        "people": data.get("people"),
        "project": data.get("project"),
        "tags": data.get("tags"),
        "related_entries": data.get("related_entries", []),
    }
    result["related_candidates"] = suggest_related_entries(current_entry, candidate_entries)
    result["confirmation"] = _build_confirmation_payload(
        journal_path=None,
        location=location,
        weather=weather,
        related_candidates=result["related_candidates"],
    )
    result["prepared_metadata"] = dict(data)


def _generate_journal_path(
    date_str: str,
    timer: Timer,
) -> tuple[Path, Path, int, int]:
    """Generate the journal file path under lock with retry.

    Returns (journal_path, month_dir, year, month).
    """
    max_retries = 3
    journal_path = None
    month_dir = None
    year = 0
    month = 0

    with timer.measure("sequence_gen"):
        for retry in range(max_retries):
            year, month = get_year_month(date_str)
            sequence = get_next_sequence(date_str)

            month_dir = get_journals_dir() / str(year) / f"{month:02d}"
            filename = generate_filename(date_str, sequence)
            journal_path = month_dir / filename

            logger.debug(f"尝试生成文件名：{filename}, retry={retry}")

            if journal_path.exists() and retry < max_retries - 1:
                logger.debug(f"文件已存在，准备重试：{journal_path}")
                continue
            break

    assert journal_path is not None
    assert month_dir is not None
    return journal_path, month_dir, year, month


def _process_attachments(
    data: Dict[str, Any],
    result: Dict[str, Any],
    date_str: str,
    dry_run: bool,
    timer: Timer,
) -> AttachmentStaging | None:
    """Detect and process attachments from content and explicit data."""
    content = data.get("content", "")
    auto_detected_paths = extract_file_paths_from_content(content)
    result["attachments_detected_count"] = len(auto_detected_paths)
    logger.debug(f"从内容中检测到 {len(auto_detected_paths)} 个附件路径")

    attachments = data.get("attachments", [])
    try:
        with timer.measure("attachments"):
            if dry_run:
                processed_attachments = process_attachments(
                    attachments, date_str, True, auto_detected_paths
                )
                staging = None
            else:
                staging = stage_attachments(attachments, date_str, auto_detected_paths)
                processed_attachments = staging.processed
    except (OSError, IOError, RuntimeError) as exc:
        leftover_paths = list(getattr(exc, "leftover_paths", []))
        _record_side_effect(
            result,
            name="attachments",
            phase="pre_commit",
            status=SideEffectExecutionStatus.FAILED,
            blocking=True,
            error=str(exc),
            recovery_strategy=(
                f"remove the transaction staging path(s) {', '.join(leftover_paths)}, "
                "then fix the attachment source and retry the write"
                if leftover_paths
                else "fix the attachment source and retry the write"
            ),
        )
        raise
    result["attachments_processed"] = processed_attachments
    stored_attachments = [
        att for att in processed_attachments if not att.get("error") and att.get("rel_path")
    ]
    result["attachments_processed_count"] = len(stored_attachments)
    result["attachments_failed_count"] = (
        len(processed_attachments) - result["attachments_processed_count"]
    )
    if processed_attachments:
        logger.info(f"处理了 {len(processed_attachments)} 个附件")

    data["attachments"] = stored_attachments
    if not processed_attachments:
        attachment_status = SideEffectExecutionStatus.SKIPPED
    elif result["attachments_failed_count"]:
        attachment_status = SideEffectExecutionStatus.FAILED
    else:
        attachment_status = SideEffectExecutionStatus.COMPLETE
    _record_side_effect(
        result,
        name="attachments",
        phase="pre_commit",
        status=attachment_status,
        blocking=not bool(result["attachments_failed_count"]),
        error=(
            f"{result['attachments_failed_count']} attachment(s) failed"
            if result["attachments_failed_count"]
            else None
        ),
        recovery_strategy=(
            "fix attachment inputs and write a new journal only if no journal_path was returned"
            if result["attachments_failed_count"]
            else None
        ),
    )
    return staging


class PartialIndexUpdateError(RuntimeError):
    """A later legacy index failed after earlier artifacts were updated."""

    def __init__(self, message: str, updated_indices: list[str]):
        super().__init__(message)
        self.updated_indices = updated_indices


def _update_indices(
    *,
    topic: str | None,
    project: str | None,
    tags: list[str],
    journal_path: Path,
    data: Dict[str, Any],
    timer: Timer,
) -> list[str]:
    """Update topic, project, and tag indices. Raises on failure."""
    updated_indices: list[str] = []
    with timer.measure("index_update"):
        try:
            if topic:
                indices = update_topic_index(topic, journal_path, data)
                updated_indices.extend([str(i) for i in indices])

            if project:
                idx = update_project_index(project, journal_path, data)
                if idx:
                    updated_indices.append(str(idx))

            if tags:
                indices = update_tag_indices(tags, journal_path, data)
                updated_indices.extend([str(i) for i in indices])

        except (OSError, IOError, RuntimeError) as e:
            logger.error(f"索引更新失败：{e}")
            raise PartialIndexUpdateError(f"索引更新失败：{e}", list(updated_indices)) from e
    return updated_indices


def _update_metadata_relations(
    source_rel_path: str,
    data: Dict[str, Any],
) -> None:
    """Update metadata cache relations for a committed journal."""
    metadata_conn = init_metadata_cache()
    try:
        replace_entry_relations(
            metadata_conn,
            source_rel_path,
            data.get("related_entries", []),
        )
    finally:
        metadata_conn.close()


def _journal_rel_path(journal_path: Path) -> str:
    """Return the canonical relative path used by metadata and pending views."""
    return build_journal_path_fields(
        journal_path,
        journals_dir=get_journals_dir(),
        user_data_dir=resolve_user_data_dir(),
    )["rel_path"]


def _commit_journal_to_disk(
    *,
    data: Dict[str, Any],
    result: Dict[str, Any],
    journal_path: Path,
    month_dir: Path,
    year: int,
    month: int,
    full_content: str,
    timer: Timer,
    attachment_staging: AttachmentStaging | None,
) -> None:
    """Write journal file and update indices in a transactional manner."""
    temp_path = journal_path.with_suffix(".tmp")
    try:
        month_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"写入日志文件：{journal_path}")
        try:
            with timer.measure("file_write"):
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(full_content)
        except (OSError, IOError, RuntimeError) as exc:
            _record_side_effect(
                result,
                name="journal_stage",
                phase="pre_commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=True,
                error=str(exc),
                recovery_strategy="resolve the filesystem error, then retry the write",
            )
            raise
        _record_side_effect(
            result,
            name="journal_stage",
            phase="pre_commit",
            status=SideEffectExecutionStatus.COMPLETE,
            blocking=True,
        )

        if attachment_staging:
            publish_staged_attachments(attachment_staging)

        # 原子性重命名
        try:
            temp_path.replace(journal_path)
        except (OSError, IOError, RuntimeError) as exc:
            _record_side_effect(
                result,
                name="journal_commit",
                phase="commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=True,
                error=str(exc),
                recovery_strategy="retry the write after resolving the filesystem error",
            )
            raise
        _record_side_effect(
            result,
            name="journal_commit",
            phase="commit",
            status=SideEffectExecutionStatus.COMPLETE,
            blocking=True,
        )
        staging_cleanup_errors = discard_attachment_staging(attachment_staging)
        if staging_cleanup_errors:
            leftover_paths = "; ".join(staging_cleanup_errors)
            _update_side_effect_record(
                result,
                name="attachments",
                status=SideEffectExecutionStatus.FAILED,
                phase="post_commit",
                blocking=False,
                error=f"attachment staging cleanup failed: {leftover_paths}",
                recovery_strategy=f"remove the transaction staging path: {leftover_paths}",
            )
        result["journal_path"] = str(journal_path)
        logger.info(f"日志文件写入成功：{journal_path}")

        # Derived artifacts only observe journals after the durable commit.
        with timer.measure("abstract_update"):
            abstract_result = None
            abstract_error = None
            abstract_success = False
            try:
                abstract_result = update_monthly_abstract(year, month, False)
                if isinstance(abstract_result, dict) and abstract_result.get("success") is False:
                    abstract_error = str(
                        abstract_result.get("error") or "monthly abstract refresh failed"
                    )
                else:
                    abstract_success = True
            except Exception as exc:
                abstract_error = str(exc)
        _record_side_effect(
            result,
            name="monthly_abstract",
            phase="post_commit",
            status=(
                SideEffectExecutionStatus.COMPLETE
                if abstract_success
                else SideEffectExecutionStatus.FAILED
            ),
            blocking=False,
            error=abstract_error,
            recovery_strategy=(
                f"life-index abstract --month {year:04d}-{month:02d}" if abstract_error else None
            ),
        )

        try:
            updated_indices = _update_indices(
                topic=data.get("topic"),
                project=data.get("project"),
                tags=data.get("tags", []),
                journal_path=journal_path,
                data=data,
                timer=timer,
            )
        except Exception as exc:
            updated_indices = list(getattr(exc, "updated_indices", []))
            _record_side_effect(
                result,
                name="legacy_indices",
                phase="post_commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=False,
                error=str(exc),
                recovery_strategy="life-index generate-index",
            )
        else:
            _record_side_effect(
                result,
                name="legacy_indices",
                phase="post_commit",
                status=SideEffectExecutionStatus.COMPLETE,
                blocking=False,
            )

        try:
            source_rel_path = _journal_rel_path(journal_path)
        except Exception as exc:
            source_rel_path = None
            _record_side_effect(
                result,
                name="metadata_relations",
                phase="post_commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=False,
                error=str(exc),
                recovery_strategy="life-index index --rebuild",
            )
        # Metadata relations and pending freshness are independent post-commit facts.
        if source_rel_path is not None:
            try:
                _update_metadata_relations(source_rel_path, data)
            except Exception as exc:
                _record_side_effect(
                    result,
                    name="metadata_relations",
                    phase="post_commit",
                    status=SideEffectExecutionStatus.FAILED,
                    blocking=False,
                    error=str(exc),
                    recovery_strategy="life-index index --rebuild",
                )
            else:
                _record_side_effect(
                    result,
                    name="metadata_relations",
                    phase="post_commit",
                    status=SideEffectExecutionStatus.COMPLETE,
                    blocking=False,
                )

        try:
            if source_rel_path is None:
                raise RuntimeError("canonical journal rel_path is unavailable")
            mark_pending(source_rel_path)
        except Exception as exc:
            _record_side_effect(
                result,
                name="mark_pending",
                phase="post_commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=False,
                error=str(exc),
                recovery_strategy="life-index index --rebuild",
            )
        else:
            logger.info(f"已标记待索引更新: {source_rel_path}")
            _record_side_effect(
                result,
                name="mark_pending",
                phase="post_commit",
                status=SideEffectExecutionStatus.QUEUED,
                blocking=False,
            )

        # Refresh deterministic Index B navigation after the final file exists.
        try:
            with timer.measure("index_b_update"):
                index_b_result = refresh_index_b(False)
            index_b_success = bool(index_b_result.get("success"))
            index_b_error = (
                str(index_b_result.get("error") or "Index B refresh failed")
                if not index_b_success
                else None
            )
        except Exception as exc:
            index_b_result = {"success": False, "error": str(exc)}
            index_b_success = False
            index_b_error = str(exc)
        _record_side_effect(
            result,
            name="index_b",
            phase="post_commit",
            status=(
                SideEffectExecutionStatus.COMPLETE
                if index_b_success
                else SideEffectExecutionStatus.FAILED
            ),
            blocking=False,
            error=index_b_error,
            recovery_strategy=(
                "life-index index-tree ensure --json" if not index_b_success else None
            ),
        )

        result["monthly_abstract_updated"] = abstract_result
        result["index_b_updated"] = index_b_result
        if abstract_error:
            result["monthly_abstract_error"] = abstract_error
        result["updated_indices"] = updated_indices

    except (OSError, IOError, RuntimeError) as exc:
        if temp_path.exists():
            temp_path.unlink()
        journal_committed = any(
            record["name"] == "journal_commit" and record["status"] == "complete"
            for record in result["side_effects"]
        )
        if (
            not journal_committed
            and attachment_staging
            and attachment_staging.stage_root is not None
        ):
            compensation_errors = compensate_published_attachments(attachment_staging)
            if compensation_errors:
                _update_side_effect_record(
                    result,
                    name="attachments",
                    status=SideEffectExecutionStatus.FAILED,
                    error=f"{exc}; compensation failed: {'; '.join(compensation_errors)}",
                    recovery_strategy=(
                        "inspect and remove only the transaction-owned orphan attachment "
                        "path(s): "
                        f"{'; '.join(compensation_errors)}; then retry the write"
                    ),
                )
            elif isinstance(exc, FileExistsError):
                _update_side_effect_record(
                    result,
                    name="attachments",
                    status=SideEffectExecutionStatus.FAILED,
                    error=str(exc),
                    recovery_strategy=("retry the write; the existing attachment was not modified"),
                )
            else:
                _update_side_effect_record(
                    result,
                    name="attachments",
                    status=SideEffectExecutionStatus.COMPENSATED,
                    error=str(exc),
                    recovery_strategy="retry the write; no journal was committed",
                )
        else:
            cleanup_errors = discard_attachment_staging(attachment_staging)
            if cleanup_errors:
                logger.warning("attachment staging cleanup failed: %s", cleanup_errors)
        raise


def _build_post_write_confirmation(
    result: Dict[str, Any],
    journal_path: Path,
    location: str,
    weather: str,
) -> str | None:
    """Build the final confirmation message and payload after successful write."""
    result["needs_confirmation"] = True
    relation_lines = ""
    if result["related_candidates"]:
        candidate_lines = ["\n\n可考虑关联以下日志："]
        for index, candidate in enumerate(result["related_candidates"], start=1):
            candidate_lines.append(
                (
                    f"{index}. {candidate['rel_path']} | "
                    f"{candidate['date']} | {candidate['title']}"
                )
            )
        relation_lines = "\n".join(candidate_lines)

    result["confirmation"] = _build_confirmation_payload(
        journal_path=str(journal_path),
        location=location,
        weather=weather,
        related_candidates=result["related_candidates"],
    )
    snapshot_error = None
    try:
        _write_confirmation_candidate_snapshot(journal_path, result["related_candidates"])
    except Exception as e:
        snapshot_error = str(e)
        logger.warning(f"保存确认候选快照失败（不影响日志写入）：{e}")

    result["confirmation_message"] = (
        f"日志已保存至：{journal_path}\n\n"
        f"本次记录地点：{location}\n"
        f"- 天气：{weather if weather else '（未获取）'}\n\n"
        f"请确认这个地点是否正确。"
        f"如果不对，请告诉我正确地点。"
        f"我会基于新地点更新地点和天气。"
        f"{relation_lines}"
    )
    return snapshot_error


def _set_committed_confirmation_fallback(
    result: Dict[str, Any],
    journal_path: Path,
    location: str,
    weather: str,
) -> None:
    """Keep a committed write actionable when confirmation assembly degrades."""
    result["journal_path"] = str(journal_path)
    result["needs_confirmation"] = True
    result["confirmation"] = {
        "location": location,
        "weather": weather,
        "related_candidates": result.get("related_candidates", []),
        "journal_path": str(journal_path),
        "supports_related_entry_approval": True,
    }
    result["confirmation_message"] = (
        f"日志已保存至：{journal_path}\n\n" "请确认地点和天气；确认详情生成失败。"
    )


# ---------------------------------------------------------------------------
# Entity detection helper
# ---------------------------------------------------------------------------


def _detect_new_entities(data: Dict[str, Any]) -> list[str]:
    graph_path = resolve_user_data_dir() / "entity_graph.yaml"
    try:
        graph = load_entity_graph(graph_path)
    except EntityGraphValidationError as exc:
        logger.warning("Skipping entity detection due to invalid graph: %s", exc)
        return []
    if not graph:
        return []

    candidates: list[str] = []
    for key in ("people", "location", "project"):
        value = data.get(key)
        if isinstance(value, list):
            candidates.extend(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    new_entities: list[str] = []
    for candidate in candidates:
        if resolve_entity(candidate, graph) is None and candidate not in new_entities:
            new_entities.append(candidate)
    return new_entities


def extract_explicit_metadata_from_content(content: str) -> Dict[str, str]:
    """从正文中提取明确声明的元数据（地点/天气），不修改正文。

    仅做只读扫描：匹配行首的 "地点:"/"天气:" 等模式并提取值。
    调用方应将提取结果用于填充 data["location"]/data["weather"]，
    但 **不得** 用任何"清理后"的内容覆盖 data["content"]。
    """
    return _extract_explicit_metadata_from_content(content)


def _build_confirmation_payload(
    *,
    journal_path: str | None,
    location: str,
    weather: str,
    related_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "location": location,
        "weather": weather,
        "related_candidates": related_candidates,
        "journal_path": journal_path,
        "supports_related_entry_approval": True,
    }


def _resolve_candidates_or_fail(
    *,
    journal_path_obj: Path,
    refs: Sequence[str | int] | None,
    candidate_ids: Sequence[int] | None,
    candidate_context: list[dict[str, Any]] | None,
    approved_related_entries: list[str] | None,
) -> tuple[list[str], list[dict[str, Any]], list[int], dict[str, Any] | None]:
    """Resolve candidate refs and return error envelope on failure."""
    resolved, candidates, ids, error = _resolve_candidate_refs(
        refs, candidate_ids=candidate_ids, candidate_context=candidate_context
    )
    if error is not None:
        error.update(
            _build_confirm_failure_envelope(
                journal_path_obj=journal_path_obj,
                approved_related_entries=approved_related_entries,
            )
        )
    return resolved, candidates, ids, error


def _missing_journal_error(
    journal_path_obj: Path,
    approved_related_entries: list[str] | None,
) -> Dict[str, Any]:
    """Build the confirmation error returned when the journal file is missing."""
    error_result = create_error_response(
        ErrorCode.JOURNAL_NOT_FOUND,
        f"日志文件不存在：{journal_path_obj}",
        {"journal_path": str(journal_path_obj)},
        "请检查日志路径是否正确后重试",
    )
    error_result.update(
        _build_confirm_failure_envelope(
            journal_path_obj=journal_path_obj,
            approved_related_entries=approved_related_entries,
        )
    )
    return error_result


def apply_confirmation_updates(
    *,
    journal_path: str | Any,
    location: str | None = None,
    weather: str | None = None,
    approved_related_entries: list[str] | None = None,
    approved_related_candidate_ids: list[int] | None = None,
    rejected_related_entries: list[str | int] | None = None,
    rejected_related_candidate_ids: list[int] | None = None,
    candidate_context: list[dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Apply post-write confirmation decisions via edit_journal."""
    from ..edit_journal import edit_journal

    journal_path_obj = Path(journal_path)
    if not journal_path_obj.exists():
        return _missing_journal_error(journal_path_obj, approved_related_entries)

    effective_candidate_context = _confirmation_candidate_context(
        journal_path_obj,
        candidate_context=candidate_context,
        approved_related_entries=approved_related_entries,
        approved_related_candidate_ids=approved_related_candidate_ids,
        rejected_related_entries=rejected_related_entries,
        rejected_related_candidate_ids=rejected_related_candidate_ids,
    )

    (
        resolved_approved_entries,
        approved_candidates,
        approved_candidate_ids,
        approval_error,
    ) = _resolve_candidates_or_fail(
        journal_path_obj=journal_path_obj,
        refs=approved_related_entries,
        candidate_ids=approved_related_candidate_ids,
        candidate_context=effective_candidate_context,
        approved_related_entries=approved_related_entries,
    )
    if approval_error is not None:
        return approval_error

    (
        resolved_rejected_entries,
        rejected_candidates,
        rejected_candidate_ids,
        rejection_error,
    ) = _resolve_candidates_or_fail(
        journal_path_obj=journal_path_obj,
        refs=rejected_related_entries,
        candidate_ids=rejected_related_candidate_ids,
        candidate_context=effective_candidate_context,
        approved_related_entries=approved_related_entries,
    )
    if rejection_error is not None:
        return rejection_error

    frontmatter_updates, requested_fields = _build_frontmatter_updates(
        location=location,
        weather=weather,
        resolved_approved_entries=resolved_approved_entries,
    )

    result = edit_journal(
        journal_path=journal_path_obj,
        frontmatter_updates=frontmatter_updates,
    )
    _enrich_confirm_result(
        result=result,
        journal_path_obj=journal_path_obj,
        resolved_approved_entries=resolved_approved_entries,
        resolved_rejected_entries=resolved_rejected_entries,
        approved_candidates=approved_candidates,
        approved_candidate_ids=approved_candidate_ids,
        rejected_candidates=rejected_candidates,
        rejected_candidate_ids=rejected_candidate_ids,
        requested_fields=requested_fields,
    )

    return result


def _handle_dry_run(
    result: Dict[str, Any],
    journal_path: Path,
    location: str,
    weather: str,
    full_content: str,
    timer: Timer,
) -> Dict[str, Any]:
    """Handle dry_run early return: set path, preview, and metrics."""
    _record_side_effect(
        result,
        name="write_preview",
        phase="preview",
        status=SideEffectExecutionStatus.COMPLETE,
        blocking=False,
    )
    result.update(
        derive_write_statuses(
            result["side_effects"],
            needs_confirmation=result["needs_confirmation"],
            preview=True,
        )
    )
    result["journal_path"] = str(journal_path)
    result["confirmation"] = _build_confirmation_payload(
        journal_path=str(journal_path),
        location=location,
        weather=weather,
        related_candidates=result["related_candidates"],
    )
    result["content_preview"] = full_content[:500]
    timer.stop()
    result["metrics"] = timer.to_dict()
    return result


def write_journal(data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """Write a journal entry and return the agent-facing result envelope."""
    timer = Timer().start()
    result = _init_write_result()

    try:
        date_str = str(data.get("date") or "").strip()
        if not date_str:
            date_str = current_local_date_iso()
            data["date"] = date_str
            field_sources = data.get("field_sources")
            if not isinstance(field_sources, dict):
                field_sources = {}
                data["field_sources"] = field_sources
            field_sources["date"] = "auto"

        logger.info(f"开始写入日志：date={date_str}, title={data.get('title', 'N/A')}")

        location, weather = _resolve_location_and_weather(data, result, timer)
        _enrich_entities(data, result)
        _resolve_related_candidates(data, result, location, weather)

        logger.debug("获取文件锁...")
        with timer.measure("lock_acquire"):
            lock = FileLock(get_journals_lock_path(), timeout=FILE_LOCK_TIMEOUT_DEFAULT)

        try:
            with lock:
                journal_path, month_dir, year, month = _generate_journal_path(date_str, timer)
                attachment_staging = _process_attachments(data, result, date_str, dry_run, timer)
                try:
                    full_content = format_content(data)
                except (ValueError, OSError, IOError, RuntimeError) as exc:
                    if attachment_staging is not None and attachment_staging.stage_root is not None:
                        cleanup_errors = discard_attachment_staging(attachment_staging)
                        if cleanup_errors:
                            leftover_paths = "; ".join(cleanup_errors)
                            _update_side_effect_record(
                                result,
                                name="attachments",
                                status=SideEffectExecutionStatus.FAILED,
                                error=f"{exc}; staging cleanup failed: {leftover_paths}",
                                recovery_strategy=(
                                    f"remove the transaction staging path: {leftover_paths}; "
                                    "then fix the journal payload and retry the write"
                                ),
                            )
                        else:
                            _update_side_effect_record(
                                result,
                                name="attachments",
                                status=SideEffectExecutionStatus.COMPENSATED,
                                error=str(exc),
                                recovery_strategy=(
                                    "fix the journal payload, then retry the write; "
                                    "no journal was committed"
                                ),
                            )
                    raise

                if dry_run:
                    return _handle_dry_run(
                        result, journal_path, location, weather, full_content, timer
                    )

                _commit_journal_to_disk(
                    data=data,
                    result=result,
                    journal_path=journal_path,
                    month_dir=month_dir,
                    year=year,
                    month=month,
                    full_content=full_content,
                    timer=timer,
                    attachment_staging=attachment_staging,
                )
                try:
                    result["entity_candidate_pool"] = capture_write_time_candidates(
                        metadata=data,
                        candidates=result.get("entity_candidates", []),
                        journal_path=journal_path,
                    )
                except Exception as exc:
                    _record_side_effect(
                        result,
                        name="entity_candidates",
                        phase="post_commit",
                        status=SideEffectExecutionStatus.FAILED,
                        blocking=False,
                        error=str(exc),
                        recovery_strategy=(
                            "inspect the committed journal, then propose any missing "
                            "entity candidates with life-index entity --propose"
                        ),
                    )
                else:
                    _record_side_effect(
                        result,
                        name="entity_candidates",
                        phase="post_commit",
                        status=SideEffectExecutionStatus.COMPLETE,
                        blocking=False,
                    )

        except LockTimeoutError as e:
            logger.error(f"文件锁超时：{e}")
            return create_error_response(
                ErrorCode.LOCK_TIMEOUT,
                f"无法获取写入锁，请稍后重试：{e}",
                {
                    "lock_path": str(get_journals_lock_path()),
                    "timeout": FILE_LOCK_TIMEOUT_DEFAULT,
                },
                "等待几秒后重试，或检查是否有其他进程正在写入",
            )

        try:
            confirmation_snapshot_error = _build_post_write_confirmation(
                result, journal_path, location, weather
            )
        except Exception as exc:
            confirmation_snapshot_error = str(exc)
            _set_committed_confirmation_fallback(result, journal_path, location, weather)
            logger.warning("post-commit confirmation assembly failed: %s", exc)
        _record_side_effect(
            result,
            name="confirmation_snapshot",
            phase="post_commit",
            status=(
                SideEffectExecutionStatus.FAILED
                if confirmation_snapshot_error
                else SideEffectExecutionStatus.COMPLETE
            ),
            blocking=False,
            error=confirmation_snapshot_error,
            recovery_strategy=(
                "confirm this committed journal by journal_path"
                if confirmation_snapshot_error
                else None
            ),
        )

    except (ValueError, IOError, RuntimeError, OSError) as e:
        journal_committed = any(
            record.get("name") == "journal_commit" and record.get("status") == "complete"
            for record in result["side_effects"]
        )
        if journal_committed:
            _set_committed_confirmation_fallback(result, journal_path, location, weather)
            result["error"] = None
            logger.error("post-commit envelope assembly failed: %s", e, exc_info=True)
            _record_side_effect(
                result,
                name="postcommit_envelope",
                phase="post_commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=False,
                error=str(e),
                recovery_strategy="inspect this committed journal by journal_path",
            )
        else:
            logger.error(f"写入日志失败：{e}", exc_info=True)
            result["error"] = str(e)

    except Exception as exc:
        journal_committed = any(
            record.get("name") == "journal_commit" and record.get("status") == "complete"
            for record in result["side_effects"]
        )
        if not journal_committed:
            raise
        _set_committed_confirmation_fallback(result, journal_path, location, weather)
        result["error"] = None
        logger.error("post-commit envelope assembly failed: %s", exc, exc_info=True)
        _record_side_effect(
            result,
            name="postcommit_envelope",
            phase="post_commit",
            status=SideEffectExecutionStatus.FAILED,
            blocking=False,
            error=str(exc),
            recovery_strategy="inspect this committed journal by journal_path",
        )

    try:
        timer.stop()
        result["metrics"] = timer.to_dict()
    except Exception as exc:
        journal_committed = any(
            record.get("name") == "journal_commit" and record.get("status") == "complete"
            for record in result["side_effects"]
        )
        if not journal_committed:
            raise
        _record_side_effect(
            result,
            name="postcommit_envelope",
            phase="post_commit",
            status=SideEffectExecutionStatus.FAILED,
            blocking=False,
            error=str(exc),
            recovery_strategy="inspect this committed journal by journal_path",
        )

    try:
        result.update(
            derive_write_statuses(
                result["side_effects"],
                needs_confirmation=result["needs_confirmation"],
            )
        )
    except Exception as exc:
        journal_committed = any(
            record.get("name") == "journal_commit" and record.get("status") == "complete"
            for record in result["side_effects"]
        )
        if not journal_committed:
            raise
        _record_side_effect(
            result,
            name="postcommit_envelope",
            phase="post_commit",
            status=SideEffectExecutionStatus.FAILED,
            blocking=False,
            error=str(exc),
            recovery_strategy="inspect this committed journal by journal_path",
        )
        result.update(
            {
                "success": True,
                "write_outcome": WriteOutcome.SUCCESS_DEGRADED,
                "index_status": IndexStatus.DEGRADED,
                "side_effects_status": SideEffectsStatus.DEGRADED,
            }
        )

    if result["success"]:
        try:
            logger.info(f"写入完成，总耗时：{result['metrics'].get('total_ms', 0):.2f}ms")
        except Exception as exc:
            _record_side_effect(
                result,
                name="postcommit_envelope",
                phase="post_commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=False,
                error=str(exc),
                recovery_strategy="inspect this committed journal by journal_path",
            )
            result.update(
                {
                    "success": True,
                    "write_outcome": WriteOutcome.SUCCESS_DEGRADED,
                    "index_status": IndexStatus.DEGRADED,
                    "side_effects_status": SideEffectsStatus.DEGRADED,
                    "error": None,
                }
            )

    return result
