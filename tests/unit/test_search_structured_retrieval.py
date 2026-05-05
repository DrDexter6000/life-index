"""
R1-Prep: Structured metadata retrieval tests.

Verifies that when search_plan provides both date_range and topic_hints,
hierarchical_search supplements the keyword pipeline with pure metadata
matches (no keyword filtering), allowing logs whose body lacks query
keywords but whose topic/date align with user intent to enter the candidate set.
"""

from pathlib import Path

import pytest

from tools.search_journals.core import hierarchical_search
from tools.search_journals.ranking import (
    merge_and_rank_results,
    merge_and_rank_results_hybrid,
)


@pytest.fixture
def structured_retrieval_data_dir(tmp_path: Path):
    """Create a minimal data dir with two logs: one matches query keywords,
    one matches topic+date but lacks query keywords in body."""
    journals_dir = tmp_path / "Journals" / "2026" / "03"
    journals_dir.mkdir(parents=True)

    # Log A: matches "三月" and "工作" in body (FTS will hit)
    (journals_dir / "life-index_2026-03-14_001.md").write_text(
        "---\n"
        'title: "三月工作总结"\n'
        "date: 2026-03-14T10:00:00\n"
        'topic: ["work"]\n'
        "---\n\n"
        "这是三月份的工作总结。\n",
        encoding="utf-8",
    )

    # Log B: topic=work, date=2026-03, but body lacks "三月"/"工作"/"日志"
    # This is the target that structured retrieval should recall.
    (journals_dir / "life-index_2026-03-27_001.md").write_text(
        "---\n"
        'title: "Carloha Wiki AI Chat Bot 项目"\n'
        "date: 2026-03-27T23:59:00\n"
        'topic: ["work"]\n'
        "---\n\n"
        "本项目使用 BM25 算法优化搜索相关性。\n"
        "TF-IDF 已经被替换为更高效的方案。\n",
        encoding="utf-8",
    )

    return tmp_path


class TestStructuredRetrieval:
    def test_structured_candidates_added_when_date_range_and_topic_hints_present(
        self, structured_retrieval_data_dir: Path, monkeypatch
    ):
        monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-04")
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(structured_retrieval_data_dir))

        result = hierarchical_search(
            query="三月份的工作日志",
            semantic=False,
            level=3,
            explain=False,
        )

        # Verify warning is emitted
        warnings = result.get("warnings", [])
        assert any(
            "structured_metadata" in w for w in warnings
        ), f"Expected structured_metadata warning, got {warnings}"

        # Verify L2 contains structured candidates
        l2_titles = [r.get("title", "") for r in result["l2_results"]]
        assert (
            "Carloha Wiki AI Chat Bot 项目" in l2_titles
        ), f"Expected structured candidate in L2, got {l2_titles}"

        # Verify the structured candidate has correct source marker
        structured = [r for r in result["l2_results"] if r.get("source") == "structured_metadata"]
        assert len(structured) >= 1
        titles = [r.get("title", "") for r in structured]
        assert "Carloha Wiki AI Chat Bot 项目" in titles

    def test_structured_candidates_not_added_when_topic_hints_missing(
        self, structured_retrieval_data_dir: Path, monkeypatch
    ):
        monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-04")
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(structured_retrieval_data_dir))

        # "2026年03月" has date_range but no topic_hints
        result = hierarchical_search(
            query="2026年03月",
            semantic=False,
            level=3,
            explain=False,
        )

        warnings = result.get("warnings", [])
        assert not any(
            "structured_metadata" in w for w in warnings
        ), "Did not expect structured_metadata warning for query without topic_hints"

    def test_structured_candidates_not_added_when_date_range_missing(
        self, structured_retrieval_data_dir: Path, monkeypatch
    ):
        monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-04")
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(structured_retrieval_data_dir))

        # "工作日志" has topic_hints but no date_range
        result = hierarchical_search(
            query="工作日志",
            semantic=False,
            level=3,
            explain=False,
        )

        warnings = result.get("warnings", [])
        assert not any(
            "structured_metadata" in w for w in warnings
        ), "Did not expect structured_metadata warning for query without date_range"

    def test_structured_candidate_survives_candidate_path_filtering(
        self, structured_retrieval_data_dir: Path, monkeypatch
    ):
        monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-04")
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(structured_retrieval_data_dir))

        result = hierarchical_search(
            query="三月份的工作日志",
            semantic=False,
            level=3,
            explain=False,
        )

        merged_titles = [r.get("title", "") for r in result["merged_results"]]
        assert "Carloha Wiki AI Chat Bot 项目" in merged_titles, (
            "Expected structured candidate to survive filtering and appear in merged, got "
            f"{merged_titles}"
        )

    def test_structured_intent_bonus_applied_keyword_path(
        self, structured_retrieval_data_dir: Path, monkeypatch
    ):
        """Keyword path: structured-intent matches receive bonus on top of L2 base score."""
        monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-05-04")
        monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(structured_retrieval_data_dir))

        result = hierarchical_search(
            query="三月份的工作日志",
            semantic=False,
            level=3,
            explain=False,
        )

        carloha = [r for r in result["merged_results"] if "Carloha" in r.get("title", "")]
        assert len(carloha) >= 1
        # L2 base 30 + keyword bonus 50 = 80
        assert (
            carloha[0]["final_score"] >= 80
        ), f"Expected structured candidate final_score >= 80, got {carloha[0].get('final_score')}"


