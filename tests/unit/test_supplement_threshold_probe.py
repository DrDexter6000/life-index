#!/usr/bin/env python3
"""TDD tests for the M07 supplement threshold probe harness.

Tests cover:
  A. summarize_thresholds pure function — correct classification counts
  B. Boundary score (76) at default threshold
  C. Strong score (85) above threshold
  D. Missing score records
  E. Fixed / regressed / unchanged / unknown outcome counts
  F. Invalid threshold input handling
  G. Privacy redaction — no raw text, paths, or keyword objects in output
  H. CLI entry point (--input, --thresholds, --json)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.dev.supplement_threshold_probe import summarize_thresholds

# ---------------------------------------------------------------------------
# A. Basic summarize_thresholds structure
# ---------------------------------------------------------------------------


class TestSummarizeThresholdsStructure:
    """summarize_thresholds returns the expected aggregate shape."""

    def test_returns_dict_with_required_keys(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 72}], "semantic_outcome": "fixed"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        assert "thresholds" in result
        assert "total_records" in result
        for t_key in result["thresholds"]:
            bucket = result["thresholds"][t_key]
            assert "would_supplement" in bucket
            assert "would_skip" in bucket
            assert "fixed_candidates" in bucket
            assert "regression_risk_candidates" in bucket
            assert "unknown_score_records" in bucket

    def test_total_records_matches_input(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 50}]},
            {"id": "Q2", "keyword_results": [{"fts_score": 80}]},
            {"id": "Q3", "keyword_results": [{"fts_score": 90}]},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        assert result["total_records"] == 3

    def test_empty_records_returns_zero_counts(self):
        result = summarize_thresholds([], thresholds=[76.0])
        assert result["total_records"] == 0
        bucket = result["thresholds"]["76.0"]
        assert bucket["would_supplement"] == 0
        assert bucket["would_skip"] == 0


# ---------------------------------------------------------------------------
# B. Boundary score 76 at default threshold
# ---------------------------------------------------------------------------


class TestBoundaryScore76:
    """Score exactly at threshold 76 should classify as would_supplement."""

    def test_score_76_supplements_at_threshold_76(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 76}], "semantic_outcome": "fixed"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["would_supplement"] == 1
        assert bucket["would_skip"] == 0

    def test_score_75_supplements_at_threshold_76(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 75}]},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["would_supplement"] == 1

    def test_score_77_skips_at_threshold_76(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 77}]},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["would_skip"] == 1
        assert bucket["would_supplement"] == 0


# ---------------------------------------------------------------------------
# C. Strong score 85
# ---------------------------------------------------------------------------


class TestStrongScore85:
    """Strong score 85 should skip at threshold 76 but supplement at 85."""

    def test_score_85_skips_at_threshold_76(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 85}]},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["would_skip"] == 1
        assert bucket["would_supplement"] == 0

    def test_score_85_supplements_at_threshold_85(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 85}]},
        ]
        result = summarize_thresholds(records, thresholds=[85.0])
        bucket = result["thresholds"]["85.0"]
        assert bucket["would_supplement"] == 1
        assert bucket["would_skip"] == 0


# ---------------------------------------------------------------------------
# D. Missing score
# ---------------------------------------------------------------------------


class TestMissingScore:
    """Records with missing keyword_results or scores default to 0.0 and supplement."""

    def test_missing_fts_score_defaults_zero_supplements(self):
        records = [
            {"id": "Q1", "keyword_results": [{"no_score": True}]},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        # Missing score -> 0.0 -> 0.0 <= 76.0 -> supplement
        assert bucket["would_supplement"] == 1
        assert bucket["unknown_score_records"] == 1

    def test_empty_keyword_results_supplements(self):
        records = [
            {"id": "Q1", "keyword_results": []},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["would_supplement"] == 1
        assert bucket["unknown_score_records"] == 1

    def test_missing_keyword_results_key_supplements(self):
        records = [
            {"id": "Q1"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["would_supplement"] == 1
        assert bucket["unknown_score_records"] == 1


# ---------------------------------------------------------------------------
# E. Semantic outcome counts
# ---------------------------------------------------------------------------


class TestSemanticOutcomeCounts:
    """fixed_candidates, regression_risk_candidates, and unknown by outcome."""

    def test_fixed_outcome_tracked(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 50}], "semantic_outcome": "fixed"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["fixed_candidates"] == 1
        assert bucket["regression_risk_candidates"] == 0

    def test_regressed_outcome_tracked(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 50}], "semantic_outcome": "regressed"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["regression_risk_candidates"] == 1
        assert bucket["fixed_candidates"] == 0

    def test_unchanged_outcome_not_counted_as_fixed_or_regressed(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 50}], "semantic_outcome": "unchanged"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["fixed_candidates"] == 0
        assert bucket["regression_risk_candidates"] == 0

    def test_unknown_outcome_not_counted(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 50}], "semantic_outcome": "unknown"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["fixed_candidates"] == 0
        assert bucket["regression_risk_candidates"] == 0

    def test_missing_outcome_defaults_to_none(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 50}]},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        assert bucket["fixed_candidates"] == 0
        assert bucket["regression_risk_candidates"] == 0

    def test_mixed_outcomes_counted_correctly(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 50}], "semantic_outcome": "fixed"},
            {"id": "Q2", "keyword_results": [{"fts_score": 60}], "semantic_outcome": "regressed"},
            {"id": "Q3", "keyword_results": [{"fts_score": 70}], "semantic_outcome": "unchanged"},
            {"id": "Q4", "keyword_results": [{"fts_score": 80}], "semantic_outcome": "fixed"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        bucket = result["thresholds"]["76.0"]
        # Q1 (50, fixed), Q2 (60, regressed), Q3 (70, unchanged) all supplement
        # Q4 (80) skips
        assert bucket["fixed_candidates"] == 1  # only Q1
        assert bucket["regression_risk_candidates"] == 1  # Q2
        assert bucket["would_supplement"] == 3
        assert bucket["would_skip"] == 1


# ---------------------------------------------------------------------------
# F. Invalid threshold input
# ---------------------------------------------------------------------------


class TestInvalidThresholdInput:
    """Invalid threshold values should raise ValueError."""

    def test_empty_thresholds_raises(self):
        with pytest.raises(ValueError, match="thresholds"):
            summarize_thresholds([], thresholds=[])

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            summarize_thresholds([], thresholds=[-1.0])

    def test_zero_threshold_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            summarize_thresholds([], thresholds=[0.0])

    def test_non_numeric_threshold_in_cli(self):
        """Non-numeric threshold string should cause an error in CLI."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.dev.supplement_threshold_probe",
                "--input",
                '{"records": []}',
                "--thresholds",
                "abc",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# G. Privacy redaction
