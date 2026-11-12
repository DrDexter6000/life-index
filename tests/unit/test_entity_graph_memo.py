"""Entity graph memo: one parse per unchanged file, re-parse on change, safe copies."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def _entity(name: str = "Alice", alias: str = "Ally") -> dict:
    return {
        "id": "actor-alice",
        "type": "actor",
        "primary_name": name,
        "aliases": [alias],
        "attributes": {"kind": "human"},
        "relationships": [],
        "source": "user",
        "status": "confirmed",
    }


def _write_graph(path: Path, entities: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"entities": entities}, handle, allow_unicode=True, sort_keys=False)


def _count_graph_parses(monkeypatch, entity_graph_module) -> list[int]:
    counter = [0]
    original = yaml.safe_load

    def counting_safe_load(stream, *args, **kwargs):
        name = getattr(stream, "name", "")
        if isinstance(name, str) and os.path.basename(name) == "entity_graph.yaml":
            counter[0] += 1
        return original(stream, *args, **kwargs)

    monkeypatch.setattr(entity_graph_module.yaml, "safe_load", counting_safe_load)
    return counter


class TestGraphMemo:
    def test_unchanged_file_is_parsed_once_per_process(self, tmp_path: Path, monkeypatch):
        import tools.lib.entity_graph as entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _write_graph(graph_path, [_entity()])
        parses = _count_graph_parses(monkeypatch, entity_graph)

        first = load_entity_graph(graph_path)
        second = load_entity_graph(graph_path)
        third = load_entity_graph(graph_path)

        assert parses[0] == 1
        assert first == second == third

    def test_reparses_after_content_and_mtime_change(self, tmp_path: Path, monkeypatch):
        import tools.lib.entity_graph as entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _write_graph(graph_path, [_entity()])
        parses = _count_graph_parses(monkeypatch, entity_graph)
        assert load_entity_graph(graph_path)[0]["primary_name"] == "Alice"

        _write_graph(graph_path, [_entity(name="Bob")])

        assert load_entity_graph(graph_path)[0]["primary_name"] == "Bob"
        assert parses[0] == 2

    def test_reparses_after_size_change_with_mtime_restored(self, tmp_path: Path, monkeypatch):
        import tools.lib.entity_graph as entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _write_graph(graph_path, [_entity()])
        original = graph_path.stat()
        parses = _count_graph_parses(monkeypatch, entity_graph)
        assert load_entity_graph(graph_path)[0]["primary_name"] == "Alice"

        # Same mtime, different size: the signature is (mtime_ns, size), so the
        # memo must re-parse rather than trust the timestamp alone.
        _write_graph(graph_path, [_entity(name="Bartholomew")])
        os.utime(graph_path, ns=(original.st_atime_ns, original.st_mtime_ns))
        assert graph_path.stat().st_mtime_ns == original.st_mtime_ns
        assert graph_path.stat().st_size != original.st_size

        assert load_entity_graph(graph_path)[0]["primary_name"] == "Bartholomew"
        assert parses[0] == 2

    def test_missing_file_returns_empty_and_recreated_file_is_parsed(
        self, tmp_path: Path, monkeypatch
    ):
        import tools.lib.entity_graph as entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _write_graph(graph_path, [_entity()])
        parses = _count_graph_parses(monkeypatch, entity_graph)
        assert load_entity_graph(graph_path)

        graph_path.unlink()
        assert load_entity_graph(graph_path) == []

        _write_graph(graph_path, [_entity(name="Carol")])
        assert load_entity_graph(graph_path)[0]["primary_name"] == "Carol"
        assert parses[0] == 2

    def test_returned_structure_cannot_corrupt_the_memo(self, tmp_path: Path, monkeypatch):
        import tools.lib.entity_graph as entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        graph = _entity()
        graph["relationships"] = [
            {"target": "project-atlas", "relation": "owns"},
        ]
        _write_graph(
            graph_path,
            [
                graph,
                {
                    "id": "project-atlas",
                    "type": "project",
                    "primary_name": "Atlas",
                    "aliases": [],
                    "relationships": [],
                    "source": "user",
                    "status": "confirmed",
                },
            ],
        )
        parses = _count_graph_parses(monkeypatch, entity_graph)
        expected = load_entity_graph(graph_path)

        mutated = load_entity_graph(graph_path)
        mutated[0]["aliases"].append("injected")
        mutated[0]["alias_metadata"]["injected"] = {"source": "user"}
        mutated[0]["attributes"]["kind"] = "ai_model"
        mutated[0]["relationships"][0]["relation"] = "injected_relation"
        mutated[0]["relationships"].append({"target": "project-atlas", "relation": "injected"})
        mutated.append(
            {
                "id": "actor-injected",
                "type": "actor",
                "primary_name": "Injected",
                "aliases": [],
                "relationships": [],
            }
        )

        reloaded = load_entity_graph(graph_path)

        assert reloaded == expected
        assert parses[0] == 1

    def test_save_updates_the_memo_even_when_signature_looks_unchanged(self, tmp_path: Path):
        graph_path = tmp_path / "entity_graph.yaml"
        save_entity_graph([_entity(name="Alice")], graph_path)
        signature = graph_path.stat()
        assert load_entity_graph(graph_path)[0]["primary_name"] == "Alice"

        # Same byte length, then restore the exact previous (mtime_ns, size)
        # signature. Only the module's own save hook keeps the memo correct.
        save_entity_graph([_entity(name="Alicf")], graph_path)
        os.utime(graph_path, ns=(signature.st_atime_ns, signature.st_mtime_ns))
        assert graph_path.stat().st_size == signature.st_size
        assert graph_path.stat().st_mtime_ns == signature.st_mtime_ns

        assert load_entity_graph(graph_path)[0]["primary_name"] == "Alicf"

    def test_saving_does_not_alias_the_caller_graph(self, tmp_path: Path):
        graph_path = tmp_path / "entity_graph.yaml"
        entities = [_entity(name="Alice")]
        save_entity_graph(entities, graph_path)

        entities[0]["primary_name"] = "Mutated"
        entities[0]["attributes"]["kind"] = "ai_model"

        loaded = load_entity_graph(graph_path)
        assert loaded[0]["primary_name"] == "Alice"
        assert loaded[0]["attributes"]["kind"] == "human"
