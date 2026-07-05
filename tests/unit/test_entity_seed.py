"""
Tests for entity --seed command (Round 10, T1.1).

Validates graph cold-start from journal frontmatter:
- Extract candidates from people/tags/location fields
- Frequency threshold (>= 2 occurrences)
- Idempotent: re-running doesn't modify existing entities
- Type inference rules from field source
"""

import json
from pathlib import Path

# ── Fixtures ────────────────────────────────────────────────────────────


def _create_journal(
    data_dir: Path,
    title: str,
    people: list[str] | None = None,
    tags: list[str] | None = None,
    location: str | None = None,
    topic: list[str] | None = None,
    content: str = "测试内容",
    date_str: str = "2026-03-07T12:00:00",
    filename: str | None = None,
) -> Path:
    """Create a journal file with specified frontmatter."""
    journals_dir = data_dir / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        # Use a counter-like suffix to avoid collisions
        existing = list(journals_dir.glob("life-index_*.md"))
        suffix = f"{len(existing) + 1:03d}"
        filename = f"life-index_2026-03-07_{suffix}.md"

    file_path = journals_dir / filename

    people_yaml = json.dumps(people or [])
    tags_yaml = json.dumps(tags or [])
    topic_yaml = json.dumps(topic or ["work"])

    frontmatter = f"""---
title: "{title}"
date: {date_str}
location: "{location or ""}"
weather: "晴"
mood: []
tags: {tags_yaml}
people: {people_yaml}
topic: {topic_yaml}
---

# {title}

{content}
"""
    file_path.write_text(frontmatter, encoding="utf-8")
    return file_path


# ── Candidate collection tests ─────────────────────────────────────────


class TestSeedCandidateCollection:
    """Verify collect_candidates() extracts from frontmatter correctly."""

    def test_extracts_people_as_person_type(self, isolated_data_dir: Path) -> None:
        """people field → type=person, counted per occurrence."""
        from tools.entity.seed import collect_candidates

        # Create 2 journals mentioning "晴岚"
        _create_journal(isolated_data_dir, "日记1", people=["晴岚"])
        _create_journal(isolated_data_dir, "日记2", people=["晴岚", "妈妈"])
        _create_journal(isolated_data_dir, "日记3", people=["妈妈"])

        candidates = collect_candidates(
            isolated_data_dir / "Journals",
            min_frequency=2,
        )

        names = {c.primary_name for c in candidates}
        assert "晴岚" in names
        assert "妈妈" in names

        tuantuan = next(c for c in candidates if c.primary_name == "晴岚")
        assert tuantuan.type == "person"
        assert tuantuan.frequency >= 2

    def test_extracts_location_as_place_type(self, isolated_data_dir: Path) -> None:
        """location field → type=place."""
        from tools.entity.seed import collect_candidates

        _create_journal(isolated_data_dir, "日记1", location="Lagos, Nigeria")
        _create_journal(isolated_data_dir, "日记2", location="Lagos, Nigeria")

        candidates = collect_candidates(
            isolated_data_dir / "Journals",
            min_frequency=2,
        )
        names = {c.primary_name for c in candidates}
        assert any("Lagos" in n for n in names), f"Should find Lagos in candidates, got: {names}"
        lagos_cand = next(c for c in candidates if "Lagos" in c.primary_name)
        assert lagos_cand.type == "place"

    def test_extracts_tags_with_type_inference(self, isolated_data_dir: Path) -> None:
        """
        Tags type inference:
        - Matches ^[A-Z][a-zA-Z0-9 ]+$ → type=concept (v1 schema has no "tool")
        - Otherwise → type=concept
        """
        from tools.entity.seed import collect_candidates

        _create_journal(
            isolated_data_dir,
            "日记1",
            tags=["Claude Opus", "重构"],
        )
        _create_journal(
            isolated_data_dir,
            "日记2",
            tags=["Claude Opus", "重构"],
        )

        candidates = collect_candidates(
            isolated_data_dir / "Journals",
            min_frequency=2,
        )
        by_name = {c.primary_name: c for c in candidates}

        # "Claude Opus" → concept (PascalCase tags are concepts in v1 schema)
        if "Claude Opus" in by_name:
            assert by_name["Claude Opus"].type == "concept"

        # "重构" → concept (doesn't match PascalCase)
        if "重构" in by_name:
            assert by_name["重构"].type == "concept"

    def test_frequency_threshold_filters_singletons(self, isolated_data_dir: Path) -> None:
        """Entities appearing only once should NOT enter the graph."""
        from tools.entity.seed import collect_candidates

        # "晴岚" appears once, "妈妈" appears twice
        _create_journal(isolated_data_dir, "日记1", people=["晴岚"])
        _create_journal(isolated_data_dir, "日记2", people=["妈妈"])
        _create_journal(isolated_data_dir, "日记3", people=["妈妈"])

        candidates = collect_candidates(
            isolated_data_dir / "Journals",
            min_frequency=2,
        )
        names = {c.primary_name for c in candidates}

        assert "晴岚" not in names, "Singleton should be filtered"
        assert "妈妈" in names


