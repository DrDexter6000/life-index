"""Diagnostic summaries for search metrics JSONL files."""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .paths import resolve_user_data_dir

logger = logging.getLogger("search_diagnose")

_PIPELINE_KEYS = ("hybrid", "fts_only", "semantic_only", "degraded")
_LATENCY_OUTLIER_MS = 200.0
_MAX_DEGRADED_SEARCHES = 10
_MAX_LATENCY_OUTLIERS = 20


def _empty_report(days: int) -> dict[str, Any]:
    return {
        "success": True,
        "period_days": days,
        "total_searches": 0,
        "avg_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
        "pipeline_distribution": {key: 0 for key in _PIPELINE_KEYS},
        "warning_counts": {},
        "zero_result_queries": [],
        "degraded_searches": [],
        "latency_outliers": [],
    }


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _iter_month_keys(start: datetime, end: datetime) -> Iterable[str]:
    current = _month_start(start)
    last = _month_start(end)

    while current <= last:
        yield current.strftime("%Y-%m")
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)


def _candidate_metrics_paths(days: int, now: datetime) -> list[Path]:
    cutoff = now - timedelta(days=max(days, 0))
    metrics_dir = resolve_user_data_dir() / ".life-index" / "metrics"
    return [metrics_dir / f"{month_key}.jsonl" for month_key in _iter_month_keys(cutoff, now)]


def _safe_warning_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _safe_float(value: object) -> float:
    if not isinstance(value, (int, float, str)):
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    if not isinstance(value, (int, float, str)):
        return 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _load_filtered_records(days: int, now: datetime) -> list[dict[str, Any]]:
    cutoff = now - timedelta(days=max(days, 0))
    records: list[dict[str, Any]] = []

    for metrics_path in _candidate_metrics_paths(days, now):
        if not metrics_path.exists():
            continue

        try:
            with metrics_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed metrics line in %s", metrics_path)
                        continue

                    if not isinstance(payload, dict):
                        continue

                    timestamp = _parse_timestamp(payload.get("ts"))
                    if timestamp is None or timestamp < cutoff or timestamp > now:
                        continue

                    record = dict(payload)
                    record["_parsed_ts"] = timestamp
                    records.append(record)
        except OSError as exc:
            logger.warning("Failed to read metrics file %s: %s", metrics_path, exc)

    return records


def _p95_latency(latencies: list[float]) -> float:
    if not latencies:
        return 0.0

    ordered = sorted(latencies)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * 0.95) - 1))
    return ordered[index]


def diagnose_search(*, days: int = 7) -> dict[str, Any]:
    """Summarize recent search behavior from monthly JSONL metrics files."""

    safe_days = max(days, 0)
    report = _empty_report(safe_days)

    try:
        now = datetime.now(timezone.utc)
        records = _load_filtered_records(safe_days, now)
        if not records:
            return report

        latencies: list[float] = []
        warning_counts: dict[str, int] = {}
        zero_result_queries: list[str] = []
        seen_zero_result_queries: set[str] = set()
        degraded_searches: list[dict[str, Any]] = []
        latency_outliers: list[dict[str, Any]] = []
        pipeline_distribution = {key: 0 for key in _PIPELINE_KEYS}

        for record in records:
            latency_ms = _safe_float(record.get("latency_ms"))
            latencies.append(latency_ms)

            pipeline_signal = str(record.get("pipeline_signal") or "")
            if pipeline_signal in pipeline_distribution:
                pipeline_distribution[pipeline_signal] += 1

            warnings = _safe_warning_list(record.get("warnings"))
            for warning in warnings:
                warning_counts[warning] = warning_counts.get(warning, 0) + 1

            query = str(record.get("query") or "")
            if _safe_int(record.get("result_count")) == 0 and query not in seen_zero_result_queries:
                seen_zero_result_queries.add(query)
                zero_result_queries.append(query)

            if pipeline_signal == "degraded":
                degraded_searches.append(
                    {
                        "ts": str(record.get("ts") or ""),
                        "query": query,
                        "warnings": warnings,
                    }
                )

            if latency_ms > _LATENCY_OUTLIER_MS:
                latency_outliers.append(
                    {
                        "ts": str(record.get("ts") or ""),
                        "query": query,
                        "latency_ms": latency_ms,
                    }
                )

        degraded_searches.sort(key=lambda item: str(item["ts"]), reverse=True)
        latency_outliers.sort(key=lambda item: str(item["ts"]), reverse=True)

        report.update(
            {
                "total_searches": len(records),
                "avg_latency_ms": round(sum(latencies) / len(latencies), 1),
                "p95_latency_ms": _p95_latency(latencies),
                "pipeline_distribution": pipeline_distribution,
                "warning_counts": warning_counts,
                "zero_result_queries": zero_result_queries,
                "degraded_searches": degraded_searches[:_MAX_DEGRADED_SEARCHES],
                "latency_outliers": latency_outliers[:_MAX_LATENCY_OUTLIERS],
            }
        )
        return report
    except Exception as exc:  # pragma: no cover - defensive safety guarantee
        logger.error("Failed to diagnose search metrics: %s", exc)
        return report
