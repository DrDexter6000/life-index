"""Tests for unified freshness guard in search hot-path (Round 12 Phase 3 Task 3.2)."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from tools.lib.pending_writes import mark_pending, clear_pending, has_pending


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Isolate paths and modules to tmp_path."""
    import tools.lib.pending_writes as pw_mod
    import tools.lib.config as cfg
    import tools.lib.paths as paths
    import tools.lib.vector_index_simple as vi_mod
    import tools.edit_journal as edit_mod
    import tools.write_journal.core as write_core

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    journals_dir = tmp_path / "Journals"
    (journals_dir / "2026" / "03").mkdir(parents=True)

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    # Patch getter functions on each module so get_user_data_dir() returns test value
    for module in (cfg, paths, edit_mod, write_core):
        monkeypatch.setattr(module, "get_user_data_dir", lambda _t=tmp_path: _t, raising=False)
        monkeypatch.setattr(module, "get_journals_dir", lambda _j=journals_dir: _j, raising=False)

    monkeypatch.setattr(vi_mod, "INDEX_DIR", idx)
    monkeypatch.setattr(vi_mod, "VEC_INDEX_PATH", idx / "vectors_simple.pkl")
    monkeypatch.setattr(vi_mod, "META_PATH", idx / "vectors_simple_meta.json")
    monkeypatch.setattr(vi_mod, "get_user_data_dir", lambda _t=tmp_path: _t, raising=False)


def _mock_search_deps(monkeypatch):
    """Mock heavy search dependencies."""
    import tools.search_journals.core as search_core

    monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
    monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)


class TestSearchFreshnessGuard:

    def test_fresh_and_no_pending_skips_update(self, tmp_path: Path, monkeypatch):
        """Fresh index + empty pending → search directly, no build triggered."""
        import tools.build_index as bi
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        build_calls = []
        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            return {"success": True}

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        _mock_search_deps(monkeypatch)

        # Patch check_full_freshness to return fresh
        with patch(
            "tools.lib.index_freshness.check_full_freshness",
            return_value=FreshnessReport(fts_fresh=True, vector_fresh=True, overall_fresh=True),
        ):
            result = search_core.hierarchical_search(query="test", level=3)

        assert result["success"] is True
        assert len(build_calls) == 0, "No build should be triggered when fresh"

    def test_fresh_but_pending_triggers_build(self, tmp_path: Path, monkeypatch):
        """Fresh index but pending writes → consume pending then search."""
        import tools.build_index as bi
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        mark_pending("Journals/2026/03/test.md")

        build_calls = []
        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            return {"success": True, "fts": {"success": True}, "vector": {"success": True}}

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        _mock_search_deps(monkeypatch)

        with patch(
            "tools.lib.index_freshness.check_full_freshness",
            return_value=FreshnessReport(fts_fresh=True, vector_fresh=True, overall_fresh=True),
        ):
            result = search_core.hierarchical_search(query="test", level=3)

        assert result["success"] is True
        assert not has_pending(), "Pending should be consumed"
        assert len(build_calls) == 1

    def test_stale_index_triggers_incremental_update(self, tmp_path: Path, monkeypatch):
        """Stale index → triggers incremental build_all, then searches."""
        import tools.build_index as bi
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        build_calls = []
        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            return {"success": True, "fts": {"success": True}, "vector": {"success": True}}

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        _mock_search_deps(monkeypatch)

        with patch(
            "tools.lib.index_freshness.check_full_freshness",
            return_value=FreshnessReport(
                fts_fresh=False, vector_fresh=True, overall_fresh=False,
                issues=["fts_stale: FTS has 5 docs, manifest expects 10"],
            ),
        ):
            result = search_core.hierarchical_search(query="test", level=3)

        assert result["success"] is True
        assert len(build_calls) == 1, "Stale index should trigger build"
        assert build_calls[0].get("incremental") is True

    def test_build_failure_degrades_gracefully(self, tmp_path: Path, monkeypatch):
        """Build failure → search still works (degraded), returns warnings."""
        import tools.build_index as bi
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        def mock_build_all(**kwargs):
            raise RuntimeError("Build crashed!")

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        _mock_search_deps(monkeypatch)

        # Make index stale to trigger build
        with patch(
            "tools.lib.index_freshness.check_full_freshness",
            return_value=FreshnessReport(
                fts_fresh=False, vector_fresh=False, overall_fresh=False,
                issues=["fts_stale"],
            ),
        ):
            result = search_core.hierarchical_search(query="test", level=3)

        assert result["success"] is True  # Search doesn't crash
        assert any("stale" in str(w).lower() or "index" in str(w).lower()
                    for w in result.get("warnings", []))

    def test_result_contains_freshness_field(self, tmp_path: Path, monkeypatch):
        """Search result includes index_status with freshness info."""
        import tools.build_index as bi
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport

        monkeypatch.setattr(bi, "build_all", lambda **kw: {"success": True})
        _mock_search_deps(monkeypatch)

        with patch(
            "tools.lib.index_freshness.check_full_freshness",
            return_value=FreshnessReport(fts_fresh=True, vector_fresh=True, overall_fresh=True),
        ):
            result = search_core.hierarchical_search(query="test", level=3)

        assert "index_status" in result
        index_status = result["index_status"]
        assert "freshness" in index_status or "overall_fresh" in str(index_status)
