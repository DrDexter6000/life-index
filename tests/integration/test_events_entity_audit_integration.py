"""Integration tests for events + entity audit workflow."""

import os
import time
import pytest
from pathlib import Path


class TestEventEntityAuditIntegration:
    def test_stale_graph_triggers_event_with_audit_command(self, tmp_path: Path):
        """Entity graph > 30 days old → event with suggested_command."""
        from tools.lib.event_detectors import check_entity_audit_due

        graph_file = tmp_path / "entity_graph.yaml"
        graph_file.write_text("entities: []", encoding="utf-8")
        old_time = time.time() - 35 * 86400
        os.utime(graph_file, (old_time, old_time))

        events = check_entity_audit_due({"data_dir": tmp_path})
        assert len(events) == 1
        assert events[0].data["suggested_command"] == "life-index entity --audit"

    def test_audit_report_actionable_by_agent(self, tmp_path: Path):
        """Audit report issues should each contain suggested_action."""
        import yaml
        from tools.entity.audit import audit_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        graph_path.write_text(
            yaml.dump(
                {
                    "entities": [
                        {
                            "id": "p1",
                            "type": "person",
                            "primary_name": "妈妈",
                            "aliases": [],
                            "relationships": [],
                        },
                        {
                            "id": "p2",
                            "type": "person",
                            "primary_name": "母亲",
                            "aliases": [],
                            "relationships": [],
                        },
                    ]
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

        report = audit_entity_graph(graph_path, journals_dir=None)
        for issue in report["issues"]:
            assert "suggested_action" in issue

    def test_full_event_detection_under_budget(self, tmp_path: Path):
        """All 5 detectors should execute in < 100ms."""
        from tools.lib.events import EventRegistry
        from tools.lib.event_detectors import (
            check_no_journal_streak,
            check_monthly_review_due,
            check_entity_audit_due,
            check_schema_migration_available,
            check_index_stale,
        )

        registry = EventRegistry()
        registry.register("streak", check_no_journal_streak)
        registry.register("review", check_monthly_review_due)
        registry.register("entity", check_entity_audit_due)
        registry.register("schema", check_schema_migration_available)
        registry.register("index", check_index_stale)

        context = {
            "journals_dir": tmp_path / "Journals",
            "data_dir": tmp_path,
        }
        (tmp_path / "Journals").mkdir()

        start = time.monotonic()
        events = registry.detect_all(context=context, timeout_ms=50)
        elapsed_ms = (time.monotonic() - start) * 1000

        assert elapsed_ms < 100  # Relaxed for CI
