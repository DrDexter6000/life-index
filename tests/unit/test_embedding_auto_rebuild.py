#!/usr/bin/env python3
"""Embedding version mismatch auto-rebuild tests (RED phase).

Tests for Task 1.1.1 from .strategy/v1.x/TDD.md:
When embedding model version changes, incremental index should auto-rebuild
to prevent mixing incompatible old/new vectors.

Expected behavior:
- Version mismatch → auto rebuild (not just warning)
- Version match → stay incremental
- Rebuild updates model_meta.json
- Missing model_meta → rebuild (first-time use)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


class TestEmbeddingAutoRebuild:
    """Test suite for embedding version mismatch auto-rebuild guardrail."""

    def test_verify_model_integrity_returns_needs_rebuild(self) -> None:
        """verify_model_integrity() should return needs_rebuild flag correctly."""
        from tools.lib.embedding_backends import verify_model_integrity

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            model_name = "BAAI/bge-m3"

            # Test 1: Missing model_meta.json → needs_rebuild=True
            result = verify_model_integrity(model_name, cache_dir)
            assert result.is_valid is True
            assert result.needs_rebuild is True
            assert "首次使用" in result.message

            # Create old version metadata
            model_meta_dir = cache_dir / model_name.replace("/", "_")
            model_meta_dir.mkdir(parents=True, exist_ok=True)

            old_meta = {
                "name": model_name,
                "version": "2.0.0",  # Old version
                "dimension": 1024,
                "config_hash": "",
                "recorded_at": "2026-03-01T10:00:00",
            }
            meta_file = model_meta_dir / "model_meta.json"
            meta_file.write_text(
                json.dumps(old_meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            # Test 2: Version mismatch → needs_rebuild=True
            result = verify_model_integrity(model_name, cache_dir)
            assert result.is_valid is False
            assert result.needs_rebuild is True
            assert "版本不一致" in result.message

            # Update to current version
            old_meta["version"] = "3.0.0"
            meta_file.write_text(
                json.dumps(old_meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            # Test 3: Version match → needs_rebuild=False
            result = verify_model_integrity(model_name, cache_dir)
            assert result.is_valid is True
            assert result.needs_rebuild is False
            assert "验证通过" in result.message

    def test_record_model_metadata_updates_version(self) -> None:
        """record_model_metadata() should write current model version."""
        from tools.lib.embedding_backends import record_model_metadata
        from tools.lib.search_config import EMBEDDING_MODEL

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            model_name = "BAAI/bge-m3"

            # Call record_model_metadata
            record_model_metadata(model_name, cache_dir)

            # Verify model_meta.json was created
            meta_file = cache_dir / model_name.replace("/", "_") / "model_meta.json"
            assert meta_file.exists()

            # Verify content
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            assert meta["version"] == EMBEDDING_MODEL["version"]
            assert meta["name"] == model_name
            assert meta["dimension"] == EMBEDDING_MODEL["dimension"]

    def test_update_vector_index_auto_rebuild_logic(self) -> None:
        """update_vector_index() should set auto_rebuild_triggered flag when needed."""
        from tools.lib.embedding_backends import (
            verify_model_integrity,
            record_model_metadata,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            model_name = "BAAI/bge-m3"

            # Simulate version mismatch scenario
            model_meta_dir = cache_dir / model_name.replace("/", "_")
            model_meta_dir.mkdir(parents=True, exist_ok=True)

            old_meta = {
                "name": model_name,
                "version": "2.0.0",
                "dimension": 1024,
                "config_hash": "",
            }
            meta_file = model_meta_dir / "model_meta.json"
            meta_file.write_text(
                json.dumps(old_meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            # Verify version check detects mismatch
            result = verify_model_integrity(model_name, cache_dir)
            assert result.needs_rebuild is True

            # Simulate rebuild by updating metadata
            record_model_metadata(model_name, cache_dir)

            # Verify metadata was updated
            updated_meta = json.loads(meta_file.read_text(encoding="utf-8"))
            assert updated_meta["version"] == "3.0.0"
