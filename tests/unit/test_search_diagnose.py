#!/usr/bin/env python3

import json
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path


def _iso_timestamp(days_ago: int, *, hours_ago: int = 0) -> str:
    timestamp = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)
    return timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_metrics_record(base_dir: Path, record: dict[str, object]) -> None:
    month_key = str(record["ts"])[:7]
    metrics_path = base_dir / ".life-index" / "metrics" / f"{month_key}.jsonl"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _sample_record(
    *,
    ts: str,
    query: str,
    latency_ms: float,
    result_count: int,
    pipeline_signal: str,
    warnings: list[str] | None = None,
) -> dict[str, object]:
    return {
        "ts": ts,
        "query": query,
        "expanded_query": query,
        "latency_ms": latency_ms,
        "result_count": result_count,
        "pipeline_signal": pipeline_signal,
        "fts_results": 1,
        "semantic_results": 1,
        "warnings": warnings or [],
        "entity_hints_count": 0,
        "trace_id": "trace123",
    }


def test_diagnose_empty_metrics_dir(isolated_data_dir: Path) -> None:
    diagnose_search = import_module("tools.lib.search_diagnose").diagnose_search

    report = diagnose_search(days=7)

    assert report == {
        "success": True,
        "period_days": 7,
        "total_searches": 0,
        "avg_latency_ms": 0.0,
        "p95_latency_ms": 0.0,
        "pipeline_distribution": {
            "hybrid": 0,
            "fts_only": 0,
            "semantic_only": 0,
            "degraded": 0,
        },
        "warning_counts": {},
        "zero_result_queries": [],
        "degraded_searches": [],
        "latency_outliers": [],
    }


def test_diagnose_reads_jsonl(isolated_data_dir: Path) -> None:
    diagnose_search = import_module("tools.lib.search_diagnose").diagnose_search

    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(0, hours_ago=1),
            query="OpenClaw",
            latency_ms=50.0,
            result_count=3,
            pipeline_signal="hybrid",
        ),
    )
    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(1),
            query="乐乐",
            latency_ms=150.0,
            result_count=2,
            pipeline_signal="fts_only",
        ),
    )

    report = diagnose_search(days=7)

    assert report["success"] is True
    assert report["period_days"] == 7
    assert report["total_searches"] == 2
    assert report["avg_latency_ms"] == 100.0
    assert report["p95_latency_ms"] == 150.0


def test_diagnose_pipeline_distribution(isolated_data_dir: Path) -> None:
    diagnose_search = import_module("tools.lib.search_diagnose").diagnose_search

    for index, signal in enumerate(["hybrid", "fts_only", "semantic_only", "degraded"]):
        _write_metrics_record(
            isolated_data_dir,
            _sample_record(
                ts=_iso_timestamp(index),
                query=f"query-{signal}",
                latency_ms=20.0 + index,
                result_count=1,
                pipeline_signal=signal,
            ),
        )

    report = diagnose_search(days=7)

    assert report["pipeline_distribution"] == {
        "hybrid": 1,
        "fts_only": 1,
        "semantic_only": 1,
        "degraded": 1,
    }


def test_diagnose_warning_aggregation(isolated_data_dir: Path) -> None:
    diagnose_search = import_module("tools.lib.search_diagnose").diagnose_search

    warning_a = "semantic_unavailable: 向量索引未建立"
    warning_b = "semantic_disabled: 用户通过 --no-semantic 禁用语义搜索"
    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(0),
            query="q1",
            latency_ms=10.0,
            result_count=1,
            pipeline_signal="degraded",
            warnings=[warning_a, warning_b],
        ),
    )
    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(1),
            query="q2",
            latency_ms=20.0,
            result_count=1,
            pipeline_signal="fts_only",
            warnings=[warning_a],
        ),
    )

    report = diagnose_search(days=7)

    assert report["warning_counts"] == {
        warning_a: 2,
        warning_b: 1,
    }


def test_diagnose_zero_result_queries(isolated_data_dir: Path) -> None:
    diagnose_search = import_module("tools.lib.search_diagnose").diagnose_search

    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(0),
            query="人生碎片",
            latency_ms=30.0,
            result_count=0,
            pipeline_signal="hybrid",
        ),
    )
    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(1),
            query="兴奋",
            latency_ms=40.0,
            result_count=0,
            pipeline_signal="hybrid",
        ),
    )
    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(2),
            query="人生碎片",
            latency_ms=50.0,
            result_count=0,
            pipeline_signal="hybrid",
        ),
    )

    report = diagnose_search(days=7)

    assert sorted(report["zero_result_queries"]) == sorted(["人生碎片", "兴奋"])


def test_diagnose_latency_outliers(isolated_data_dir: Path) -> None:
    diagnose_search = import_module("tools.lib.search_diagnose").diagnose_search

    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(0, hours_ago=2),
            query="slow-old",
            latency_ms=250.0,
            result_count=1,
            pipeline_signal="hybrid",
        ),
    )
    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(0, hours_ago=1),
            query="slow-new",
            latency_ms=450.2,
            result_count=1,
            pipeline_signal="hybrid",
        ),
    )
    _write_metrics_record(
        isolated_data_dir,
        _sample_record(
            ts=_iso_timestamp(0),
            query="fast",
            latency_ms=120.0,
            result_count=1,
            pipeline_signal="hybrid",
        ),
    )

    report = diagnose_search(days=7)

    assert report["latency_outliers"] == [
        {
            "ts": _iso_timestamp(0, hours_ago=1),
            "query": "slow-new",
            "latency_ms": 450.2,
        },
        {
            "ts": _iso_timestamp(0, hours_ago=2),
            "query": "slow-old",
            "latency_ms": 250.0,
        },
    ]


def test_diagnose_days_filter(isolated_data_dir: Path) -> None:
    diagnose_search = import_module("tools.lib.search_diagnose").diagnose_search

    recent_record = _sample_record(
        ts=_iso_timestamp(2),
        query="recent",
        latency_ms=42.0,
        result_count=0,
        pipeline_signal="degraded",
        warnings=["semantic_unavailable: 向量索引未建立"],
    )
    old_record = _sample_record(
        ts=_iso_timestamp(10),
        query="old",
        latency_ms=500.0,
        result_count=0,
        pipeline_signal="degraded",
        warnings=["semantic_unavailable: 向量索引未建立"],
    )
    _write_metrics_record(isolated_data_dir, recent_record)
    _write_metrics_record(isolated_data_dir, old_record)

    report = diagnose_search(days=7)

    assert report["total_searches"] == 1
    assert report["zero_result_queries"] == ["recent"]
    assert report["degraded_searches"] == [
        {
            "ts": recent_record["ts"],
            "query": "recent",
            "warnings": ["semantic_unavailable: 向量索引未建立"],
        }
    ]
