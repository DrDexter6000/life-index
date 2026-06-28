#!/usr/bin/env python3
"""Unit tests for tools.__main__ CLI helpers."""

import json
import sys
import types

import pytest

from tools.__main__ import health_check
from tools.search_journals.__main__ import _apply_presentation_layer


class TestHealthCheck:
    """Tests for unified CLI health check."""

    def test_health_check_uses_configured_data_dir(self, tmp_path, monkeypatch, capsys):
        """Health check should respect config-level data directory overrides."""
        data_dir = tmp_path / "life-index-data"
        journals_dir = data_dir / "Journals"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2026-01-01_001.md").write_text("# test\n", encoding="utf-8")

        index_dir = data_dir / ".index"
        index_dir.mkdir(parents=True)
        (index_dir / "journals_fts.db").write_text("fts", encoding="utf-8")
        (index_dir / "vectors_simple.pkl").write_text("vec", encoding="utf-8")

        cache_dir = tmp_path / "model-cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "model.onnx").write_text("model", encoding="utf-8")

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
        monkeypatch.setattr("tools.__main__.get_model_cache_dir", lambda: cache_dir)
        monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(__version__="test"))
        monkeypatch.setitem(
            sys.modules,
            "sentence_transformers",
            types.SimpleNamespace(__version__="test"),
        )

        health_check()

        captured = capsys.readouterr()
        payload = json.loads(captured.out)

        assert payload["success"] is True
        assert payload["data"]["status"] in {"healthy", "degraded"}
        data_directory_check = next(
            check for check in payload["data"]["checks"] if check["name"] == "data_directory"
        )
        search_index_check = next(
            check for check in payload["data"]["checks"] if check["name"] == "search_index"
        )

        assert data_directory_check["path"] == str(data_dir)
        assert data_directory_check["journal_count"] == 1
        assert search_index_check["path"] == str(index_dir)

    def test_health_reports_semantic_index_disabled(self, tmp_path, monkeypatch, capsys):
        data_dir = tmp_path / "life-index-data"
        journals_dir = data_dir / "Journals"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2026-01-01_001.md").write_text("# test\n", encoding="utf-8")
        index_dir = data_dir / ".index"
        index_dir.mkdir(parents=True)
        (index_dir / "journals_fts.db").write_text("fts", encoding="utf-8")
        (index_dir / "semantic_status.json").write_text(
            '{"status":"building","pid":1234}',
            encoding="utf-8",
        )

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
        monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(__version__="test"))
        monkeypatch.setitem(
            sys.modules,
            "sentence_transformers",
            types.SimpleNamespace(__version__="test"),
        )

        health_check()

        payload = json.loads(capsys.readouterr().out)
        search_index_check = next(
            check for check in payload["data"]["checks"] if check["name"] == "search_index"
        )
        assert search_index_check["semantic_status"] == "disabled"
        assert search_index_check["semantic"]["status"] == "disabled"
        assert "removed" in search_index_check["semantic"]["reason"]


class TestMainCli:
    def test_serve_command_is_not_available(self, monkeypatch, capsys) -> None:
        from tools import __main__

        monkeypatch.setattr(__main__.sys, "argv", ["life-index", "serve"])

        with pytest.raises(SystemExit) as exc_info:
            __main__.main()

        output = capsys.readouterr().out
        assert exc_info.value.code == 1
        assert "Unknown command: serve" in output


