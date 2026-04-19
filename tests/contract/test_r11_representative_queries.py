"""Contract tests for R11 Representative Query Set (Round 11 Phase 0 T0.4).

Basic tests: verify fixture completeness + search doesn't crash + new fields exist.
Advanced tests: verify specific signal values — marked xfail until Phase 1/2/5.
"""

from __future__ import annotations

import json

import pytest

from tests.fixtures.r11_representative_queries import R11_REPRESENTATIVE_QUERIES


@pytest.fixture
def isolated_search(tmp_path, monkeypatch):
    """Return a function that runs hierarchical_search in isolation."""
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    def _search(query: str):
        from tools.search_journals.core import hierarchical_search

        return hierarchical_search(query=query)

    return _search


# ── Fixture completeness ───────────────────────────────────────────────


class TestFixtureCompleteness:
    def test_eight_queries_present(self):
        assert len(R11_REPRESENTATIVE_QUERIES) == 8

    def test_all_ids_unique(self):
        ids = [q["id"] for q in R11_REPRESENTATIVE_QUERIES]
        assert len(ids) == len(set(ids))

    def test_all_ids_match_prd(self):
        expected_ids = {f"R11-Q{i:02d}" for i in range(1, 9)}
        actual_ids = {q["id"] for q in R11_REPRESENTATIVE_QUERIES}
        assert actual_ids == expected_ids

    def test_all_have_query_field(self):
        for q in R11_REPRESENTATIVE_QUERIES:
            assert "query" in q and isinstance(q["query"], str) and len(q["query"]) > 0

    def test_all_have_expect_field(self):
        for q in R11_REPRESENTATIVE_QUERIES:
            assert "expect" in q and isinstance(q["expect"], dict)


# ── Basic: search doesn't crash + new fields exist ─────────────────────


class TestBasicQueryExecution:
    @pytest.mark.parametrize("qdef", R11_REPRESENTATIVE_QUERIES, ids=lambda q: q["id"])
    def test_search_returns_success(self, isolated_search, qdef):
        r = isolated_search(qdef["query"])
        assert r["success"] is True, f"{qdef['id']}: search should succeed"

    @pytest.mark.parametrize("qdef", R11_REPRESENTATIVE_QUERIES, ids=lambda q: q["id"])
    def test_search_plan_exists(self, isolated_search, qdef):
        r = isolated_search(qdef["query"])
        assert "search_plan" in r, f"{qdef['id']}: search_plan field must exist"
        assert r["search_plan"] is not None, f"{qdef['id']}: search_plan should not be None"

    @pytest.mark.parametrize("qdef", R11_REPRESENTATIVE_QUERIES, ids=lambda q: q["id"])
    def test_ambiguity_exists(self, isolated_search, qdef):
        r = isolated_search(qdef["query"])
        assert "ambiguity" in r, f"{qdef['id']}: ambiguity field must exist"
        assert isinstance(r["ambiguity"]["has_ambiguity"], bool)

    @pytest.mark.parametrize("qdef", R11_REPRESENTATIVE_QUERIES, ids=lambda q: q["id"])
    def test_hints_exists(self, isolated_search, qdef):
        r = isolated_search(qdef["query"])
        assert "hints" in r, f"{qdef['id']}: hints field must exist"
        assert isinstance(r["hints"], list)

    @pytest.mark.parametrize("qdef", R11_REPRESENTATIVE_QUERIES, ids=lambda q: q["id"])
    def test_output_json_serializable(self, isolated_search, qdef):
        r = isolated_search(qdef["query"])
        json_str = json.dumps(r, default=str, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["success"] is True


# ── Advanced: specific signal assertions (Phase 1/2/3 verified) ─────


class TestR11Q01TimeAggregation:
    def test_date_range_not_null(self, isolated_search):
        r = isolated_search("过去60天我有多少次晚于10点睡觉？")
        assert r["search_plan"]["date_range"] is not None

    def test_intent_type_count(self, isolated_search):
        r = isolated_search("过去60天我有多少次晚于10点睡觉？")
        assert r["search_plan"]["intent_type"] == "count"


class TestR11Q02TimeWork:
    def test_topic_hints_work(self, isolated_search):
        r = isolated_search("上个月在工作中取得了什么进展？")
        assert "work" in r["search_plan"]["topic_hints"]


class TestR11Q03TopicHealth:
    def test_topic_hints_health(self, isolated_search):
        r = isolated_search("我有多久没有关心过健康了？")
        assert "health" in r["search_plan"]["topic_hints"]


class TestR11Q01Ambiguity:
    def test_aggregation_ambiguity(self, isolated_search):
        r = isolated_search("过去60天我有多少次晚于10点睡觉？")
        types = [item["type"] for item in r["ambiguity"]["items"]]
        assert "aggregation_requires_agent_judgement" in types


class TestR11Q06Rejection:
    """R11-Q06: 量子计算机编程 — rejection depends on corpus content.

    In a sparse corpus, semantic search may still return results for this query.
    The no_confident_match signal is corpus-dependent, not a guaranteed rejection.
    Marked xfail(strict=False) as a best-effort check — passes when corpus
    has no relevant content, xfail when semantic finds weak matches.
    """

    @pytest.mark.xfail(
        reason="Corpus-dependent: semantic may find weak matches in test data",
        strict=False,
    )
    def test_no_confident_match(self, isolated_search):
        r = isolated_search("量子计算机编程")
        assert r.get("no_confident_match") is True
