"""
Tests for Lazy Getter Path System (Round 13 Phase 0).

T0.1: Verify all getter functions return correct paths.
T0.2: Verify getters work with monkeypatched resolve_user_data_dir.
"""

import tools.lib.paths as paths_module
from pathlib import Path


# ── T0.1: Basic Getter Tests ──────────────────────────────────────────


class TestGettersBasic:
    """Verify each getter returns the expected sub-path of user data dir."""

    def test_get_user_data_dir_default(self) -> None:
        """get_user_data_dir() returns resolved user data dir."""
        result = paths_module.get_user_data_dir()
        assert result == paths_module.resolve_user_data_dir()

    def test_get_journals_dir(self) -> None:
        result = paths_module.get_journals_dir()
        assert result == paths_module.get_user_data_dir() / "Journals"

    def test_get_index_dir(self) -> None:
        result = paths_module.get_index_dir()
        assert result == paths_module.get_user_data_dir() / ".index"

    def test_get_fts_db_path(self) -> None:
        result = paths_module.get_fts_db_path()
        assert result == paths_module.get_index_dir() / "journals_fts.db"

    def test_get_vec_index_path(self) -> None:
        result = paths_module.get_vec_index_path()
        assert result == paths_module.get_index_dir() / "vectors_simple.pkl"

    def test_get_cache_dir(self) -> None:
        result = paths_module.get_cache_dir()
        assert result == paths_module.get_user_data_dir() / ".cache"

    def test_get_metadata_db_path(self) -> None:
        result = paths_module.get_metadata_db_path()
        assert result == paths_module.get_cache_dir() / "metadata_cache.db"

    def test_get_by_topic_dir(self) -> None:
        result = paths_module.get_by_topic_dir()
        assert result == paths_module.get_user_data_dir() / "by-topic"

    def test_get_attachments_dir(self) -> None:
        result = paths_module.get_attachments_dir()
        assert result == paths_module.get_user_data_dir() / "attachments"

    def test_get_config_dir(self) -> None:
        result = paths_module.get_config_dir()
        assert result == paths_module.get_user_data_dir() / ".life-index"

    def test_cache_hit(self) -> None:
        """Consecutive calls resolve to the same path value."""
        paths_module.reset_path_cache()
        first = paths_module.get_user_data_dir()
        second = paths_module.get_user_data_dir()
        assert first == second

    def test_reset_clears_cache(self) -> None:
        """After reset_path_cache(), get_user_data_dir() returns fresh value."""
        first = paths_module.get_user_data_dir()
        paths_module.reset_path_cache()
        second = paths_module.get_user_data_dir()
        # Both resolve to the same path but may be different objects
        assert first == second


# ── T0.2: Patching Tests ──────────────────────────────────────────────


class TestGettersWithPatching:
    """Verify getters respond correctly when resolve_user_data_dir is patched."""

    def test_env_override_changes_getter(self, tmp_path: Path, monkeypatch) -> None:
        """Getter reads LIFE_INDEX_DATA_DIR dynamically on each call."""
        fake_dir = tmp_path / "fake_data"
        fake_dir.mkdir()

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(fake_dir))
        paths_module.reset_path_cache()
        assert paths_module.get_user_data_dir() == fake_dir

    def test_env_override_changes_all_getters(self, tmp_path: Path, monkeypatch) -> None:
        """All derived getters chain from the active env-based base dir."""
        fake_dir = tmp_path / "fake_data"
        fake_dir.mkdir()

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(fake_dir))
        paths_module.reset_path_cache()

        assert paths_module.get_user_data_dir() == fake_dir
        assert paths_module.get_index_dir() == fake_dir / ".index"
        assert paths_module.get_journals_dir() == fake_dir / "Journals"
        assert paths_module.get_by_topic_dir() == fake_dir / "by-topic"
        assert paths_module.get_attachments_dir() == fake_dir / "attachments"
        assert paths_module.get_config_dir() == fake_dir / ".life-index"
        assert paths_module.get_cache_dir() == fake_dir / ".cache"
        assert paths_module.get_fts_db_path() == fake_dir / ".index" / "journals_fts.db"
        assert paths_module.get_metadata_db_path() == fake_dir / ".cache" / "metadata_cache.db"

    def test_ensure_dirs_uses_getter(self, tmp_path: Path, monkeypatch) -> None:
        """ensure_dirs() creates directories under the env-selected path."""
        fake_dir = tmp_path / "ensure_test"
        # Don't mkdir fake_dir — ensure_dirs should create subdirs via parents=True

        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(fake_dir))
        paths_module.reset_path_cache()

        paths_module.ensure_dirs()

        assert (fake_dir / "Journals").exists()
        assert (fake_dir / "by-topic").exists()
        assert (fake_dir / "attachments").exists()
        assert (fake_dir / ".life-index").exists()
