"""Characterization tests pinning SimpleVectorIndex.search() semantics.

These lock the observable behavior of the brute-force search path before it is
refactored to a vectorized (single-matmul) implementation. Every assertion here
must hold identically before and after that refactor.
"""

import math
from pathlib import Path

import pytest

from tools.lib.vector_index_simple import SimpleVectorIndex


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Redirect vector index paths to tmp_path so no real index is touched."""
    import tools.lib.vector_index_simple as vi_mod
    import tools.lib.paths as paths_mod

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)

    monkeypatch.setattr(vi_mod, "get_index_dir", lambda: idx)
    monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: idx / "vectors_simple.pkl")
    monkeypatch.setattr(vi_mod, "get_vec_meta_path", lambda: idx / "vectors_simple_meta.json")
    monkeypatch.setattr(vi_mod, "get_user_data_dir", lambda: d)
    monkeypatch.setattr(vi_mod, "get_journals_dir", lambda: d / "Journals")
    monkeypatch.setattr(paths_mod, "_user_data_dir_cache", None)
    monkeypatch.setattr(paths_mod, "resolve_user_data_dir", lambda: d)


def _unit(vec):
    n = math.sqrt(sum(c * c for c in vec))
    return [c / n for c in vec]


def _entry(vec, date="2026-03-01", normalized=True):
    return {"embedding": vec, "date": date, "hash": "h", "normalized": normalized}


def test_results_ranked_by_descending_similarity():
    idx = SimpleVectorIndex()
    idx.vectors = {
        "a": _entry(_unit([1, 0, 0, 0])),  # dot=1.0
        "b": _entry(_unit([0.6, 0.8, 0, 0])),  # dot=0.6
        "c": _entry(_unit([0, 1, 0, 0])),  # dot=0.0
        "d": _entry(_unit([-1, 0, 0, 0])),  # dot=-1.0
    }
    out = idx.search([1.0, 0, 0, 0], top_k=4)
    assert [p for p, _ in out] == ["a", "b", "c", "d"]
    scores = [s for _, s in out]
    assert scores == pytest.approx([1.0, 0.6, 0.0, -1.0], abs=1e-6)


def test_top_k_limits_result_count():
    idx = SimpleVectorIndex()
    idx.vectors = {
        "a": _entry(_unit([1, 0, 0, 0])),
        "b": _entry(_unit([0.6, 0.8, 0, 0])),
        "c": _entry(_unit([0, 1, 0, 0])),
    }
    out = idx.search([1.0, 0, 0, 0], top_k=2)
    assert [p for p, _ in out] == ["a", "b"]


def test_empty_index_returns_empty():
    idx = SimpleVectorIndex()
    idx.vectors = {}
    assert idx.search([1.0, 0, 0, 0], top_k=5) == []


def test_date_from_and_to_filter_range():
    idx = SimpleVectorIndex()
    idx.vectors = {
        "early": _entry(_unit([1, 0, 0, 0]), date="2026-01-01"),
        "mid": _entry(_unit([0.6, 0.8, 0, 0]), date="2026-06-01"),
        "late": _entry(_unit([0, 1, 0, 0]), date="2026-12-01"),
    }
    out = idx.search([1.0, 0, 0, 0], top_k=5, date_from="2026-05-01", date_to="2026-11-01")
    assert [p for p, _ in out] == ["mid"]


def test_empty_doc_date_not_excluded_by_filters():
    idx = SimpleVectorIndex()
    idx.vectors = {
        "no_date": _entry(_unit([1, 0, 0, 0]), date=""),
        "in_range": _entry(_unit([0.6, 0.8, 0, 0]), date="2026-06-01"),
    }
    out = idx.search([1.0, 0, 0, 0], top_k=5, date_from="2026-01-01", date_to="2026-12-31")
    assert set(p for p, _ in out) == {"no_date", "in_range"}


def test_legacy_unnormalized_vector_is_normalized_at_query_time():
    idx = SimpleVectorIndex()
    idx.vectors = {
        "legacy": _entry([3, 0, 0, 0], normalized=False),  # raw norm 3
        "modern": _entry(_unit([1, 0, 0, 0]), normalized=True),
    }
    out = dict(idx.search([1.0, 0, 0, 0], top_k=5))
    # legacy must be normalized -> dot 1.0, not 3.0
    assert out["legacy"] == pytest.approx(1.0, abs=1e-6)
    assert out["modern"] == pytest.approx(1.0, abs=1e-6)


def test_query_vector_is_not_normalized():
    idx = SimpleVectorIndex()
    idx.vectors = {"a": _entry(_unit([1, 0, 0, 0]))}
    # query has norm 2; search does not normalize it -> score 2.0
    out = idx.search([2.0, 0, 0, 0], top_k=1)
    assert out[0][1] == pytest.approx(2.0, abs=1e-6)


def test_equal_scores_preserve_insertion_order():
    idx = SimpleVectorIndex()
    idx.vectors = {
        "first": _entry(_unit([1, 0, 0, 0])),
        "second": _entry(_unit([1, 0, 0, 0])),  # identical -> tie
        "third": _entry(_unit([0, 1, 0, 0])),
    }
    out = idx.search([1.0, 0, 0, 0], top_k=2)
    assert [p for p, _ in out] == ["first", "second"]


def test_add_after_search_is_reflected():
    """A vector added after a prior search must appear in the next search
    (guards against a stale cached matrix)."""
    idx = SimpleVectorIndex()
    idx.vectors = {"a": _entry(_unit([0, 1, 0, 0]))}  # dot 0.0
    idx.search([1.0, 0, 0, 0], top_k=5)  # warm any cache
    idx.add("b", _unit([1, 0, 0, 0]), "2026-03-01", "h")  # dot 1.0
    out = idx.search([1.0, 0, 0, 0], top_k=5)
    assert [p for p, _ in out] == ["b", "a"]


def test_remove_after_search_is_reflected():
    idx = SimpleVectorIndex()
    idx.vectors = {
        "a": _entry(_unit([1, 0, 0, 0])),
        "b": _entry(_unit([0, 1, 0, 0])),
    }
    idx.search([1.0, 0, 0, 0], top_k=5)  # warm any cache
    idx.remove("a")
    out = idx.search([1.0, 0, 0, 0], top_k=5)
    assert [p for p, _ in out] == ["b"]


def test_clear_after_search_returns_empty():
    idx = SimpleVectorIndex()
    idx.vectors = {"a": _entry(_unit([1, 0, 0, 0]))}
    idx.search([1.0, 0, 0, 0], top_k=5)  # warm any cache
    idx.clear()
    assert idx.search([1.0, 0, 0, 0], top_k=5) == []
