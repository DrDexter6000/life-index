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


# Shapes the serializer normalizes on purpose: an edit goes through, and the
# rewritten file says the same thing in the serializer's form.
NORMALIZED = {
    "title_null": ("title:\ndate: 2026-03-04", {"date": "2026-03-04"}),
    "topic_scalar": (
        "title: T\ndate: 2026-03-04\ntopic: life",
        {"title": "T", "date": "2026-03-04", "topic": ["life"]},
    ),
    "tags_comma_text": (
        "title: T\ndate: 2026-03-04\ntags: alpha, beta",
        {"title": "T", "date": "2026-03-04", "tags": ["alpha", "beta"]},
    ),
    "people_null": ("title: T\ndate: 2026-03-04\npeople:", {"title": "T", "date": "2026-03-04"}),
    "unknown_null": (
        "title: T\ndate: 2026-03-04\ncustom:",
        {"title": "T", "date": "2026-03-04", "custom": None},
    ),
    "nested_mapping": (
        "title: T\ndate: 2026-03-04\nplace:\n  name: x\n  lat: 1.5",
        {"title": "T", "date": "2026-03-04", "place": {"name": "x", "lat": 1.5}},
    ),
}


@pytest.mark.parametrize("shape", sorted(NORMALIZED))
def test_edit_still_rewrites_what_the_serializer_only_normalizes(isolated_data_dir, shape):
    from tools.lib.frontmatter import parse_frontmatter
    from tools.lib.schema import SCHEMA_VERSION

    frontmatter, expected = NORMALIZED[shape]
    journal = _journal(isolated_data_dir)
    journal.write_bytes(f"---\n{frontmatter}\n---\n\nthe body stays\n".encode())

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "sunny"})

    assert result["success"] is True, result
    metadata, body = parse_frontmatter(journal.read_text(encoding="utf-8"))
    assert metadata == {"schema_version": SCHEMA_VERSION, "weather": "sunny", **expected}
    assert body.strip() == "the body stays"


def test_edit_checks_again_under_the_lock(isolated_data_dir, monkeypatch):
    """The content read under the lock is what gets rewritten, so it is what is checked."""
    import tools.edit_journal as edit_module

    journal = _journal(isolated_data_dir)
    journal.write_bytes(b"---\ntitle: T\ndate: 2026-03-04\n---\n\nbody\n")
    swapped = b"---\ntitle: T\ndate: 2026-03-04\n2024: x\n---\n\nother words\n"
    real_apply = edit_module._apply_edit_updates
    calls = []

    def apply_then_swap(**kwargs):
        computed = real_apply(**kwargs)
        calls.append(1)
        if len(calls) == 1:
            # Another writer replaces the file after the first check passed.
            journal.write_bytes(swapped)
        return computed

    monkeypatch.setattr(edit_module, "_apply_edit_updates", apply_then_swap)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "sunny"})

    assert len(calls) == 1
    assert result["success"] is False
    assert result["error"]["code"] == "E0202"
    assert result["error"]["details"]["reason"] == "not_round_trippable"
    assert journal.read_bytes() == swapped
    assert list_revisions(journal) == []


@pytest.mark.parametrize("value", ["5", "1.5", "true", "null", "{a: 1}", "[1, [2]]"])
def test_a_malformed_related_entries_value_does_not_raise_after_the_write(isolated_data_dir, value):
    """The relations store is fed through the shared indexable rule."""
    from tools.lib.frontmatter import parse_frontmatter

    journal = _journal(isolated_data_dir)
    journal.write_bytes(
        f"---\ntitle: T\ndate: 2026-03-04\nrelated_entries: {value}\n---\n\nbody\n".encode()
    )
    before, _ = parse_frontmatter(journal.read_text(encoding="utf-8"))

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "sunny"})

    assert result["success"] is True, result
    after, _ = parse_frontmatter(journal.read_text(encoding="utf-8"))
    assert after.get("related_entries") == before.get("related_entries")
    assert after["weather"] == "sunny"


_FUZZ_KEYS = [
    "title",
    "date",
    "location",
    "weather",
    "mood",
    "entities",
    "people",
    "tags",
    "project",
    "topic",
    "summary",
    "abstract",
    "links",
    "related_entries",
    "attachments",
    "schema_version",
    "custom",
    "place",
    "occurred",
    "source",
    "id",
    "kind",
    "expressed_at",
    "reply_to",
    "_private",
    "time",
    "X Y",
    "\u4e2d\u6587\u952e",
]
_FUZZ_TEXTS = [
    "plain",
    "a, b",
    "with: colon",
    "# hash",
    "- dash",
    "",
    " lead",
    "trail ",
    "two\nlines",
    'quote"s',
    "it's",
    "2026-03-04",
    "2026-03-04T10:11:12+08:00",
    "true",
    "null",
    "007",
    "1e3",
    "~",
    "[x]",
    "{y}",
    "|",
    ">",
    "@at",
    "`tick`",
    "%pct",
    "tab\there",
    "sep" + chr(0x2028),
    "emoji" + chr(0x1F600),
    "yes",
    "No",
    "0x1F",
    "1_000",
    "12:30",
    ".5",
    "a" + chr(92) + "b",
    "\u4e2d\u6587",
]


def _fuzz_value(rng, depth):
    roll = rng.random()
    if depth < 3 and roll < 0.15:
        return [_fuzz_value(rng, depth + 1) for _ in range(rng.randint(0, 3))]
    if depth < 3 and roll < 0.30:
        return {
            rng.choice(_FUZZ_TEXTS[:6] + ["k1", "k2"]): _fuzz_value(rng, depth + 1)
            for _ in range(rng.randint(0, 3))
        }
    if roll < 0.70:
        return rng.choice(_FUZZ_TEXTS)
    if roll < 0.78:
        return rng.randint(-5, 10**6)
    if roll < 0.84:
        return rng.choice([0.0, 1.5, -2.25, 1e20, 1e-7, 3.0])
    if roll < 0.90:
        return rng.choice([True, False])
    return None


def test_every_frontmatter_the_guard_admits_survives_a_real_edit(isolated_data_dir):
    """The guard's promise, end to end, on seeded random frontmatter.

    Admitted: the edit succeeds and every field it did not touch comes back as
    the serializer's form of what was there, types included. Refused: the bytes
    are unchanged. Nothing raises either way.
    """
    import random

    import yaml

    from tools.lib.frontmatter import (
        _rewrite_form,
        _same_value,
        frontmatter_rewrite_blocker,
        parse_frontmatter,
    )

    rng = random.Random(20261113)
    journal = _journal(isolated_data_dir)
    admitted = refused = 0
    for round_number in range(160):
        metadata = {key: _fuzz_value(rng, 0) for key in rng.sample(_FUZZ_KEYS, rng.randint(0, 8))}
        dumped = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) if metadata else ""
        text = f"---\n{dumped}---\n\nbody words\n"
        original = text.encode("utf-8")
        journal.write_bytes(original)

        result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "sunny"})

        if frontmatter_rewrite_blocker(text) is not None:
            refused += 1
            assert result["success"] is False, (round_number, metadata)
            assert journal.read_bytes() == original, (round_number, metadata)
            continue
        admitted += 1
        assert result["success"] is True, (round_number, metadata, result)
        before, _ = parse_frontmatter(text)
        after, body = parse_frontmatter(journal.read_text(encoding="utf-8"))
        expected = _rewrite_form(before)
        expected["weather"] = "sunny"
        assert _same_value(after, expected), (round_number, metadata, after)
        assert body.strip() == "body words", (round_number, metadata)

    assert admitted >= 100
    assert refused >= 10
