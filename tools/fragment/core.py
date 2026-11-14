#!/usr/bin/env python3
"""
Life Index - Fragment Tool - Core
fragment add 的写入事务。

`fragment add` 存的是用户本人的原话：没有标题、没有摘要、没有解释、没有
确认步骤、没有网络。事务复用 `write` 的共享助手（journals 锁、附件
staging/publish/compensate、序列号分配、FTS 行与 metadata-cache 行写穿），
按 import 复用，不移动、不修改那些函数。与 `write` 的三点不同：

1. 发布是 create-only 的（`os.link`，目标已存在即失败），路径被并发占用时
   顺延序号重试，有界次内仍冲突则报错，绝不覆盖既有文件；
2. 去重（`source.channel` + `source.message_id`）以文件为权威，窗口是候选日
   所在月与相邻两个月的 fragment 文件，不依赖 metadata cache；
3. 提交后只写穿 FTS 行与 metadata-cache 行；月/年生成的索引不重建
   （side effect 记 `skipped`），不做地点默认值、天气、entity 富化、关联
   候选、确认快照与 entity 候选捕获。
"""

import json
import os
import re
import tempfile
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..lib.config import FILE_LOCK_TIMEOUT_DEFAULT, resolve_user_data_dir
from ..lib.errors import ErrorCode, create_error_response
from ..lib.file_lock import FileLock, LockTimeoutError, get_journals_lock_path
from ..lib.frontmatter import format_frontmatter, frontmatter_is_unreadable, parse_frontmatter
from ..lib.journal_files import iter_month_journal_files
from ..lib.logger import get_logger
from ..lib.metadata_cache import upsert_journal_cache_row
from ..lib.path_contract import build_journal_path_fields
from ..lib.paths import get_journals_dir
from ..lib.pending_writes import mark_pending
from ..lib.search_index import upsert_fts_row
from ..lib.timing import Timer
from ..lib.workflow_signals import SideEffectExecutionStatus, derive_write_statuses
from ..write_journal.attachments import (
    AttachmentStaging,
    compensate_published_attachments,
    discard_attachment_staging,
    publish_staged_attachments,
    stage_attachments,
)
from ..write_journal.core import _generate_journal_path, _record_side_effect
from ..write_journal.utils import generate_filename, get_next_sequence

logger = get_logger(__name__)

# 顶层输入键。未知键一律拒绝并点名；这组键单独解释“碎片只存用户的原话与事实”。
_ALLOWED_TOP_LEVEL = frozenset(
    {
        "text",
        "expressed_at",
        "occurred",
        "source",
        "location",
        "place",
        "weather",
        "reply_to",
        "attachments",
    }
)
_FRAGMENT_ONLY_KEYS = frozenset(
    {"title", "topic", "people", "mood", "tags", "abstract", "project", "content"}
)
_FRAGMENT_ONLY_MESSAGE = (
    "a fragment holds only the user's own words and recorded facts; "
    "write remains the command for title-and-topic journals"
)

_SOURCE_KEYS = frozenset({"channel", "input", "persona", "message_id"})
_PLACE_PROVENANCE = frozenset({"device", "stated", "carried"})
_OCCURRED_PRECISIONS = frozenset({"year", "month", "day", "time"})

# occurred.from / occurred.to 接受的形状：年、年-月、日、完整 date-time。
_OCCURRED_SHAPES = (
    re.compile(r"^[0-9]{4}$"),
    re.compile(r"^[0-9]{4}-[0-9]{2}$"),
    re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
    re.compile(
        r"^[0-9]{4}-[0-9]{2}-[0-9]{2}"
        r"[T ][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?"
        r"(?:[Zz]|[+-][0-9]{2}:[0-9]{2})?$"
    ),
)

# 发布冲突时的有界重试次数（每次顺延一个序号；绝不 replace 既有文件）。
_MAX_PUBLISH_ATTEMPTS = 8

_DEDUPE_CHECK_COMPLETE = "complete"
_DEDUPE_CHECK_INCOMPLETE = "incomplete"
_DEDUPE_CHECK_NOT_REQUESTED = "not_requested"

_GENERATED_INDEXES_REASON = "a fragment write does not regenerate the monthly/yearly indexes"
_GENERATED_INDEXES_RECOVERY = "life-index generate-index --rebuild"
_HARD_LINK_PUBLISH_MESSAGE = (
    "the fragment could not be published because the data directory's filesystem "
    "refused a hard link; fragment add needs a hard link to publish without "
    "overwriting, and nothing was written"
)


