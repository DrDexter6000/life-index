#!/usr/bin/env python3
"""M09 RED/GREEN: Date Navigation + Generic Token Suppression.

Bounded M09 slice — three test scenarios from the lead dispatch:
1. Date-topic query suppresses generic nouns while preserving meaningful tokens.
2. Compound month expression does not leak orphan "份".
3. End-to-end hierarchical_search with date-only query returns correct date-filtered candidates.

RED phase: these tests are expected to FAIL before implementation.
GREEN phase: these tests must PASS after implementation, with no regression.
"""

from datetime import date
from pathlib import Path

import pytest

# ── Test 1: Date-topic query suppresses generic noun, preserves meaningful token ──


def test_date_topic_query_suppresses_generic_noun() -> None:
    """build_search_plan("三月份的工作日志") must suppress "日志" but keep "工作" and date_range."""
    from tools.search_journals.query_preprocessor import build_search_plan

    plan = build_search_plan("三月份的工作日志", reference_date=date(2026, 5, 20))

    # Date range must be March 2026
    assert plan.date_range is not None
    assert plan.date_range.since == "2026-03-01"
    assert plan.date_range.until == "2026-03-31"

    # Topic hints must include "work"
    assert "work" in plan.topic_hints

    # "日志" must be suppressed as a generic noun
    assert (
        "日志" not in plan.keywords
    ), f'"日志" should be suppressed as generic noun; got keywords={plan.keywords}'

    # "工作" must survive — it maps to topic "work" and is meaningful content
    assert (
        "工作" in plan.keywords
    ), f'"工作" must be preserved as meaningful token; got keywords={plan.keywords}'


# ── Test 2: Compound month expression does not leak orphan "份" ────────────────


def test_compound_month_no_orphan_fen() -> None:
    """build_search_plan("今年一月份发生了什么") must not include "份" in keywords."""
    from tools.search_journals.query_preprocessor import build_search_plan

    plan = build_search_plan("今年一月份发生了什么", reference_date=date(2026, 5, 20))

    # Date range must be January 2026
    assert plan.date_range is not None
    assert plan.date_range.since == "2026-01-01"
    assert plan.date_range.until == "2026-01-31"

    # "份" must not appear as a keyword
    assert (
        "份" not in plan.keywords
    ), f'"份" must not leak as orphan keyword; got keywords={plan.keywords}'


# ── Test 3: End-to-end hierarchical_search with date-only query ───────────────


def _write_journal(path: Path, *, title: str, date: str, body: str, topic: str = "work") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ndate: {date}\ntopic: [{topic}]\n---\n\n{body}\n',
        encoding="utf-8",
    )


def _patch_search_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Patch all search module path references to use tmp_path."""
    import tools.search_journals.core as core_module
    import tools.search_journals.keyword_pipeline as keyword_pipeline
    import tools.search_journals.l2_metadata as l2_metadata
    import tools.search_journals.l3_content as l3_content
    import tools.search_journals.semantic as semantic_module
    import tools.lib.pending_writes as pw_mod
    import tools.lib.index_freshness as freshness_mod

    journals_dir = tmp_path / "Journals"
    idx_dir = tmp_path / ".index"

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    for module in (
        core_module,
        keyword_pipeline,
        l2_metadata,
        l3_content,
        semantic_module,
    ):
        monkeypatch.setattr(module, "get_user_data_dir", lambda _t=tmp_path: _t, raising=False)
        monkeypatch.setattr(module, "get_journals_dir", lambda _j=journals_dir: _j, raising=False)

    monkeypatch.setattr(l2_metadata, "ENABLE_CACHE", False)
    monkeypatch.setattr(
        semantic_module,
        "SEMANTIC_INDEX_PATH",
        idx_dir / "vectors_simple.pkl",
        raising=False,
    )
    monkeypatch.setattr(pw_mod, "get_index_dir", lambda: idx_dir)
    monkeypatch.setattr(pw_mod, "has_pending", lambda: False)
    monkeypatch.setattr(
        freshness_mod,
        "check_full_freshness",
        lambda *a, **kw: type(
            "F",
            (),
            {
                "overall_fresh": True,
                "issues": [],
                "to_dict": lambda self: {"overall_fresh": True, "issues": []},
            },
        )(),
    )


def test_date_only_navigation_returns_correct_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Date-only hierarchical_search returns March candidates from isolated tmp_path."""
    _patch_search_roots(monkeypatch, tmp_path)

    # Create journals in different months
    _write_journal(
        tmp_path / "Journals" / "2026" / "01" / "life-index_2026-01-05_001.md",
        title="一月记录",
        date="2026-01-05",
        body="January content about daily life.",
        topic="life",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "03" / "life-index_2026-03-10_001.md",
        title="三月工作",
        date="2026-03-10",
        body="March work journal entry with needle content.",
        topic="work",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "03" / "life-index_2026-03-20_001.md",
        title="三月思考",
        date="2026-03-20",
        body="Reflections on life in March.",
        topic="think",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "04" / "life-index_2026-04-01_001.md",
        title="四月笔记",
        date="2026-04-01",
        body="April notes about learning.",
        topic="learn",
    )

    from tools.search_journals.core import hierarchical_search

    result = hierarchical_search(
        query="2026年03月的日志",
        level=3,
        semantic=False,
        use_index=False,
    )

    # Verify search_plan was created and has date_range
    assert "search_plan" in result
    sp = result["search_plan"]
    assert sp["date_range"] is not None
    assert sp["date_range"]["since"] == "2026-03-01"
    assert sp["date_range"]["until"] == "2026-03-31"

    # Extract paths from results
    result_paths = [r.get("rel_path", r.get("path", "")) for r in result["merged_results"]]

    # March entries should be present
    march_results = [p for p in result_paths if "2026/03/" in p]
    assert (
        len(march_results) >= 1
    ), f"Expected at least 1 March result, got {len(march_results)}: {result_paths}"

    # January and April entries must be excluded
    jan_results = [p for p in result_paths if "2026/01/" in p]
    apr_results = [p for p in result_paths if "2026/04/" in p]
    assert len(jan_results) == 0, f"January entries should be excluded: {jan_results}"
    assert len(apr_results) == 0, f"April entries should be excluded: {apr_results}"
