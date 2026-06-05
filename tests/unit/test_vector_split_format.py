"""Tests for RFC-2026-06-05 split vector-index storage."""

from __future__ import annotations

import math
import pickle
from pathlib import Path

import numpy as np
import pytest

from tools.lib.vector_index_simple import SimpleVectorIndex


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Redirect vector index paths to tmp_path so no real index is touched."""
    import tools.lib.paths as paths_mod
    import tools.lib.vector_index_simple as vi_mod

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(d))
    monkeypatch.setattr(vi_mod, "get_index_dir", lambda: idx)
    monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: idx / "vectors_simple.pkl")
    monkeypatch.setattr(vi_mod, "get_vec_meta_path", lambda: idx / "vectors_simple_meta.json")
    monkeypatch.setattr(vi_mod, "get_user_data_dir", lambda: d)
    monkeypatch.setattr(vi_mod, "get_journals_dir", lambda: d / "Journals")
    monkeypatch.setattr(paths_mod, "_user_data_dir_cache", None)
    monkeypatch.setattr(paths_mod, "resolve_user_data_dir", lambda: d)


def _unit(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


def _pickle_payload() -> dict:
    import tools.lib.vector_index_simple as vi_mod

    with open(vi_mod.get_vec_index_path(), "rb") as f:
        return pickle.load(f)


def _matrix_payload():
    import tools.lib.vector_index_simple as vi_mod

    return np.load(vi_mod.get_vec_matrix_path(), mmap_mode="r")


def _write_journal(rel_path: str, body: str = "body") -> None:
    import tools.lib.vector_index_simple as vi_mod

    path = vi_mod.get_user_data_dir() / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ndate: 2026-03-01\n---\n{body}", encoding="utf-8")


def test_round_trip_split_storage_preserves_ranked_results():
    path_a = "Journals/2026/03/life-index_2026-03-01_001.md"
    path_b = "Journals/2026/03/b.md"
    _write_journal(path_a)
    _write_journal(path_b)
    idx = SimpleVectorIndex()
    idx.add(path_a, _unit([1, 0, 0, 0]), "2026-03-01", "ha")
    idx.add(path_b, _unit([0.6, 0.8, 0, 0]), "2026-03-02", "hb")
    expected = idx.search([1, 0, 0, 0], top_k=2)

    idx.commit()
    fresh = SimpleVectorIndex()
    actual = fresh.search([1, 0, 0, 0], top_k=2)

    assert [path for path, _ in actual] == [path for path, _ in expected]
    assert [score for _, score in actual] == pytest.approx([score for _, score in expected])
    assert fresh.get(path_a) == {
        "date": "2026-03-01",
        "hash": "ha",
        "added_at": fresh.get(path_a)["added_at"],
    }
    assert fresh.get_embedding(path_a) == pytest.approx(_unit([1, 0, 0, 0]))


def test_commit_writes_metadata_pickle_and_matrix_sidecar():
    idx = SimpleVectorIndex()
    idx.add("a.md", _unit([1, 0, 0, 0]), "2026-03-01", "ha")
    idx.add("b.md", _unit([0, 1, 0, 0]), "2026-03-02", "hb")

    idx.commit()

    metadata = _pickle_payload()
    assert set(metadata) == {"a.md", "b.md"}
    assert all("embedding" not in entry for entry in metadata.values())
    assert all("normalized" not in entry for entry in metadata.values())

    with _matrix_payload() as payload:
        assert payload["matrix"].dtype == np.float32
        assert payload["matrix"].shape == (2, 4)
        assert payload["paths"].tolist() == list(metadata.keys())


def test_old_inline_embedding_pickle_migrates_to_split_format():
    import tools.lib.vector_index_simple as vi_mod

    _write_journal("Journals/2026/03/legacy.md")
    _write_journal("Journals/2026/03/modern.md")
    old_format = {
        "Journals/2026/03/legacy.md": {
            "embedding": [3, 0, 0, 0],
            "date": "2026-03-01",
            "hash": "hl",
            "added_at": "2026-03-01T00:00:00",
            "normalized": False,
        },
        "Journals/2026/03/modern.md": {
            "embedding": _unit([0, 1, 0, 0]),
            "date": "2026-03-02",
            "hash": "hm",
            "added_at": "2026-03-02T00:00:00",
            "normalized": True,
        },
    }
    with open(vi_mod.get_vec_index_path(), "wb") as f:
        pickle.dump(old_format, f)

    idx = SimpleVectorIndex()

    out = dict(idx.search([1, 0, 0, 0], top_k=2))
    assert out["Journals/2026/03/legacy.md"] == pytest.approx(1.0, abs=1e-6)
    metadata = _pickle_payload()
    assert all("embedding" not in entry for entry in metadata.values())
    with _matrix_payload() as payload:
        assert set(payload["paths"].tolist()) == set(metadata)


def test_incremental_commit_preserves_existing_rows():
    path_a = "Journals/2026/03/life-index_2026-03-01_001.md"
    path_b = "Journals/2026/03/b.md"
    path_c = "Journals/2026/03/c.md"
    _write_journal(path_a)
    _write_journal(path_b)
    _write_journal(path_c)
    first = SimpleVectorIndex()
    first.add(path_a, _unit([1, 0, 0, 0]), "2026-03-01", "ha")
    first.add(path_b, _unit([0, 1, 0, 0]), "2026-03-02", "hb")
    first.commit()

    second = SimpleVectorIndex()
    second.add(path_c, _unit([0.6, 0.8, 0, 0]), "2026-03-03", "hc")
    second.commit()

    fresh = SimpleVectorIndex()
    assert [path for path, _ in fresh.search([1, 0, 0, 0], top_k=3)] == [
        path_a,
        path_c,
        path_b,
    ]
    assert fresh.get_embedding(path_b) == pytest.approx(_unit([0, 1, 0, 0]))


def test_missing_or_mismatched_files_degrade_to_empty_search():
    from tools.lib.search_index import search_fts, update_index
    import tools.lib.vector_index_simple as vi_mod

    path_a = "Journals/2026/03/life-index_2026-03-01_001.md"
    _write_journal(path_a, body="lifesidecarkeyword")
    update_index(incremental=False)
    idx = SimpleVectorIndex()
    idx.add(path_a, _unit([1, 0, 0, 0]), "2026-03-01", "ha")
    idx.commit()

    vi_mod.get_vec_matrix_path().unlink()
    assert SimpleVectorIndex().search([1, 0, 0, 0], top_k=1) == []
    assert search_fts("lifesidecarkeyword")

    idx = SimpleVectorIndex()
    idx.add(path_a, _unit([1, 0, 0, 0]), "2026-03-01", "ha")
    idx.commit()
    vi_mod.get_vec_index_path().unlink()
    assert SimpleVectorIndex().search([1, 0, 0, 0], top_k=1) == []

    idx = SimpleVectorIndex()
    idx.add(path_a, _unit([1, 0, 0, 0]), "2026-03-01", "ha")
    idx.commit()
    np.savez(
        vi_mod.get_vec_matrix_path(),
        matrix=np.asarray([_unit([1, 0, 0, 0])], dtype=np.float32),
        paths=np.asarray(["different.md"]),
    )
    assert SimpleVectorIndex().search([1, 0, 0, 0], top_k=1) == []


def test_load_removes_stale_matrix_tmp_without_degrading_split_index():
    import tools.lib.vector_index_simple as vi_mod

    path_a = "Journals/2026/03/a.md"
    _write_journal(path_a)
    idx = SimpleVectorIndex()
    idx.add(path_a, _unit([1, 0, 0, 0]), "2026-03-01", "ha")
    idx.commit()

    tmp_matrix = vi_mod.get_vec_matrix_path().with_name(f"{vi_mod.get_vec_matrix_path().name}.tmp")
    tmp_matrix.write_bytes(b"partial matrix write")

    fresh = SimpleVectorIndex()

    actual = fresh.search([1, 0, 0, 0], top_k=1)
    assert not tmp_matrix.exists()
    assert actual[0][0] == path_a
    assert actual[0][1] == pytest.approx(1.0)


def test_semantic_baseline_from_matrix_matches_dict_baseline():
    from tools.lib.semantic_baseline import (
        compute_semantic_baseline,
        compute_semantic_baseline_from_matrix,
    )

    vectors = {f"{i}.md": {"embedding": _unit([1 + i, 2 + i, 3 + i, 4 + i])} for i in range(8)}
    matrix = np.asarray([data["embedding"] for data in vectors.values()], dtype=np.float32)

    assert compute_semantic_baseline_from_matrix(matrix, sample_size=8, seed=7) == pytest.approx(
        compute_semantic_baseline(vectors, sample_size=8, seed=7), abs=1e-6
    )