class _InvalidFragment(ValueError):
    """One invalid input field; message names the field."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class _StagingFailed(RuntimeError):
    """An attachment could not be staged; the message names it."""

    def __init__(self, message: str, source_paths: List[str]):
        super().__init__(message)
        self.source_paths = source_paths


class _PublishCollision(RuntimeError):
    """Create-only publish collided on every allocated sequence number."""

    def __init__(self, last_path: Path):
        super().__init__(str(last_path))
        self.last_path = last_path


class _JournalPublishFailed(RuntimeError):
    """The data directory's filesystem refused the journal hard link."""

    def __init__(self, os_error: str):
        super().__init__(_HARD_LINK_PUBLISH_MESSAGE)
        self.os_error = os_error


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _require_object(value: Any, field: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise _InvalidFragment(f"{field} must be a JSON object", {"field": field})
    return value


def _reject_unknown_keys(obj: Dict[str, Any], allowed: frozenset[str], field: str) -> None:
    unknown = sorted(str(key) for key in obj if str(key) not in allowed)
    if unknown:
        raise _InvalidFragment(
            f"unknown {field} key(s): {', '.join(unknown)}",
            {"field": field, "unknown_keys": unknown},
        )


def _one_line_text(data: Dict[str, Any], field: str) -> str:
    """location / weather: one line of text; blank is rejected, never defaulted."""
    value = data.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise _InvalidFragment(f"{field} must be a string", {"field": field})
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise _InvalidFragment(
            f"{field} must be one non-blank line of text; "
            "blank strings are rejected, not treated as absent",
            {"field": field},
        )
    if "\n" in normalized:
        raise _InvalidFragment(f"{field} must be one line of text", {"field": field})
    return normalized


def _parse_offset_datetime(value: Any, field: str) -> datetime:
    """Really parse an ISO 8601 date-time that carries an offset."""
    if not isinstance(value, str):
        raise _InvalidFragment(f"{field} must be an ISO 8601 date-time string", {"field": field})
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError as exc:
        raise _InvalidFragment(
            f"{field} is not a valid ISO 8601 date-time: {value!r}",
            {"field": field, "value": value},
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _InvalidFragment(
            f"{field} must carry a UTC offset (e.g. +01:00 or Z)",
            {"field": field, "value": value},
        )
    return parsed


def _validate_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _InvalidFragment(
            f"{field} must be a non-empty string; blank strings are rejected, "
            "not treated as absent",
            {"field": field},
        )
    return value.strip()


def _validate_source(value: Any) -> Dict[str, str]:
    obj = _require_object(value, "source")
    _reject_unknown_keys(obj, _SOURCE_KEYS, "source")
    normalized: Dict[str, str] = {}
    for key in sorted(obj):
        normalized[key] = _validate_nonempty_string(obj[key], f"source.{key}")
    return normalized


def _validate_occurred_bound(value: Any, field: str) -> str:
    if not isinstance(value, str) or not any(shape.match(value) for shape in _OCCURRED_SHAPES):
        raise _InvalidFragment(
            f"{field} must be a year, YYYY-MM, YYYY-MM-DD, or a full date-time: {value!r}",
            {"field": field, "value": value},
        )
    # 形状已匹配；再证明日历真实（拒绝 2026-13-32 这类不可能日期）。
    day_text = value.split("T")[0].split(" ")[0]
    try:
        if len(day_text) == 10:
            date.fromisoformat(day_text)
        elif len(day_text) == 7:
            month = int(day_text[5:7])
            if not 1 <= month <= 12:
                raise ValueError("month out of range")
            int(day_text[:4])
        else:
            int(day_text)
        if "T" in value or " " in value.strip():
            datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError as exc:
        raise _InvalidFragment(
            f"{field} is not a real calendar value: {value!r}",
            {"field": field, "value": value},
        ) from exc
    return value


def _validate_occurred(value: Any) -> Dict[str, str]:
    obj = _require_object(value, "occurred")
    _reject_unknown_keys(obj, frozenset({"from", "to", "precision"}), "occurred")
    for bound in ("from", "to"):
        if bound not in obj:
            raise _InvalidFragment(f"occurred.{bound} is required", {"field": f"occurred.{bound}"})
        _validate_occurred_bound(obj[bound], f"occurred.{bound}")
    precision = obj.get("precision")
    if not isinstance(precision, str) or precision not in _OCCURRED_PRECISIONS:
        raise _InvalidFragment(
            "occurred.precision must be one of year|month|day|time",
            {"field": "occurred.precision", "value": precision},
        )
    return {"from": obj["from"], "to": obj["to"], "precision": precision}


def _validate_place(value: Any) -> Dict[str, Any]:
    obj = _require_object(value, "place")
    _reject_unknown_keys(
        obj, frozenset({"lat", "lon", "from", "observed_at", "carried_from"}), "place"
    )
    for key in ("lat", "lon", "from"):
        if key not in obj:
            raise _InvalidFragment(f"place.{key} is required", {"field": f"place.{key}"})
    for key, low, high in (("lat", -90.0, 90.0), ("lon", -180.0, 180.0)):
        raw = obj[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise _InvalidFragment(
                f"place.{key} must be a number", {"field": f"place.{key}", "value": raw}
            )
        if not low <= float(raw) <= high:
            raise _InvalidFragment(
                f"place.{key} must be within [{low}, {high}]: {raw!r}",
                {"field": f"place.{key}", "value": raw},
            )
    provenance = obj["from"]
    if not isinstance(provenance, str) or provenance not in _PLACE_PROVENANCE:
        raise _InvalidFragment(
            "place.from must be one of device|stated|carried",
            {"field": "place.from", "value": provenance},
        )
    normalized: Dict[str, Any] = {
        "lat": float(obj["lat"]),
        "lon": float(obj["lon"]),
        "from": provenance,
    }
    if "observed_at" in obj:
        normalized["observed_at"] = _parse_offset_datetime(
            obj["observed_at"], "place.observed_at"
        ).isoformat(timespec="seconds")
    if "carried_from" in obj:
        normalized["carried_from"] = _validate_nonempty_string(
            obj["carried_from"], "place.carried_from"
        )
    return normalized


def _validate_reply_to(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise _InvalidFragment("reply_to must be a list of objects", {"field": "reply_to"})
    entries: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        field = f"reply_to[{index}]"
        obj = _require_object(item, field)
        _reject_unknown_keys(obj, frozenset({"id", "version", "quote"}), field)
        if "id" not in obj:
            raise _InvalidFragment(f"{field}.id is required", {"field": f"{field}.id"})
        entry: Dict[str, Any] = {"id": _validate_nonempty_string(obj["id"], f"{field}.id")}
        if "version" in obj:
            version = obj["version"]
            if isinstance(version, bool) or not isinstance(version, (int, str)):
                raise _InvalidFragment(
                    f"{field}.version must be an integer or a non-empty string",
                    {"field": f"{field}.version"},
                )
            if isinstance(version, str) and not version.strip():
                raise _InvalidFragment(
                    f"{field}.version must be a non-empty string",
                    {"field": f"{field}.version"},
                )
            entry["version"] = version
        if "quote" in obj:
            if not isinstance(obj["quote"], str):
                raise _InvalidFragment(
                    f"{field}.quote must be a string", {"field": f"{field}.quote"}
                )
            entry["quote"] = obj["quote"]
        entries.append(entry)
    return entries


def _validate_attachments(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise _InvalidFragment("attachments must be a list of objects", {"field": "attachments"})
    entries: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        field = f"attachments[{index}]"
        obj = _require_object(item, field)
        if "source_url" in obj:
            raise _InvalidFragment(
                f"{field} uses source_url; fragment add never touches the network",
                {"field": field, "key": "source_url"},
            )
        _reject_unknown_keys(obj, frozenset({"source_path", "description"}), field)
        if "source_path" not in obj:
            raise _InvalidFragment(
                f"{field}.source_path is required", {"field": f"{field}.source_path"}
            )
        source_path = _validate_nonempty_string(obj["source_path"], f"{field}.source_path")
        if os.path.isdir(source_path):
            raise _InvalidFragment(
                f"{field}.source_path is a directory, not a file",
                {"field": f"{field}.source_path", "value": source_path},
            )
        entry: Dict[str, Any] = {"source_path": source_path}
        if "description" in obj:
            if not isinstance(obj["description"], str):
                raise _InvalidFragment(
                    f"{field}.description must be a string", {"field": f"{field}.description"}
                )
            entry["description"] = obj["description"]
        entries.append(entry)
    return entries


def _normalize_text_form(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def _normalize_text(value: Any) -> str:
    """LF endings, boundary whitespace removed; nothing else is touched."""
    if not isinstance(value, str):
        raise _InvalidFragment("text must be a string", {"field": "text"})
    normalized = _normalize_text_form(value)
    if not normalized:
        raise _InvalidFragment(
            "text is empty after trimming; a fragment stores the user's words",
            {"field": "text"},
        )
    return normalized


def _validate_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the fragment input object and normalize what will be stored."""
    unknown = sorted(str(key) for key in data if str(key) not in _ALLOWED_TOP_LEVEL)
    fragment_only = sorted(key for key in unknown if key in _FRAGMENT_ONLY_KEYS)
    if fragment_only:
        raise _InvalidFragment(
            f"fragment add rejects {', '.join(fragment_only)}: {_FRAGMENT_ONLY_MESSAGE}",
            {"field": fragment_only[0], "rejected_keys": fragment_only},
        )
    if unknown:
        raise _InvalidFragment(
            f"unknown input key(s): {', '.join(unknown)}",
            {"unknown_keys": unknown},
        )

    normalized: Dict[str, Any] = {"text": _normalize_text(data.get("text"))}
    if data.get("expressed_at") is not None:
        expressed = _parse_offset_datetime(data["expressed_at"], "expressed_at")
    else:
        # Default: now, machine local zone, with offset, seconds precision.
        expressed = datetime.now().astimezone()
    normalized["expressed_at"] = expressed
    if data.get("occurred") is not None:
        normalized["occurred"] = _validate_occurred(data["occurred"])
    if data.get("source") is not None:
        normalized["source"] = _validate_source(data["source"])
    location = _one_line_text(data, "location")
    if location:
        normalized["location"] = location
    if data.get("place") is not None:
        normalized["place"] = _validate_place(data["place"])
    weather = _one_line_text(data, "weather")
    if weather:
        normalized["weather"] = weather
    if data.get("reply_to") is not None:
        normalized["reply_to"] = _validate_reply_to(data["reply_to"])
    if data.get("attachments") is not None:
        normalized["attachments"] = _validate_attachments(data["attachments"])
    return normalized


# ---------------------------------------------------------------------------
# Stored form
# ---------------------------------------------------------------------------


def _frontmatter_payload(
    fragment_id: str,
    expressed: datetime,
    ingested: datetime,
    normalized: Dict[str, Any],
    stored_attachments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """The six fixed fields, then only the optional fields the caller supplied."""
    payload: Dict[str, Any] = {
        "kind": "fragment",
        "id": fragment_id,
        # date is expressed_at's own wall clock: the offset is removed, the
        # machine zone is never applied.
        "date": expressed.replace(tzinfo=None).isoformat(timespec="seconds"),
        "expressed_at": expressed.isoformat(timespec="seconds"),
        "ingested_at": ingested.isoformat(timespec="seconds"),
    }
    for key in ("occurred", "source", "location", "place", "weather", "reply_to"):
        if key in normalized:
            payload[key] = normalized[key]
    if stored_attachments:
        payload["attachments"] = stored_attachments
    return payload


def _render_fragment_file(payload: Dict[str, Any], text: str) -> bytes:
    """UTF-8, LF, no BOM, exactly one trailing newline; no title line."""
    return (format_frontmatter(payload) + "\n\n" + text + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Create-only publication
# ---------------------------------------------------------------------------


def _write_temp_bytes(month_dir: Path, content: bytes) -> Path:
    """Stage the fragment bytes beside the final path, fsynced, binary mode."""
    month_dir.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(month_dir), prefix=".fragment-", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, IOError):
        try:
            temp_path.unlink()
        except OSError as cleanup_exc:
            logger.error("fragment temp cleanup failed: %s", cleanup_exc)
        raise
    return temp_path


def _publish_create_only(temp_path: Path, final_path: Path) -> None:
    """Publish staged bytes via a hard link; fail if the name already exists.

    ``os.link`` never replaces an existing target, so a path allocated a moment
    ago cannot be overwritten by this transaction. Any other ``OSError`` is
    raised (no silent fallback to a clobbering replace).
    """
    os.link(temp_path, final_path)


# ---------------------------------------------------------------------------
# Dedupe (file authority)
# ---------------------------------------------------------------------------


def _shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _dedupe_window_dirs(year: int, month: int) -> List[Path]:
    journals_dir = get_journals_dir()
    return [
        journals_dir / str(shift_year) / f"{shift_month:02d}"
        for shift_year, shift_month in (
            _shift_month(year, month, -1),
            (year, month),
            _shift_month(year, month, 1),
        )
    ]


_DEDUPE_LITERAL_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _candidate_matches(
    channel: str, message_id: str, year: int, month: int
) -> Tuple[List[Dict[str, Any]], int]:
    """Scan the candidate month and its two neighbours for the same key.

    Only ASCII ids whose serialized form is always literal use the cheap text
    prefilter. Other ids parse every readable file. Unreadable directories,
    invalid UTF-8, and unreadable frontmatter are counted without refusing the
    user's words.
    """
    matches: List[Dict[str, Any]] = []
    unreadable = 0
    prefilter_safe = _DEDUPE_LITERAL_ID_RE.fullmatch(message_id) is not None
    quoted_id = json.dumps(message_id, ensure_ascii=False)
    for month_dir in _dedupe_window_dirs(year, month):
        try:
            with os.scandir(month_dir) as entries:
                for _entry in entries:
                    pass
        except FileNotFoundError:
            continue
        except OSError:
            unreadable += 1
            continue
        for path in iter_month_journal_files(month_dir):
            try:
                raw = path.read_bytes().decode("utf-8")
            except (OSError, UnicodeError):
                unreadable += 1
                continue
            if prefilter_safe and message_id not in raw and quoted_id not in raw:
                continue
            if frontmatter_is_unreadable(raw):
                unreadable += 1
                continue
            metadata, body = parse_frontmatter(raw)
            source = metadata.get("source")
            if not isinstance(source, dict):
                continue
            if source.get("channel") != channel or source.get("message_id") != message_id:
                continue
            stored_attachments = metadata.get("attachments")
            attachment_paths = (
                [
                    str(entry.get("rel_path"))
                    for entry in stored_attachments
                    if isinstance(entry, dict) and entry.get("rel_path")
                ]
                if isinstance(stored_attachments, list)
                else []
            )
            matches.append(
                {
                    "id": str(metadata.get("id") or ""),
                    "rel_path": _rel_path(path),
                    "journal_path": str(path),
                    "expressed_at": str(metadata.get("expressed_at") or ""),
                    "ingested_at": str(metadata.get("ingested_at") or ""),
                    "body": _normalize_text_form(body),
                    "attachments": attachment_paths,
                }
            )
    return matches, unreadable


def _conflict_error(matches: List[Dict[str, Any]]) -> Dict[str, Any]:
    existing = [{"id": match["id"], "rel_path": match["rel_path"]} for match in matches]
    missing_identity = next((match for match in matches if not match["id"]), None)
    if missing_identity is not None:
        detail = (
            "stored file with this source channel/message_id has no fragment id: "
            f"{missing_identity['rel_path']}"
        )
        recovery = "restore a non-empty fragment id in the named file, or use a distinct message_id"
    else:
        if len(matches) > 1:
            detail = (
                f"{len(matches)} fragments already carry this source "
                "channel/message_id with different text"
            )
        else:
            detail = "this source channel/message_id is already stored with different text"
        recovery = "reuse the stored fragment, or give this message a distinct message_id"
    return create_error_response(
        ErrorCode.FRAGMENT_KEY_CONFLICT,
        detail,
        {"existing": existing},
        recovery,
    )


# ---------------------------------------------------------------------------
# Transaction helpers
# ---------------------------------------------------------------------------


def _init_result() -> Dict[str, Any]:
    return {
        "success": False,
        "id": None,
        "journal_path": None,
        "rel_path": None,
        "expressed_at": None,
        "ingested_at": None,
        "deduplicated": False,
        "dedupe_check": _DEDUPE_CHECK_NOT_REQUESTED,
        "attachments": [],
        "side_effects": [],
        "error": None,
        "metrics": {},
    }


def _rel_path(journal_path: Path) -> str:
    return build_journal_path_fields(
        journal_path,
        journals_dir=get_journals_dir(),
        user_data_dir=resolve_user_data_dir(),
    )["rel_path"]


def _stage_fragment_attachments(
    result: Dict[str, Any],
    attachments: List[Dict[str, Any]],
    date_str: str,
    timer: Timer,
) -> Optional[AttachmentStaging]:
    """Stage every listed attachment, all-or-nothing, inside the lock."""
    if not attachments:
        _record_side_effect(
            result,
            name="attachments",
            phase="pre_commit",
            status=SideEffectExecutionStatus.SKIPPED,
            blocking=False,
        )
        return None
    try:
        with timer.measure("attachments"):
            staging = stage_attachments(attachments, date_str, None)
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
                "then fix the attachment source and retry"
                if leftover_paths
                else "fix the attachment source and retry"
            ),
        )
        raise
    failed: List[str] = []
    processed = staging.processed
    if len(processed) == len(attachments):
        for attachment, entry in zip(attachments, processed):
            if entry.get("error") or not entry.get("rel_path"):
                failed.append(str(attachment.get("source_path")))
    else:
        # 一个输入被共享 helper 静默跳过（如目录）；按无法全部入账处理。
        failed = [str(attachment.get("source_path")) for attachment in attachments]
    if failed:
        discard_attachment_staging(staging)
        _record_side_effect(
            result,
            name="attachments",
            phase="pre_commit",
            status=SideEffectExecutionStatus.FAILED,
            blocking=True,
            error=f"attachment(s) could not be staged: {', '.join(failed)}",
            recovery_strategy="fix the attachment source(s) and retry; nothing was committed",
        )
        raise _StagingFailed(f"attachment(s) could not be staged: {', '.join(failed)}", failed)
    _record_side_effect(
        result,
        name="attachments",
        phase="pre_commit",
        status=SideEffectExecutionStatus.COMPLETE,
        blocking=True,
    )
    return staging


def _allocate_and_publish(
    result: Dict[str, Any],
    temp_path: Path,
    date_str: str,
    timer: Timer,
    on_committed: Callable[[Path], None],
) -> Path:
    """Create-only publish; on collision take the next sequence, bounded."""
    month_dir: Optional[Path] = None
    journal_path: Optional[Path] = None
    with timer.measure("publish"):
        for attempt in range(_MAX_PUBLISH_ATTEMPTS):
            if attempt == 0:
                journal_path, month_dir, _year, _month = _generate_journal_path(date_str, timer)
            else:
                assert month_dir is not None
                sequence = get_next_sequence(date_str)
                journal_path = month_dir / generate_filename(date_str, sequence)
            assert journal_path is not None
            try:
                _publish_create_only(temp_path, journal_path)
            except FileExistsError:
                logger.debug(f"publish collision, allocating next sequence: {journal_path}")
                continue
            on_committed(journal_path)
            break
        else:
            last_path = journal_path if journal_path is not None else temp_path
            _record_side_effect(
                result,
                name="journal_commit",
                phase="commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=True,
                error=(
                    f"fragment publish collided {_MAX_PUBLISH_ATTEMPTS} times "
                    f"under {last_path.parent}"
                ),
                recovery_strategy="retry fragment add; existing files were not modified",
            )
            raise _PublishCollision(last_path)
    assert journal_path is not None
    _record_side_effect(
        result,
        name="journal_commit",
        phase="commit",
        status=SideEffectExecutionStatus.COMPLETE,
        blocking=True,
    )
    return journal_path


def _after_publish(result: Dict[str, Any], journal_path: Path, timer: Timer) -> None:
    """Best-effort FTS + cache write-through; never fail a committed fragment."""
    source_rel_path: Optional[str]
    try:
        source_rel_path = _rel_path(journal_path)
    except Exception as exc:  # noqa: BLE001 - a derived row failure never fails the fragment
        source_rel_path = None
        _record_side_effect(
            result,
            name="metadata_cache_row",
            phase="post_commit",
            status=SideEffectExecutionStatus.FAILED,
            blocking=False,
            error=str(exc),
            recovery_strategy="life-index index --rebuild",
        )
    else:
        result["rel_path"] = source_rel_path
    if source_rel_path is not None:
        try:
            with timer.measure("metadata_cache_row"):
                cached_row = upsert_journal_cache_row(journal_path, get_journals_dir())
            if cached_row is None:
                raise RuntimeError("metadata cache row upsert produced no row")
        except Exception as exc:  # noqa: BLE001
            _record_side_effect(
                result,
                name="metadata_cache_row",
                phase="post_commit",
                status=SideEffectExecutionStatus.FAILED,
                blocking=False,
                error=str(exc),
                recovery_strategy="life-index index --rebuild",
            )
        else:
            _record_side_effect(
                result,
                name="metadata_cache_row",
                phase="post_commit",
                status=SideEffectExecutionStatus.COMPLETE,
                blocking=False,
            )

    fts_row_failed = False
    try:
        with timer.measure("fts_row"):
            fts_row_doc = upsert_fts_row(journal_path, get_journals_dir())
        if fts_row_doc is None:
            raise RuntimeError("FTS row write-through produced no row")
    except Exception as exc:  # noqa: BLE001
        fts_row_failed = True
        _record_side_effect(
            result,
            name="fts_row",
            phase="post_commit",
            status=SideEffectExecutionStatus.FAILED,
            blocking=False,
            error=str(exc),
            recovery_strategy="life-index index",
        )
    else:
        _record_side_effect(
            result,
            name="fts_row",
            phase="post_commit",
            status=SideEffectExecutionStatus.COMPLETE,
            blocking=False,
        )

    if not fts_row_failed:
        _record_side_effect(
            result,
            name="mark_pending",
            phase="post_commit",
            status=SideEffectExecutionStatus.SKIPPED,
            blocking=False,
        )
    else:
        try:
            if source_rel_path is None:
                raise RuntimeError("canonical fragment rel_path is unavailable")
            mark_pending(source_rel_path)
        except Exception as exc:  # noqa: BLE001
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
            _record_side_effect(
                result,
                name="mark_pending",
                phase="post_commit",
                status=SideEffectExecutionStatus.QUEUED,
                blocking=False,
            )

    # A fragment write does not regenerate the monthly/yearly generated
    # indexes or the navigation index; one recovery command refreshes them all.
    result["side_effects"].append(
        {
            "name": "generated_indexes",
            "phase": "post_commit",
            "status": SideEffectExecutionStatus.SKIPPED,
            "blocking": False,
            "reason": _GENERATED_INDEXES_REASON,
            "recovery_strategy": _GENERATED_INDEXES_RECOVERY,
        }
    )


def _deduplicated_envelope(
    result: Dict[str, Any], match: Dict[str, Any], dedupe_check: str, timer: Timer
) -> Dict[str, Any]:
    """Success envelope for a retry that was already stored; writes nothing."""
    result["side_effects"].append(
        {
            "name": "journal_commit",
            "phase": "commit",
            "status": SideEffectExecutionStatus.SKIPPED,
            "blocking": False,
            "reason": "already stored",
        }
    )
    result["side_effects"].append(
        {
            "name": "generated_indexes",
            "phase": "post_commit",
            "status": SideEffectExecutionStatus.SKIPPED,
            "blocking": False,
            "reason": _GENERATED_INDEXES_REASON,
            "recovery_strategy": _GENERATED_INDEXES_RECOVERY,
        }
    )
    result.update(
        {
            "success": True,
            "id": match["id"],
            "journal_path": match["journal_path"],
            "rel_path": match["rel_path"],
            "expressed_at": match["expressed_at"],
            "ingested_at": match["ingested_at"],
            "deduplicated": True,
            "dedupe_check": dedupe_check,
            "attachments": match["attachments"],
            # journal_commit is "skipped" by design, so derive_write_statuses
            # cannot express this outcome; these statuses describe this
            # invocation: nothing was written and nothing needs repair.
            "write_outcome": "success",
            "index_status": "not_started",
            "side_effects_status": "complete",
        }
    )
    timer.stop()
    result["metrics"] = timer.to_dict()
    return result


def _degrade_committed_envelope(result: Dict[str, Any], exc: Exception) -> None:
    """A committed fragment never turns into a failure."""
    result["error"] = None
    _record_side_effect(
        result,
        name="postcommit_envelope",
        phase="post_commit",
        status=SideEffectExecutionStatus.FAILED,
        blocking=False,
        error=str(exc),
        recovery_strategy="inspect this committed fragment by journal_path",
    )
    result.update(
        {
            "success": True,
            "write_outcome": "success_degraded",
            "index_status": "degraded",
            "side_effects_status": "degraded",
        }
    )


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def add_fragment(data: Dict[str, Any]) -> Dict[str, Any]:
    """Store the user's own words as a fragment and return the result envelope."""
    timer = Timer().start()
    result = _init_result()
    committed = False
    journal_path: Optional[Path] = None
    temp_path: Optional[Path] = None
    staging: Optional[AttachmentStaging] = None

    try:
        if not isinstance(data, dict):
            raise _InvalidFragment("fragment input must be a JSON object")
        normalized = _validate_input(data)
        text = normalized["text"]
        expressed = normalized["expressed_at"]
        ingested = datetime.now().astimezone()
        result["expressed_at"] = expressed.isoformat(timespec="seconds")
        result["ingested_at"] = ingested.isoformat(timespec="seconds")
        date_str = expressed.replace(tzinfo=None).isoformat(timespec="seconds")
        source: Dict[str, str] = dict(normalized.get("source") or {})
        channel = source.get("channel")
        message_id = source.get("message_id")
        attachments = normalized.get("attachments") or []

        with FileLock(get_journals_lock_path(), timeout=FILE_LOCK_TIMEOUT_DEFAULT):
            if channel and message_id:
                with timer.measure("dedupe_check"):
                    matches, unreadable = _candidate_matches(
                        channel, message_id, expressed.year, expressed.month
                    )
                if unreadable:
                    result["dedupe_check"] = _DEDUPE_CHECK_INCOMPLETE
                    result["dedupe_unreadable_count"] = unreadable
                else:
                    result["dedupe_check"] = _DEDUPE_CHECK_COMPLETE
                if any(not match["id"] for match in matches) or len(matches) > 1:
                    return _conflict_error(matches)
                if matches:
                    if matches[0]["body"] != text:
                        return _conflict_error(matches)
                    return _deduplicated_envelope(result, matches[0], result["dedupe_check"], timer)

            staging = _stage_fragment_attachments(result, attachments, date_str, timer)
            try:
                stored_attachments = list(staging.processed) if staging is not None else []
                fragment_id = uuid.uuid4().hex
                payload = _frontmatter_payload(
                    fragment_id, expressed, ingested, normalized, stored_attachments
                )
                content_bytes = _render_fragment_file(payload, text)
                month_dir = get_journals_dir() / str(expressed.year) / f"{expressed.month:02d}"
                try:
                    with timer.measure("file_write"):
                        temp_path = _write_temp_bytes(month_dir, content_bytes)
                except (OSError, IOError) as exc:
                    _record_side_effect(
                        result,
                        name="journal_stage",
                        phase="pre_commit",
                        status=SideEffectExecutionStatus.FAILED,
                        blocking=True,
                        error=str(exc),
                        recovery_strategy="resolve the filesystem error, then retry fragment add",
                    )
                    raise
                _record_side_effect(
                    result,
                    name="journal_stage",
                    phase="pre_commit",
                    status=SideEffectExecutionStatus.COMPLETE,
                    blocking=True,
                )

                if staging is not None:
                    try:
                        publish_staged_attachments(staging)
                    except (OSError, IOError, RuntimeError) as exc:
                        _record_side_effect(
                            result,
                            name="attachments",
                            phase="commit",
                            status=SideEffectExecutionStatus.FAILED,
                            blocking=True,
                            error=str(exc),
                            recovery_strategy=(
                                "retry fragment add; existing files were not modified"
                            ),
                        )
                        raise
                assert temp_path is not None

                def mark_committed(published_path: Path) -> None:
                    nonlocal committed, journal_path
                    committed = True
                    journal_path = published_path
                    result["id"] = fragment_id
                    result["journal_path"] = str(published_path)

                try:
                    journal_path = _allocate_and_publish(
                        result, temp_path, date_str, timer, mark_committed
                    )
                except _PublishCollision:
                    raise
                except (OSError, IOError) as exc:
                    if committed:
                        raise
                    _record_side_effect(
                        result,
                        name="journal_commit",
                        phase="commit",
                        status=SideEffectExecutionStatus.FAILED,
                        blocking=True,
                        error=_HARD_LINK_PUBLISH_MESSAGE,
                        recovery_strategy=(
                            "use a data directory on a filesystem that supports hard links, "
                            "then retry fragment add; nothing was written"
                        ),
                    )
                    raise _JournalPublishFailed(str(exc)) from exc
            finally:
                # A failure before publish leaves no journal file, no temp file,
                # and no transaction-owned staging bytes.
                if not committed:
                    if temp_path is not None and temp_path.exists():
                        try:
                            temp_path.unlink()
                        except OSError as cleanup_exc:
                            logger.error("fragment temp cleanup failed: %s", cleanup_exc)
                    if staging is not None:
                        cleanup_errors: List[str] = []
                        if staging.published_paths:
                            cleanup_errors = compensate_published_attachments(staging)
                        else:
                            cleanup_errors = discard_attachment_staging(staging)
                        if cleanup_errors:
                            logger.error(
                                "fragment transaction cleanup failed: %s",
                                "; ".join(cleanup_errors),
                            )

            assert temp_path is not None
            assert journal_path is not None
            result["id"] = fragment_id
            result["journal_path"] = str(journal_path)
            result["attachments"] = [
                str(entry.get("rel_path")) for entry in stored_attachments if entry.get("rel_path")
            ]
            try:
                temp_path.unlink()
            except OSError as exc:
                _record_side_effect(
                    result,
                    name="journal_cleanup",
                    phase="post_commit",
                    status=SideEffectExecutionStatus.FAILED,
                    blocking=False,
                    error=f"{temp_path}: {exc}",
                    recovery_strategy=f"remove the leftover temporary file {temp_path}",
                )
            cleanup_errors = discard_attachment_staging(staging)
            if cleanup_errors:
                _record_side_effect(
                    result,
                    name="attachment_cleanup",
                    phase="post_commit",
                    status=SideEffectExecutionStatus.FAILED,
                    blocking=False,
                    error="; ".join(cleanup_errors),
                    recovery_strategy="remove the named leftover attachment staging path(s)",
                )
            _after_publish(result, journal_path, timer)

    except _InvalidFragment as exc:
        error = create_error_response(
            ErrorCode.INVALID_INPUT,
            str(exc),
            exc.details,
            "fix the named field and retry; nothing was committed",
        )
        error["dedupe_check"] = result.get("dedupe_check")
        return error
    except _StagingFailed as exc:
        error = create_error_response(
            ErrorCode.ATTACHMENT_COPY_FAILED,
            str(exc),
            {"source_paths": exc.source_paths},
            "fix the attachment source(s) and retry; nothing was committed",
        )
        error["side_effects"] = result["side_effects"]
        error["dedupe_check"] = result.get("dedupe_check")
        return error
    except _PublishCollision as exc:
        error = create_error_response(
            ErrorCode.FRAGMENT_PUBLISH_COLLISION,
            f"fragment publish collided {_MAX_PUBLISH_ATTEMPTS} times near {exc.last_path}; "
            "existing files were not modified",
            {"last_allocated_path": str(exc.last_path)},
            "retry fragment add; existing files were not modified",
        )
        error["side_effects"] = result["side_effects"]
        error["dedupe_check"] = result.get("dedupe_check")
        return error
    except _JournalPublishFailed as exc:
        error = create_error_response(
            ErrorCode.WRITE_FAILED,
            str(exc),
            {"os_error": exc.os_error},
            "use a data directory on a filesystem that supports hard links, "
            "then retry fragment add; nothing was written",
        )
        error["side_effects"] = result["side_effects"]
        error["dedupe_check"] = result.get("dedupe_check")
        return error
    except LockTimeoutError as exc:
        logger.error(f"fragment add lock timeout: {exc}")
        return create_error_response(
            ErrorCode.LOCK_TIMEOUT,
            f"无法获取写入锁，请稍后重试：{exc}",
            {
                "lock_path": str(get_journals_lock_path()),
                "timeout": FILE_LOCK_TIMEOUT_DEFAULT,
            },
            "等待几秒后重试，或检查是否有其他进程正在写入",
        )
    except (OSError, IOError, RuntimeError) as exc:
        if committed:
            _degrade_committed_envelope(result, exc)
            timer.stop()
            result["metrics"] = timer.to_dict()
            return result
        logger.error(f"fragment add failed: {exc}", exc_info=True)
        error = create_error_response(
            ErrorCode.WRITE_FAILED,
            str(exc),
            None,
            "resolve the filesystem error, then retry fragment add; "
            "existing files were not modified",
        )
        error["side_effects"] = result["side_effects"]
        error["dedupe_check"] = result.get("dedupe_check")
        return error

    try:
        timer.stop()
        result["metrics"] = timer.to_dict()
        result.update(derive_write_statuses(result["side_effects"], needs_confirmation=False))
    except Exception as exc:  # noqa: BLE001 - a committed fragment never fails
        if not committed:
            raise
        _degrade_committed_envelope(result, exc)

    return result
