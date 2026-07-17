"""Validation-only JSONL tool-call logging for runtime diagnostics."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_LOG_BYTES = 5_000_000
_MAX_STRING_CHARS = 240
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "token",
    "secret",
    "password",
    "credential",
    ".env",
)
_CONTENT_KEY_PARTS = (
    "content",
    "body",
    "raw",
    "answer",
    "delta",
    "metadata",
)
_ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\|//)")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _enabled_log_path() -> Path | None:
    if os.environ.get("LIFE_INDEX_VALIDATION_MODE") != "1":
        return None
    configured = os.environ.get("LIFE_INDEX_TOOL_CALL_LOG")
    if not configured:
        return None
    return Path(configured)


def _paths_overlap(first: Path, second: Path) -> bool:
    """Return whether two resolved paths share a containment boundary."""
    try:
        first.relative_to(second)
        return True
    except ValueError:
        try:
            second.relative_to(first)
            return True
        except ValueError:
            return False


def _is_safe_log_target(log_path: Path, forbidden_root: Path | str | None) -> bool:
    """Reject a target that resolves into or overlaps a protected data root."""
    if forbidden_root is None:
        return True
    try:
        resolved_root = Path(forbidden_root).resolve(strict=True)
        resolved_parent = log_path.parent.resolve(strict=False)
        resolved_target = log_path.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False
    return not (
        _paths_overlap(resolved_parent, resolved_root)
        or _paths_overlap(resolved_target, resolved_root)
    )


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _is_content_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in _CONTENT_KEY_PARTS)


def _sanitize_value(value: Any, *, drop_content_keys: bool = False) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if _is_sensitive_key(key_str):
                sanitized[key_str] = "[redacted]"
                continue
            if drop_content_keys and _is_content_key(key_str):
                continue
            sanitized[key_str] = _sanitize_value(item, drop_content_keys=drop_content_keys)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item, drop_content_keys=drop_content_keys) for item in value[:50]]
    if isinstance(value, tuple):
        return [_sanitize_value(item, drop_content_keys=drop_content_keys) for item in value[:50]]
    if isinstance(value, (str, Path)):
        text = str(value)
        if _ABSOLUTE_PATH_RE.match(text):
            return "[absolute-path-redacted]"
        if len(text) > _MAX_STRING_CHARS:
            return text[:_MAX_STRING_CHARS] + "...[truncated]"
        return text
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)


def emit_tool_call_log(
    tool: str,
    *,
    params: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    elapsed_ms: float | None = None,
    success: bool = True,
    error_code: str | None = None,
    forbidden_root: Path | str | None = None,
) -> None:
    """Append one sanitized tool-call record when validation logging is enabled.

    This diagnostic sink is intentionally outside answer, grounding, and SSE
    paths. It is gated by validation mode plus an explicit log path and is
    fire-and-forget so ordinary CLI behavior remains unchanged.  Callers with
    a protected data boundary can provide ``forbidden_root``; a log target
    that resolves into or overlaps it is silently rejected.
    """

    log_path = _enabled_log_path()
    if log_path is None:
        return
    if not _is_safe_log_target(log_path, forbidden_root):
        return

    try:
        if log_path.exists() and log_path.stat().st_size > _MAX_LOG_BYTES:
            return

        record: dict[str, Any] = {
            "ts": _utc_timestamp(),
            "tool": str(tool),
            "success": bool(success),
            "params": _sanitize_value(params or {}),
            "result": _sanitize_value(result or {}, drop_content_keys=True),
        }
        if elapsed_ms is not None:
            record["elapsed_ms"] = round(float(elapsed_ms), 3)
        if error_code:
            record["error_code"] = str(error_code)

        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        return