class TestHealthCheckIndexTree:
    """TDD 3 RED: health check must report Index Tree freshness/status."""

    def test_health_includes_index_tree_check(self, tmp_path, monkeypatch, capsys):
        data_dir = tmp_path / "life-index-data"
        journals_dir = data_dir / "Journals"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2026-01-01_001.md").write_text("# test\n", encoding="utf-8")

        index_dir = data_dir / ".index"
        index_dir.mkdir(parents=True)
        (index_dir / "journals_fts.db").write_text("fts", encoding="utf-8")

        cache_dir = tmp_path / "model-cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "model.onnx").write_text("model", encoding="utf-8")

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
        monkeypatch.setattr("tools.__main__.get_model_cache_dir", lambda: cache_dir)
        monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(__version__="test"))
        monkeypatch.setitem(
            sys.modules,
            "sentence_transformers",
            types.SimpleNamespace(__version__="test"),
        )

        health_check()

        captured = capsys.readouterr()
        payload = json.loads(captured.out)

        assert payload["success"] is True
        checks = payload["data"]["checks"]
        check_names = [c["name"] for c in checks]
        assert "index_tree" in check_names

        it_check = next(c for c in checks if c["name"] == "index_tree")
        assert "status" in it_check
        assert it_check["status"] in ("ok", "warning", "info")

    def test_health_index_tree_not_critical_when_missing(self, tmp_path, monkeypatch, capsys):
        data_dir = tmp_path / "life-index-data"
        journals_dir = data_dir / "Journals"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2026-01-01_001.md").write_text("# test\n", encoding="utf-8")

        index_dir = data_dir / ".index"
        index_dir.mkdir(parents=True)
        (index_dir / "journals_fts.db").write_text("fts", encoding="utf-8")

        cache_dir = tmp_path / "model-cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "model.onnx").write_text("model", encoding="utf-8")

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
        monkeypatch.setattr("tools.__main__.get_model_cache_dir", lambda: cache_dir)
        monkeypatch.setitem(sys.modules, "yaml", types.SimpleNamespace(__version__="test"))
        monkeypatch.setitem(
            sys.modules,
            "sentence_transformers",
            types.SimpleNamespace(__version__="test"),
        )

        health_check()

        captured = capsys.readouterr()
        payload = json.loads(captured.out)

        assert payload["success"] is True
        assert payload["data"]["status"] != "unhealthy"

        it_check = next(c for c in payload["data"]["checks"] if c["name"] == "index_tree")
        assert it_check["status"] in ("warning", "info")

    def test_index_tree_issue_suggests_runnable_generate_all_months_command(
        self, tmp_path, monkeypatch
    ):
        from tools import __main__ as main_cli

        data_dir = tmp_path / "life-index-data"
        journal_dir = data_dir / "Journals" / "2026" / "03"
        journal_dir.mkdir(parents=True)
        (journal_dir / "life-index_2026-03-14_001.md").write_text(
            "---\ndate: 2026-03-14\ntitle: Test\n---\n\n# Test\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))

        check = main_cli._check_index_tree()

        assert check["status"] == "warning"
        assert check["suggested_command"] == "life-index generate-index --all-months"
        assert "life-index generate-index --all-months" in check["issue"]
        assert "run 'life-index generate-index'" not in check["issue"]


class TestApplyPresentationLayer:
    """Regression tests for _apply_presentation_layer (lead review finding 2026-05-24).

    The original implementation called this helper from main() but never
    defined it, causing NameError at runtime.  These tests would have caught
    that bug before it reached the lead reviewer.
    """

    def test_function_exists_and_is_callable(self):
        """Regression gate: _apply_presentation_layer is defined and importable."""
        assert callable(_apply_presentation_layer)

    def test_limit_5_truncates_to_5(self):
        """--limit 5: merged_results sliced to 5, total_matches preserved."""
        result = {
            "merged_results": [
                {"path": f"/test/doc_{i}.md", "score": 0.9 - i * 0.01} for i in range(20)
            ],
            "total_matches": 20,
            "total_found": 20,
            "total_available": 20,
            "has_more": False,
        }
        _apply_presentation_layer(result, limit=5, offset=0)

        assert len(result["merged_results"]) == 5
        assert result["total_matches"] == 20  # preserved
        assert result["total_found"] == 5  # displayed count
        assert result["total_available"] == 20  # backward compat
        assert result["has_more"] is True
        assert result["display_summary"] == "Showing 5 of 20 results"

    def test_limit_0_returns_all_results(self):
        """--limit 0: no truncation, all results returned."""
        result = {
            "merged_results": [{"path": f"/test/doc_{i}.md", "score": 0.9} for i in range(15)],
            "total_matches": 15,
            "total_found": 15,
            "total_available": 15,
            "has_more": False,
        }
        _apply_presentation_layer(result, limit=0, offset=0)

        assert len(result["merged_results"]) == 15
        assert result["total_matches"] == 15
        assert result["total_found"] == 15
        assert result["has_more"] is False
        assert result["display_summary"] == "Showing 15 of 15 results"

    def test_offset_skip_first_n_results(self):
        """Offset skips first N results before limit is applied."""
        result = {
            "merged_results": [
                {"path": f"/test/doc_{i}.md", "score": 0.9 - i * 0.01} for i in range(20)
            ],
            "total_matches": 20,
            "total_found": 20,
            "total_available": 20,
            "has_more": False,
        }
        _apply_presentation_layer(result, limit=5, offset=10)

        assert len(result["merged_results"]) == 5
        assert result["merged_results"][0]["path"] == "/test/doc_10.md"

    def test_zero_results_has_display_summary(self):
        """Zero-result response gets appropriate display_summary."""
        result = {
            "merged_results": [],
            "total_matches": 0,
            "total_found": 0,
            "total_available": 0,
            "has_more": False,
        }
        _apply_presentation_layer(result, limit=20, offset=0)

        assert result["total_matches"] == 0
        assert result["display_summary"] == "No results found"
        assert result["has_more"] is False

    def test_no_merged_results_key_does_not_raise(self):
        """Result dict without merged_results key is a no-op."""
        result: dict = {"success": False, "total_matches": 0}
        _apply_presentation_layer(result, limit=20, offset=0)
        assert "display_summary" not in result  # unchanged

    def test_limit_none_is_treated_as_zero_full(self):
        """limit=None (legacy) treated same as limit=0 (all results)."""
        result = {
            "merged_results": [{"path": "/test/doc_0.md", "score": 0.9} for _ in range(8)],
            "total_matches": 8,
            "total_found": 8,
            "total_available": 8,
            "has_more": False,
        }
        _apply_presentation_layer(result, limit=None, offset=0)

        assert len(result["merged_results"]) == 8  # no truncation

    def test_invariant_total_matches_ge_returned_results(self):
        """total_matches >= len(merged_results) always holds after slicing."""
        result = {
            "merged_results": [{"path": f"/test/doc_{i}.md", "score": 0.9} for i in range(30)],
            "total_matches": 30,
            "total_found": 30,
            "total_available": 30,
            "has_more": False,
        }
        _apply_presentation_layer(result, limit=7, offset=3)

        assert result["total_matches"] >= len(result["merged_results"])
        assert result["total_matches"] == 30
        assert len(result["merged_results"]) == 7

    def test_has_more_false_for_tail_page_offset(self):
        """has_more must be False when offset+displayed reaches total_matches.

        Lead review finding 2: has_more semantics were based on displayed < total_matches,
        which breaks for tail pages with offset.  Correct invariant:
        has_more == (offset + displayed < total_matches).
        """
        result = {
            "merged_results": [
                {"path": f"/test/doc_{i}.md", "score": 0.9 - i * 0.01} for i in range(20)
            ],
            "total_matches": 20,
            "total_found": 20,
            "total_available": 20,
            "has_more": True,
        }
        _apply_presentation_layer(result, limit=0, offset=10)

        assert len(result["merged_results"]) == 10
        assert result["has_more"] is False
        assert result["display_summary"] == "Showing 10 of 20 results"

    def test_has_more_true_for_mid_page_with_offset(self):
        """has_more must be True when offset+displayed < total_matches."""
        result = {
            "merged_results": [
                {"path": f"/test/doc_{i}.md", "score": 0.9 - i * 0.01} for i in range(25)
            ],
            "total_matches": 25,
            "total_found": 25,
            "total_available": 25,
            "has_more": False,
        }
        _apply_presentation_layer(result, limit=5, offset=5)

        assert len(result["merged_results"]) == 5
        assert result["has_more"] is True
        assert result["display_summary"] == "Showing 5 of 25 results"

    def test_has_more_false_for_exact_page_boundary(self):
        """has_more must be False when offset+displayed equals total_matches (exact boundary)."""
        result = {
            "merged_results": [
                {"path": f"/test/doc_{i}.md", "score": 0.9 - i * 0.01} for i in range(15)
            ],
            "total_matches": 15,
            "total_found": 15,
            "total_available": 15,
            "has_more": True,
        }
        _apply_presentation_layer(result, limit=10, offset=5)

        assert len(result["merged_results"]) == 10
        assert result["has_more"] is False
        assert result["display_summary"] == "Showing 10 of 15 results"
