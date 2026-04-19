#!/usr/bin/env python3
"""Regression tests for pytest fixture isolation."""

import tools.lib.metadata_cache as metadata_cache
import tools.search_journals.semantic as semantic_module


class TestIsolatedDataDir:
    def test_reloads_metadata_cache_module_for_temp_cache_paths(
        self, isolated_data_dir
    ) -> None:
        expected_cache_path = isolated_data_dir / ".cache" / "metadata_cache.db"

        assert metadata_cache.get_metadata_db_path() == expected_cache_path

    def test_reloads_semantic_module_for_temp_index_paths(
        self, isolated_data_dir
    ) -> None:
        expected_index_path = isolated_data_dir / ".index" / "vectors_simple.pkl"

        assert semantic_module.get_vec_index_path() == expected_index_path
