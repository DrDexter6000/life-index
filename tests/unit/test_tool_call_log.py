from __future__ import annotations

import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_tool_call_log_requires_validation_mode_and_explicit_path(
    tmp_path: Path, monkeypatch
) -> None:
    from tools.lib.tool_call_log import emit_tool_call_log

    log_path = tmp_path / "tool-calls.jsonl"
    monkeypatch.delenv("LIFE_INDEX_VALIDATION_MODE", raising=False)
    monkeypatch.setenv("LIFE_INDEX_TOOL_CALL_LOG", str(log_path))

    emit_tool_call_log(
        "index-tree.navigate",
        params={"from": "2026-03"},
        result={"count": 1},
        elapsed_ms=1.2,
        success=True,
    )

    assert not log_path.exists()

    monkeypatch.setenv("LIFE_INDEX_VALIDATION_MODE", "1")
    monkeypatch.delenv("LIFE_INDEX_TOOL_CALL_LOG", raising=False)

    emit_tool_call_log(
        "index-tree.navigate",
        params={"from": "2026-03"},
        result={"count": 1},
        elapsed_ms=1.2,
        success=True,
    )

    assert not log_path.exists()


def test_tool_call_log_writes_bounded_sanitized_jsonl(tmp_path: Path, monkeypatch) -> None:
    from tools.lib.tool_call_log import emit_tool_call_log

    log_path = tmp_path / "logs" / "tool-calls.jsonl"
    monkeypatch.setenv("LIFE_INDEX_VALIDATION_MODE", "1")
    monkeypatch.setenv("LIFE_INDEX_TOOL_CALL_LOG", str(log_path))

    emit_tool_call_log(
        "journal get",
        params={
            "path": "Journals/2026/03/life-index_2026-03-14_001.md",
            "api_key": "sk-secret",
            "absolute": "C:/Users/example/Documents/Life-Index/private.md",
            "long": "x" * 400,
        },
        result={"word_count": 123, "content": "must not be logged"},
        elapsed_ms=12.3456,
        success=True,
    )

    records = _read_jsonl(log_path)
    assert len(records) == 1
    record = records[0]
    assert record["tool"] == "journal get"
    assert record["success"] is True
    assert record["elapsed_ms"] == 12.346
    assert record["params"]["path"] == "Journals/2026/03/life-index_2026-03-14_001.md"
    assert record["params"]["api_key"] == "[redacted]"
    assert record["params"]["absolute"] == "[absolute-path-redacted]"
    assert record["params"]["long"].endswith("...[truncated]")
    assert record["result"] == {"word_count": 123}
    serialized = json.dumps(record, ensure_ascii=False)
    assert "sk-secret" not in serialized
    assert "must not be logged" not in serialized
    assert "C:/Users/example" not in serialized
