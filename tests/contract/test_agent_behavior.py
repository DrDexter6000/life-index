#!/usr/bin/env python3
"""
Agent behavior scenario tests — YAML-driven.

Loads scenarios from tests/contract/scenarios/*.yaml and runs them against
the actual tool functions with mocks, asserting agent-critical output fields.

This layer sits between:
  - Contract tests (field presence/type) — already exist
  - E2E tests (Agent-executed, YAML-described) — already exist

Agent behavior tests verify **decision-relevant semantics**:
  "Given this input, what does the Agent see, and can it make the right decision?"
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from tools.write_journal.core import write_journal
from tools.search_journals.core import hierarchical_search

# ── Helpers ──

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def _load_scenarios(filename: str) -> list[dict]:
    """Load scenarios from a YAML file."""
    path = SCENARIOS_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["scenarios"]


# ── Write Behavior Fixtures ──


@pytest.fixture
def writable_env(tmp_path):
    """Set up a writable environment with all required directories."""
    journals_dir = tmp_path / "Journals"
    journals_dir.mkdir(parents=True)
    by_topic_dir = tmp_path / "by-topic"
    by_topic_dir.mkdir(parents=True)
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir(parents=True)
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(parents=True)
    lock_path = cache_dir / "journals.lock"
    lock_path.touch()
    return {
        "journals_dir": journals_dir,
        "by_topic_dir": by_topic_dir,
        "attachments_dir": attachments_dir,
        "cache_dir": cache_dir,
        "lock_path": lock_path,
        "user_data_dir": tmp_path,
    }


def _run_write_scenario(scenario: dict, writable_env: dict) -> dict:
    """Run a single write scenario with mocks configured from YAML."""
    mocks = scenario.get("mocks", {})
    data = dict(scenario["input"])
    dry_run = scenario.get("options", {}).get("dry_run", False)

    weather_return = mocks.get("weather_return", "Sunny 25°C")
    index_return = mocks.get("index_return", [])
    index_raises = mocks.get("index_raises")
    vector_return = mocks.get("vector_return", False)

    with patch(
        "tools.write_journal.core.get_journals_dir",
        return_value=writable_env["journals_dir"],
    ):
        with patch(
            "tools.write_journal.core.get_journals_lock_path",
            return_value=writable_env["lock_path"],
        ):
            with patch(
                "tools.write_journal.core.get_year_month", return_value=(2026, 4)
            ):
                with patch(
                    "tools.write_journal.core.get_next_sequence", return_value=1
                ):
                    with patch(
                        "tools.write_journal.core.query_weather_for_location",
                        return_value=weather_return,
                    ):
                        # Index update mock — can raise or return
                        if index_raises:
                            topic_mock = MagicMock(
                                side_effect=RuntimeError("test index failure")
                            )
                        else:
                            topic_mock = MagicMock(return_value=index_return)

                        with patch(
                            "tools.write_journal.core.update_topic_index",
                            topic_mock,
                        ):
                            with patch(
                                "tools.write_journal.core.update_project_index",
                                return_value=None,
                            ):
                                with patch(
                                    "tools.write_journal.core.update_tag_indices",
                                    return_value=[],
                                ):
                                    with patch(
                                        "tools.write_journal.core.update_monthly_abstract",
                                        return_value="abstract.md",
                                    ):
                                        with patch(
                                            "tools.write_journal.core.mark_pending",
                                        ):
                                            return write_journal(data, dry_run=dry_run)


def _check_write_assertions(result: dict, assertions: dict, scenario_id: str) -> None:
    """Check agent-critical assertions for a write scenario."""
    prefix = f"[{scenario_id}]"

    if "success" in assertions:
        assert result["success"] is assertions["success"], (
            f"{prefix} success: expected {assertions['success']}, got {result['success']}"
        )

    if "write_outcome" in assertions:
        assert result["write_outcome"] == assertions["write_outcome"], (
            f"{prefix} write_outcome: expected {assertions['write_outcome']!r}, "
            f"got {result['write_outcome']!r}"
        )

    if "write_outcome_in" in assertions:
        assert result["write_outcome"] in assertions["write_outcome_in"], (
            f"{prefix} write_outcome: expected one of {assertions['write_outcome_in']}, "
            f"got {result['write_outcome']!r}"
        )

    if "needs_confirmation" in assertions:
        assert result["needs_confirmation"] is assertions["needs_confirmation"], (
            f"{prefix} needs_confirmation: expected {assertions['needs_confirmation']}, "
            f"got {result['needs_confirmation']}"
        )

    if "location_auto_filled" in assertions:
        assert result["location_auto_filled"] is assertions["location_auto_filled"], (
            f"{prefix} location_auto_filled: expected {assertions['location_auto_filled']}, "
            f"got {result['location_auto_filled']}"
        )

    if "weather_auto_filled" in assertions:
        assert result["weather_auto_filled"] is assertions["weather_auto_filled"], (
            f"{prefix} weather_auto_filled: expected {assertions['weather_auto_filled']}, "
            f"got {result['weather_auto_filled']}"
        )

    if "index_status" in assertions:
        assert result["index_status"] == assertions["index_status"], (
            f"{prefix} index_status: expected {assertions['index_status']!r}, "
            f"got {result['index_status']!r}"
        )

    if "side_effects_status" in assertions:
        assert result["side_effects_status"] == assertions["side_effects_status"], (
            f"{prefix} side_effects_status: expected {assertions['side_effects_status']!r}, "
            f"got {result['side_effects_status']!r}"
        )

    if assertions.get("error_is_null"):
        assert result.get("error") is None, (
            f"{prefix} error should be null, got {result.get('error')!r}"
        )

    if assertions.get("error_is_structured"):
        err = result.get("error")
        assert isinstance(err, dict), (
            f"{prefix} error should be structured dict, got {type(err).__name__}: {err!r}"
        )
        assert "code" in err, f"{prefix} structured error must have 'code'"
        assert "recovery_strategy" in err, (
            f"{prefix} structured error must have 'recovery_strategy'"
        )

    if assertions.get("error_is_string"):
        err = result.get("error")
        assert isinstance(err, str) and len(err) > 0, (
            f"{prefix} error should be a non-empty string, got {type(err).__name__}: {err!r}"
        )

    if "error_recovery_strategy" in assertions:
        err = result.get("error", {})
        assert err.get("recovery_strategy") == assertions["error_recovery_strategy"], (
            f"{prefix} recovery_strategy: expected {assertions['error_recovery_strategy']!r}, "
            f"got {err.get('recovery_strategy')!r}"
        )

    if assertions.get("confirmation_has_location"):
        confirmation = result.get("confirmation", {})
        assert "location" in confirmation, (
            f"{prefix} confirmation must contain 'location'"
        )

    if assertions.get("confirmation_has_weather"):
        confirmation = result.get("confirmation", {})
        assert "weather" in confirmation, (
            f"{prefix} confirmation must contain 'weather'"
        )


# ── Search Behavior Helpers ──


def _run_search_scenario(scenario: dict) -> dict:
    """Run a single search scenario with mocks configured from YAML."""
    mocks = scenario.get("mocks", {})
    query = scenario["input"]["query"]
    level = scenario["input"].get("level", 3)

    l1_return = mocks.get("l1_return", [])
    l2_return = mocks.get(
        "l2_return", {"results": [], "truncated": False, "total_available": 0}
    )
    l3_return = mocks.get("l3_return", [])
    semantic_cfg = mocks.get("semantic_return", {})
    semantic_results = semantic_cfg.get("results", [])
    semantic_status = semantic_cfg.get(
        "status", {"available": True, "reason": "", "note": ""}
    )
    freshness = MagicMock()
    freshness.overall_fresh = True
    freshness.issues = []
    freshness.to_dict.return_value = {"overall_fresh": True, "issues": []}

    with patch("tools.search_journals.core.search_l1_index", return_value=l1_return):
        with patch(
            "tools.search_journals.core.search_l2_metadata",
            return_value=l2_return,
        ):
            with patch(
                "tools.search_journals.core.scan_all_indices", return_value=l1_return
            ):
                with patch(
                    "tools.search_journals.keyword_pipeline.search_l3_content",
                    return_value=l3_return,
                ):
                    with patch(
                        "tools.search_journals.keyword_pipeline.search_l2_metadata",
                        return_value=l2_return,
                    ):
                        with patch(
                            "tools.search_journals.keyword_pipeline.search_l1_index",
                            return_value=l1_return,
                        ):
                            with patch(
                                "tools.lib.search_index.search_fts",
                                return_value=[],
                            ):
                                with patch(
                                    "tools.search_journals.semantic_pipeline.search_semantic",
                                    return_value=(semantic_results, {}),
                                ):
                                    with patch(
                                        "tools.search_journals.semantic_pipeline.get_semantic_runtime_status",
                                        return_value=semantic_status,
                                    ):
                                        with patch(
                                            "tools.lib.pending_writes.has_pending",
                                            return_value=False,
                                        ):
                                            with patch("tools.lib.pending_writes.clear_pending"):
                                                with patch(
                                                    "tools.lib.index_freshness.check_full_freshness",
                                                    return_value=freshness,
                                                ):
                                                    with patch("tools.build_index.build_all"):
                                                        return hierarchical_search(
                                                            query=query, level=level
                                                        )


def _check_search_assertions(result: dict, assertions: dict, scenario_id: str) -> None:
    """Check agent-critical assertions for a search scenario."""
    prefix = f"[{scenario_id}]"

    if "success" in assertions:
        assert result["success"] is assertions["success"], (
            f"{prefix} success: expected {assertions['success']}, got {result['success']}"
        )

    if "total_found" in assertions:
        assert result["total_found"] == assertions["total_found"], (
            f"{prefix} total_found: expected {assertions['total_found']}, "
            f"got {result['total_found']}"
        )

    if "total_found_gt" in assertions:
        assert result["total_found"] > assertions["total_found_gt"], (
            f"{prefix} total_found should be > {assertions['total_found_gt']}, "
            f"got {result['total_found']}"
        )

    if assertions.get("merged_results_not_empty"):
        assert len(result.get("merged_results", [])) > 0, (
            f"{prefix} merged_results should not be empty"
        )

    if assertions.get("merged_results_empty"):
        assert len(result.get("merged_results", [])) == 0, (
            f"{prefix} merged_results should be empty"
        )

    if assertions.get("l1_results_not_empty"):
        assert len(result.get("l1_results", [])) > 0, (
            f"{prefix} l1_results should not be empty"
        )

    if assertions.get("warnings_empty"):
        warnings = result.get("warnings", [])
        assert len(warnings) == 0, f"{prefix} warnings should be empty, got {warnings}"


# ── Parametrized Test Classes ──


_write_scenarios = _load_scenarios("write_agent_behavior.yaml")
_search_scenarios = _load_scenarios("search_agent_behavior.yaml")


class TestWriteAgentBehavior:
    """Agent behavior scenarios for write_journal."""

    @pytest.mark.parametrize(
        "scenario",
        _write_scenarios,
        ids=[s["id"] for s in _write_scenarios],
    )
    def test_write_scenario(self, scenario, writable_env):
        result = _run_write_scenario(scenario, writable_env)
        _check_write_assertions(result, scenario["assertions"], scenario["id"])


class TestSearchAgentBehavior:
    """Agent behavior scenarios for search_journals."""

    @pytest.mark.parametrize(
        "scenario",
        _search_scenarios,
        ids=[s["id"] for s in _search_scenarios],
    )
    def test_search_scenario(self, scenario):
        result = _run_search_scenario(scenario)
        _check_search_assertions(result, scenario["assertions"], scenario["id"])
