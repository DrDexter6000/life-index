#!/usr/bin/env python3

import sys
from pathlib import Path

import pytest

from tools.lib.index_freshness import FreshnessReport


def _write_journal(
    path: Path, *, title: str, date: str, body: str, topic: str = "work"
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ndate: {date}\ntopic: [{topic}]\n---\n\n{body}\n',
        encoding="utf-8",
    )


def _patch_search_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import tools.lib.config as config_module
    import tools.lib.paths as paths_module
    import tools.search_journals.core as core_module
    import tools.search_journals.keyword_pipeline as keyword_pipeline
    import tools.search_journals.l2_metadata as l2_metadata
    import tools.search_journals.l3_content as l3_content
    import tools.search_journals.semantic as semantic_module

    journals_dir = tmp_path / "Journals"

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))

    # Patch getter functions on each module
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
        tmp_path / ".index" / "vectors_simple.pkl",
        raising=False,
    )
    fresh_report = FreshnessReport(
        fts_fresh=True,
        vector_fresh=True,
        overall_fresh=True,
        issues=[],
    )
    monkeypatch.setattr(
        "tools.lib.index_freshness.check_full_freshness",
        lambda *_args, **_kwargs: fresh_report,
    )
    monkeypatch.setattr(
        "tools.lib.pending_writes.has_pending",
        lambda *_args, **_kwargs: False,
    )


def test_cli_accepts_year_month_and_topic_without_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.search_journals import __main__ as cli_module

    captured: dict[str, object] = {}

    def fake_search(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"success": True, "merged_results": [], "total_found": 0}

    monkeypatch.setattr(cli_module, "hierarchical_search", fake_search)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "search_journals",
            "--query",
            "needle",
            "--year",
            "2026",
            "--month",
            "3",
            "--topic",
            "work",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main()

    assert exc_info.value.code == 0
    assert captured["year"] == 2026
    assert captured["month"] == 3
    assert captured["topic"] == "work"


def test_search_month_without_year_still_searches_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.search_journals.core import hierarchical_search

    _patch_search_roots(monkeypatch, tmp_path)
    _write_journal(
        tmp_path / "Journals" / "2025" / "03" / "life-index_2025-03-01_001.md",
        title="March 2025",
        date="2025-03-01",
        body="shared needle\nshared needle again",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "04" / "life-index_2026-04-01_001.md",
        title="April 2026",
        date="2026-04-01",
        body="shared needle\nshared needle again",
    )

    result = hierarchical_search(
        query="shared needle",
        level=3,
        semantic=False,
        use_index=False,
        month=3,
    )

    matched_paths = {Path(item["path"]).as_posix() for item in result["l3_results"]}
    assert (
        str(
            tmp_path / "Journals" / "2025" / "03" / "life-index_2025-03-01_001.md"
        ).replace("\\", "/")
        in matched_paths
    )
    assert (
        str(
            tmp_path / "Journals" / "2026" / "04" / "life-index_2026-04-01_001.md"
        ).replace("\\", "/")
        in matched_paths
    )


def test_search_without_prefilter_params_has_zero_regression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.search_journals.core import hierarchical_search

    _patch_search_roots(monkeypatch, tmp_path)
    _write_journal(
        tmp_path / "Journals" / "2025" / "03" / "life-index_2025-03-01_001.md",
        title="First",
        date="2025-03-01",
        body="shared needle\nshared needle again",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "03" / "life-index_2026-03-01_001.md",
        title="Second",
        date="2026-03-01",
        body="shared needle\nshared needle again",
    )

    result = hierarchical_search(
        query="shared needle",
        level=3,
        semantic=False,
        use_index=False,
    )

    matched_paths = {Path(item["path"]).name for item in result["l3_results"]}
    assert matched_paths == {
        "life-index_2025-03-01_001.md",
        "life-index_2026-03-01_001.md",
    }


def test_search_year_prefilter_restricts_to_matching_year(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.search_journals.core import hierarchical_search

    _patch_search_roots(monkeypatch, tmp_path)
    _write_journal(
        tmp_path / "Journals" / "2025" / "03" / "life-index_2025-03-01_001.md",
        title="Old Year",
        date="2025-03-01",
        body="shared needle\nshared needle again",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "03" / "life-index_2026-03-01_001.md",
        title="Target Year",
        date="2026-03-01",
        body="shared needle\nshared needle again",
    )

    result = hierarchical_search(
        query="shared needle",
        level=3,
        semantic=False,
        use_index=False,
        year=2026,
    )

    matched_paths = [Path(item["path"]).name for item in result["l3_results"]]
    assert matched_paths == ["life-index_2026-03-01_001.md"]