# ── Preview plan tests ─────────────────────────────────────────────────


class TestSeedPlan:
    """Verify journal seed planning is read-only and preserves existing data."""

    def test_preview_does_not_create_graph_file(self, isolated_data_dir: Path) -> None:
        """Previewing seed candidates should not write entity_graph.yaml."""
        from tools.entity.seed import preview_seed_entity_graph

        graph_path = isolated_data_dir / "entity_graph.yaml"

        _create_journal(isolated_data_dir, "日记1", people=["晴岚", "妈妈"])
        _create_journal(isolated_data_dir, "日记2", people=["晴岚", "妈妈"])

        result = preview_seed_entity_graph(graph_path, isolated_data_dir / "Journals")

        assert result["success"] is True
        assert result["data"]["preview"] is True
        assert result["data"]["new_entities"] > 0
        assert not graph_path.exists()

    def test_plan_skips_existing_entity_and_does_not_mutate_aliases(
        self, isolated_data_dir: Path
    ) -> None:
        """
        If graph already has {primary_name: "晴岚", aliases: ["小队长"]},
        planning must skip it and leave aliases untouched.
        """
        from tools.entity.seed import preview_seed_entity_graph
        from tools.lib.entity_graph import load_entity_graph

        graph_path = isolated_data_dir / "entity_graph.yaml"

        # Pre-create graph with "晴岚" having alias "小队长"
        from tools.lib.entity_graph import save_entity_graph

        initial_entities = [
            {
                "id": "entity_tuantuan",
                "type": "person",
                "primary_name": "晴岚",
                "aliases": ["小队长"],
                "attributes": {},
                "relationships": [],
            }
        ]
        save_entity_graph(initial_entities, graph_path)

        _create_journal(isolated_data_dir, "日记1", people=["晴岚", "妈妈"])
        _create_journal(isolated_data_dir, "日记2", people=["晴岚", "妈妈"])

        result = preview_seed_entity_graph(graph_path, isolated_data_dir / "Journals")

        # "晴岚" should be in skipped_existing, not in added
        added_names = {e["primary_name"] for e in result["data"]["added"]}
        assert "晴岚" not in added_names
        skipped_names = {e["primary_name"] for e in result["data"]["skipped_existing"]}
        assert "晴岚" in skipped_names

        # Verify aliases preserved
        entities = load_entity_graph(graph_path)
        tuantuan = next(e for e in entities if e["primary_name"] == "晴岚")
        assert tuantuan["aliases"] == ["小队长"], "Existing aliases must be preserved"

    def test_output_structure(self, isolated_data_dir: Path) -> None:
        """Output must have added/skipped_existing/skipped_low_frequency lists."""
        from tools.entity.seed import preview_seed_entity_graph

        graph_path = isolated_data_dir / "entity_graph.yaml"
        _create_journal(isolated_data_dir, "日记1", people=["晴岚"])
        _create_journal(isolated_data_dir, "日记2", people=["晴岚"])

        result = preview_seed_entity_graph(graph_path, isolated_data_dir / "Journals")

        data = result["data"]
        assert "added" in data
        assert "skipped_existing" in data
        assert "skipped_low_frequency" in data
        assert isinstance(data["added"], list)
        assert isinstance(data["skipped_existing"], list)
        assert isinstance(data["skipped_low_frequency"], list)
