"""
Tests for conftest.py integration with lazy getter path system (Round 13 Phase 0).

T0.3: Verify isolated_data_dir fixture correctly resets the lazy getter cache
      and that all getters chain from the isolated directory.
"""

from pathlib import Path

import tools.lib.paths as paths_module


class TestConftestLazyPaths:
    """Verify isolated_data_dir fixture plays nicely with lazy getters."""

    def test_isolated_dir_uses_tmp(self, isolated_data_dir: Path) -> None:
        """get_user_data_dir() returns the isolated dir, not the real one."""
        result = paths_module.get_user_data_dir()
        assert result == isolated_data_dir
        # Sanity: not pointing to ~/Documents/Life-Index
        assert "Documents" not in str(result) or "tmp" in str(result).lower()

    def test_isolated_dir_getters_chain(self, isolated_data_dir: Path) -> None:
        """All derived getters chain from the isolated dir."""
        assert paths_module.get_journals_dir() == isolated_data_dir / "Journals"
        assert paths_module.get_index_dir() == isolated_data_dir / ".index"
        assert paths_module.get_by_topic_dir() == isolated_data_dir / "by-topic"
        assert paths_module.get_attachments_dir() == isolated_data_dir / "attachments"
        assert paths_module.get_config_dir() == isolated_data_dir / ".life-index"
        assert paths_module.get_cache_dir() == isolated_data_dir / ".cache"
        assert paths_module.get_fts_db_path() == isolated_data_dir / ".index" / "journals_fts.db"
        assert paths_module.get_metadata_db_path() == isolated_data_dir / ".cache" / "metadata_cache.db"

    def test_isolated_dir_cleanup(self, isolated_data_dir: Path) -> None:
        """After fixture teardown, getters return to original state.

        We verify this by checking that during the fixture scope,
        the getter points to isolated_data_dir. The actual teardown
        verification requires a test that runs AFTER the fixture scope ends,
        which pytest doesn't easily support in the same session.

        Round 15: getters are stateless (no cache), so we verify
        consistency (==) not identity (is).
        """
        # Verify the getter returns the isolated dir
        assert paths_module.get_user_data_dir() == isolated_data_dir
        # Verify consistency: consecutive calls return equal values
        assert paths_module.get_user_data_dir() == paths_module.get_user_data_dir()
