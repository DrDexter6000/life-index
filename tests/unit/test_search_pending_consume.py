"""Tests for search pending queue consumption (Round 12 Phase 1 Task 1.4)."""

import pytest
from pathlib import Path

from tools.lib.pending_writes import mark_pending, get_pending, clear_pending, has_pending


@pytest.fixture(autouse=True)
def _isolate_index(tmp_path: Path, monkeypatch):
    """Isolate pending_writes, data dir, and index to tmp_path."""
    import tools.lib.pending_writes as pw_mod
    idx = tmp_path / ".index"
    idx.mkdir()
    journals_dir = tmp_path / "Journals"
    (journals_dir / "2026" / "03").mkdir(parents=True)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))


class TestSearchPendingConsume:
    def test_pending_consumed_before_search(self, tmp_path: Path, monkeypatch):
        """When pending is non-empty, search triggers incremental update then clears."""
        mark_pending("Journals/2026/03/test.md")

        # Mock build_all to avoid actually building indexes
        built = {"called": False}
        def mock_build_all(**kwargs):
            built["called"] = True
            return {"success": True, "fts": {"success": True}, "vector": {"success": True}}

        import tools.build_index as bi
        import tools.lib.search_index as si
        import tools.search_journals.core as search_core
        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(si, "check_index_freshness", lambda: {"stale": False})
        monkeypatch.setattr(si, "update_index", lambda **kw: {"success": True})
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

        result = search_core.hierarchical_search(query="test", level=3)
        assert built["called"], "build_all should be called when pending is non-empty"
        assert not has_pending(), "pending should be cleared after consumption"

    def test_no_build_when_pending_empty(self, tmp_path: Path, monkeypatch):
        """When pending is empty and index is fresh, search does not trigger build_all."""
        clear_pending()

        built = {"called": False}
        def mock_build_all(**kwargs):
            built["called"] = True
            return {"success": True}

        import tools.build_index as bi
        import tools.lib.search_index as si
        import tools.search_journals.core as search_core
        from tools.lib.index_freshness import FreshnessReport
        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(si, "check_index_freshness", lambda: {"stale": False})
        monkeypatch.setattr(si, "update_index", lambda **kw: {"success": True})
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)
        # Phase 3: mock freshness as fresh so the unified guard doesn't trigger build
        monkeypatch.setattr(
            "tools.lib.index_freshness.check_full_freshness",
            lambda _: FreshnessReport(fts_fresh=True, vector_fresh=True, overall_fresh=True),
        )

        search_core.hierarchical_search(query="test", level=3)
        assert not built["called"], "build_all should NOT be called when pending is empty and index is fresh"

    def test_build_failure_does_not_block_search(self, tmp_path: Path, monkeypatch):
        """If build_all fails, search still proceeds and pending is retained."""
        mark_pending("Journals/2026/03/test.md")

        def mock_build_all(**kwargs):
            raise RuntimeError("Build failed!")

        import tools.build_index as bi
        import tools.lib.search_index as si
        import tools.search_journals.core as search_core
        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(si, "check_index_freshness", lambda: {"stale": False})
        monkeypatch.setattr(si, "update_index", lambda **kw: {"success": True})
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

        result = search_core.hierarchical_search(query="test", level=3)
        assert result.get("success") is True
        assert result.get("pending_consumed") is False
        assert has_pending(), "pending should be retained so next search can retry the build"
