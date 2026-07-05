"""Contract tests for the entity audit facade."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import yaml

from tools.lib.entity_graph import save_entity_graph


def _run_entity_cli(argv: list[str]) -> dict:
    from tools.entity.__main__ import main

    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        main(argv)
    finally:
        sys.stdout = old_stdout
    return json.loads(buffer.getvalue())


def test_entity_audit_facade_reports_combined_health_without_writes(
    isolated_data_dir: Path,
) -> None:
    """`entity audit --json` is a read-only health facade over check/audit/stats."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "source": "user",
                "status": "confirmed",
                "relationships": [],
            },
            {
                "id": "person-morgan",
                "type": "person",
                "primary_name": "Morgan",
                "source": "agent",
                "status": "candidate",
                "reason": "Host agent saw repeated evidence.",
                "evidence": ["Journals/2026/07/life-index_2026-07-01_001.md"],
                "relationships": [],
            },
        ],
        graph_path,
    )
    before = graph_path.read_text(encoding="utf-8")

    payload = _run_entity_cli(["audit", "--json"])

    after = graph_path.read_text(encoding="utf-8")
    assert after == before
    assert payload["success"] is True
    assert payload["data"]["workflow"] == "audit"
    assert payload["data"]["traffic_light"] == "yellow"
    assert payload["data"]["pending_count"] == 1
    assert payload["data"]["structural_issue_count"] == 0
    assert payload["data"]["quality_issue_count"] == 1
    assert payload["data"]["next_step"]["command"] == "life-index entity --review"
    assert payload["data"]["components"]["check"]["summary"]["schema_issues"] == 0
    assert payload["data"]["components"]["stats"]["total_entities"] == 2


def test_entity_audit_facade_reports_red_for_structural_issues(
    isolated_data_dir: Path,
) -> None:
    """Structural graph errors should still return a red audit facade payload."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    graph_path.write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "person-alice",
                        "type": "person",
                        "primary_name": "Alice",
                        "relationships": [{"target": "person-missing", "relation": "knows"}],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = _run_entity_cli(["audit", "--json"])

    assert payload["success"] is True
    assert payload["data"]["traffic_light"] == "red"
    assert payload["data"]["structural_issue_count"] == 1
    assert payload["data"]["components"]["check"]["issues"][0]["type"] == "dangling_relationship"
    assert payload["data"]["component_errors"]["audit"]
    assert payload["data"]["component_errors"]["stats"]
