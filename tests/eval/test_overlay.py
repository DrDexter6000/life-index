#!/usr/bin/env python3
"""Unit tests for private eval overlay loader."""

from __future__ import annotations

import pytest
import yaml

from tools.eval.overlay import (
    apply_overlay,
    is_ci_environment,
    load_overlay,
)


class TestIsCiEnvironment:
    """Tests for is_ci_environment()."""

    def test_returns_false_by_default(self):
        assert is_ci_environment() is False

    def test_detects_ci_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CI", "true")
        assert is_ci_environment() is True
        monkeypatch.delenv("CI", raising=False)

    def test_detects_github_actions(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert is_ci_environment() is True
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)


class TestLoadOverlay:
    """Tests for load_overlay()."""

    def test_returns_none_when_file_missing(self, tmp_path: pytest.TempPathFactory):
        missing = tmp_path / "does_not_exist.yaml"
        assert load_overlay(missing) is None

    def test_loads_empty_file_as_empty_dict(self, tmp_path: pytest.TempPathFactory):
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        result = load_overlay(path)
        assert result == {}

    def test_loads_valid_mapping(self, tmp_path: pytest.TempPathFactory):
        path = tmp_path / "valid.yaml"
        payload = {"queries": {"GQ01": {"must_contain_title_override": ["Title A"]}}}
        path.write_text(yaml.dump(payload), encoding="utf-8")
        result = load_overlay(path)
        assert result == payload

    def test_fail_fast_on_non_mapping(self, tmp_path: pytest.TempPathFactory):
        path = tmp_path / "bad.yaml"
        path.write_text("- not a mapping", encoding="utf-8")
        with pytest.raises(ValueError, match="must contain a YAML mapping"):
            load_overlay(path)


class TestApplyOverlay:
    """Tests for apply_overlay()."""

    def _make_queries(self) -> list[dict]:
        return [
            {
                "id": "GQ01",
                "query": "test query one",
                "expected": {"must_contain_title": ["Public Title"], "min_results": 1},
            },
            {
                "id": "GQ02",
                "query": "test query two",
                "expected": {"min_results": 2},
            },
        ]

    def test_zero_impact_when_overlay_none(self):
        queries = self._make_queries()
        modified, count, warnings, applied_ids = apply_overlay(queries, None)
        assert count == 0
        assert warnings == []
        assert applied_ids == set()
        assert modified == queries

    def test_must_contain_title_override_list(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"must_contain_title_override": ["Private Title"]},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 1
        assert warnings == []
        assert applied_ids == {"GQ01"}
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["expected"]["must_contain_title"] == ["Private Title"]
        # Original list should be untouched (deepcopy)
        assert queries[0]["expected"]["must_contain_title"] == ["Public Title"]

    def test_must_contain_title_override_scalar_string(self):
        """P2: scalar string must be normalized to list."""
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"must_contain_title_override": "Private Title"},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 1
        assert applied_ids == {"GQ01"}
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["expected"]["must_contain_title"] == ["Private Title"]

    def test_expected_titles_add_list(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"expected_titles_add": ["Extra A", "Extra B"]},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 1
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["expected"]["must_contain_title"] == ["Public Title", "Extra A", "Extra B"]

    def test_expected_titles_add_scalar_string(self):
        """P2: scalar string must be normalized to list."""
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"expected_titles_add": "Extra A"},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 1
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["expected"]["must_contain_title"] == ["Public Title", "Extra A"]

    def test_expected_titles_add_deduplicates(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"expected_titles_add": ["Public Title", "Extra A"]},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["expected"]["must_contain_title"] == ["Public Title", "Extra A"]

    def test_expected_titles_add_creates_list_when_missing(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ02": {"expected_titles_add": ["New Title"]},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 1
        gq02 = next(q for q in modified if q["id"] == "GQ02")
        assert gq02["expected"]["must_contain_title"] == ["New Title"]

    def test_unknown_query_id_produces_warning(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ99": {"must_contain_title_override": ["Nope"]},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 0
        assert len(warnings) == 1
        assert "unknown query id: GQ99" in warnings[0]
        assert applied_ids == set()

    def test_notes_only_does_not_count_as_applied(self):
        """P1: notes-only should not set overlay_applied=true."""
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"notes": "local private title override"},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["_local_notes"] == ["local private title override"]
        assert applied_ids == set()
        assert count == 0

    def test_notes_plus_override_counts_as_applied(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {
                    "must_contain_title_override": ["Private"],
                    "notes": "override note",
                },
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert applied_ids == {"GQ01"}
        assert count == 1

    def test_query_override_replaces_query_string(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"query_override": "Private Query"},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 1
        assert applied_ids == {"GQ01"}
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["query"] == "Private Query"
        assert gq01["_public_query"] == "test query one"
        # Original untouched
        assert queries[0]["query"] == "test query one"

    def test_query_override_requires_string(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"query_override": 123},
            }
        }
        with pytest.raises(ValueError, match="must be a string"):
            apply_overlay(queries, overlay)

    def test_query_override_plus_title_override(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {
                    "query_override": "Private Query",
                    "must_contain_title_override": ["Private Title"],
                },
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 2
        assert applied_ids == {"GQ01"}
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["query"] == "Private Query"
        assert gq01["_public_query"] == "test query one"
        assert gq01["expected"]["must_contain_title"] == ["Private Title"]

    def test_query_override_only_counts_as_applied(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"query_override": "Private Query"},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 1
        assert applied_ids == {"GQ01"}

    def test_notes_plus_query_override_counts_as_applied(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {
                    "query_override": "Private Query",
                    "notes": "query override note",
                },
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert count == 1
        assert applied_ids == {"GQ01"}
        gq01 = next(q for q in modified if q["id"] == "GQ01")
        assert gq01["_local_notes"] == ["query override note"]

    def test_invalid_schema_fail_fast_unknown_key(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"bad_key": "value"},
            }
        }
        with pytest.raises(ValueError, match="unknown keys"):
            apply_overlay(queries, overlay)

    def test_invalid_schema_fail_fast_non_string_non_list_override(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"must_contain_title_override": 123},
            }
        }
        with pytest.raises(ValueError, match="must be a string or list"):
            apply_overlay(queries, overlay)

    def test_invalid_schema_fail_fast_non_string_non_list_add(self):
        queries = self._make_queries()
        overlay = {
            "queries": {
                "GQ01": {"expected_titles_add": 123},
            }
        }
        with pytest.raises(ValueError, match="must be a string or list"):
            apply_overlay(queries, overlay)


