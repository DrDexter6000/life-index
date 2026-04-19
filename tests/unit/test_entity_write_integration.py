#!/usr/bin/env python3

from pathlib import Path


def _entity_graph_payload() -> list[dict]:
    return [
        {
            "id": "mama",
            "type": "person",
            "primary_name": "妈妈",
            "aliases": ["老妈", "婆婆"],
            "relationships": [],
        },
        {
            "id": "chongqing",
            "type": "place",
            "primary_name": "重庆",
            "aliases": ["老家", "山城"],
            "relationships": [],
        },
    ]


class TestEntityDetectionOnWrite:
    def test_new_entity_detected_on_write(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.write_journal.core import write_journal

        save_entity_graph(_entity_graph_payload(), isolated_data_dir / "entity_graph.yaml")

        result = write_journal(
            {
                "date": "2026-04-03",
                "title": "新的朋友",
                "content": "今天和小王见面。",
                "people": ["小王"],
                "location": "重庆",
            },
            dry_run=True,
        )

        assert result["success"] is True
        assert result["new_entities_detected"] == ["小王"]

    def test_known_entity_no_alert(self, isolated_data_dir: Path) -> None:
        from tools.lib.entity_graph import save_entity_graph
        from tools.write_journal.core import write_journal

        save_entity_graph(_entity_graph_payload(), isolated_data_dir / "entity_graph.yaml")

        result = write_journal(
            {
                "date": "2026-04-03",
                "title": "回家",
                "content": "今天回重庆看妈妈。",
                "people": ["妈妈"],
                "location": "重庆",
            },
            dry_run=True,
        )

        assert result["success"] is True
        assert result["new_entities_detected"] == []
