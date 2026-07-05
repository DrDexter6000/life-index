"""Contract tests for the Entity Graph build facade."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from tools.lib.entity_graph import load_entity_graph
from tools.lib.entity_graph import save_entity_graph


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


def _write_batch(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "id": "actor-alice",
                        "type": "actor",
                        "primary_name": "Alice",
                        "aliases": ["A."],
                        "attributes": {"kind": "human"},
                    },
                    {
                        "id": "place-garden",
                        "type": "place",
                        "primary_name": "Garden",
                    },
                ],
                "relationships": [
                    {
                        "source": "actor-alice",
                        "target": "place-garden",
                        "relation": "visited",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_journal(path: Path, frontmatter: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        + yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
        + "---\n\nJournal body.\n",
        encoding="utf-8",
    )


def test_entity_build_from_batch_preview_delegates_without_writes(
    isolated_data_dir: Path,
) -> None:
    """Build facade preview preserves batch semantics and does not mutate graph."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph([], graph_path)
    batch_path = isolated_data_dir / "batch.yaml"
    _write_batch(batch_path)
    before = graph_path.read_text(encoding="utf-8")

    payload = _run_entity_cli(["build", "--from-batch", str(batch_path), "--preview", "--json"])

    assert graph_path.read_text(encoding="utf-8") == before
    assert payload["success"] is True
    assert payload["data"] == {
        "preview": True,
        "new_entities": 2,
        "new_relationships": 1,
        "conflicts": 0,
        "duplicates_skipped": 0,
        "conflict_items": [],
    }
    assert payload["error"] is None


def test_entity_build_from_batch_apply_delegates_to_batch_apply(
    isolated_data_dir: Path,
) -> None:
    """Build facade apply writes the same confirmed graph as --apply-batch."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph([], graph_path)
    batch_path = isolated_data_dir / "batch.yaml"
    _write_batch(batch_path)

    payload = _run_entity_cli(["build", "--from-batch", str(batch_path), "--apply", "--json"])

    assert payload["success"] is True
    assert payload["data"]["preview"] is False
    assert payload["data"]["new_entities"] == 2
    assert payload["data"]["new_relationships"] == 1
    graph = {entity["id"]: entity for entity in load_entity_graph(graph_path)}
    assert graph["actor-alice"]["source"] == "user"
    assert graph["actor-alice"]["status"] == "confirmed"
    assert graph["actor-alice"]["attributes"]["kind"] == "human"
    assert graph["actor-alice"]["relationships"][0]["target"] == "place-garden"


def test_entity_build_from_journals_preview_plans_seed_without_writes(
    isolated_data_dir: Path,
) -> None:
    """Build facade can preview journal-derived seed candidates without mutation."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    save_entity_graph(
        [
            {
                "id": "person-existing",
                "type": "person",
                "primary_name": "Existing Person",
                "aliases": [],
                "relationships": [],
            }
        ],
        graph_path,
    )
    journals_dir = isolated_data_dir / "Journals" / "2026" / "01"
    _write_journal(
        journals_dir / "life-index_2026-01-01_001.md",
        {
            "title": "One",
            "date": "2026-01-01",
            "people": ["Alice", "Existing Person", "Single Mention"],
            "location": "Garden",
            "tags": ["Project Atlas"],
        },
    )
    _write_journal(
        journals_dir / "life-index_2026-01-02_001.md",
        {
            "title": "Two",
            "date": "2026-01-02",
            "people": ["Alice", "Existing Person"],
            "location": "Garden",
            "tags": ["Project Atlas"],
        },
    )
    before = graph_path.read_text(encoding="utf-8")

    payload = _run_entity_cli(["build", "--from-journals", "--preview", "--json"])

    assert graph_path.read_text(encoding="utf-8") == before
    assert payload["success"] is True
    assert payload["data"]["preview"] is True
    assert payload["data"]["source"] == "journals"
    assert payload["data"]["new_entities"] == 3
    assert payload["data"]["skipped_existing"] == [
        {"primary_name": "Existing Person", "type": "person", "frequency": 2}
    ]
    assert payload["data"]["skipped_low_frequency"] == [
        {"primary_name": "Single Mention", "type": "person", "frequency": 1}
    ]
    planned_names = {item["primary_name"] for item in payload["data"]["added"]}
    assert planned_names == {"Alice", "Garden", "Project Atlas"}
    assert payload["error"] is None


def test_entity_build_from_journals_preview_to_batch_apply_closes_cold_start_loop(
    isolated_data_dir: Path,
) -> None:
    """Cold-start build uses previewed journal candidates followed by batch apply."""
    graph_path = isolated_data_dir / "entity_graph.yaml"
    journals_dir = isolated_data_dir / "Journals" / "2026" / "01"
    _write_journal(
        journals_dir / "life-index_2026-01-01_001.md",
        {
            "title": "One",
            "date": "2026-01-01",
            "people": ["Alice"],
            "location": "Garden",
            "tags": [],
        },
    )
    _write_journal(
        journals_dir / "life-index_2026-01-02_001.md",
        {
            "title": "Two",
            "date": "2026-01-02",
            "people": ["Alice"],
            "location": "Garden",
            "tags": [],
        },
    )

    preview = _run_entity_cli(["build", "--from-journals", "--preview", "--json"])
    assert preview["success"] is True
    assert not graph_path.exists()

    batch_path = isolated_data_dir / "journal-seed-batch.yaml"
    batch_path.write_text(
        yaml.safe_dump(
            {"entities": preview["data"]["added"], "relationships": []},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    applied = _run_entity_cli(["build", "--from-batch", str(batch_path), "--apply", "--json"])

    assert applied["success"] is True
    graph = {entity["primary_name"]: entity for entity in load_entity_graph(graph_path)}
    assert set(graph) == {"Alice", "Garden"}
    assert all(entity["source"] == "user" for entity in graph.values())
    assert all(entity["status"] == "confirmed" for entity in graph.values())
