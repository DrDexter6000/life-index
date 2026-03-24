#!/usr/bin/env python3
"""Regression tests for pytest fixture isolation."""

import tools.lib.metadata_cache as metadata_cache


class TestIsolatedDataDir:
    def test_reloads_metadata_cache_module_for_temp_cache_paths(
        self, isolated_data_dir
    ) -> None:
        expected_cache_path = isolated_data_dir / ".cache" / "metadata_cache.db"

        assert metadata_cache.METADATA_DB_PATH == expected_cache_path
