#!/usr/bin/env python3

import json
from importlib import import_module
from datetime import datetime, timezone
from pathlib import Path


def _metrics_file_path(base_dir: Path) -> Path:
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    return base_dir / ".life-index" / "metrics" / f"{month_key}.jsonl"


def _sample_result(
    *,
    query: str = "用户原始查询",
    expanded_query: str | None = "展开后查询",
    semantic_enabled: bool = True,
    semantic_available: bool = True,
    fts_count: int = 3,
    semantic_count: int = 2,
    warnings: list[str] | None = None,
    entity_hints_count: int = 1,
) -> dict:
    query_params: dict[str, object] = {
        "query": query,
        "semantic": semantic_enabled,
    }
    if expanded_query is not None:
        query_params["expanded_query"] = expanded_query

    return {
        "query_params": query_params,
        "performance": {"total_time_ms": 42.5},
        "total_found": fts_count + semantic_count,
        "l3_results": [{"path": f"fts-{index}.md"} for index in range(fts_count)],
        "semantic_results": [
            {"path": f"semantic-{index}.md"} for index in range(semantic_count)
        ],
        "semantic_available": semantic_available,
        "warnings": warnings or [],
        "entity_hints": [{} for _ in range(entity_hints_count)],
    }


def _read_metrics_lines(base_dir: Path) -> list[dict]:
    metrics_path = _metrics_file_path(base_dir)
    return [
        json.loads(line)
        for line in metrics_path.read_text(encoding="utf-8").splitlines()
    ]


def test_emit_creates_jsonl_file(isolated_data_dir: Path) -> None:
    emit_search_metrics = import_module("tools.lib.search_metrics").emit_search_metrics

    emit_search_metrics(_sample_result())

    metrics_path = _metrics_file_path(isolated_data_dir)
    assert metrics_path.exists()

    payload = _read_metrics_lines(isolated_data_dir)[0]
    assert payload["query"] == "用户原始查询"
    assert payload["expanded_query"] == "展开后查询"
    assert payload["latency_ms"] == 42.5
    assert payload["result_count"] == 5
    assert payload["fts_results"] == 3
    assert payload["semantic_results"] == 2
    assert payload["entity_hints_count"] == 1
    assert payload["warnings"] == []
    assert len(payload["trace_id"]) == 8


def test_emit_appends_multiple_entries(isolated_data_dir: Path) -> None:
    emit_search_metrics = import_module("tools.lib.search_metrics").emit_search_metrics

    emit_search_metrics(_sample_result(query="第一次"))
    emit_search_metrics(_sample_result(query="第二次"))

    lines = _read_metrics_lines(isolated_data_dir)
    assert len(lines) == 2
    assert lines[0]["query"] == "第一次"
    assert lines[1]["query"] == "第二次"


def test_pipeline_signal_hybrid(isolated_data_dir: Path) -> None:
    emit_search_metrics = import_module("tools.lib.search_metrics").emit_search_metrics

    emit_search_metrics(_sample_result(fts_count=3, semantic_count=2))

    payload = _read_metrics_lines(isolated_data_dir)[0]
    assert payload["pipeline_signal"] == "hybrid"


def test_pipeline_signal_fts_only(isolated_data_dir: Path) -> None:
    emit_search_metrics = import_module("tools.lib.search_metrics").emit_search_metrics

    emit_search_metrics(
        _sample_result(fts_count=3, semantic_count=0, semantic_enabled=True)
    )

    payload = _read_metrics_lines(isolated_data_dir)[0]
    assert payload["pipeline_signal"] == "fts_only"


def test_pipeline_signal_degraded(isolated_data_dir: Path) -> None:
    emit_search_metrics = import_module("tools.lib.search_metrics").emit_search_metrics

    emit_search_metrics(
        _sample_result(
            fts_count=3,
            semantic_count=0,
            semantic_enabled=True,
            semantic_available=False,
            warnings=["semantic_unavailable: 向量索引未建立"],
        )
    )

    payload = _read_metrics_lines(isolated_data_dir)[0]
    assert payload["pipeline_signal"] == "degraded"


def test_emit_does_not_crash_on_error(monkeypatch) -> None:
    search_metrics = import_module("tools.lib.search_metrics")

    def _raise_error() -> Path:
        raise OSError("boom")

    monkeypatch.setattr(search_metrics, "resolve_user_data_dir", _raise_error)

    search_metrics.emit_search_metrics(_sample_result())


def test_metrics_respects_data_dir_override(monkeypatch, tmp_path: Path) -> None:
    emit_search_metrics = import_module("tools.lib.search_metrics").emit_search_metrics

    override_dir = tmp_path / "override-data"
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(override_dir))

    emit_search_metrics(_sample_result(query="override"))

    metrics_path = _metrics_file_path(override_dir)
    assert metrics_path.exists()
    payload = [
        json.loads(line)
        for line in metrics_path.read_text(encoding="utf-8").splitlines()
    ][0]
    assert payload["query"] == "override"
