#!/usr/bin/env python3

from pathlib import Path

import pytest


def _sample_entity_graph() -> dict:
    return {
        "entities": [
            {
                "id": "author-self",
                "type": "person",
                "primary_name": "我",
                "aliases": ["作者", "自己"],
                "relationships": [],
            },
            {
                "id": "mama",
                "type": "person",
                "primary_name": "妈妈",
                "aliases": ["老妈", "婆婆"],
                "relationships": [{"target": "author-self", "relation": "mother_of"}],
            },
            {
                "id": "tuantuan",
                "type": "person",
                "primary_name": "乐乐",
                "aliases": ["圆圆"],
                "relationships": [{"target": "mama", "relation": "granddaughter_of"}],
            },
        ]
    }


class TestEntitySchema:
    def test_relationship_targets_must_exist_in_graph(self) -> None:
        from tools.lib.entity_schema import (
            EntityGraphValidationError,
            RESERVED_RELATIONSHIP_TARGETS,
            validate_entity_graph_payload,
        )

        payload = {
            "entities": [
                {
                    "id": "mama",
                    "type": "person",
                    "primary_name": "妈妈",
                    "relationships": [{"target": "unknown", "relation": "mother_of"}],
                }
            ]
        }

        assert RESERVED_RELATIONSHIP_TARGETS == set()
        with pytest.raises(
            EntityGraphValidationError, match="unknown relationship target"
        ):
            validate_entity_graph_payload(payload)

    def test_valid_entity_accepted(self) -> None:
        from tools.lib.entity_schema import validate_entity_graph_payload

        payload = _sample_entity_graph()

        validated = validate_entity_graph_payload(payload)

        assert len(validated) == 3
        assert validated[1]["id"] == "mama"

    def test_missing_required_fields_rejected(self) -> None:
        from tools.lib.entity_schema import (
            EntityGraphValidationError,
            validate_entity_graph_payload,
        )

        payload = {"entities": [{"id": "mama", "type": "person"}]}

        with pytest.raises(EntityGraphValidationError, match="primary_name"):
            validate_entity_graph_payload(payload)

    def test_duplicate_id_rejected(self) -> None:
        from tools.lib.entity_schema import (
            EntityGraphValidationError,
            validate_entity_graph_payload,
        )

        payload = {
            "entities": [
                {"id": "mama", "type": "person", "primary_name": "妈妈"},
                {"id": "mama", "type": "person", "primary_name": "老妈"},
            ]
        }

        with pytest.raises(EntityGraphValidationError, match="duplicate entity id"):
            validate_entity_graph_payload(payload)

    def test_invalid_type_rejected(self) -> None:
        from tools.lib.entity_schema import (
            EntityGraphValidationError,
            validate_entity_graph_payload,
        )

        payload = {
            "entities": [{"id": "mama", "type": "animal", "primary_name": "妈妈"}]
        }

        with pytest.raises(EntityGraphValidationError, match="invalid entity type"):
            validate_entity_graph_payload(payload)

    def test_relationship_target_exists(self) -> None:
        from tools.lib.entity_schema import (
            EntityGraphValidationError,
            validate_entity_graph_payload,
        )

        payload = {
            "entities": [
                {
                    "id": "mama",
                    "type": "person",
                    "primary_name": "妈妈",
                    "relationships": [{"target": "unknown", "relation": "mother_of"}],
                }
            ]
        }

        with pytest.raises(
            EntityGraphValidationError, match="unknown relationship target"
        ):
            validate_entity_graph_payload(payload)

    def test_alias_no_duplicate_across_entities(self) -> None:
        from tools.lib.entity_schema import (
            EntityGraphValidationError,
            validate_entity_graph_payload,
        )

        payload = {
            "entities": [
                {
                    "id": "mama",
                    "type": "person",
                    "primary_name": "妈妈",
                    "aliases": ["老妈"],
                },
                {
                    "id": "tuantuan",
                    "type": "person",
                    "primary_name": "乐乐",
                    "aliases": ["老妈"],
                },
            ]
        }

        with pytest.raises(EntityGraphValidationError, match="alias conflict"):
            validate_entity_graph_payload(payload)


class TestEntityGraphPersistence:
    def test_load_and_save_entity_graph_roundtrip(self, tmp_path: Path) -> None:
        from tools.lib.entity_graph import load_entity_graph, save_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        payload = _sample_entity_graph()["entities"]

        save_entity_graph(payload, graph_path)
        loaded = load_entity_graph(graph_path)

        assert loaded[0]["primary_name"] == "我"
        assert loaded[2]["id"] == "tuantuan"

    def test_resolve_entity_by_id_primary_name_or_alias(self, tmp_path: Path) -> None:
        from tools.lib.entity_graph import resolve_entity, save_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        payload = _sample_entity_graph()["entities"]
        save_entity_graph(payload, graph_path)

        by_id = resolve_entity("mama", payload)
        by_name = resolve_entity("妈妈", payload)
        by_alias = resolve_entity("婆婆", payload)

        assert by_id is not None
        assert by_name is not None
        assert by_alias is not None
        assert by_id["primary_name"] == "妈妈"
        assert by_name["id"] == "mama"
        assert by_alias["id"] == "mama"

    def test_resolve_relationship(self, tmp_path: Path) -> None:
        from tools.lib.entity_graph import resolve_relationship, save_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        payload = _sample_entity_graph()["entities"]
        save_entity_graph(payload, graph_path)

        resolved = resolve_relationship("tuantuan", "granddaughter_of", payload)

        assert resolved is not None
        assert resolved["id"] == "mama"


class TestEntityCache:
    def test_build_and_query_entity_cache(self, tmp_path: Path) -> None:
        from tools.lib.entity_cache import build_entity_cache, query_entity_cache
        from tools.lib.entity_graph import save_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        db_path = tmp_path / "entity_cache.db"
        payload = _sample_entity_graph()["entities"]
        save_entity_graph(payload, graph_path)

        build_entity_cache(graph_path, db_path)
        results = query_entity_cache(db_path, "婆婆")

        assert len(results) == 1
        assert results[0]["id"] == "mama"


class TestEntityCli:
    def test_entity_list_cli(
        self, isolated_data_dir: Path, monkeypatch, capsys
    ) -> None:
        from tools import __main__
        from tools.lib.entity_graph import save_entity_graph

        graph_path = isolated_data_dir / "entity_graph.yaml"
        save_entity_graph(_sample_entity_graph()["entities"], graph_path)

        monkeypatch.setattr(__main__.sys, "argv", ["life-index", "entity", "--list"])

        __main__.main()
        captured = capsys.readouterr()

        assert '"success": true' in captured.out
        assert '"mama"' in captured.out

    def test_entity_resolve_cli(
        self, isolated_data_dir: Path, monkeypatch, capsys
    ) -> None:
        from tools import __main__
        from tools.lib.entity_graph import save_entity_graph

        graph_path = isolated_data_dir / "entity_graph.yaml"
        save_entity_graph(_sample_entity_graph()["entities"], graph_path)

        monkeypatch.setattr(
            __main__.sys, "argv", ["life-index", "entity", "--resolve", "婆婆"]
        )

        __main__.main()
        captured = capsys.readouterr()

        assert '"success": true' in captured.out
        assert '"primary_name": "妈妈"' in captured.out
