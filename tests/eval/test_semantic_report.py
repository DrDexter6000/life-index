#!/usr/bin/env python3
"""TDD tests for semantic report-only eval mode (Option C2).

Tests cover:
  A. Default behavior unchanged (no semantic_report field)
  B. semantic_report field structure when enabled
  C. Official failures unaffected by semantic_report
  D. Regression detection (keyword pass, semantic fail)
  E. save_baseline + semantic_report raises error
  F. Overlay/CI safety — semantic_report does not bypass overlay disable
"""

from __future__ import annotations

import importlib
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


def _make_queries_for_delta() -> list[dict]:
    """Return a small query set that produces different results under keyword vs semantic."""
    return [
        {
            "id": "DQ01",
            "query": "想念小英雄",
            "category": "entity_expansion",
            "expected": {"min_results": 1, "must_contain_title": ["想念小英雄"]},
        },
        {
            "id": "DQ02",
            "query": "nonexistent query xyz",
            "category": "noise_rejection",
            "expected": {"min_results": 0},
        },
    ]


@pytest.fixture(autouse=True)
def _anchor():
    os.environ["LIFE_INDEX_TIME_ANCHOR"] = "2026-05-04"
    yield


# ---------------------------------------------------------------------------
# A. Default behavior unchanged
# ---------------------------------------------------------------------------


class TestDefaultBehaviorUnchanged:
    """Without semantic_report, run_evaluation output is identical to before."""

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

    def test_cli_default_no_semantic_report(self, tmp_path: Path):
        """CLI without --semantic-report must not emit semantic_report."""
        from tools.eval.__main__ import main

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        import io
        import sys

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main(["--data-dir", str(data_dir), "--json"])
        finally:
            sys.stdout = old_stdout

        import json

        payload = json.loads(captured.getvalue())
        assert "semantic_report" not in payload["data"]


# ---------------------------------------------------------------------------
# B. semantic_report field structure
# ---------------------------------------------------------------------------


class TestSemanticReportStructure:
    """semantic_report=True produces the expected JSON shape."""

    def test_semantic_report_enabled_field(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir, use_semantic=False, semantic_report=True
        )
        assert "semantic_report" in result
        assert result["semantic_report"]["enabled"] is True

    def test_semantic_report_has_required_fields(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir, use_semantic=False, semantic_report=True
        )
        sr = result["semantic_report"]
        assert "enabled" in sr
        assert "metrics" in sr
        assert "failure_count" in sr
        assert "failure_ids" in sr
        assert "fixed_by_semantic" in sr
        assert "regressed_by_semantic" in sr
        assert "still_failing_both" in sr
        assert "delta" in sr

    def test_top_level_metrics_are_keyword(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir, use_semantic=False, semantic_report=True
        )
        # Top-level metrics must come from keyword (use_semantic=False)
        assert result["semantic_enabled"] is False
        # semantic_report metrics come from semantic run
        sr = result["semantic_report"]
        assert isinstance(sr["metrics"], dict)
        assert "mrr_at_5" in sr["metrics"]

    def test_delta_fields_present(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir, use_semantic=False, semantic_report=True
        )
        delta = result["semantic_report"]["delta"]
        assert "mrr_at_5" in delta
        assert "recall_at_5" in delta
        assert "precision_at_5" in delta
        assert "ndcg_at_5" in delta
        assert "failure_count" in delta


# ---------------------------------------------------------------------------
# C. Official failures unaffected — tested via _build_semantic_report helper
# ---------------------------------------------------------------------------


