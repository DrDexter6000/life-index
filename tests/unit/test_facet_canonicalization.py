from __future__ import annotations

from pathlib import Path

import yaml


def _write_graph(data_dir: Path, entities: list[dict]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "entity_graph.yaml").write_text(
        yaml.safe_dump({"entities": entities}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def test_canonicalizer_uses_entity_graph_aliases_by_allowed_facet_type(tmp_path: Path) -> None:
    from tools.lib.facet_canonicalization import load_facet_canonicalizer

    data_dir = tmp_path / "Life-Index"
    _write_graph(
        data_dir,
        [
            {
                "id": "project-life-index",
                "type": "project",
                "primary_name": "Life Index",
                "aliases": ["Life-Index", "Life Index 2.0"],
            },
            {
                "id": "place-lagos",
                "type": "place",
                "primary_name": "Lagos, Nigeria",
                "aliases": ["Lagos"],
            },
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "aliases": ["Alicia"],
            },
            {
                "id": "concept-ai",
                "type": "concept",
                "primary_name": "AI",
                "aliases": ["ai"],
            },
        ],
    )

    canonicalizer = load_facet_canonicalizer(data_dir)

    assert canonicalizer.status == "active"
    assert canonicalizer.canonicalize("project", " Life-Index ").value == "Life Index"
    assert canonicalizer.canonicalize("location", "Lagos").value == "Lagos, Nigeria"
    assert canonicalizer.canonicalize("people", "Alicia").value == "Alice"
    assert canonicalizer.canonicalize("tag", "ai").value == "AI"
    assert canonicalizer.canonicalize("project", "Lagos").value == "Lagos"
    assert canonicalizer.canonicalize("topic", "ai").value == "ai"
    assert canonicalizer.canonicalize("weather", "sunny").value == "sunny"
    assert canonicalizer.canonicalization_hash


def test_canonicalizer_fail_closes_ambiguous_labels(tmp_path: Path) -> None:
    from tools.lib.facet_canonicalization import load_facet_canonicalizer

    data_dir = tmp_path / "Life-Index"
    _write_graph(
        data_dir,
        [
            {
                "id": "project-phoenix",
                "type": "project",
                "primary_name": "Phoenix",
                "aliases": [],
            },
            {
                "id": "place-phoenix",
                "type": "place",
                "primary_name": "Phoenix",
                "aliases": [],
            },
        ],
    )

    canonicalizer = load_facet_canonicalizer(data_dir)

    assert canonicalizer.canonicalize("tag", "Phoenix").value == "Phoenix"
    assert any(item["code"] == "ambiguous_alias" for item in canonicalizer.diagnostics)
    assert canonicalizer.canonicalize("project", "Phoenix").value == "Phoenix"


def test_canonicalizer_degrades_invalid_graph_to_noop_with_diagnostic(tmp_path: Path) -> None:
    from tools.lib.facet_canonicalization import load_facet_canonicalizer

    data_dir = tmp_path / "Life-Index"
    _write_graph(
        data_dir,
        [
            {
                "id": "person-alice",
                "type": "person",
                "primary_name": "Alice",
                "relationships": [{"target": "missing", "relation": "knows"}],
            }
        ],
    )

    canonicalizer = load_facet_canonicalizer(data_dir)

    assert canonicalizer.status == "disabled"
    assert canonicalizer.canonicalize("people", "Alice").value == "Alice"
    assert canonicalizer.canonicalization_hash
    assert canonicalizer.diagnostics[0]["code"] == "entity_graph_invalid"
