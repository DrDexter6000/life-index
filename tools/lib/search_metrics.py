"""Structured JSONL metrics emission for search invocations."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import resolve_user_data_dir


logger = logging.getLogger("search_metrics")


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _current_metrics_path() -> Path:
    metrics_dir = resolve_user_data_dir() / ".life-index" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    return metrics_dir / f"{month_key}.jsonl"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _warning_list(result: dict[str, Any]) -> list[str]:
    warnings = _as_list(result.get("warnings"))
    return [str(item) for item in warnings]


def _pipeline_signal(
    *,
    fts_results: int,
    semantic_results: int,
    semantic_enabled: bool,
    warnings: list[str],
) -> str:
    has_semantic_warning = any(
        warning.startswith("semantic_unavailable:") for warning in warnings
    )

    if semantic_enabled and has_semantic_warning:
        return "degraded"
    if fts_results > 0 and semantic_results > 0:
        return "hybrid"
    if semantic_results > 0 and fts_results == 0:
        return "semantic_only"
    if fts_results > 0 and semantic_results == 0:
        return "fts_only"
    if semantic_enabled:
        return "hybrid"
    return "fts_only"


def _build_metrics_record(result: dict[str, Any]) -> dict[str, Any]:
    query_params = _as_dict(result.get("query_params"))
    performance = _as_dict(result.get("performance"))
    warnings = _warning_list(result)
    fts_results = len(_as_list(result.get("l3_results")))
    semantic_results = len(_as_list(result.get("semantic_results")))
    semantic_enabled = bool(
        query_params.get("semantic", result.get("semantic_available"))
    )

    return {
        "ts": _utc_timestamp(),
        "query": str(query_params.get("query") or ""),
        "expanded_query": str(query_params.get("expanded_query") or ""),
        "latency_ms": float(performance.get("total_time_ms") or 0.0),
        "result_count": int(result.get("total_found") or 0),
        "pipeline_signal": _pipeline_signal(
            fts_results=fts_results,
            semantic_results=semantic_results,
            semantic_enabled=semantic_enabled,
            warnings=warnings,
        ),
        "fts_results": fts_results,
        "semantic_results": semantic_results,
        "warnings": warnings,
        "entity_hints_count": len(_as_list(result.get("entity_hints"))),
        "trace_id": uuid.uuid4().hex[:8],
    }


def emit_search_metrics(result: dict[str, Any]) -> None:
    """Append one structured search metrics record to monthly JSONL.

    This function is fire-and-forget by design and must never raise.
    """

    try:
        record = _build_metrics_record(result)
        metrics_path = _current_metrics_path()
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - defensive safety guarantee
        logger.error("Failed to emit search metrics: %s", exc)
