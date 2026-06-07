"""Edit -> index -> search round-trip coverage.

These tests keep the data directory isolated and use ASCII fixture content so
the assertions do not depend on terminal encoding behavior.
"""

from pathlib import Path


def _write_journal(
    data_dir: Path,
    *,
    body: str,
    topic: str = "work",
    tags: str = "initial",
) -> Path:
    journal_dir = data_dir / "Journals" / "2026" / "03"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_path = journal_dir / "life-index_2026-03-14_001.md"
    journal_path.write_text(
        "---\n"
        'title: "Search Impact Fixture"\n'
        "date: 2026-03-14\n"
        f"topic: [{topic}]\n"
        "project: LifeIndex\n"
        f"tags: [{tags}]\n"
        "---\n\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return journal_path


def _contains_path(results: list[dict], journal_path: Path) -> bool:
    return any(str(item.get("path", "")).endswith(journal_path.name) for item in results)


def test_edit_content_is_reflected_in_fts_search(isolated_data_dir: Path) -> None:
    from tools.edit_journal import edit_journal
    from tools.lib.pending_writes import clear_pending
    from tools.lib.search_index import search_fts, update_index

    journal_path = _write_journal(
        isolated_data_dir,
        body="alphaoriginal marker exists before editing.",
    )
    initial_index = update_index(incremental=False)
    assert initial_index["success"] is True
    assert _contains_path(search_fts("alphaoriginal"), journal_path)
    assert not _contains_path(search_fts("betaedited"), journal_path)

    clear_pending()
    edit_result = edit_journal(
        journal_path=journal_path,
        frontmatter_updates={},
        replace_content="betaedited marker exists after editing.",
    )
    assert edit_result["success"] is True
    assert edit_result["pending_marked"] is True

    updated_index = update_index(incremental=True)
    assert updated_index["success"] is True
    assert _contains_path(search_fts("betaedited"), journal_path)
    assert not _contains_path(search_fts("alphaoriginal"), journal_path)


def test_edit_metadata_is_reflected_in_fts_search(isolated_data_dir: Path) -> None:
    from tools.edit_journal import edit_journal
    from tools.lib.pending_writes import clear_pending
    from tools.lib.search_index import search_fts, update_index

    journal_path = _write_journal(
        isolated_data_dir,
        body="neutral body without metadata route tokens.",
        topic="work",
        tags="initial",
    )
    initial_index = update_index(incremental=False)
    assert initial_index["success"] is True
    assert _contains_path(search_fts("work"), journal_path)
    assert not _contains_path(search_fts("learning"), journal_path)

    clear_pending()
    edit_result = edit_journal(
        journal_path=journal_path,
        frontmatter_updates={"topic": ["learning"], "tags": ["searchimpact"]},
    )
    assert edit_result["success"] is True
    assert edit_result["pending_marked"] is True
    assert edit_result["indices_updated"]

    updated_index = update_index(incremental=True)
    assert updated_index["success"] is True
    assert _contains_path(search_fts("learning"), journal_path)
    assert _contains_path(search_fts("searchimpact"), journal_path)
    assert not _contains_path(search_fts("work"), journal_path)


def test_edit_pending_is_auto_consumed_by_next_search(isolated_data_dir: Path, monkeypatch) -> None:
    from tools import build_index as build_index_module
    from tools.edit_journal import edit_journal
    from tools.lib.pending_writes import clear_pending, get_pending
    from tools.lib.search_index import search_fts, update_index
    from tools.search_journals.core import hierarchical_search

    journal_path = _write_journal(
        isolated_data_dir,
        body="beforeauto marker exists before editing.",
    )
    initial_index = update_index(incremental=False)
    assert initial_index["success"] is True

    real_build_all = build_index_module.build_all

    def fts_only_build_all(
        incremental: bool = True, fts_only: bool = False, vec_only: bool = False
    ) -> dict:
        return real_build_all(incremental=incremental, fts_only=True)

    monkeypatch.setattr(build_index_module, "build_all", fts_only_build_all)

    clear_pending()
    edit_result = edit_journal(
        journal_path=journal_path,
        frontmatter_updates={},
        replace_content="afterauto marker exists after editing.",
    )
    assert edit_result["success"] is True
    assert get_pending() == ["Journals/2026/03/life-index_2026-03-14_001.md"]

    result = hierarchical_search(
        query="afterauto",
        level=3,
        semantic=False,
        semantic_policy="fallback",
    )

    assert result["pending_consumed"] is True
    assert get_pending() == []
    assert _contains_path(result["merged_results"], journal_path)
    assert _contains_path(search_fts("afterauto"), journal_path)
    assert not _contains_path(search_fts("beforeauto"), journal_path)


def test_edit_date_is_reflected_in_fts_date_filters(isolated_data_dir: Path) -> None:
    from tools.edit_journal import edit_journal
    from tools.lib.pending_writes import clear_pending
    from tools.lib.search_index import search_fts, update_index

    journal_path = _write_journal(
        isolated_data_dir,
        body="dateeditable marker exists across date changes.",
    )
    initial_index = update_index(incremental=False)
    assert initial_index["success"] is True
    assert _contains_path(
        search_fts("dateeditable", date_from="2026-03-14", date_to="2026-03-14"),
        journal_path,
    )

    clear_pending()
    edit_result = edit_journal(
        journal_path=journal_path,
        frontmatter_updates={"date": "2026-03-15"},
    )
    assert edit_result["success"] is True
    assert edit_result["pending_marked"] is True

    updated_index = update_index(incremental=True)
    assert updated_index["success"] is True
    assert _contains_path(
        search_fts("dateeditable", date_from="2026-03-15", date_to="2026-03-15"),
        journal_path,
    )
    assert not _contains_path(
        search_fts("dateeditable", date_from="2026-03-14", date_to="2026-03-14"),
        journal_path,
    )