# ---------------------------------------------------------------------------


class TestPrivacyRedaction:
    """Output must not include raw private fields."""

    def test_no_raw_keyword_results_in_output(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 72}], "semantic_outcome": "fixed"},
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        result_str = json.dumps(result)
        assert "keyword_results" not in result_str
        assert "fts_score" not in result_str

    def test_no_query_text_in_output(self):
        records = [
            {
                "id": "Q1",
                "keyword_results": [{"fts_score": 72}],
                "semantic_outcome": "fixed",
                "query": "secret user query",
            },
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        result_str = json.dumps(result)
        assert "secret user query" not in result_str
        assert "query" not in result_str

    def test_no_title_or_content_in_output(self):
        records = [
            {
                "id": "Q1",
                "keyword_results": [{"fts_score": 72}],
                "semantic_outcome": "fixed",
                "title": "private title",
                "content": "private content",
            },
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        result_str = json.dumps(result)
        assert "private title" not in result_str
        assert "private content" not in result_str

    def test_no_absolute_paths_in_output(self):
        records = [
            {
                "id": "Q1",
                "keyword_results": [{"fts_score": 72, "path": "/home/user/docs/journal.md"}],
                "semantic_outcome": "fixed",
            },
        ]
        result = summarize_thresholds(records, thresholds=[76.0])
        result_str = json.dumps(result)
        assert "/home/user" not in result_str
        assert "journal.md" not in result_str

    def test_privacy_field_in_cli_output(self, tmp_path: Path):
        input_data = {
            "records": [
                {"id": "Q1", "keyword_results": [{"fts_score": 72}], "semantic_outcome": "fixed"},
            ]
        }
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(input_data), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.dev.supplement_threshold_probe",
                "--input",
                str(input_file),
                "--thresholds",
                "76",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert "privacy" in payload
        assert payload["privacy"]["redacted_fields"] is not None


# ---------------------------------------------------------------------------
# H. CLI entry point
# ---------------------------------------------------------------------------


class TestCLIEntryPoint:
    """CLI must accept --input, --thresholds, --json and produce valid JSON."""

    def test_cli_basic_invocation(self, tmp_path: Path):
        input_data = {
            "records": [
                {"id": "Q1", "keyword_results": [{"fts_score": 72}], "semantic_outcome": "fixed"},
                {
                    "id": "Q2",
                    "keyword_results": [{"fts_score": 85}],
                    "semantic_outcome": "regressed",
                },
            ]
        }
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(input_data), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.dev.supplement_threshold_probe",
                "--input",
                str(input_file),
                "--thresholds",
                "70,76,85",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert "thresholds" in payload
        assert "70.0" in payload["thresholds"]
        assert "76.0" in payload["thresholds"]
        assert "85.0" in payload["thresholds"]
        assert payload["total_records"] == 2

    def test_cli_without_json_flag_still_works(self, tmp_path: Path):
        input_data = {
            "records": [
                {"id": "Q1", "keyword_results": [{"fts_score": 72}]},
            ]
        }
        input_file = tmp_path / "input.json"
        input_file.write_text(json.dumps(input_data), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.dev.supplement_threshold_probe",
                "--input",
                str(input_file),
                "--thresholds",
                "76",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        # Should still produce parseable JSON
        payload = json.loads(result.stdout)
        assert "thresholds" in payload

    def test_cli_missing_input_file_exits_nonzero(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.dev.supplement_threshold_probe",
                "--input",
                "/nonexistent/path.json",
                "--thresholds",
                "76",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0

    def test_cli_inline_json_input(self):
        input_json = json.dumps(
            {
                "records": [
                    {"id": "Q1", "keyword_results": [{"fts_score": 50}]},
                ]
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.dev.supplement_threshold_probe",
                "--input",
                input_json,
                "--thresholds",
                "76",
                "--json",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["total_records"] == 1


# ---------------------------------------------------------------------------
# I. Multiple thresholds
# ---------------------------------------------------------------------------


class TestMultipleThresholds:
    """Multiple thresholds produce separate buckets."""

    def test_three_thresholds_produce_three_buckets(self):
        records = [
            {"id": "Q1", "keyword_results": [{"fts_score": 72}], "semantic_outcome": "fixed"},
            {"id": "Q2", "keyword_results": [{"fts_score": 80}], "semantic_outcome": "regressed"},
            {"id": "Q3", "keyword_results": [{"fts_score": 90}]},
        ]
        result = summarize_thresholds(records, thresholds=[70.0, 76.0, 85.0])
        assert len(result["thresholds"]) == 3
        # At 70: Q1 (72>70 skip), Q2 (80>70 skip), Q3 (90>70 skip)
        assert result["thresholds"]["70.0"]["would_skip"] == 3
        assert result["thresholds"]["70.0"]["would_supplement"] == 0
        # At 76: Q1 (72<=76 supplement), Q2 (80>76 skip), Q3 (90>76 skip)
        assert result["thresholds"]["76.0"]["would_supplement"] == 1
        assert result["thresholds"]["76.0"]["would_skip"] == 2
        # At 85: Q1 (72<=85 supplement), Q2 (80<=85 supplement), Q3 (90>85 skip)
        assert result["thresholds"]["85.0"]["would_supplement"] == 2
        assert result["thresholds"]["85.0"]["would_skip"] == 1
