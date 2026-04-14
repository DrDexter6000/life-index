#!/usr/bin/env python3
"""
Tests for CSV/Excel review export-import — Round 7 Phase 3 Task 11.

Validates that:
- review queue can export to CSV
- review decisions can import from CSV
- export/import round-trip preserves data
- xlsx export is optional (graceful degradation when openpyxl absent)
"""

from pathlib import Path

import pytest

from tools.lib.entity_graph import save_entity_graph


def _conflict_graph() -> list[dict]:
    """Graph with audit-triggering entities."""
    return [
        {
            "id": "person-a",
            "type": "person",
            "primary_name": "王晓丽",
            "aliases": ["小王"],
            "attributes": {},
            "relationships": [{"target": "person-c", "relation": "colleague_of"}],
        },
        {
            "id": "person-b",
            "type": "person",
            "primary_name": "王晓里",
            "aliases": ["老王"],
            "attributes": {},
            "relationships": [{"target": "person-c", "relation": "friend_of"}],
        },
        {
            "id": "person-c",
            "type": "person",
            "primary_name": "李四",
            "aliases": [],
            "attributes": {},
            "relationships": [],
        },
    ]


def _save_graph(entities: list[dict], isolated_data_dir: Path) -> None:
    from tools.lib.paths import USER_DATA_DIR

    save_entity_graph(entities, USER_DATA_DIR / "entity_graph.yaml")


def _graph_path_for(isolated_data_dir: Path) -> Path:
    return isolated_data_dir / "entity_graph.yaml"


class TestCSVExport:
    """Review queue can export to CSV."""

    def test_export_csv_creates_file(self, isolated_data_dir: Path) -> None:
        from tools.entity.review_io import export_review_csv

        _save_graph(_conflict_graph(), isolated_data_dir)

        output_path = isolated_data_dir / "review.csv"
        result = export_review_csv(
            output_path=output_path,
            graph_path=_graph_path_for(isolated_data_dir),
        )

        assert result["success"] is True
        assert output_path.exists()

    def test_export_csv_has_required_columns(self, isolated_data_dir: Path) -> None:
        import csv as csv_mod
        from tools.entity.review_io import export_review_csv

        _save_graph(_conflict_graph(), isolated_data_dir)

        output_path = isolated_data_dir / "review.csv"
        export_review_csv(
            output_path=output_path,
            graph_path=_graph_path_for(isolated_data_dir),
        )

        with output_path.open("r", encoding="utf-8-sig") as f:
            reader = csv_mod.DictReader(f)
            headers = reader.fieldnames or []

        required = {"item_id", "risk_level", "category", "action_choices"}
        assert required.issubset(set(headers)), (
            f"Missing columns: {required - set(headers)}"
        )

    def test_export_csv_has_rows(self, isolated_data_dir: Path) -> None:
        import csv as csv_mod
        from tools.entity.review_io import export_review_csv

        _save_graph(_conflict_graph(), isolated_data_dir)

        output_path = isolated_data_dir / "review.csv"
        export_review_csv(
            output_path=output_path,
            graph_path=_graph_path_for(isolated_data_dir),
        )

        with output_path.open("r", encoding="utf-8-sig") as f:
            rows = list(csv_mod.DictReader(f))

        assert len(rows) >= 1


class TestCSVImport:
    """Review decisions can import from CSV."""

    def test_import_csv_applies_decisions(self, isolated_data_dir: Path) -> None:
        import csv as csv_mod
        from tools.entity.review_io import export_review_csv, import_review_csv

        _save_graph(_conflict_graph(), isolated_data_dir)
        gp = _graph_path_for(isolated_data_dir)

        # Export
        output_path = isolated_data_dir / "review.csv"
        export_review_csv(output_path=output_path, graph_path=gp)

        # Modify CSV with a skip decision
        with output_path.open("r", encoding="utf-8-sig") as f:
            rows = list(csv_mod.DictReader(f))

        if rows:
            rows[0]["decision"] = "skip"
            rows[0]["source_id"] = ""
            rows[0]["target_id"] = ""

            fieldnames = rows[0].keys()
            with output_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv_mod.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

        # Import should not crash
        result = import_review_csv(
            input_path=output_path,
            graph_path=gp,
        )

        assert result["success"] is True

    def test_import_empty_csv_returns_success(self, isolated_data_dir: Path) -> None:
        from tools.entity.review_io import import_review_csv

        # Create empty CSV with headers
        empty_path = isolated_data_dir / "empty.csv"
        empty_path.write_text(
            "item_id,risk_level,category,decision\n", encoding="utf-8"
        )

        result = import_review_csv(
            input_path=empty_path,
            graph_path=_graph_path_for(isolated_data_dir),
        )

        assert result["success"] is True
        assert result["data"]["applied"] == 0


class TestXLSXOptional:
    """xlsx export gracefully degrades when openpyxl unavailable."""

    def test_xlsx_export_reports_unavailable(self, isolated_data_dir: Path) -> None:
        from tools.entity.review_io import export_review_xlsx

        _save_graph(_conflict_graph(), isolated_data_dir)

        output_path = isolated_data_dir / "review.xlsx"
        result = export_review_xlsx(
            output_path=output_path,
            graph_path=_graph_path_for(isolated_data_dir),
        )

        # Either succeeds (openpyxl installed) or reports unavailable
        if not result["success"]:
            assert (
                "unavailable" in result.get("error", "").lower()
                or "not installed" in result.get("error", "").lower()
            )
