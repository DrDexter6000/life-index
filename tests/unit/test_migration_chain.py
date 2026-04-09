"""Tests for schema migration chain framework."""

import pytest
from tools.lib.schema import (
    SCHEMA_VERSION,
    get_migration_chain,
    run_migration_chain,
    MigrationResult,
)


class TestMigrationChain:
    def test_get_chain_v1_to_current(self):
        """v1 to current version should return ordered migration step list."""
        chain = get_migration_chain(1, SCHEMA_VERSION)
        assert len(chain) >= 1
        # Each step is (from_ver, to_ver, func) triple
        assert chain[0][0] == 1
        assert chain[0][1] == 2
        assert chain[-1][1] == SCHEMA_VERSION

    def test_get_chain_current_to_current_is_empty(self):
        """Already at latest version: migration chain is empty."""
        chain = get_migration_chain(SCHEMA_VERSION, SCHEMA_VERSION)
        assert chain == []

    def test_get_chain_missing_version_raises(self):
        """Non-existent version jump should raise ValueError."""
        with pytest.raises(ValueError, match="no migration path"):
            get_migration_chain(0, SCHEMA_VERSION)

    def test_run_chain_v1_to_v2(self):
        """v1 metadata should be migrated to v2 format."""
        meta_v1 = {
            "schema_version": 1,
            "title": "测试",
            "date": "2026-01-01",
            "mood": ["开心"],
            "tags": ["测试"],
            "topic": ["life"],
        }
        result = run_migration_chain(meta_v1, content="测试正文")
        assert isinstance(result, MigrationResult)
        assert result.metadata["schema_version"] == SCHEMA_VERSION
        assert "sentiment_score" in result.metadata
        assert "themes" in result.metadata
        assert "entities" in result.metadata
        assert len(result.deterministic_changes) >= 1

    def test_run_chain_already_current_is_noop(self):
        """Already-current metadata should not be modified."""
        meta_current = {
            "schema_version": SCHEMA_VERSION,
            "title": "测试",
            "date": "2026-01-01",
            "sentiment_score": 0.5,
            "themes": [],
            "entities": [],
        }
        result = run_migration_chain(meta_current, content="")
        assert result.metadata == meta_current
        assert result.deterministic_changes == []
        assert result.needs_agent == []

    def test_migration_result_dataclass(self):
        """MigrationResult should contain three fields."""
        r = MigrationResult(
            metadata={"schema_version": 2},
            deterministic_changes=["added sentiment_score"],
            needs_agent=["abstract missing"],
        )
        assert r.metadata["schema_version"] == 2
        assert len(r.deterministic_changes) == 1
        assert len(r.needs_agent) == 1

    def test_run_chain_detects_needs_agent_for_empty_abstract(self):
        """V1 journal without abstract/summary should flag needs_agent."""
        meta_v1 = {
            "schema_version": 1,
            "title": "无摘要",
            "date": "2026-01-01",
            "mood": ["开心"],
        }
        result = run_migration_chain(meta_v1, content="正文内容")
        assert len(result.needs_agent) >= 1
        assert any(
            "abstract" in item or "summary" in item for item in result.needs_agent
        )

    def test_run_chain_detects_needs_agent_for_empty_mood(self):
        """V1 journal with empty mood should flag needs_agent."""
        meta_v1 = {
            "schema_version": 1,
            "title": "无心情",
            "date": "2026-01-01",
            "mood": [],
            "abstract": "有摘要",
        }
        result = run_migration_chain(meta_v1, content="正文")
        assert any("mood" in item for item in result.needs_agent)

    def test_run_chain_no_needs_agent_when_complete(self):
        """Complete v1 journal with abstract and mood should have no needs_agent."""
        meta_v1 = {
            "schema_version": 1,
            "title": "完整",
            "date": "2026-01-01",
            "mood": ["开心"],
            "abstract": "这是摘要",
        }
        result = run_migration_chain(meta_v1, content="正文")
        assert result.needs_agent == []

    def test_missing_schema_version_treated_as_v1(self):
        """Metadata without schema_version should be treated as v1."""
        meta = {
            "title": "无版本号",
            "date": "2026-01-01",
        }
        result = run_migration_chain(meta, content="正文")
        assert result.metadata["schema_version"] == SCHEMA_VERSION

    def test_run_chain_does_not_mutate_input(self):
        """run_migration_chain should not mutate the original metadata dict."""
        meta_v1 = {
            "schema_version": 1,
            "title": "测试",
            "date": "2026-01-01",
        }
        original = dict(meta_v1)
        run_migration_chain(meta_v1, content="正文")
        assert meta_v1 == original
