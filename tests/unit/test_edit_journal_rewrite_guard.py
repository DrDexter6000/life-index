#!/usr/bin/env python3
"""``edit`` refuses a frontmatter it cannot write back, before touching anything.

Every blocked shape is driven through a frontmatter change, a body append, a
body replace and ``dry_run``. In each case the result is the standard E0202
envelope, the journal bytes are unchanged, no revision is written and neither
the pending queue nor the two derived index stores move.
"""

from pathlib import Path

import pytest

from tools.edit_journal import edit_journal
from tools.lib.revisions import list_revisions

DATE = "2026-03-04"

BLOCKED = {
    "invalid_yaml": (
        "---\ntitle: [unterminated\ndate: 2026-03-04\n---\n\nbody\n",
        "unreadable",
    ),
    "list_root": ("---\n- a\n- b\n---\n\nbody\n", "unreadable"),
    "scalar_root": ("---\njust a scalar\n---\n\nbody\n", "unreadable"),
    "recursive_alias": (
        "---\ntitle: T\ncustom: &a [*a]\n---\n\nbody\n",
        "unreadable",
    ),
    "impossible_timestamp": (
        "---\ntitle: T\ndate: 2026-99-99\n---\n\nbody\n",
        "unreadable",
    ),
    "int_key": ("---\ntitle: T\ndate: 2026-03-04\n2024: x\n---\n\nbody\n", "not_round_trippable"),
    "boolean_key": (
        "---\ntitle: T\ndate: 2026-03-04\ntrue: x\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "null_key": (
        "---\ntitle: T\ndate: 2026-03-04\nnull: x\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "set_value": (
        "---\ntitle: T\ndate: 2026-03-04\ntags: !!set {alpha: null}\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "pairs_value": (
        "---\ntitle: T\ndate: 2026-03-04\ncustom: !!pairs [a: b]\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "title_null": (
        "---\ntitle:\ndate: 2026-03-04\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "topic_scalar": (
        "---\ntitle: T\ndate: 2026-03-04\ntopic: life\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "topic_null": (
        "---\ntitle: T\ndate: 2026-03-04\ntopic:\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "tags_scalar": (
        "---\ntitle: T\ndate: 2026-03-04\ntags: alpha, beta\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "tags_null": (
        "---\ntitle: T\ndate: 2026-03-04\ntags:\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "people_scalar": (
        "---\ntitle: T\ndate: 2026-03-04\npeople: Alice\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "people_null": (
        "---\ntitle: T\ndate: 2026-03-04\npeople:\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "mood_scalar": (
        "---\ntitle: T\ndate: 2026-03-04\nmood: calm\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "mood_null": (
        "---\ntitle: T\ndate: 2026-03-04\nmood:\n---\n\nbody\n",
        "not_round_trippable",
    ),
    "private_key": (
        "---\n_custom: x\n---\n\nbody\n",
        "not_round_trippable",
    ),
}

MODES = {
    "frontmatter_change": {"frontmatter_updates": {"weather": "sunny"}},
    "body_append": {"frontmatter_updates": {}, "append_content": "appended words\n"},
    "body_replace": {"frontmatter_updates": {}, "replace_content": "replacement words\n"},
    "dry_run": {"frontmatter_updates": {"weather": "sunny"}, "dry_run": True},
}


def _journal(data_dir: Path) -> Path:
    journal = data_dir / "Journals" / "2026" / "03" / f"life-index_{DATE}_001.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    return journal


def _tree(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _derived_state(data_dir: Path) -> dict[str, dict[str, bytes]]:
    return {
        "index": _tree(data_dir / ".index"),
        "cache": _tree(data_dir / ".cache"),
        "by_topic": _tree(data_dir / "by-topic"),
    }


@pytest.mark.parametrize("mode", sorted(MODES))
@pytest.mark.parametrize("shape", sorted(BLOCKED))
def test_edit_refuses_without_touching_the_journal(isolated_data_dir, shape, mode):
    content, reason = BLOCKED[shape]
    journal = _journal(isolated_data_dir)
    original = content.encode()
    journal.write_bytes(original)
    before = _derived_state(isolated_data_dir)

    result = edit_journal(journal_path=journal, **MODES[mode])

    assert result["success"] is False
    error = result["error"]
    assert error["code"] == "E0202"
    assert error["details"]["reason"] == reason
    assert reason in error["message"]
    assert journal.read_bytes() == original
    assert list_revisions(journal) == []
    assert _derived_state(isolated_data_dir) == before
