#!/usr/bin/env python3

from pathlib import Path

import pytest


def _write_journal(path: Path, *, title: str, date: str, topic: str = "work") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{title}"\ndate: {date}\ntopic: [{topic}]\n---\n\n{title} body\n',
        encoding="utf-8",
    )


def _patch_index_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import tools.generate_index as generate_index_module

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(generate_index_module, "get_journals_dir", lambda _j=tmp_path / "Journals": _j, raising=False)
    monkeypatch.setattr(generate_index_module, "get_user_data_dir", lambda _t=tmp_path: _t, raising=False)


def test_rebuild_fixes_stale_counter_in_existing_monthly_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.generate_index import rebuild_index_tree

    _patch_index_roots(monkeypatch, tmp_path)
    month_dir = tmp_path / "Journals" / "2026" / "03"
    _write_journal(
        month_dir / "life-index_2026-03-01_001.md",
        title="Only Entry",
        date="2026-03-01",
    )
    (month_dir / "index_2026-03.md").write_text(
        "---\nentries: 999\n---\n\n# stale\n",
        encoding="utf-8",
    )

    report = rebuild_index_tree()

    rebuilt_content = (month_dir / "index_2026-03.md").read_text(encoding="utf-8")
    assert "entries: 1" in rebuilt_content
    assert report["monthly_indexes_rebuilt"] == 1
    assert report["errors"] == []


def test_rebuild_creates_missing_indexes_for_months_with_journals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.generate_index import rebuild_index_tree

    _patch_index_roots(monkeypatch, tmp_path)
    _write_journal(
        tmp_path / "Journals" / "2026" / "03" / "life-index_2026-03-01_001.md",
        title="March Entry",
        date="2026-03-01",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "04" / "life-index_2026-04-01_001.md",
        title="April Entry",
        date="2026-04-01",
    )

    report = rebuild_index_tree()

    assert (tmp_path / "Journals" / "2026" / "03" / "index_2026-03.md").exists()
    assert (tmp_path / "Journals" / "2026" / "04" / "index_2026-04.md").exists()
    assert (tmp_path / "Journals" / "2026" / "index_2026.md").exists()
    assert (tmp_path / "INDEX.md").exists()
    assert report["monthly_indexes_rebuilt"] == 2
    assert report["yearly_indexes_rebuilt"] == 1
    assert report["root_index_rebuilt"] is True


def test_rebuild_returns_report_with_correct_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.generate_index import rebuild_index_tree

    _patch_index_roots(monkeypatch, tmp_path)
    _write_journal(
        tmp_path / "Journals" / "2025" / "12" / "life-index_2025-12-01_001.md",
        title="Dec Entry",
        date="2025-12-01",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "03" / "life-index_2026-03-01_001.md",
        title="March Entry",
        date="2026-03-01",
    )
    _write_journal(
        tmp_path / "Journals" / "2026" / "04" / "life-index_2026-04-01_001.md",
        title="April Entry",
        date="2026-04-01",
    )

    report = rebuild_index_tree()

    assert report == {
        "monthly_indexes_rebuilt": 3,
        "yearly_indexes_rebuilt": 2,
        "root_index_rebuilt": True,
        "errors": [],
    }
