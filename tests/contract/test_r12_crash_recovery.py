"""Round 12 Phase 2 Task 2.4: Crash recovery contract tests.

Validates that the system recovers gracefully from various crash scenarios:
1. Missing removed vector index → search still works
2. Missing FTS index → search reports unhealthy but doesn't crash
3. Pending writes not consumed → next search auto-consumes
4. Partial manifest → index --check reports unhealthy
"""

from pathlib import Path

import pytest

from tools.lib.pending_writes import mark_pending, has_pending
from tools.lib.index_manifest import IndexManifest, write_manifest


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Isolate all paths to tmp_path with a zero-count fresh manifest."""
    idx = tmp_path / ".index"
    idx.mkdir()
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)
    (d / "by-topic").mkdir(parents=True)
    (d / ".cache").mkdir(parents=True)
    (d / ".cache" / "journals.lock").touch()

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))

    write_manifest(
        IndexManifest(
            fts_count=0,
            vector_count=0,
            file_count=0,
            fts_checksum="",
            vector_checksum="",
            build_timestamp="2026-01-01T00:00:00",
            build_version="2.0.0",
            partial=False,
        ),
        idx,
    )


class TestCrashRecovery:

    def test_missing_removed_vector_index_search_still_works(self, tmp_path: Path, monkeypatch):
        """Search no longer depends on vectors_simple.pkl."""
        import tools.build_index as bi
        import tools.search_journals.core as search_core

        build_calls = []

        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            return {"success": True, "fts": {"success": True}, "vector": None}

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

        result = search_core.hierarchical_search(query="test", level=3, semantic=False)
        assert result["success"] is True
        assert build_calls == [{"incremental": True, "fts_only": True}]

    def test_missing_fts_index_search_reports_unhealthy(self, tmp_path: Path, monkeypatch):
        """When FTS DB is missing, search reports unhealthy but doesn't crash."""
        import tools.search_journals.core as search_core
        import tools.lib.index_freshness as freshness_mod
        import tools.build_index as bi

        _stale_report = type(
            "FR",
            (),
            {
                "overall_fresh": False,
                "issues": ["fts_stale: FTS index missing"],
                "to_dict": lambda self: {
                    "fts_fresh": False,
                    "vector_fresh": True,
                    "overall_fresh": False,
                    "issues": ["fts_stale: FTS index missing"],
                },
            },
        )()

        monkeypatch.setattr(freshness_mod, "check_full_freshness", lambda _dir: _stale_report)
        monkeypatch.setattr(
            bi,
            "build_all",
            lambda **kw: {
                "success": True,
                "fts": {"success": True},
                "vector": {"success": True},
            },
        )
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

        result = search_core.hierarchical_search(query="test", level=3, semantic=False)
        assert result["success"] is True
        assert any("index_stale" in w for w in result.get("warnings", []))

    def test_pending_not_consumed_auto_consumed_on_next_search(self, tmp_path: Path, monkeypatch):
        """Pending writes not consumed → next search auto-consumes them."""
        import tools.search_journals.core as search_core
        import tools.build_index as bi
        import tools.lib.index_freshness as freshness_mod

        mark_pending("Journals/2026/03/test.md")
        assert has_pending()

        build_calls = []

        def mock_build_all(**kwargs):
            build_calls.append(kwargs)
            return {"success": True, "fts": {"success": True}, "vector": {"success": True}}

        _fresh_report = type(
            "FR",
            (),
            {
                "overall_fresh": True,
                "issues": [],
                "to_dict": lambda self: {
                    "fts_fresh": True,
                    "vector_fresh": True,
                    "overall_fresh": True,
                    "issues": [],
                },
            },
        )()

        monkeypatch.setattr(bi, "build_all", mock_build_all)
        monkeypatch.setattr(freshness_mod, "check_full_freshness", lambda _dir: _fresh_report)
        monkeypatch.setattr(search_core, "build_l0_candidate_set", lambda **kw: set())
        monkeypatch.setattr(search_core, "_emit_search_metrics", lambda r: None)

        search_core.hierarchical_search(query="test", level=3, semantic=False)
        assert not has_pending(), "Pending should be consumed by search"
        assert len(build_calls) == 1

    def test_partial_manifest_index_check_unhealthy(self, tmp_path: Path, monkeypatch):
        """Manifest marked partial → index --check reports unhealthy."""
        from tools.build_index import check_index

        data_dir = tmp_path / "Life-Index"
        index_dir = data_dir / ".index"

        partial_manifest = IndexManifest(
            fts_count=10,
            vector_count=0,
            file_count=10,
            fts_checksum="abc",
            vector_checksum="",
            build_timestamp="2026-04-18T12:00:00",
            build_version="1.0.0",
            partial=True,
        )
        write_manifest(partial_manifest, index_dir)

        result = check_index()
        assert result["healthy"] is False
        assert any("partial" in str(issue).lower() for issue in result.get("issues", []))
