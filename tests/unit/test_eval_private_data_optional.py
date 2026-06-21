from __future__ import annotations

from pathlib import Path

import pytest

from tools.eval import run_eval


@pytest.mark.blocker
def test_eval_without_local_private_query_set_is_explicit_skip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LIFE_INDEX_EVAL_DATA_DIR", str(tmp_path / "missing-eval-data"))
    monkeypatch.setenv("LIFE_INDEX_TIME_ANCHOR", "2026-03-31")

    result = run_eval.run_evaluation(data_dir=tmp_path / "data", use_overlay=False)

    assert result["eval_data_available"] is False
    assert result["total_queries"] == 0
    assert result["per_query"] == []
    assert result["failures"] == []
    assert any("data-dependent eval skipped" in line for line in result["summary_lines"])


@pytest.mark.blocker
def test_explicit_missing_eval_query_path_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        run_eval.load_golden_queries(tmp_path / "missing-golden.yaml")


@pytest.mark.blocker
def test_default_eval_query_set_uses_private_eval_data_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    eval_dir = tmp_path / "private-eval"
    eval_dir.mkdir()
    (eval_dir / "golden_queries.yaml").write_text(
        "queries:\n"
        "  - id: Q1\n"
        "    query: neutral sample\n"
        "    category: smoke\n"
        "    expected:\n"
        "      min_results: 0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LIFE_INDEX_EVAL_DATA_DIR", str(eval_dir))

    queries = run_eval.load_golden_queries()

    assert [q["id"] for q in queries] == ["Q1"]
