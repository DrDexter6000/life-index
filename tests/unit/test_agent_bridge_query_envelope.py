"""Unit tests for the V6-G2 rich Agent Bridge query envelope mapping layer."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.agent_bridge.query_envelope import (
    RICH_SCHEMA_VERSION,
    build_answer,
    build_evidence,
    build_provenance,
    clean_scaffold,
    map_to_rich_envelope,
)


def _grounded_internal() -> dict:
    return {
        "schema_version": "m35.agent_bridge_query.v0",
        "status": "GROUNDED",
        "answer": "You visited the park on June 4th.",
        "insights": [
            {
                "text": "The journal mentions a park visit.",
                "evidence_refs": ["Journals/2026/06/life-index_2026-06-04_001.md"],
            },
        ],
        "evidence_refs": ["Journals/2026/06/life-index_2026-06-04_001.md"],
        "gap": None,
        "provenance": {
            "transport": "acp",
            "model": "hermes-agent",
            "runtime": "fake-acp",
            "degraded": False,
        },
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def _degraded_internal() -> dict:
    return {
        "schema_version": "m35.agent_bridge_query.v0",
        "status": "UNGROUNDED",
        "answer": None,
        "insights": [],
        "evidence_refs": [],
        "gap": "Model output failed validation after retry.",
        "provenance": {
            "transport": "acp",
            "model": "unknown",
            "runtime": "acp",
            "degraded": True,
        },
        "usage": None,
    }


def _sample_scaffold() -> dict:
    return {
        "intent": "location",
        "date_from": "2026-06-03",
        "date_to": "2026-06-06",
        "queries": ["park"],
        "filters": {},
        "evidence_pack": {
            "items": [
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-04_001.md",
                        "title": "Park day",
                        "date": "2026-06-04",
                        "metadata": {"location": "Central Park"},
                    },
                    "snippet": "Spent the afternoon at Central Park.",
                },
                {
                    "document": {
                        "doc_id": "Journals/2026/06/life-index_2026-06-05_001.md",
                        "title": "Work day",
                        "date": "2026-06-05",
                    },
                    "snippet": "Busy day at the office.",
                },
            ],
        },
    }


def test_map_to_rich_envelope_grounded():
    """A grounded internal envelope maps to the full rich GUI contract."""
    result = map_to_rich_envelope(
        "Where did I go?",
        _sample_scaffold(),
        _grounded_internal(),
        host_agent="hermes-agent",
    )

    assert result["success"] is True
    assert result["schema_version"] == RICH_SCHEMA_VERSION
    assert result["command"] == "agent-bridge query"
    assert result["source"] == "host-agent"
    assert result["query"] == "Where did I go?"
    assert result["mode"] == "GROUNDED"
    assert result["scaffold"]["intent"] == "location"
    assert result["scaffold"]["date_from"] == "2026-06-03"
    assert result["events"] == []

    assert len(result["evidence"]) == 1
    ev = result["evidence"][0]
    assert ev["id"] == "2026/06/life-index_2026-06-04_001"
    assert ev["rel_path"] == "Journals/2026/06/life-index_2026-06-04_001.md"
    assert ev["title"] == "Park day"
    assert ev["date"] == "2026-06-04"
    assert "Central Park" in ev["snippet"]
    assert ev["metadata"] == {"location": "Central Park"}

    answer = result["answer"]
    assert answer["mode"] == "GROUNDED"
    assert answer["summary"] == "You visited the park on June 4th."
    assert len(answer["insights"]) == 1
    ins = answer["insights"][0]
    assert ins["theme"] == "location"
    assert ins["quote"] == "Spent the afternoon at Central Park."
    assert ins["date"] == "2026-06-04"
    assert ins["interpretation"] == "The journal mentions a park visit."
    assert ins["evidence_refs"] == ["2026/06/life-index_2026-06-04_001"]
    assert answer["gap"] is None
    assert answer["explanation"] is None

    assert result["synthesis"] == answer["summary"]
    assert result["provenance"] == {
        "evidence_source": "life-index search",
        "host_agent": "hermes-agent",
        "degraded": False,
    }


def test_map_to_rich_envelope_preserves_structured_magazine_insight():
    """Structured ACP insight quote/interpretation populate rich answer fields."""
    internal = _grounded_internal()
    internal["answer"] = "整体总结保留在 summary。"
    internal["insights"] = [
        {
            "theme": "work",
            "quote": "ACP agent selected this exact journal excerpt.",
            "interpretation": "ACP interpretation should be preserved.",
            "evidence_refs": ["Journals/2026/06/life-index_2026-06-04_001.md"],
        }
    ]

    result = map_to_rich_envelope(
        "What happened?",
        _sample_scaffold(),
        internal,
        host_agent="hermes-agent",
    )

    insight = result["answer"]["insights"][0]
    assert insight["theme"] == "work"
    assert insight["quote"] == "ACP agent selected this exact journal excerpt."
    assert insight["interpretation"] == "ACP interpretation should be preserved."
    assert insight["evidence_refs"] == ["2026/06/life-index_2026-06-04_001"]
    assert result["answer"]["summary"] == "整体总结保留在 summary。"


def test_map_to_rich_envelope_degraded():
    """A degraded internal envelope maps to a rich UNGROUNDED response."""
    result = map_to_rich_envelope(
        "Where did I go?",
        _sample_scaffold(),
        _degraded_internal(),
        host_agent="hermes-agent",
    )

    assert result["success"] is True
    assert result["mode"] == "UNGROUNDED"
    assert result["evidence"] == []
    assert result["answer"]["mode"] == "UNGROUNDED"
    assert result["answer"]["summary"] == ""
    assert result["answer"]["insights"] == []
    assert result["answer"]["gap"] == "Model output failed validation after retry."
    assert result["answer"]["explanation"] == "Model output failed validation after retry."
    assert result["synthesis"] == ""
    assert result["provenance"]["degraded"] is True


def test_build_evidence_filters_by_accepted_ids():
    """Only scaffold entries matching accepted IDs become evidence."""
    evidence = build_evidence(
        _sample_scaffold(),
        ["Journals/2026/06/life-index_2026-06-04_001.md"],
    )

    assert len(evidence) == 1
    assert evidence[0]["id"] == "2026/06/life-index_2026-06-04_001"


def test_build_evidence_skips_unknown_ids():
    """Unknown evidence IDs are silently dropped from evidence[]."""
    evidence = build_evidence(
        _sample_scaffold(),
        ["Journals/2026/06/does-not-exist.md"],
    )

    assert evidence == []


def test_build_evidence_loads_validated_agentic_refs_from_data_dir(tmp_path, monkeypatch):
    """Agentic citations outside the seed scaffold can still render evidence."""
    rel_path = "Journals/2026/06/life-index_2026-06-10_001.md"
    journal = tmp_path / rel_path
    journal.parent.mkdir(parents=True)
    journal.write_text(
        "---\n"
        "title: Agentic cited entry\n"
        "date: 2026-06-10\n"
        "location: Sandbox\n"
        "---\n\n"
        "This journal content was cited by the ACP agent.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    evidence = build_evidence({"evidence_pack": {"items": []}}, [rel_path])

    assert len(evidence) == 1
    assert evidence[0]["id"] == "2026/06/life-index_2026-06-10_001"
    assert evidence[0]["rel_path"] == rel_path
    assert evidence[0]["title"] == "Agentic cited entry"
    assert evidence[0]["date"] == "2026-06-10"
    assert "ACP agent" in evidence[0]["snippet"]
    assert evidence[0]["metadata"]["location"] == "Sandbox"


def test_build_evidence_from_filtered_results():
    """Evidence is also gathered from filtered_results when present."""
    scaffold = {
        "filtered_results": [
            {
                "rel_path": "Journals/2026/06/life-index_2026-06-05_001.md",
                "title": "Filtered work day",
                "date": "2026-06-05",
                "snippet": "Filtered result snippet.",
            },
        ],
    }
    evidence = build_evidence(
        scaffold,
        ["Journals/2026/06/life-index_2026-06-05_001.md"],
    )

    assert len(evidence) == 1
    assert evidence[0]["id"] == "2026/06/life-index_2026-06-05_001"
    assert evidence[0]["title"] == "Filtered work day"
    assert evidence[0]["snippet"] == "Filtered result snippet."


def test_build_answer_maps_insights_with_gui_ids():
    """Internal insight evidence_refs are normalized to GUI ids."""
    internal = {
        "status": "GROUNDED",
        "answer": "Answer.",
        "insights": [
            {
                "text": "Insight one.",
                "evidence_refs": ["Journals/2026/06/life-index_2026-06-04_001.md"],
            },
        ],
        "evidence_refs": ["Journals/2026/06/life-index_2026-06-04_001.md"],
        "gap": None,
    }
    evidence = build_evidence(_sample_scaffold(), internal["evidence_refs"])
    answer = build_answer(internal, evidence, _sample_scaffold())

    assert answer["insights"][0]["evidence_refs"] == ["2026/06/life-index_2026-06-04_001"]
    assert answer["insights"][0]["theme"] == "location"


def test_build_answer_filters_insight_refs_absent_from_evidence():
    """Insight evidence_refs cannot point to IDs absent from top-level evidence[]."""
    internal = {
        "status": "GROUNDED",
        "answer": "Answer.",
        "insights": [
            {
                "text": "Insight with one valid and one dangling ref.",
                "evidence_refs": [
                    "Journals/2026/06/life-index_2026-06-04_001.md",
                    "Journals/2026/06/does-not-exist.md",
                ],
            },
        ],
        "evidence_refs": ["Journals/2026/06/life-index_2026-06-04_001.md"],
        "gap": None,
    }
    evidence = build_evidence(_sample_scaffold(), internal["evidence_refs"])
    answer = build_answer(internal, evidence, _sample_scaffold())

    assert answer["insights"][0]["evidence_refs"] == ["2026/06/life-index_2026-06-04_001"]


def test_clean_scaffold_returns_subset():
    """clean_scaffold returns only the GUI-expected keys with defaults."""
    scaffold = {
        "intent": "recall",
        "date_from": "2026-01-01",
        "date_to": "2026-01-07",
        "queries": ["family"],
        "filters": {"topic": ["family"]},
        "extra_field": "ignored",
    }
    cleaned = clean_scaffold(scaffold)

    assert cleaned == {
        "intent": "recall",
        "date_from": "2026-01-01",
        "date_to": "2026-01-07",
        "queries": ["family"],
        "filters": {"topic": ["family"]},
    }


def test_clean_scaffold_defaults_for_missing_keys():
    """Missing scaffold keys default to empty values."""
    assert clean_scaffold({}) == {
        "intent": "",
        "date_from": "",
        "date_to": "",
        "queries": [],
        "filters": {},
    }


def test_clean_scaffold_tolerates_non_dict():
    """clean_scaffold returns defaults when scaffold is not a dict."""
    assert clean_scaffold(None) == {
        "intent": "",
        "date_from": "",
        "date_to": "",
        "queries": [],
        "filters": {},
    }


def test_clean_scaffold_falls_back_to_query_plan_sub_queries():
    """Real smart-search shape carries queries under query_plan.sub_queries."""
    scaffold = {
        "intent": "recall",
        "query_plan": {
            "raw_query": "What did we discuss at the offsite?",
            "expanded_query": "team offsite discussion",
            "sub_queries": ["team offsite", "offsite discussion"],
            "strategy": "keyword_only",
        },
    }
    cleaned = clean_scaffold(scaffold)
    assert cleaned["queries"] == ["team offsite", "offsite discussion"]
    assert cleaned["intent"] == "recall"


def test_clean_scaffold_prefers_top_level_queries_over_query_plan():
    """Explicit top-level queries win when both are present."""
    scaffold = {
        "queries": ["top level"],
        "query_plan": {"sub_queries": ["plan level"]},
    }
    cleaned = clean_scaffold(scaffold)
    assert cleaned["queries"] == ["top level"]


def test_clean_scaffold_includes_strategy_when_queries_empty():
    """When sub_queries is empty, strategy alone does not create queries."""
    scaffold = {
        "query_plan": {
            "sub_queries": [],
            "strategy": "keyword_with_semantic_fallback",
        }
    }
    cleaned = clean_scaffold(scaffold)
    assert cleaned["queries"] == []


def test_build_provenance_preserves_degraded_flag():
    """build_provenance surfaces the internal degraded boolean."""
    assert build_provenance({"provenance": {"degraded": True}})["degraded"] is True
    assert build_provenance({"provenance": {"degraded": False}})["degraded"] is False
    assert build_provenance({})["degraded"] is False


def test_map_to_rich_envelope_tolerates_invalid_status():
    """An invalid status falls back to UNGROUNDED in rich shape."""
    result = map_to_rich_envelope(
        "q",
        {},
        {"status": "HALLUCINATED", "answer": "oops", "insights": [], "evidence_refs": []},
    )
    assert result["mode"] == "UNGROUNDED"
    assert result["answer"]["mode"] == "UNGROUNDED"


def test_map_to_rich_envelope_empty_input():
    """map_to_rich_envelope returns a valid rich UNGROUNDED envelope for empty input."""
    result = map_to_rich_envelope("q", {}, {})
    assert result["success"] is True
    assert result["mode"] == "UNGROUNDED"
    assert result["evidence"] == []
    assert result["answer"]["summary"] == ""
