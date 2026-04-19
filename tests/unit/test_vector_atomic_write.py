"""Tests for vector index atomic write (Round 12 Phase 2 Task 2.2)."""

import pickle
from pathlib import Path

import pytest

from tools.lib.vector_index_simple import SimpleVectorIndex, get_vec_index_path, get_vec_meta_path


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    """Redirect vector index paths to tmp_path."""
    import tools.lib.vector_index_simple as vi_mod
    import tools.lib.paths as paths_mod

    idx = tmp_path / ".index"
    idx.mkdir(parents=True)
    d = tmp_path / "Life-Index"
    (d / "Journals" / "2026" / "03").mkdir(parents=True)

    # Patch getter functions to return temp paths
    monkeypatch.setattr(vi_mod, "get_index_dir", lambda: idx)
    monkeypatch.setattr(vi_mod, "get_vec_index_path", lambda: idx / "vectors_simple.pkl")
    monkeypatch.setattr(vi_mod, "get_vec_meta_path", lambda: idx / "vectors_simple_meta.json")
    monkeypatch.setattr(vi_mod, "get_user_data_dir", lambda: d)
    monkeypatch.setattr(vi_mod, "get_journals_dir", lambda: d / "Journals")
    # Also patch the paths module so any cross-module getter calls work
    monkeypatch.setattr(paths_mod, "_user_data_dir_cache", None)
    monkeypatch.setattr(paths_mod, "resolve_user_data_dir", lambda: d)


class TestAtomicSave:
    """Tests for SimpleVectorIndex._save() atomic write behavior."""

    def test_save_creates_valid_pickle(self, tmp_path: Path):
        """After _save(), the pickle file contains valid data."""
        import tools.lib.vector_index_simple as vi_mod

        idx = SimpleVectorIndex()
        idx.vectors = {"test/path.md": {"embedding": [0.1, 0.2], "date": "2026-03-07", "hash": "abc"}}
        idx._save()

        pkl_path = vi_mod.get_vec_index_path()
        assert pkl_path.exists()
        with open(pkl_path, "rb") as f:
            loaded = pickle.load(f)
        assert "test/path.md" in loaded
        assert loaded["test/path.md"]["embedding"] == [0.1, 0.2]

    def test_no_tmp_residual_after_save(self, tmp_path: Path):
        """After _save(), no .tmp files remain."""
        import tools.lib.vector_index_simple as vi_mod

        idx = SimpleVectorIndex()
        idx.vectors = {"a.md": {"embedding": [0.5], "date": "2026-01-01", "hash": "x"}}
        idx._save()

        idx_dir = vi_mod.get_index_dir()
        tmp_files = list(idx_dir.glob("*.tmp"))
        assert tmp_files == [], f"Found residual tmp files: {tmp_files}"

    def test_consecutive_saves_both_correct(self, tmp_path: Path):
        """Two rapid _save() calls both produce correct results."""
        import tools.lib.vector_index_simple as vi_mod

        idx = SimpleVectorIndex()
        idx.vectors = {"first.md": {"embedding": [1.0], "date": "2026-01-01", "hash": "a"}}
        idx._save()

        idx.vectors = {"second.md": {"embedding": [2.0], "date": "2026-02-02", "hash": "b"}}
        idx._save()

        pkl_path = vi_mod.get_vec_index_path()
        with open(pkl_path, "rb") as f:
            loaded = pickle.load(f)
        assert "first.md" not in loaded  # Second save replaced entirely
        assert "second.md" in loaded

    def test_save_replaces_not_appends(self, tmp_path: Path):
        """_save() completely replaces the file, doesn't append."""
        import tools.lib.vector_index_simple as vi_mod

        idx = SimpleVectorIndex()
        # First save with many entries
        idx.vectors = {f"file_{i}.md": {"embedding": [float(i)], "date": "2026-01-01", "hash": str(i)} for i in range(10)}
        idx._save()

        # Second save with single entry
        idx.vectors = {"only_this.md": {"embedding": [42.0], "date": "2026-01-01", "hash": "z"}}
        idx._save()

        pkl_path = vi_mod.get_vec_index_path()
        with open(pkl_path, "rb") as f:
            loaded = pickle.load(f)
        assert len(loaded) == 1
        assert "only_this.md" in loaded

    def test_load_handles_stale_tmp_file(self, tmp_path: Path):
        """If a .tmp file exists from a crashed save, _load ignores it."""
        import tools.lib.vector_index_simple as vi_mod

        pkl_path = vi_mod.get_vec_index_path()
        tmp_path_file = pkl_path.with_suffix(".pkl.tmp")

        # Create the actual journal file so cleanup doesn't remove it
        data_dir = tmp_path / "Life-Index"
        (data_dir / "Journals" / "2026" / "01").mkdir(parents=True, exist_ok=True)
        (data_dir / "Journals" / "2026" / "01" / "good.md").write_text("content", encoding="utf-8")

        # Create the main pickle with valid data
        valid_data = {"Journals/2026/01/good.md": {"embedding": [1.0], "date": "2026-01-01", "hash": "x"}}
        with open(pkl_path, "wb") as f:
            pickle.dump(valid_data, f)

        # Create a stale tmp file (simulating a crashed save)
        with open(tmp_path_file, "wb") as f:
            f.write(b"corrupt partial data that is not valid pickle")

        # _load should succeed with the valid pickle
        idx = SimpleVectorIndex()
        assert "Journals/2026/01/good.md" in idx.vectors
