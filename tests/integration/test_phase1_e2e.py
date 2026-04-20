"""
Phase 1 Integration Test — Entity graph cold-start + search + health + write (Round 10).

End-to-end verification that T1.1–T1.4 work together:
1. Graph doesn't exist → seed → graph is created
2. Search exposes graph status (not_initialized → initialized)
3. Health detects graph missing → fixed after seed
4. Write with new person returns frontmatter_fallback candidates + suggested_command
5. Seed again → idempotent (added: [])
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest


def _create_journal(
    journals_dir: Path,
    filename: str,
    title: str,
    people: list[str] | None = None,
    tags: list[str] | None = None,
    location: str = "",
    content: str = "",
) -> Path:
    """Helper to create a test journal file."""
    people_yaml = json.dumps(people or [], ensure_ascii=False)
    tags_yaml = json.dumps(tags or [], ensure_ascii=False)

    frontmatter = f"""---
title: "{title}"
date: 2026-03-04T19:43:02
location: "{location}"
weather: "晴天"
mood: ["温暖"]
people: {people_yaml}
tags: {tags_yaml}
topic: ["life"]
abstract: "测试日志"
---

# {title}

{content}
"""
    path = journals_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter, encoding="utf-8")
    return path


class TestPhase1Integration:
    """Phase 1 E2E: graph cold-start → search → health → write → seed again."""

    @pytest.mark.integration
    def test_full_phase1_chain(self, isolated_data_dir: Path) -> None:
        """
        Complete Phase 1 chain:
        1. Empty state: graph doesn't exist
        2. Seed → graph created with entities
        3. Search returns entity_graph_status: initialized
        4. Health no longer reports entity_graph_missing
        5. Write with new person → frontmatter_fallback candidates
        6. Seed again → idempotent (no new additions)
        """
        journals_root = isolated_data_dir / "Journals"
        month_dir = journals_root / "2026" / "03"
        graph_path = isolated_data_dir / "entity_graph.yaml"

        # Create multiple journals with overlapping people to meet min_frequency=2
        _create_journal(
            month_dir,
            "life-index_2026-03-04_001.md",
            "想念小英雄",
            people=["乐乐"],
            tags=["亲子", "回忆"],
            location="Chongqing, China",
            content="看到乐乐小时候的照片，那个只有2岁上下的小英雄。",
        )
        _create_journal(
            month_dir,
            "life-index_2026-03-05_001.md",
            "乐乐的生日",
            people=["乐乐"],
            tags=["生日"],
            location="Lagos, Nigeria",
            content="今天是乐乐的生日，祝她快乐。",
        )

        # ── Step 1: Verify graph doesn't exist ─────────────────────
        assert not graph_path.exists(), "Graph should not exist initially"

        # ── Step 2: Seed → graph created ───────────────────────────
        import tools.lib.config as cfg_mod

        importlib.reload(cfg_mod)
        from tools.entity.seed import seed_entity_graph

        seed_result = seed_entity_graph(graph_path, journals_root)

        assert seed_result["success"] is True, f"Seed failed: {seed_result}"
        # "乐乐" appears 2x in people → should be added
        added_names = {e["primary_name"] for e in seed_result["added"]}
        assert "乐乐" in added_names, (
            f"Expected '乐乐' in added, got: {seed_result['added']}"
        )

        # Graph file now exists
        assert graph_path.exists(), "Graph file should exist after seed"

        # ── Step 3: Search exposes graph status ─────────────────────
        import tools.lib.search_index as si_mod
        import tools.lib.fts_update as fu_mod
        import tools.lib.fts_search as fs_mod

        importlib.reload(cfg_mod)
        importlib.reload(si_mod)
        importlib.reload(fu_mod)
        importlib.reload(fs_mod)

        from tools.lib.search_index import update_index
        from tools.search_journals.core import hierarchical_search

        idx_result = update_index(incremental=False)
        assert idx_result["success"], f"Index build failed: {idx_result}"

        search_result = hierarchical_search("乐乐", semantic=False)
        assert search_result["success"] is True

        graph_status = search_result["entity_graph_status"]
        assert graph_status["status"] == "initialized", (
            f"Expected initialized, got: {graph_status}"
        )
        assert graph_status["entity_count"] >= 1

        # ── Step 4: Health no longer reports graph missing ──────────
        from tools.__main__ import _check_entity_graph
        from tools.lib.paths import resolve_user_data_dir

        graph_check_path = resolve_user_data_dir() / "entity_graph.yaml"
        graph_check = _check_entity_graph(graph_check_path)
        assert graph_check["status"] in ("ok", "degraded"), (
            f"Graph check should pass after seed, got: {graph_check}"
        )

        # ── Step 5: Write with new person → fallback candidates ────
        from tools.lib.entity_candidates import extract_entity_candidates

        candidates = extract_entity_candidates(
            metadata={"people": ["新朋友"], "tags": ["聚会"]},
            content="今天和新朋友一起吃饭",
            graph=[],  # Simulate no graph (or use loaded graph)
        )

        assert len(candidates) > 0, "Should return fallback candidates"
        new_friend = next(c for c in candidates if c["text"] == "新朋友")
        assert new_friend["source"] == "frontmatter_fallback"
        assert "suggested_command" in new_friend
        assert "entity --add" in new_friend["suggested_command"]

        # Verify suggested_command is valid JSON
        cmd = new_friend["suggested_command"]
        json_start = cmd.index("{")
        json_end = cmd.rindex("}") + 1
        entity_json = json.loads(cmd[json_start:json_end])
        assert entity_json["primary_name"] == "新朋友"
        assert entity_json["type"] == "person"

        # ── Step 6: Seed again → idempotent ─────────────────────────
        seed_result_2 = seed_entity_graph(graph_path, journals_root)
        assert seed_result_2["success"] is True
        assert len(seed_result_2["added"]) == 0, (
            f"Second seed should add nothing, got: {seed_result_2['added']}"
        )
        # "乐乐" should be in skipped_existing
        skipped_names = {e["primary_name"] for e in seed_result_2["skipped_existing"]}
        assert "乐乐" in skipped_names, (
            f"'乐乐' should be skipped as existing, got: {seed_result_2['skipped_existing']}"
        )

    @pytest.mark.integration
    def test_search_before_seed_shows_not_initialized(
        self, isolated_data_dir: Path
    ) -> None:
        """Before seeding, search should return entity_graph_status: not_initialized."""
        journals_dir = isolated_data_dir / "Journals" / "2026" / "03"

        _create_journal(
            journals_dir,
            "life-index_2026-03-04_001.md",
            "想念小英雄",
            people=["乐乐"],
            content="乐乐很可爱。",
        )

        import tools.lib.config as cfg_mod
        import tools.lib.search_index as si_mod
        import tools.lib.fts_update as fu_mod
        import tools.lib.fts_search as fs_mod

        importlib.reload(cfg_mod)
        importlib.reload(si_mod)
        importlib.reload(fu_mod)
        importlib.reload(fs_mod)

        from tools.lib.search_index import update_index
        from tools.search_journals.core import hierarchical_search

        idx_result = update_index(incremental=False)
        assert idx_result["success"]

        search_result = hierarchical_search("乐乐", semantic=False)
        graph_status = search_result["entity_graph_status"]
        assert graph_status["status"] == "not_initialized", (
            f"Expected not_initialized before seed, got: {graph_status}"
        )

    @pytest.mark.integration
    def test_write_candidates_with_existing_graph(
        self, isolated_data_dir: Path
    ) -> None:
        """With existing graph, write returns confirm_match for known, add_entity for new."""
        graph_path = isolated_data_dir / "entity_graph.yaml"
        journals_root = isolated_data_dir / "Journals"
        month_dir = journals_root / "2026" / "03"

        # Seed first
        _create_journal(
            month_dir,
            "life-index_2026-03-04_001.md",
            "想念小英雄",
            people=["乐乐"],
            content="乐乐很可爱。",
        )
        _create_journal(
            month_dir,
            "life-index_2026-03-05_001.md",
            "乐乐的日常",
            people=["乐乐"],
            content="乐乐今天很开心。",
        )

        import tools.lib.config as cfg_mod

        importlib.reload(cfg_mod)
        from tools.entity.seed import seed_entity_graph

        seed_entity_graph(graph_path, journals_root)

        # Now test entity_candidates WITH the loaded graph
        from tools.lib.entity_graph import load_entity_graph

        graph = load_entity_graph(graph_path)
        assert len(graph) > 0

        from tools.lib.entity_candidates import extract_entity_candidates

        candidates = extract_entity_candidates(
            metadata={"people": ["乐乐", "新朋友"]},
            content="乐乐和新朋友一起玩",
            graph=graph,
        )

        # "乐乐" should match existing entity
        tuantuan = next((c for c in candidates if c["text"] == "乐乐"), None)
        assert tuantuan is not None, "Should find '乐乐' candidate"
        assert tuantuan["suggested_action"] == "confirm_match"
        assert tuantuan["matched_entity_id"] is not None

        # "新朋友" should be add_entity
        new_friend = next((c for c in candidates if c["text"] == "新朋友"), None)
        assert new_friend is not None, "Should find '新朋友' candidate"
        assert new_friend["suggested_action"] == "add_entity"
        assert new_friend["matched_entity_id"] is None
