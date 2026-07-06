from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.lib.entity_graph import load_entity_graph


def _run_entity_cli(argv: list[str]) -> dict[str, Any]:
    from tools.entity.__main__ import main

    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer
    try:
        main(argv)
    finally:
        sys.stdout = old_stdout
    return json.loads(buffer.getvalue())


def _write_journal(path: Path, frontmatter: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
        + "---\n\nJournal body.\n",
        encoding="utf-8",
    )


def test_legacy_person_type_load_fails_closed_with_normalize_guidance(
    isolated_data_dir: Path,
) -> None:
    from tools.lib.entity_graph import load_entity_graph
    from tools.lib.entity_schema import EntityGraphValidationError

    graph_path = isolated_data_dir / "entity_graph.yaml"
    graph_path.write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "person-alice",
                        "type": "person",
                        "primary_name": "Alice",
                        "aliases": [],
                        "relationships": [],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(EntityGraphValidationError) as exc_info:
        load_entity_graph(graph_path)

    exc = exc_info.value
    assert exc.code == "ENTITY_SCHEMA_LEGACY"
    assert exc.details["legacy_type"] == "person"
    assert (
        exc.details["replacement_command"]
        == "life-index entity maintain --normalize --preview --json"
    )
    assert "maintain --normalize" in str(exc)

    check = _run_entity_cli(["--check"])
    issue = next(
        item for item in check["data"]["issues"] if item.get("code") == "ENTITY_SCHEMA_LEGACY"
    )
    assert issue["details"]["legacy_type"] == "person"
    assert (
        issue["suggested_action"]["command"]
        == "life-index entity maintain --normalize --preview --json"
    )
    assert check["data"]["summary"]["schema_issues"] == 1


def test_normalize_migrates_merged_entity_tombstones_before_schema_cutover(
    isolated_data_dir: Path,
) -> None:
    graph_path = isolated_data_dir / "entity_graph.yaml"
    graph_path.write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "actor-alice",
                        "type": "actor",
                        "primary_name": "Alice",
                        "aliases": ["Alicia"],
                        "attributes": {"kind": "human"},
                        "relationships": [],
                        "merged_entities": [
                            {
                                "id": "person-ally",
                                "target_id": "actor-alice",
                                "source": "user",
                                "merged_at": "2026-07-01T00:00:00+00:00",
                                "entity": {
                                    "id": "person-ally",
                                    "type": "person",
                                    "primary_name": "Ally",
                                    "aliases": [],
                                    "relationships": [],
                                },
                                "transferred_aliases": ["Ally"],
                                "transferred_relationships": [],
                                "rewired_relationships": [],
                            }
                        ],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    payload = _run_entity_cli(["maintain", "--normalize", "--apply", "--backup", "--json"])

    assert payload["success"] is True
    graph = load_entity_graph(graph_path)
    tombstone_entity = graph[0]["merged_entities"][0]["entity"]
    assert tombstone_entity["type"] == "actor"
    assert tombstone_entity["attributes"]["kind"] == "human"


def test_build_from_journals_preview_uses_cutover_entity_types(isolated_data_dir: Path) -> None:
    journals_dir = isolated_data_dir / "Journals" / "2026" / "01"
    _write_journal(
        journals_dir / "life-index_2026-01-01_001.md",
        {
            "title": "One",
            "date": "2026-01-01",
            "people": ["Alice"],
            "location": "Garden",
            "tags": ["Project Atlas"],
        },
    )
    _write_journal(
        journals_dir / "life-index_2026-01-02_001.md",
        {
            "title": "Two",
            "date": "2026-01-02",
            "people": ["Alice"],
            "location": "Garden",
            "tags": ["Project Atlas"],
        },
    )

    preview = _run_entity_cli(["build", "--from-journals", "--preview", "--json"])

    assert preview["success"] is True
    by_name = {item["primary_name"]: item for item in preview["data"]["added"]}
    assert by_name["Alice"]["type"] == "actor"
    assert by_name["Alice"]["attributes"]["kind"] == "human"
    assert by_name["Garden"]["type"] == "place"
    assert by_name["Project Atlas"]["type"] == "concept"

    batch_path = isolated_data_dir / "journal-seed-batch.yaml"
    batch_path.write_text(
        yaml.safe_dump(
            {"entities": preview["data"]["added"], "relationships": []}, sort_keys=False
        ),
        encoding="utf-8",
    )
    applied = _run_entity_cli(["build", "--from-batch", str(batch_path), "--apply", "--json"])

    assert applied["success"] is True
    graph = {
        entity["primary_name"]: entity
        for entity in load_entity_graph(isolated_data_dir / "entity_graph.yaml")
    }
    assert graph["Alice"]["type"] == "actor"
    assert graph["Alice"]["attributes"]["kind"] == "human"


def test_write_time_candidate_pool_uses_cutover_entity_types(isolated_data_dir: Path) -> None:
    from tools.write_journal.core import write_journal

    for day in (1, 2):
        result = write_journal(
            {
                "date": f"2026-07-{day:02d}",
                "title": f"Fixture {day}",
                "content": "Abstract fixture content.",
                "people": ["Morgan"],
                "location": "Test Lab",
                "weather": "Clear",
                "topic": ["life"],
                "mood": [],
                "tags": [],
            },
            dry_run=False,
        )
        assert result["success"] is True

    graph = load_entity_graph(isolated_data_dir / "entity_graph.yaml")
    candidate = next(entity for entity in graph if entity["primary_name"] == "Morgan")
    assert candidate["type"] == "actor"
    assert candidate["attributes"]["kind"] == "human"
    assert candidate["status"] == "candidate"


def test_agent_propose_accepts_cutover_entity_payload(isolated_data_dir: Path, capsys) -> None:
    from tools.entity.__main__ import main

    proposal = {
        "kind": "entity",
        "id": "actor-morgan",
        "entity_type": "actor",
        "primary_name": "Morgan",
        "attributes": {"kind": "human"},
        "reason": "Host agent saw repeated evidence.",
        "evidence": ["Journals/2026/07/life-index_2026-07-02_001.md"],
    }

    main(["--propose", json.dumps(proposal)])
    payload = json.loads(capsys.readouterr().out)

    assert payload["success"] is True
    graph = load_entity_graph(isolated_data_dir / "entity_graph.yaml")
    candidate = next(entity for entity in graph if entity["id"] == "actor-morgan")
    assert candidate["type"] == "actor"
    assert candidate["attributes"]["kind"] == "human"
    assert candidate["status"] == "candidate"
