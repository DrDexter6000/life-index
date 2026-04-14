#!/usr/bin/env python3
"""
Tests for entity --merge / --delete CLI operations — Round 7 Phase 2 Task 8.

Validates that:
- merge combines aliases and preserves relationships
- delete reports and cleans dangling refs
- both operations produce structured JSON output
"""

from pathlib import Path
import io
import sys

import pytest

from tools.lib.entity_graph import load_entity_graph, save_entity_graph


def _sample_graph() -> list[dict]:
    """Graph with two entities that can be merged."""
    return [
        {
            "id": "person-a",
            "type": "person",
            "primary_name": "张三",
            "aliases": ["老张"],
            "attributes": {},
            "relationships": [
                {"target": "person-c", "relation": "colleague_of"},
            ],
        },
        {
            "id": "person-b",
            "type": "person",
            "primary_name": "张叁",
            "aliases": ["小张"],
            "attributes": {},
            "relationships": [
                {"target": "person-c", "relation": "friend_of"},
            ],
        },
        {
            "id": "person-c",
            "type": "person",
            "primary_name": "李四",
            "aliases": [],
            "attributes": {},
            "relationships": [
                {"target": "person-a", "relation": "colleague_of"},
            ],
        },
    ]


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:
    from tools.lib.paths import USER_DATA_DIR

    save_entity_graph(entities, USER_DATA_DIR / "entity_graph.yaml")


def _graph_path_for(isolated_data_dir: Path) -> Path:
    return isolated_data_dir / "entity_graph.yaml"


class TestMergeCLI:
    """entity --merge combines aliases and preserves relationships."""

    def test_merge_combines_aliases(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import apply_action

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        result = apply_action(
            action="merge_as_alias",
            source_id="person-b",
            target_id="person-a",
            graph_path=gp,
        )

        assert result["success"] is True

        graph = load_entity_graph(gp)
        merged = next(e for e in graph if e["id"] == "person-a")
        # person-b's primary_name and alias should now be aliases on person-a
        assert "张叁" in merged["aliases"]
        assert "小张" in merged["aliases"]

    def test_merge_preserves_relationships(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import apply_action

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        result = apply_action(
            action="merge_as_alias",
            source_id="person-b",
            target_id="person-a",
            graph_path=gp,
        )

        assert result["success"] is True

        graph = load_entity_graph(gp)
        merged = next(e for e in graph if e["id"] == "person-a")
        rels = {(r["target"], r["relation"]) for r in merged.get("relationships", [])}
        # person-a's own rel preserved
        assert ("person-c", "colleague_of") in rels
        # person-b's rel transferred
        assert ("person-c", "friend_of") in rels

    def test_merge_updates_reverse_refs(self, isolated_data_dir: Path) -> None:
        from tools.entity.review import apply_action

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        apply_action(
            action="merge_as_alias",
            source_id="person-a",
            target_id="person-b",
            graph_path=gp,
        )

        graph = load_entity_graph(gp)
        # person-c was pointing to person-a — should now point to person-b
        person_c = next(e for e in graph if e["id"] == "person-c")
        targets = [r["target"] for r in person_c.get("relationships", [])]
        assert "person-a" not in targets
        assert "person-b" in targets


class TestDeleteCLI:
    """entity --delete removes entity and reports/cleans refs."""

    def test_delete_removes_entity(self, isolated_data_dir: Path) -> None:
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        main(["--delete", "--id", "person-b"])

        graph = load_entity_graph(gp)
        ids = {e["id"] for e in graph}
        assert "person-b" not in ids

    def test_delete_reports_cleaned_refs(self, isolated_data_dir: Path) -> None:
        """Deleting person-a should clean the ref from person-c."""
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        main(["--delete", "--id", "person-a"])

        graph = load_entity_graph(gp)
        person_c = next(e for e in graph if e["id"] == "person-c")
        targets = [r["target"] for r in person_c.get("relationships", [])]
        assert "person-a" not in targets

    def test_delete_uses_ascii_safe_json_on_narrow_stdout(
        self, isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete output should not crash on Windows-style non-UTF-8 stdout."""
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)

        buffer = io.BytesIO()
        fake_stdout = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
        monkeypatch.setattr(sys, "stdout", fake_stdout)

        main(["--delete", "--id", "person-a"])

        fake_stdout.flush()
        output = buffer.getvalue().decode("ascii")
        assert "\\u5f20" in output or "\\u674e" in output
        assert '"success": true' in output

    def test_delete_nonexistent_returns_error(self, isolated_data_dir: Path) -> None:
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        # Should not crash — outputs JSON with success=false
        main(["--delete", "--id", "nonexistent"])

        # Graph should be unchanged
        graph = load_entity_graph(gp)
        ids = {e["id"] for e in graph}
        assert "person-a" in ids  # nothing was deleted

    def test_delete_without_id_raises(self, isolated_data_dir: Path) -> None:
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)

        with pytest.raises(SystemExit):
            main(["--delete"])


class TestReviewCLI:
    """entity --review shows review queue."""

    def test_review_shows_queue(self, isolated_data_dir: Path) -> None:
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)

        # Should not crash
        main(["--review"])

    def test_review_with_action_skip(self, isolated_data_dir: Path) -> None:
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)

        main(["--review", "--action", "skip", "--id", "person-b"])
