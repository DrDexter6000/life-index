"""Semantic/vector compatibility flags are deprecated no-ops."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.lib.index_freshness import FreshnessReport


@pytest.fixture(autouse=True)
def _isolated_search_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    graph_path = tmp_path / "entity_graph.yaml"
    graph_path.write_text("entities: []\nrelations: []\n", encoding="utf-8")
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    with (
        patch(
            "tools.lib.index_freshness.check_full_freshness",
            return_value=FreshnessReport(
                fts_fresh=True,
                vector_fresh=True,
                overall_fresh=True,
                issues=[],
            ),
        ),
        patch("tools.lib.pending_writes.has_pending", return_value=False),
    ):
        yield


def _keyword_results(count: int):
    l3 = [{"path": f"Journals/2026/01/item_{i}.md", "title": f"item {i}"} for i in range(count)]
    return ([], [], l3, False, count, {"l1_time_ms": 0.0, "l2_time_ms": 0.0, "l3_time_ms": 1.0})


def test_search_semantic_flag_is_deprecated_keyword_noop():
    import tools.search_journals.core as core
    from tools.search_journals.core import hierarchical_search

    assert not hasattr(core, "run_semantic_pipeline")

    with (
        patch("tools.search_journals.core.run_keyword_pipeline", return_value=_keyword_results(1)),
        patch(
            "tools.search_journals.core._filter_results_by_candidates", side_effect=lambda x, _: x
        ),
        patch(
            "tools.search_journals.core.merge_and_rank_results",
            side_effect=lambda _l1, _l2, l3, *_args, **_kwargs: l3,
        ),
    ):
        result = hierarchical_search(
            query="test query",
            semantic=True,
            semantic_policy="hybrid",
            semantic_weight=7.0,
        )

    assert [item["path"] for item in result["merged_results"]] == ["Journals/2026/01/item_0.md"]
    assert result["semantic_results"] == []
    assert result["semantic_available"] is False
    assert result["semantic_fallback_used"] is False
    assert result["semantic_effective_policy"] == "deprecated_noop"
    assert any("deprecated_noop" in warning for warning in result["warnings"])


def test_smart_search_does_not_request_semantic_fallback(monkeypatch: pytest.MonkeyPatch):
    from tools.search_journals.orchestrator import SmartSearchOrchestrator

    calls: list[dict] = []

    def fake_search(**kwargs):
        calls.append(kwargs)
        return {
            "success": True,
            "merged_results": [],
            "total_available": 0,
            "performance": {},
            "warnings": [],
        }

    monkeypatch.setattr("tools.search_journals.orchestrator._get_search_fn", lambda: fake_search)
    orch = SmartSearchOrchestrator(llm_client=None)

    result = orch.execute_search(
        {
            "rewritten_query": "女儿回忆",
            "sub_queries": ["女儿", "回忆"],
            "semantic_fallback_query": "女儿回忆",
            "search_plan": {},
        }
    )

    assert calls
    assert all(call.get("semantic") is not True for call in calls)
    assert result["semantic_fallback_used"] is False
    assert result["semantic_fallback_query"] is None


def test_index_semantic_options_do_not_build_vectors(monkeypatch: pytest.MonkeyPatch):
    import tools.build_index as build_index

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", "unused")
    monkeypatch.setattr(build_index, "get_index_lock_path", lambda: Path("unused.lock"))
    lock = MagicMock()
    lock.__enter__ = MagicMock(return_value=lock)
    lock.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(build_index, "FileLock", lambda *_args, **_kwargs: lock)
    monkeypatch.setattr(build_index, "write_manifest", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        build_index, "update_fts_index", lambda incremental=True: {"success": True, "added": 1}
    )

    result = build_index.build_all(incremental=True, fts_only=False, vec_only=True)

    assert result["success"] is True
    assert result["vector"] is None
    assert result["semantic_status"] == "disabled"
    assert any("deprecated_noop" in warning for warning in result["warnings"])
