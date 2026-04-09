"""Tests for entity --audit functionality."""

import pytest
import yaml
from pathlib import Path


def _create_entity_graph(path: Path, entities: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    yaml_data = {"entities": entities}
    path.write_text(yaml.dump(yaml_data, allow_unicode=True), encoding="utf-8")


class TestEntityAuditDuplicates:
    def test_detects_similar_names(self, tmp_path: Path):
        """Highly similar entity names should be flagged as possible duplicates."""
        from tools.entity.audit import audit_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _create_entity_graph(
            graph_path,
            [
                {
                    "id": "person_001",
                    "type": "person",
                    "primary_name": "妈妈",
                    "aliases": [],
                    "relationships": [],
                },
                {
                    "id": "person_002",
                    "type": "person",
                    "primary_name": "母亲",
                    "aliases": [],
                    "relationships": [],
                },
            ],
        )

        report = audit_entity_graph(graph_path, journals_dir=None)
        duplicates = [i for i in report["issues"] if i["type"] == "possible_duplicate"]
        assert len(duplicates) >= 1
        entity_names = set()
        for d in duplicates:
            entity_names.update(d["entities"])
        assert "妈妈" in entity_names or "母亲" in entity_names

    def test_detects_alias_overlap(self, tmp_path: Path):
        """An alias matching another entity's primary_name should flag."""
        from tools.entity.audit import audit_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _create_entity_graph(
            graph_path,
            [
                {
                    "id": "person_001",
                    "type": "person",
                    "primary_name": "张三",
                    "aliases": ["小张"],
                    "relationships": [],
                },
                {
                    "id": "person_002",
                    "type": "person",
                    "primary_name": "小张",
                    "aliases": [],
                    "relationships": [],
                },
            ],
        )

        report = audit_entity_graph(graph_path, journals_dir=None)
        duplicates = [i for i in report["issues"] if i["type"] == "possible_duplicate"]
        assert len(duplicates) >= 1


class TestEntityAuditOrphans:
    def test_detects_orphan_entities(self, tmp_path: Path):
        """Entities with zero references in journals should be flagged."""
        from tools.entity.audit import audit_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _create_entity_graph(
            graph_path,
            [
                {
                    "id": "person_001",
                    "type": "person",
                    "primary_name": "无人引用",
                    "aliases": [],
                    "relationships": [],
                },
            ],
        )

        journals_dir = tmp_path / "Journals" / "2026" / "04"
        journals_dir.mkdir(parents=True)
        (journals_dir / "life-index_2026-04-01_001.md").write_text(
            "---\ntitle: 测试\ndate: 2026-04-01\npeople: []\nentities: []\n---\n\n正文\n",
            encoding="utf-8",
        )

        report = audit_entity_graph(graph_path, journals_dir=tmp_path / "Journals")
        orphans = [i for i in report["issues"] if i["type"] == "orphan_entity"]
        assert len(orphans) >= 1
        assert orphans[0]["entity_id"] == "person_001"


class TestEntityAuditIncompleteRelationships:
    def test_detects_frequent_co_occurrence_without_relationship(self, tmp_path: Path):
        """Entities frequently co-occurring without relationship should be flagged."""
        from tools.entity.audit import audit_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _create_entity_graph(
            graph_path,
            [
                {
                    "id": "person_001",
                    "type": "person",
                    "primary_name": "爸爸",
                    "aliases": [],
                    "relationships": [],
                },
                {
                    "id": "person_002",
                    "type": "person",
                    "primary_name": "妈妈",
                    "aliases": [],
                    "relationships": [],
                },
            ],
        )

        journals_dir = tmp_path / "Journals" / "2026" / "04"
        journals_dir.mkdir(parents=True)
        for day in range(1, 4):
            (journals_dir / f"life-index_2026-04-0{day}_001.md").write_text(
                f"---\ntitle: 日志{day}\ndate: 2026-04-0{day}\n"
                'people: ["爸爸", "妈妈"]\n---\n\n和爸爸妈妈一起吃饭\n',
                encoding="utf-8",
            )

        report = audit_entity_graph(graph_path, journals_dir=tmp_path / "Journals")
        incomplete = [
            i for i in report["issues"] if i["type"] == "incomplete_relationship"
        ]
        assert len(incomplete) >= 1


class TestEntityAuditOutputFormat:
    def test_report_has_required_structure(self, tmp_path: Path):
        """Audit report should contain all required fields."""
        from tools.entity.audit import audit_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _create_entity_graph(
            graph_path,
            [
                {
                    "id": "p1",
                    "type": "person",
                    "primary_name": "测试人",
                    "aliases": [],
                    "relationships": [],
                },
            ],
        )

        report = audit_entity_graph(graph_path, journals_dir=None)
        assert "audit_date" in report
        assert "total_entities" in report
        assert "issues" in report
        assert "summary" in report
        assert isinstance(report["issues"], list)
        assert isinstance(report["summary"], dict)

    def test_each_issue_has_required_fields(self, tmp_path: Path):
        """Each issue should contain type, severity, suggested_action."""
        from tools.entity.audit import audit_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _create_entity_graph(
            graph_path,
            [
                {
                    "id": "p1",
                    "type": "person",
                    "primary_name": "A",
                    "aliases": ["B"],
                    "relationships": [],
                },
                {
                    "id": "p2",
                    "type": "person",
                    "primary_name": "B",
                    "aliases": [],
                    "relationships": [],
                },
            ],
        )

        report = audit_entity_graph(graph_path, journals_dir=None)
        for issue in report["issues"]:
            assert "type" in issue
            assert "severity" in issue
            assert issue["severity"] in ("high", "medium", "low")
            assert "suggested_action" in issue

    def test_empty_graph_returns_clean_report(self, tmp_path: Path):
        """Empty entity graph should return clean report with zero issues."""
        from tools.entity.audit import audit_entity_graph

        graph_path = tmp_path / "entity_graph.yaml"
        _create_entity_graph(graph_path, [])

        report = audit_entity_graph(graph_path, journals_dir=None)
        assert report["total_entities"] == 0
        assert report["issues"] == []
        assert report["summary"] == {"high": 0, "medium": 0, "low": 0}
