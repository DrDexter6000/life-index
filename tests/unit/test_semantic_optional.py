"""Contract: health no longer depends on sentence-transformers."""

import sys

import pytest


@pytest.mark.blocker
def test_health_reports_semantic_disabled_without_sentence_transformers(monkeypatch, tmp_path):
    """Missing sentence-transformers must not degrade health."""
    from tools.__main__ import _check_index

    data_dir = tmp_path / "Life-Index"
    index_dir = data_dir / ".index"
    index_dir.mkdir(parents=True)
    (index_dir / "journals_fts.db").write_text("fts", encoding="utf-8")

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(data_dir))
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    check, issue = _check_index()

    assert issue == ""
    assert check["status"] == "ok"
    assert check["semantic_status"] == "disabled"
    assert check["semantic"]["status"] == "disabled"