class TestStructuredIntentBonus:
    """R1: Ranking-layer structured-intent bonus behaviour."""

    def test_structured_intent_bonus_affects_hybrid_ranking(self) -> None:
        """Hybrid path: bonus raises final_score enough to reorder within bucket."""
        semantic_a = {
            "path": "a.md",
            "similarity": 0.40,
            "title": "A",
            "date": "2026-03-15",
            "topic": ["work"],
        }
        semantic_b = {
            "path": "b.md",
            "similarity": 0.45,
            "title": "B",
            "date": "2026-04-15",
            "topic": ["learn"],
        }

        merged = merge_and_rank_results_hybrid(
            [],
            [],
            [],
            [semantic_b, semantic_a],
            query="test",
            min_rrf_score=0.0,
            min_non_rrf_score=0.0,
            date_range={"since": "2026-03-01", "until": "2026-03-31"},
            topic_hints=["work"],
        )

        paths = [r["path"] for r in merged]
        # semantic_b has higher raw similarity but no structured match;
        # semantic_a has lower similarity but gets +0.035 structured bonus.
        assert (
            paths[0] == "a.md"
        ), f"Expected structured-intent match to outrank non-match, got {paths}"

    def test_semantic_only_structured_candidate_no_fake_fts_score(self) -> None:
        """Semantic-only candidates must never receive fabricated fts_score or FTS source."""
        semantic_result = {
            "path": "doc.md",
            "similarity": 0.45,
            "title": "Doc",
            "date": "2026-03-15",
            "topic": ["work"],
        }

        merged = merge_and_rank_results_hybrid(
            [],
            [],
            [],
            [semantic_result],
            query="test",
            min_rrf_score=0.0,
            min_non_rrf_score=0.0,
            date_range={"since": "2026-03-01", "until": "2026-03-31"},
            topic_hints=["work"],
        )

        assert len(merged) == 1
        assert (
            merged[0]["fts_score"] == 0.0
        ), f"Semantic-only candidate must not get fake fts_score, got {merged[0]['fts_score']}"
        assert (
            merged[0]["source"] == "semantic"
        ), f"Semantic-only candidate source must be 'semantic', got '{merged[0]['source']}'"

    def test_non_structured_candidate_no_bonus(self) -> None:
        """Candidates outside date_range+topic_hints must not receive bonus."""
        l2_outside = {
            "path": "outside.md",
            "title": "Outside",
            "date": "2026-04-15",
            "topic": ["learn"],
            "metadata": {},
        }

        merged = merge_and_rank_results(
            [],
            [l2_outside],
            [],
            query="test",
            min_score=0,
            date_range={"since": "2026-03-01", "until": "2026-03-31"},
            topic_hints=["work"],
        )

        assert len(merged) == 1
        # L2 base score is 30; without bonus final_score stays well below 80
        assert (
            merged[0]["final_score"] < 80
        ), f"Non-structured candidate should not receive bonus, got {merged[0]['final_score']}"
