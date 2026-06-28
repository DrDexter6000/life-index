from pathlib import Path


def test_search_keeps_edit_pending_when_auto_index_returns_unsuccessful(
    tmp_path: Path, monkeypatch
) -> None:
    import tools.edit_journal as edit_module
    import tools.lib.pending_writes as pending_writes
    import tools.search_journals.core as search_core

    data_dir = tmp_path / "Life-Index"
    journal_dir = data_dir / "Journals" / "2026" / "03"
    index_dir = data_dir / ".index"
    cache_dir = data_dir / ".cache"
    journal_dir.mkdir(parents=True)
    index_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)

    journal_path = journal_dir / "life-index_2026-03-14_001.md"
    journal_path.write_text(
        "---\n"
        'title: "Search Impact"\n'
        "date: 2026-03-14\n"
        "---\n\n"
        "Original searchable content.\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    monkeypatch.setattr(pending_writes, "get_index_dir", lambda: index_dir)
    monkeypatch.setattr(edit_module, "resolve_user_data_dir", lambda: data_dir)
    monkeypatch.setattr(edit_module, "get_user_data_dir", lambda: data_dir)
    monkeypatch.setattr(
        edit_module,
        "get_journals_lock_path",
        lambda: cache_dir / "journals.lock",
    )

    edit_result = edit_module.edit_journal(
        journal_path=journal_path,
        frontmatter_updates={},
        append_content="new search-impact token",
    )

    assert edit_result["success"] is True
    assert pending_writes.get_pending() == ["Journals/2026/03/life-index_2026-03-14_001.md"]

    monkeypatch.setattr(
        "tools.build_index.build_all",
        lambda incremental=True: {
            "success": False,
            "fts": {"success": False, "error": "simulated index failure"},
        },
    )
    monkeypatch.setattr(
        search_core,
        "run_keyword_pipeline",
        lambda **kwargs: ([], [], [], False, 0, {}),
    )
    result = search_core.hierarchical_search(
        query="new search-impact token",
        semantic=False,
        semantic_policy="fallback",
    )

    assert result["pending_consumed"] is False
    assert pending_writes.get_pending() == ["Journals/2026/03/life-index_2026-03-14_001.md"]
