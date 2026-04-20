#!/usr/bin/env python3
"""Unit tests for tools.__main__ CLI helpers."""

import json
import sys
import types

import pytest

from tools.__main__ import health_check


class TestHealthCheck:
    """Tests for unified CLI health check."""

    def test_health_check_uses_configured_data_dir(self, tmp_path, monkeypatch, capsys):
        """Health check should respect config-level data directory overrides."""
        data_dir = tmp_path / "life-index-data"
        journals_dir = data_dir / "Journals"
        journals_dir.mkdir(parents=True)
        (journals_dir / "entry.md").write_text("# test\n", encoding="utf-8")

        index_dir = data_dir / ".index"
        index_dir.mkdir(parents=True)
        (index_dir / "journals_fts.db").write_text("fts", encoding="utf-8")
        (index_dir / "vectors_simple.pkl").write_text("vec", encoding="utf-8")

        cache_dir = tmp_path / "model-cache"
        cache_dir.mkdir(parents=True)
        (cache_dir / "model.onnx").write_text("model", encoding="utf-8")

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
        monkeypatch.setattr("tools.__main__.get_model_cache_dir", lambda: cache_dir)
        monkeypatch.setitem(
            sys.modules, "yaml", types.SimpleNamespace(__version__="test")
        )
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
            check
            for check in payload["data"]["checks"]
            if check["name"] == "data_directory"
        )
        search_index_check = next(
            check
            for check in payload["data"]["checks"]
            if check["name"] == "search_index"
        )

        assert data_directory_check["path"] == str(data_dir)
        assert data_directory_check["journal_count"] == 1
        assert search_index_check["path"] == str(index_dir)


class TestMainCli:
    def test_serve_command_is_not_available(self, monkeypatch, capsys) -> None:
        from tools import __main__

        monkeypatch.setattr(__main__.sys, "argv", ["life-index", "serve"])

        with pytest.raises(SystemExit) as exc_info:
            __main__.main()

        output = capsys.readouterr().out
        assert exc_info.value.code == 1
        assert "Unknown command: serve" in output