class TestOfficialFailuresUnaffected:
    """Top-level failures must come from keyword eval only.

    Tested via _build_semantic_report() which is the pure function
    that computes the classification.
    """

    def test_keyword_fail_semantic_pass_is_fixed(self):
        run_eval = importlib.import_module("tools.eval.run_eval")
        keyword_result = {
            "metrics": {
                "mrr_at_5": 0.5,
                "recall_at_5": 0.8,
                "precision_at_5": 0.4,
                "ndcg_at_5": 0.5,
            },
            "failures": [
                {"id": "CF01", "query": "q1", "reason": "not found"},
                {"id": "CF02", "query": "q2", "reason": "not found"},
            ],
        }
        semantic_result = {
            "metrics": {
                "mrr_at_5": 0.6,
                "recall_at_5": 0.9,
                "precision_at_5": 0.35,
                "ndcg_at_5": 0.6,
            },
            "failures": [
                {"id": "CF02", "query": "q2", "reason": "not found"},
            ],
        }
        report = run_eval._build_semantic_report(keyword_result, semantic_result)
        assert "CF01" in report["fixed_by_semantic"]
        assert "CF01" not in report["failure_ids"]
        assert "CF02" in report["still_failing_both"]
        assert report["delta"]["failure_count"] == -1

    def test_keyword_fail_still_in_top_level_failures(self, tmp_path: Path, monkeypatch):
        """End-to-end: keyword fail stays in top-level failures."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        queries = [
            {
                "id": "CF01",
                "query": "nonexistent query that returns zero",
                "category": "noise_rejection",
                "expected": {"min_results": 1, "must_contain_title": ["想念小英雄"]},
            },
        ]
        gold_path = _make_temp_gold_set(tmp_path, queries)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir,
            queries_path=gold_path,
            use_semantic=False,
            semantic_report=True,
        )

        # CF01 must be in top-level failures (keyword fails for this query)
        top_level_ids = [f["id"] for f in result["failures"]]
        assert "CF01" in top_level_ids


# ---------------------------------------------------------------------------
# D. Regression detection — tested via _build_semantic_report helper
# ---------------------------------------------------------------------------


class TestRegressionDetection:
    """keyword pass + semantic fail = regressed_by_semantic."""

    def test_keyword_pass_semantic_fail_is_regression(self):
        run_eval = importlib.import_module("tools.eval.run_eval")
        keyword_result = {
            "metrics": {
                "mrr_at_5": 0.5,
                "recall_at_5": 0.8,
                "precision_at_5": 0.4,
                "ndcg_at_5": 0.5,
            },
            "failures": [
                {"id": "CF01", "query": "q1", "reason": "not found"},
            ],
        }
        semantic_result = {
            "metrics": {
                "mrr_at_5": 0.6,
                "recall_at_5": 0.9,
                "precision_at_5": 0.35,
                "ndcg_at_5": 0.6,
            },
            "failures": [
                {"id": "CF01", "query": "q1", "reason": "not found"},
                {"id": "RD01", "query": "q_reg", "reason": "not found"},
            ],
        }
        report = run_eval._build_semantic_report(keyword_result, semantic_result)
        assert "RD01" in report["regressed_by_semantic"]
        assert "RD01" in report["failure_ids"]
        assert report["delta"]["failure_count"] == 1


# ---------------------------------------------------------------------------
# E. save_baseline + semantic_report raises error
# ---------------------------------------------------------------------------


class TestSaveBaselineProhibition:
    """semantic_report cannot be combined with save_baseline."""

    def test_save_baseline_with_semantic_report_raises(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)
        baseline_path = tmp_path / "baseline.json"

        run_eval = importlib.import_module("tools.eval.run_eval")
        with pytest.raises(ValueError, match="semantic report is diagnostic-only"):
            run_eval.run_evaluation(
                data_dir=data_dir,
                save_baseline=baseline_path,
                semantic_report=True,
            )

    def test_cli_save_baseline_with_semantic_report_exits_nonzero(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)
        baseline_path = tmp_path / "baseline.json"

        from tools.eval.__main__ import main

        with pytest.raises(SystemExit):
            main(
                [
                    "--data-dir",
                    str(data_dir),
                    "--save-baseline",
                    str(baseline_path),
                    "--semantic-report",
                ]
            )


# ---------------------------------------------------------------------------
# F. Overlay / CI safety
# ---------------------------------------------------------------------------


class TestOverlayCISafety:
    """semantic_report must not bypass overlay disable rules."""

    def test_ci_env_semantic_report_overlay_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Not Apply"]}}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("CI", "true")

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir,
            use_semantic=False,
            semantic_report=True,
            use_overlay=None,
            overlay_path=overlay_path,
        )
        assert result["overlay_applied_count"] == 0
        monkeypatch.delenv("CI", raising=False)

    def test_save_baseline_semantic_report_overlay_disabled(self, tmp_path: Path):
        """Even without explicit CI, save_baseline + semantic_report must fail."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Not Apply"]}}}),
            encoding="utf-8",
        )
        baseline_path = tmp_path / "baseline.json"

        run_eval = importlib.import_module("tools.eval.run_eval")
        with pytest.raises(ValueError, match="semantic report is diagnostic-only"):
            run_eval.run_evaluation(
                data_dir=data_dir,
                save_baseline=baseline_path,
                semantic_report=True,
                use_overlay=None,
                overlay_path=overlay_path,
            )

    def test_semantic_report_does_not_affect_overlay_applied_count(self, tmp_path: Path):
        """overlay_applied_count must reflect keyword eval overlay only."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Apply"]}}}),
            encoding="utf-8",
        )

        run_eval = importlib.import_module("tools.eval.run_eval")
        result_with = run_eval.run_evaluation(
            data_dir=data_dir,
            use_semantic=False,
            semantic_report=True,
            use_overlay=True,
            overlay_path=overlay_path,
        )
        result_without = run_eval.run_evaluation(
            data_dir=data_dir,
            use_semantic=False,
            semantic_report=False,
            use_overlay=True,
            overlay_path=overlay_path,
        )
        assert result_with["overlay_applied_count"] == result_without["overlay_applied_count"]


# ---------------------------------------------------------------------------
# G. use_semantic=True + semantic_report=True prohibited
# ---------------------------------------------------------------------------


class TestSemanticReportWithSemanticMode:
    """semantic_report must only work with keyword/default top-level eval."""

    def test_api_use_semantic_true_with_semantic_report_raises(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        with pytest.raises(ValueError, match="semantic report requires keyword"):
            run_eval.run_evaluation(
                data_dir=data_dir,
                use_semantic=True,
                semantic_report=True,
            )

    def test_cli_semantic_flag_with_semantic_report_exits_nonzero(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        from tools.eval.__main__ import main

        with pytest.raises(SystemExit):
            main(
                [
                    "--data-dir",
                    str(data_dir),
                    "--semantic",
                    "--semantic-report",
                ]
            )

    def test_no_semantic_with_semantic_report_still_works(self, tmp_path: Path):
        """--no-semantic --semantic-report must succeed (keyword official + semantic report)."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        _write_minimal_fixture(data_dir)

        run_eval = importlib.import_module("tools.eval.run_eval")
        result = run_eval.run_evaluation(
            data_dir=data_dir,
            use_semantic=False,
            semantic_report=True,
        )
        assert "semantic_report" in result
        assert result["semantic_enabled"] is False
