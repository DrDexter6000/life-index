#!/usr/bin/env python3
"""Unit tests for web/services/search.py."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from web.services.search import search_journals_web


def _make_item(file_path: Path, index: int) -> dict[str, object]:
    return {
        "journal_route_path": f"2026/03/test-{index}.md",
        "file_path": str(file_path),
        "path": str(file_path),
        "title": f"Result {index}",
        "snippet": f"snippet {index}",
        "rrf_score": 1.0 / (index + 1),
    }


def test_search_journals_web_caps_results_to_default_limit(tmp_path: Path) -> None:
    files = []
    for index in range(25):
        file_path = tmp_path / f"test-{index}.md"
        file_path.write_text("body", encoding="utf-8")
        files.append(_make_item(file_path, index))

    with patch(
        "web.services.search.hierarchical_search",
        return_value={
            "success": True,
            "merged_results": files,
            "total_found": 25,
            "performance": {"total_time_ms": 10.0},
        },
    ):
        result = asyncio.run(search_journals_web(query="python"))

    assert len(result["results"]) == 20


def test_search_journals_web_respects_custom_limit(tmp_path: Path) -> None:
    files = []
    for index in range(10):
        file_path = tmp_path / f"test-{index}.md"
        file_path.write_text("body", encoding="utf-8")
        files.append(_make_item(file_path, index))

    with patch(
        "web.services.search.hierarchical_search",
        return_value={
            "success": True,
            "merged_results": files,
            "total_found": 10,
            "performance": {"total_time_ms": 10.0},
        },
    ):
        result = asyncio.run(search_journals_web(query="python", limit=5))

    assert len(result["results"]) == 5


def test_search_journals_web_adds_ai_summary_when_provider_available(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "test-0.md"
    file_path.write_text("body", encoding="utf-8")
    provider = AsyncMock()
    provider.summarize_search.return_value = {
        "summary": "关于团团，你最近主要在回忆亲子相处片段。",
        "key_entries": [
            {
                "title": "想念团团",
                "date": "2026-03-07",
                "reason": "回看旧照片触发了强烈想念",
            }
        ],
        "time_span": "2026年3月",
    }

    with patch(
        "web.services.search.hierarchical_search",
        return_value={
            "success": True,
            "merged_results": [_make_item(file_path, 0)],
            "performance": {"total_time_ms": 10.0},
        },
    ):
        result = asyncio.run(search_journals_web(query="团团", provider=provider))

    assert result["ai_summary"]["summary"] == "关于团团，你最近主要在回忆亲子相处片段。"
    assert result["ai_summary"]["state"] == "ready"
    assert result["ai_summary"]["key_entries"][0]["title"] == "想念团团"
    assert result["ai_summary"]["time_span"] == "2026年3月"


def test_search_journals_web_returns_ai_unavailable_state_without_provider(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "test-0.md"
    file_path.write_text("body", encoding="utf-8")

    with patch(
        "web.services.search.hierarchical_search",
        return_value={
            "success": True,
            "merged_results": [_make_item(file_path, 0)],
            "performance": {"total_time_ms": 10.0},
        },
    ):
        result = asyncio.run(search_journals_web(query="团团", provider=None))

    assert result["ai_summary"]["state"] == "unavailable"
    assert result["ai_summary"]["summary"] is None


def test_search_journals_web_downgrades_ai_summary_on_provider_failure(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "test-0.md"
    file_path.write_text("body", encoding="utf-8")
    provider = AsyncMock()
    provider.summarize_search.side_effect = RuntimeError("llm timeout")

    with patch(
        "web.services.search.hierarchical_search",
        return_value={
            "success": True,
            "merged_results": [_make_item(file_path, 0)],
            "performance": {"total_time_ms": 10.0},
        },
    ):
        result = asyncio.run(search_journals_web(query="团团", provider=provider))

    assert result["ai_summary"]["state"] == "failed"
    assert "llm timeout" in result["ai_summary"]["message"]


def test_search_journals_web_excludes_summary_report_documents(tmp_path: Path) -> None:
    journal_file = tmp_path / "life-index_2026-03-20_001.md"
    summary_file = tmp_path / "monthly_report_2026-03.md"
    abstract_file = tmp_path / "monthly_abstract.md"
    yearly_report = tmp_path / "yearly_report_2026.md"
    for file_path in [journal_file, summary_file, abstract_file, yearly_report]:
        file_path.write_text("body", encoding="utf-8")

    with patch(
        "web.services.search.hierarchical_search",
        return_value={
            "success": True,
            "merged_results": [
                {
                    **_make_item(journal_file, 0),
                    "journal_route_path": "2026/03/life-index_2026-03-20_001.md",
                },
                {
                    **_make_item(summary_file, 1),
                    "journal_route_path": "2026/03/monthly_report_2026-03.md",
                },
                {
                    **_make_item(abstract_file, 2),
                    "journal_route_path": "2026/03/monthly_abstract.md",
                },
                {
                    **_make_item(yearly_report, 3),
                    "journal_route_path": "2026/yearly_report_2026.md",
                },
            ],
            "total_found": 4,
            "performance": {"total_time_ms": 10.0},
        },
    ):
        result = asyncio.run(search_journals_web(query="团团", semantic=False))

    assert [item["journal_route_path"] for item in result["results"]] == [
        "2026/03/life-index_2026-03-20_001.md"
    ]
    assert result["total_found"] == 1


def test_search_ai_journals_web_uses_single_canonical_search_call(
    tmp_path: Path,
) -> None:
    from web.services.search import search_ai_journals_web

    file_path = tmp_path / "test-0.md"
    file_path.write_text("body", encoding="utf-8")
    provider = AsyncMock()

    with patch(
        "web.services.search.search_journals_web",
        new=AsyncMock(
            return_value={
                "success": True,
                "results": [_make_item(file_path, 0)],
                "total_found": 1,
                "time_ms": 10.0,
                "error": None,
                "ai_summary": {
                    "state": "ready",
                    "summary": "过去30天有晚睡记录。",
                    "key_entries": [],
                    "time_span": "过去30天",
                },
            }
        ),
    ) as mock_search:
        result = asyncio.run(
            search_ai_journals_web(
                user_query="过去30天我有哪几天是晚于十点之后睡觉的",
                derived_queries=["睡眠不足", "凌晨", "晚睡", "睡眠不足"],
                date_from="2026-03-01",
                date_to="2026-03-30",
                provider=provider,
                limit=15,
            )
        )

    mock_search.assert_awaited_once_with(
        query="过去30天我有哪几天是晚于十点之后睡觉的 睡眠不足 凌晨 晚睡",
        date_from="2026-03-01",
        date_to="2026-03-30",
        level=3,
        semantic=True,
        limit=15,
        provider=provider,
    )
    assert result["derived_queries"] == ["睡眠不足", "凌晨", "晚睡"]
    assert result["display_query"] == "过去30天我有哪几天是晚于十点之后睡觉的"