class TestOverlayCiAndBaselineDisable:
    """P1: CI and save_baseline must auto-disable overlay."""

    def test_ci_env_disables_overlay(
        self, tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
    ):
        from tools.eval.run_eval import run_evaluation

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Not Apply"]}}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("CI", "true")
        result = run_evaluation(
            data_dir=tmp_path,
            use_semantic=False,
            use_overlay=None,
            overlay_path=overlay_path,
        )
        assert result["overlay_applied_count"] == 0
        monkeypatch.delenv("CI", raising=False)

    def test_save_baseline_disables_overlay(self, tmp_path: pytest.MonkeyPatch):
        from tools.eval.run_eval import run_evaluation

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Not Apply"]}}}),
            encoding="utf-8",
        )
        baseline_path = tmp_path / "baseline.json"
        result = run_evaluation(
            data_dir=tmp_path,
            use_semantic=False,
            use_overlay=None,
            overlay_path=overlay_path,
            save_baseline=baseline_path,
        )
        assert result["overlay_applied_count"] == 0

    def test_ci_env_overrides_explicit_true(
        self, tmp_path: pytest.MonkeyPatch, monkeypatch: pytest.MonkeyPatch
    ):
        """CI must force overlay off even if caller passes use_overlay=True."""
        from tools.eval.run_eval import run_evaluation

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Not Apply"]}}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("CI", "true")
        result = run_evaluation(
            data_dir=tmp_path,
            use_semantic=False,
            use_overlay=True,
            overlay_path=overlay_path,
        )
        assert result["overlay_applied_count"] == 0
        monkeypatch.delenv("CI", raising=False)

    def test_save_baseline_overrides_explicit_true(self, tmp_path: pytest.MonkeyPatch):
        """save_baseline must force overlay off even if caller passes use_overlay=True."""
        from tools.eval.run_eval import run_evaluation

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Not Apply"]}}}),
            encoding="utf-8",
        )
        baseline_path = tmp_path / "baseline.json"
        result = run_evaluation(
            data_dir=tmp_path,
            use_semantic=False,
            use_overlay=True,
            overlay_path=overlay_path,
            save_baseline=baseline_path,
        )
        assert result["overlay_applied_count"] == 0

    def test_local_eval_with_overlay_enabled(self, tmp_path: pytest.TempPathFactory):
        from tools.eval.run_eval import run_evaluation

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump({"queries": {"GQ07": {"must_contain_title_override": ["Should Apply"]}}}),
            encoding="utf-8",
        )
        result = run_evaluation(
            data_dir=tmp_path,
            use_semantic=False,
            use_overlay=True,
            overlay_path=overlay_path,
        )
        assert result["overlay_applied_count"] == 1


class TestPerQueryOverlayApplied:
    """P1: per-query overlay_applied field."""

    def test_applied_query_has_overlay_applied_true(self):
        queries = [
            {"id": "GQ01", "query": "q1", "expected": {}},
            {"id": "GQ02", "query": "q2", "expected": {}},
        ]
        overlay = {
            "queries": {
                "GQ01": {"must_contain_title_override": ["Title"]},
            }
        }
        modified, count, warnings, applied_ids = apply_overlay(queries, overlay)
        assert applied_ids == {"GQ01"}
        assert "GQ01" not in applied_ids or "GQ02" not in applied_ids

    def test_run_eval_per_query_overlay_applied_field(self, tmp_path: pytest.TempPathFactory):
        from tools.eval.run_eval import run_evaluation

        overlay_path = tmp_path / "overlay.yaml"
        overlay_path.write_text(
            yaml.dump(
                {
                    "queries": {
                        "GQ07": {"must_contain_title_override": ["想念尿片侠"]},
                    }
                }
            ),
            encoding="utf-8",
        )
        result = run_evaluation(
            data_dir=tmp_path,
            use_semantic=False,
            use_overlay=True,
            overlay_path=overlay_path,
        )
        gq07 = next(p for p in result["per_query"] if p["id"] == "GQ07")
        gq09 = next(p for p in result["per_query"] if p["id"] == "GQ09")
        assert gq07["overlay_applied"] is True
        assert gq09["overlay_applied"] is False


class TestIntegrationWithRunEval:
    """Integration tests: overlay loaded through run_evaluation."""

    def test_eval_without_overlay_zero_drift(self, tmp_path: pytest.TempPathFactory):
        """run_evaluation without overlay must produce identical metrics
        before and after the overlay feature was added."""
        from tools.eval.run_eval import run_evaluation

        result = run_evaluation(
            data_dir=tmp_path,
            use_semantic=False,
            use_overlay=False,
        )
        assert result["overlay_applied_count"] == 0
        assert result["overlay_warnings"] == []
