#!/usr/bin/env python3
"""Entity source authority and neutral review semantics."""

from __future__ import annotations

import json
from pathlib import Path

from tools.lib.entity_graph import save_entity_graph


def _save_graph(data_dir: Path, entities: list[dict]) -> Path:
    graph_path = data_dir / "entity_graph.yaml"
    save_entity_graph(entities, graph_path)
    return graph_path


def test_user_confirmed_entity_and_relationship_need_no_journal_evidence(
    isolated_data_dir: Path,
) -> None:
    from tools.entity.audit import audit_entity_graph

    graph_path = _save_graph(
        isolated_data_dir,
        [
            {
                "id": "person-alice",
                "type": "actor",
                "primary_name": "Alice",
                "aliases": [],
                "source": "user",
                "status": "confirmed",
                "relationships": [
                    {
                        "target": "person-bob",
                        "relation": "grandparent_of",
                        "source": "user",
                        "status": "confirmed",
                        "evidence": [],
                    }
                ],
            },
            {
                "id": "person-bob",
                "type": "actor",
                "primary_name": "Bob",
                "aliases": [],
                "source": "user",
                "status": "confirmed",
                "relationships": [],
            },
        ],
    )

    report = audit_entity_graph(graph_path, journals_dir=isolated_data_dir / "Journals")

    assert report["issues"] == []
    assert report["summary"] == {"high": 0, "medium": 0, "low": 0}


def test_audit_and_review_use_neutral_pending_language_not_archive_decisions(
    isolated_data_dir: Path,
) -> None:
    from tools.entity.audit import audit_entity_graph
    from tools.entity.review import build_review_queue

    graph_path = _save_graph(
        isolated_data_dir,
        [
            {
                "id": "person-morgan",
                "type": "actor",
                "primary_name": "Morgan",
                "aliases": [],
                "source": "seed",
                "status": "candidate",
                "reason": "Repeated unknown person mention.",
                "evidence": ["Journals/2026/07/life-index_2026-07-02_001.md"],
                "relationships": [],
            }
        ],
    )

    report = audit_entity_graph(graph_path, journals_dir=isolated_data_dir / "Journals")
    queue = build_review_queue(graph_path=graph_path)
    combined = json.dumps({"audit": report, "queue": queue}, ensure_ascii=False).lower()

    assert "archive" not in combined
    assert "orphan_entity" not in combined
    assert any(issue["type"] == "candidate_entity" for issue in report["issues"])
    candidate = next(item for item in queue if item["category"] == "candidate_entity")
    assert candidate["suggested_action"] == "review"
    assert [choice["action"] for choice in candidate["action_choices"]] == [
        "confirm_candidate",
        "reject_candidate",
        "skip",
    ]
    assert candidate["action_choices"][0]["source_id"] == "person-morgan"
    assert candidate["action_choices"][0]["evidence"] == [
        "Journals/2026/07/life-index_2026-07-02_001.md"
    ]
    assert "human review" in candidate["why"].lower()
