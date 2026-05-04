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
