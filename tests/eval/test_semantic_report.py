#!/usr/bin/env python3
"""Tests for deprecated eval semantic flags and report compatibility."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest
import yaml


def _write_minimal_fixture(data_dir: Path) -> None:
    from tests.unit.test_eval_runner import _write_eval_fixture_data

    _write_eval_fixture_data(data_dir)


def _make_temp_gold_set(tmp_path: Path, queries: list[dict]) -> Path:
    p = tmp_path / "gold.yaml"
    p.write_text(
        yaml.dump({"queries": queries}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return p


@pytest.fixture(autouse=True)
def _anchor():
    os.environ["LIFE_INDEX_TIME_ANCHOR"] = "2026-05-04"
    yield


class TestDefaultBehaviorUnchanged:
    def test_no_semantic_report_field_by_default(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(data_dir=data_dir, use_semantic=False)
        assert "semantic_report" not in result

    def test_metrics_from_keyword_eval(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(data_dir=data_dir, use_semantic=False)
        assert result["semantic_enabled"] is False
        assert "mrr_at_5" in result["metrics"]

    def test_cli_default_no_semantic_report(self, tmp_path: Path, capsys):
        from tools.eval.__main__ import main

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        main(["--data-dir", str(data_dir), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert "semantic_report" not in payload["data"]


class TestSemanticReportNoop:
    def test_semantic_report_is_disabled_noop(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(data_dir=data_dir, semantic_report=True)

        sr = result["semantic_report"]
        assert sr["enabled"] is False
        assert sr["status"] == "deprecated_noop"
        assert sr["reason"] == (
            "semantic report is disabled because in-tool semantic/vector search was removed."
        )
        assert sr["metrics"] == {}
        assert sr["failure_count"] == 0
        assert sr["failure_ids"] == []
        assert sr["fixed_by_semantic"] == []
        assert sr["regressed_by_semantic"] == []
        assert sr["delta"] == {}
        assert sr["still_failing_both"] == [f["id"] for f in result["failures"]]
        assert result["semantic_enabled"] is False

    def test_use_semantic_flag_is_noop(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        keyword = run_eval.run_evaluation(data_dir=data_dir, use_semantic=False)
        semantic_flag = run_eval.run_evaluation(data_dir=data_dir, use_semantic=True)

        assert semantic_flag["semantic_enabled"] is False
        assert semantic_flag["metrics"] == keyword["metrics"]
        assert len(semantic_flag["failures"]) == len(keyword["failures"])

    def test_top_level_failures_remain_keyword_failures(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        queries = [
            {
                "id": "CF01",
                "query": "nonexistent query that returns zero",
                "category": "noise_rejection",
                "expected": {"min_results": 1, "must_contain_title": ["回忆小风筝"]},
            },
        ]
        gold_path = _make_temp_gold_set(tmp_path, queries)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir,
            queries_path=gold_path,
            use_semantic=True,
            semantic_report=True,
        )

        assert [f["id"] for f in result["failures"]] == ["CF01"]
        assert result["semantic_enabled"] is False
        assert result["semantic_report"]["still_failing_both"] == ["CF01"]


class TestSemanticFlagCompatibility:
    def test_save_baseline_with_semantic_report_no_longer_raises(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)
        baseline_path = tmp_path / "baseline.json"

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir,
            save_baseline=baseline_path,
            semantic_report=True,
        )

        assert result["semantic_report"]["enabled"] is False
        assert baseline_path.exists()

    def test_cli_semantic_with_semantic_report_succeeds(self, tmp_path: Path, capsys):
        from tools.eval.__main__ import main

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        main(["--data-dir", str(data_dir), "--semantic", "--semantic-report", "--json"])
        payload = json.loads(capsys.readouterr().out)

        assert payload["success"] is True
        assert payload["data"]["semantic_enabled"] is False
        assert payload["data"]["semantic_report"]["enabled"] is False

    def test_overlay_rules_are_still_keyword_rules(self, tmp_path: Path, monkeypatch):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Apply"]}}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("CI", "true")

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir,
            use_semantic=True,
            semantic_report=True,
            use_overlay=None,
            overlay_path=overlay_path,
        )

        assert result["semantic_enabled"] is False
        assert result["overlay_applied_count"] == 0
