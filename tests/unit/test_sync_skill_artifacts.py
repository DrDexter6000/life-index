"""Tests for scripts/sync_skill_artifacts.py on a temporary tree.

The root SKILL.md and references/*.md are the only editable sources; the
packaged mirror under tools/_skill_artifacts must stay a byte-for-byte copy.
The gate pins the real tree through ``--check``; these tests pin the sync
tool's own behaviour on a disposable tree.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "sync_skill_artifacts.py"


def load_sync_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Load the sync script bound to a temporary tree."""
    spec = importlib.util.spec_from_file_location("life_index_sync_skill_under_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    root = tmp_path / "repo"
    (root / "references").mkdir(parents=True)
    (root / "tools" / "_skill_artifacts" / "references").mkdir(parents=True)
    monkeypatch.setattr(module, "REPO_ROOT", root)
    monkeypatch.setattr(module, "ROOT_SKILL", root / "SKILL.md")
    monkeypatch.setattr(module, "ROOT_REFERENCES", root / "references")
    monkeypatch.setattr(module, "PACKAGED_ROOT", root / "tools" / "_skill_artifacts")
    monkeypatch.setattr(module, "PACKAGED_SKILL", root / "tools" / "_skill_artifacts" / "SKILL.md")
    monkeypatch.setattr(
        module,
        "PACKAGED_REFERENCES",
        root / "tools" / "_skill_artifacts" / "references",
    )
    return module, root


def write_tree(root: Path, *, skill: bytes, references: dict[str, bytes]) -> None:
    (root / "SKILL.md").write_bytes(skill)
    for name, content in references.items():
        (root / "references" / name).write_bytes(content)


def packaged(root: Path, name: str = "SKILL.md") -> Path:
    return root / "tools" / "_skill_artifacts" / name


def test_check_passes_when_the_mirror_matches(tmp_path, monkeypatch, capsys):
    module, root = load_sync_module(tmp_path, monkeypatch)
    sources = {"SKILL.md": b"# skill\n", "references/alpha.md": b"alpha\n"}
    write_tree(
        root, skill=sources["SKILL.md"], references={"alpha.md": sources["references/alpha.md"]}
    )
    packaged(root).write_bytes(sources["SKILL.md"])
    packaged(root, "references/alpha.md").write_bytes(sources["references/alpha.md"])

    assert module.main(["--check"]) == 0
    assert "match the root skill sources" in capsys.readouterr().out


def test_check_names_files_whose_bytes_differ(tmp_path, monkeypatch, capsys):
    module, root = load_sync_module(tmp_path, monkeypatch)
    write_tree(root, skill=b"# skill v1\n", references={"alpha.md": b"alpha\n"})
    packaged(root).write_bytes(b"# skill v2\n")  # drift
    packaged(root, "references/alpha.md").write_bytes(b"alpha\n")

    assert module.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "differs from the root source: tools/_skill_artifacts/SKILL.md" in out
    assert "sync_skill_artifacts.py" in out  # the fix command is named


def test_check_names_a_file_missing_from_the_packaged_copy(tmp_path, monkeypatch, capsys):
    module, root = load_sync_module(tmp_path, monkeypatch)
    write_tree(root, skill=b"# skill\n", references={"alpha.md": b"alpha\n", "beta.md": b"beta\n"})
    packaged(root).write_bytes(b"# skill\n")
    packaged(root, "references/alpha.md").write_bytes(b"alpha\n")
    # references/beta.md has no packaged counterpart

    assert module.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "missing from the packaged copy: tools/_skill_artifacts/references/beta.md" in out


def test_check_names_a_file_that_exists_only_in_the_packaged_copy(tmp_path, monkeypatch, capsys):
    module, root = load_sync_module(tmp_path, monkeypatch)
    write_tree(root, skill=b"# skill\n", references={"alpha.md": b"alpha\n"})
    packaged(root).write_bytes(b"# skill\n")
    packaged(root, "references/alpha.md").write_bytes(b"alpha\n")
    packaged(root, "references/ghost.md").write_bytes(b"removed from the root\n")

    assert module.main(["--check"]) == 1
    out = capsys.readouterr().out
    assert "exists only in the packaged copy: tools/_skill_artifacts/references/ghost.md" in out


def test_refresh_makes_the_mirror_a_byte_copy_and_drops_strays(tmp_path, monkeypatch):
    module, root = load_sync_module(tmp_path, monkeypatch)
    write_tree(
        root, skill=b"# skill v2\n", references={"alpha.md": b"alpha v2\n", "beta.md": b"beta\n"}
    )
    packaged(root).write_bytes(b"# skill v1\n")  # stale
    # references/beta.md is missing from the copy; ghost.md is a stray:
    packaged(root, "references/alpha.md").write_bytes(b"alpha v1\n")
    packaged(root, "references/ghost.md").write_bytes(b"ghost\n")

    assert module.main([]) == 0
    assert packaged(root).read_bytes() == b"# skill v2\n"
    assert packaged(root, "references/alpha.md").read_bytes() == b"alpha v2\n"
    assert packaged(root, "references/beta.md").read_bytes() == b"beta\n"
    assert not packaged(root, "references/ghost.md").exists()
    assert module.main(["--check"]) == 0  # in sync after the refresh


def test_the_real_repository_mirror_is_in_sync():
    """The checked-in mirror must satisfy the same check the gate runs."""
    spec = importlib.util.spec_from_file_location("life_index_sync_skill_real", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.differences() == []
