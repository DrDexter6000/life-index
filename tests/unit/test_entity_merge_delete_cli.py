#!/usr/bin/env python3
"""
Tests for entity review merge and maintain delete CLI operations.

Validates that:
- review merge combines aliases and preserves relationships
- maintain delete reports and cleans dangling refs
- destructive delete goes through preview/apply with backup
"""

import json
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
            "type": "actor",
            "primary_name": "张三",
            "aliases": ["老张"],
            "attributes": {},
            "relationships": [
                {"target": "person-c", "relation": "colleague_of"},
            ],
        },
        {
            "id": "person-b",
            "type": "actor",
            "primary_name": "张叁",
            "aliases": ["小张"],
            "attributes": {},
            "relationships": [
                {"target": "person-c", "relation": "friend_of"},
            ],
        },
        {
            "id": "person-c",
            "type": "actor",
            "primary_name": "李四",
            "aliases": [],
            "attributes": {},
            "relationships": [
                {"target": "person-a", "relation": "colleague_of"},
            ],
        },
    ]


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:
    save_entity_graph(entities, isolated_data_dir / "entity_graph.yaml")


def _graph_path_for(isolated_data_dir: Path) -> Path:
    return isolated_data_dir / "entity_graph.yaml"


class TestMergeCLI:
    """review merge_as_alias combines aliases and preserves relationships."""

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


class TestMaintainDeleteCLI:
    """entity maintain --delete removes entity and reports/cleans refs."""

    class _TeeStdout:
        """Simulate pytest tee-sys where reported encoding and write path diverge."""

        encoding = "utf-8"

        def __init__(self) -> None:
            self.captured_buffer = io.BytesIO()
            self.console_buffer = io.BytesIO()
            self.captured = io.TextIOWrapper(
                self.captured_buffer, encoding="utf-8", errors="strict"
            )
            self.console = io.TextIOWrapper(self.console_buffer, encoding="cp1252", errors="strict")

        def write(self, text: str) -> int:
            self.captured.write(text)
            return self.console.write(text)

        def flush(self) -> None:
            self.captured.flush()
            self.console.flush()

    def test_delete_removes_entity(self, isolated_data_dir: Path) -> None:
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        main(["maintain", "--delete", "--id", "person-b", "--apply", "--backup", "--json"])

        graph = load_entity_graph(gp)
        ids = {e["id"] for e in graph}
        assert "person-b" not in ids

    def test_delete_reports_cleaned_refs(self, isolated_data_dir: Path) -> None:
        """Deleting person-a should clean the ref from person-c."""
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        main(["maintain", "--delete", "--id", "person-a", "--apply", "--backup", "--json"])

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

        main(["maintain", "--delete", "--id", "person-a", "--apply", "--backup", "--json"])

        fake_stdout.flush()
        output = buffer.getvalue().decode("ascii")
        assert "\\u5f20" in output or "\\u674e" in output
        assert '"success": true' in output

    def test_delete_safe_when_stdout_encoding_and_write_path_diverge(
        self, isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Delete output should survive tee-style stdout on Windows CI."""
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)

        fake_stdout = self._TeeStdout()
        monkeypatch.setattr(sys, "stdout", fake_stdout)

        main(["maintain", "--delete", "--id", "person-a", "--apply", "--backup", "--json"])

        fake_stdout.flush()
        captured_output = fake_stdout.captured_buffer.getvalue().decode("utf-8")
        console_output = fake_stdout.console_buffer.getvalue().decode("ascii")

        assert '"success": true' in captured_output
        assert '"success": true' in console_output
        assert "\\u5f20" in console_output or "\\u674e" in console_output

    def test_delete_nonexistent_returns_error(self, isolated_data_dir: Path) -> None:
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        # Should not crash — outputs JSON with success=false
        main(["maintain", "--delete", "--id", "nonexistent", "--apply", "--backup", "--json"])

        # Graph should be unchanged
        graph = load_entity_graph(gp)
        ids = {e["id"] for e in graph}
        assert "person-a" in ids  # nothing was deleted

    def test_delete_without_id_returns_structured_error(
        self,
        isolated_data_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)

        main(["maintain", "--delete", "--apply", "--backup", "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["success"] is False
        assert payload["error"]["code"] == "ENTITY_MAINTAIN_DELETE_ID_REQUIRED"


class TestMaintainDeletePreviewCLI:
    """entity maintain --delete --preview reports impact without mutating the graph."""

    def test_preview_reports_deleted_id_name_and_cleaned_refs(
        self, isolated_data_dir: Path
    ) -> None:
        """maintain delete preview reports deleted_id, deleted_name, and cleaned_refs."""
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)

        # Capture stdout
        buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer
        try:
            main(["maintain", "--delete", "--preview", "--id", "person-a", "--json"])
        finally:
            sys.stdout = old_stdout

        output = json.loads(buffer.getvalue())
        assert output["success"] is True
        assert output["data"]["deleted_id"] == "person-a"
        assert output["data"]["deleted_name"] == "张三"
        # person-c has a relationship pointing to person-a
        assert len(output["data"]["cleaned_refs"]) == 1
        assert output["data"]["cleaned_refs"][0]["entity_id"] == "person-c"

    def test_preview_does_not_remove_entity(self, isolated_data_dir: Path) -> None:
        """Preview does not remove the target entity from the graph."""
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer
        try:
            main(["maintain", "--delete", "--preview", "--id", "person-a", "--json"])
        finally:
            sys.stdout = old_stdout

        graph = load_entity_graph(gp)
        ids = {e["id"] for e in graph}
        assert "person-a" in ids

    def test_preview_does_not_clean_relationship_refs(self, isolated_data_dir: Path) -> None:
        """Preview does not clean relationship refs from other entities."""
        from tools.entity.__main__ import main

        _save_graph(_sample_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        buffer = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buffer
        try:
            main(["maintain", "--delete", "--preview", "--id", "person-a", "--json"])
        finally:
            sys.stdout = old_stdout

        graph = load_entity_graph(gp)
        person_c = next(e for e in graph if e["id"] == "person-c")
        targets = [r["target"] for r in person_c.get("relationships", [])]
        assert "person-a" in targets


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
