"""Unit tests for the one-pass, read-only durable-id lookup.

The files are the only authority: every test here proves one facet of that —
one pass per call, bytes from the pass build the response, unread paths are
counted, and ambiguity is never silently resolved.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tools.lib.entry_id import new_entry_id
from tools.lib.entry_id_lookup import resolve_entry_ids

ENTRY_ID = "a" * 32
OTHER_ID = "b" * 32


def _seed(
    data_dir: Path,
    name: str,
    *,
    entry_id: str | None = ENTRY_ID,
    body: str = "words of the entry",
) -> Path:
    """Write one live fragment file (date extracted from the name)."""
    parts = name.split("/") if "/" in name else ["2026", "05", name]
    if len(parts) == 3:
        year, month, filename = parts
    else:
        year, month, filename = "2026", "05", name
    directory = data_dir / "Journals" / year / month
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    lines = ["---", "date: 2026-05-28"]
    if entry_id is not None:
        lines.append(f"id: {entry_id}")
    lines.extend(["---", "", body])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _resolve(ids: list[str], data_dir: Path):
    from tools.lib.paths import get_journals_dir, get_user_data_dir

    return resolve_entry_ids(
        ids, journals_dir=get_journals_dir(), user_data_dir=get_user_data_dir()
    )


def test_one_pass_resolves_many_ids_and_reads_each_file_once(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tools.lib.entry_id_lookup as lookup_module

    first = _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)
    second = _seed(isolated_data_dir, "life-index_2026-05-29_001.md", entry_id=OTHER_ID)
    reads: dict[str, int] = {}
    real_read = lookup_module._read_bytes

    def counting_read(path: Path) -> bytes:
        key = str(path)
        reads[key] = reads.get(key, 0) + 1
        return real_read(path)

    monkeypatch.setattr(lookup_module, "_read_bytes", counting_read)

    result = _resolve([ENTRY_ID, OTHER_ID], isolated_data_dir)

    assert reads[str(first)] == 1 and reads[str(second)] == 1
    assert set(reads) == {str(first), str(second)}
    assert result.outcomes[ENTRY_ID].status == "found"
    assert result.outcomes[OTHER_ID].status == "found"
    assert result.complete is True and result.unread_paths == 0


def test_response_is_built_from_the_bytes_of_the_pass(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second read of the same file (if any existed) would serve tampered bytes."""
    import tools.lib.entry_id_lookup as lookup_module

    target = _seed(isolated_data_dir, "life-index_2026-05-28_001.md", body="first read")
    real_read = lookup_module._read_bytes

    def tampering_read(path: Path) -> bytes:
        if str(path) == str(target):
            calls = getattr(tampering_read, "calls", 0) + 1
            tampering_read.calls = calls  # type: ignore[attr-defined]
            if calls > 1:
                return b"---\nid: " + ENTRY_ID.encode() + b"\n---\n\nSECOND READ"
        return real_read(path)

    monkeypatch.setattr(lookup_module, "_read_bytes", tampering_read)

    result = _resolve([ENTRY_ID], isolated_data_dir)
    hit = result.outcomes[ENTRY_ID].hits[0]

    assert hit.content.endswith("first read")
    assert "SECOND READ" not in hit.content
    assert tampering_read.calls == 1  # type: ignore[attr-defined]


def test_found_after_move_and_rename(isolated_data_dir: Path) -> None:
    _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)
    moved = isolated_data_dir / "Journals" / "2026" / "06"
    moved.mkdir(parents=True)
    (isolated_data_dir / "Journals" / "2026" / "05" / "life-index_2026-05-28_001.md").rename(
        moved / "life-index_2026-06-01_007.md"
    )

    result = _resolve([ENTRY_ID], isolated_data_dir)

    assert result.outcomes[ENTRY_ID].status == "found"
    assert result.outcomes[ENTRY_ID].hits[0].rel_path == (
        "Journals/2026/06/life-index_2026-06-01_007.md"
    )


def test_ambiguous_id_names_every_file(isolated_data_dir: Path) -> None:
    _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)
    _seed(isolated_data_dir, "life-index_2026-05-29_001.md", entry_id=ENTRY_ID)

    result = _resolve([ENTRY_ID], isolated_data_dir)

    assert result.outcomes[ENTRY_ID].status == "ambiguous"
    assert sorted(result.outcomes[ENTRY_ID].rel_paths) == [
        "Journals/2026/05/life-index_2026-05-28_001.md",
        "Journals/2026/05/life-index_2026-05-29_001.md",
    ]


def test_not_found_on_a_complete_pass(isolated_data_dir: Path) -> None:
    _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)

    result = _resolve([new_entry_id()], isolated_data_dir)

    outcome = list(result.outcomes.values())[0]
    assert outcome.status == "not_found"
    assert result.complete is True


def test_unreadable_file_makes_a_miss_incomplete_but_a_hit_still_found(
    isolated_data_dir: Path,
) -> None:
    _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)
    stray = isolated_data_dir / "Journals" / "2026" / "05" / "life-index_2026-05-30_001.md"
    stray.write_bytes(b"\xff\xfe not utf8")

    result = _resolve([ENTRY_ID, new_entry_id()], isolated_data_dir)

    assert result.complete is False and result.unread_paths == 1
    found = result.outcomes[ENTRY_ID]
    assert found.status == "found" and found.unread_paths == 1
    missing = [o for o in result.outcomes.values() if o.status != "found"][0]
    assert missing.status == "incomplete" and missing.unread_paths == 1


def test_unlistable_directory_is_counted_as_one_unread_path(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tools.lib.entry_id_lookup as lookup_module

    _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)
    (isolated_data_dir / "Journals" / "2026" / "06").mkdir()
    real_scandir = lookup_module.os.scandir

    def failing_scandir(path: object):
        if str(path).endswith("06"):
            raise OSError("directory cannot be listed")
        return real_scandir(path)  # type: ignore[arg-type]

    monkeypatch.setattr(lookup_module.os, "scandir", failing_scandir)

    result = _resolve([ENTRY_ID], isolated_data_dir)

    assert result.complete is False and result.unread_paths == 1


def test_dot_directories_and_non_fragments_are_outside_the_scope(
    isolated_data_dir: Path,
) -> None:
    revisions = isolated_data_dir / "Journals" / "2026" / "05" / ".revisions"
    revisions.mkdir(parents=True)
    (revisions / "life-index_2026-05-28_001.md").write_text(
        f"---\nid: {ENTRY_ID}\n---\n", encoding="utf-8"
    )
    digest = isolated_data_dir / "Journals" / "2026" / "05" / "digest_2026-05.md"
    digest.write_text(f"---\nid: {ENTRY_ID}\n---\n", encoding="utf-8")

    result = _resolve([ENTRY_ID], isolated_data_dir)

    assert list(result.outcomes.values())[0].status == "not_found"
    assert result.complete is True


def test_a_malformed_stored_id_is_not_a_match(isolated_data_dir: Path) -> None:
    _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id="NOT-A-VALID-ID")

    result = _resolve([ENTRY_ID], isolated_data_dir)

    assert list(result.outcomes.values())[0].status == "not_found"


def test_invalid_selectors_collapse_to_no_outcome(isolated_data_dir: Path) -> None:
    _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)

    result = _resolve(["zz", "", ENTRY_ID, ENTRY_ID], isolated_data_dir)

    assert set(result.outcomes) == {ENTRY_ID}


def test_missing_journals_dir_is_a_complete_empty_pass(tmp_path: Path) -> None:
    empty_root = tmp_path / "fresh-data"
    empty_root.mkdir()

    result = resolve_entry_ids(
        [ENTRY_ID], journals_dir=empty_root / "Journals", user_data_dir=empty_root
    )

    assert list(result.outcomes.values())[0].status == "not_found"
    assert result.complete is True and result.unread_paths == 0
    # A missing Journals/ tree is not created by the read.
    assert not (empty_root / "Journals").exists()


def test_no_lock_or_directory_is_created(isolated_data_dir: Path, tmp_path: Path) -> None:
    before = {p.relative_to(isolated_data_dir).as_posix() for p in isolated_data_dir.rglob("*")}

    _resolve([ENTRY_ID], isolated_data_dir)

    after = {p.relative_to(isolated_data_dir).as_posix() for p in isolated_data_dir.rglob("*")}
    assert before == after
    assert not any(name.endswith(".lock") for name in after)
    assert os.access(isolated_data_dir, os.W_OK)  # sanity: the dir was writable


def _symlink_or_skip(target: Path, link: Path) -> None:
    """Create a symlink or skip the test where the platform refuses one."""
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable on this platform")


class TestCandidateScope:
    """The lookup's candidates are exactly the files `get --path` serves."""

    def test_nested_entry_is_not_a_candidate(self, isolated_data_dir: Path) -> None:
        nested = isolated_data_dir / "Journals" / "2026" / "05" / "nested"
        nested.mkdir(parents=True)
        (nested / "life-index_2026-05-29_001.md").write_text(
            f"---\nid: {ENTRY_ID}\n---\n", encoding="utf-8"
        )

        result = _resolve([ENTRY_ID], isolated_data_dir)

        outcome = list(result.outcomes.values())[0]
        assert outcome.status == "not_found"
        assert result.complete is True and result.unread_paths == 0

        from tools.journal.__main__ import run_journal_get

        by_path = run_journal_get(path="Journals/2026/05/nested/life-index_2026-05-29_001.md")
        assert by_path["error"]["code"] == "JOURNAL_PATH_INVALID"

    def test_escaping_file_symlink_is_not_a_candidate(
        self, isolated_data_dir: Path, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside-entry.md"
        outside.write_text(f"---\nid: {ENTRY_ID}\n---\noutside words\n", encoding="utf-8")
        month = isolated_data_dir / "Journals" / "2026" / "05"
        month.mkdir(parents=True, exist_ok=True)
        _symlink_or_skip(outside, month / "life-index_2026-05-30_001.md")

        result = _resolve([ENTRY_ID], isolated_data_dir)

        outcome = list(result.outcomes.values())[0]
        assert outcome.status == "not_found"
        assert result.complete is True and result.unread_paths == 0

        from tools.journal.__main__ import run_journal_get

        by_path = run_journal_get(path="Journals/2026/05/life-index_2026-05-30_001.md")
        assert by_path["error"]["code"] == "JOURNAL_PATH_INVALID"

    def test_escaping_directory_symlink_is_not_a_candidate(
        self, isolated_data_dir: Path, tmp_path: Path
    ) -> None:
        outside_year = tmp_path / "outside-archive" / "2027"
        month = outside_year / "03"
        month.mkdir(parents=True)
        (month / "life-index_2027-03-05_001.md").write_text(
            f"---\nid: {ENTRY_ID}\n---\noutside words\n", encoding="utf-8"
        )
        _symlink_or_skip(outside_year, isolated_data_dir / "Journals" / "2027")

        result = _resolve([ENTRY_ID], isolated_data_dir)

        outcome = list(result.outcomes.values())[0]
        assert outcome.status == "not_found"
        assert result.complete is True and result.unread_paths == 0

    def test_entry_in_a_normal_month_directory_is_found(self, isolated_data_dir: Path) -> None:
        _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)

        result = _resolve([ENTRY_ID], isolated_data_dir)

        assert result.outcomes[ENTRY_ID].status == "found"


class TestReadSeams:
    """The get/batch items built from an id lookup come from the pass itself."""

    def _read_then_replace(self, lookup_module, target: Path, replacement: str):
        """A pass-read seam that replaces the file on disk right after reading it."""
        real_read = lookup_module._read_bytes

        def read_then_replace(path: Path) -> bytes:
            raw = real_read(path)
            if str(path) == str(target):
                target.write_text(replacement, encoding="utf-8")
            return raw

        return read_then_replace

    def test_mixed_batch_item_comes_from_the_lookup_pass(
        self, isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One file selected by path and by id: the id-scan read wins, not a reread."""
        import argparse

        import tools.lib.entry_id_lookup as lookup_module
        from tools.journal.__main__ import _handle_batch_get

        _seed(isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID)
        target = isolated_data_dir / "Journals" / "2026" / "05" / "life-index_2026-05-28_001.md"
        replacement = f"---\nid: {OTHER_ID}\n---\n\nreplaced body"
        monkeypatch.setattr(
            lookup_module,
            "_read_bytes",
            self._read_then_replace(lookup_module, target, replacement),
        )

        payload = _handle_batch_get(
            argparse.Namespace(
                path=["Journals/2026/05/life-index_2026-05-28_001.md"], id=[ENTRY_ID]
            )
        )

        assert payload["success"] is True, payload
        assert payload["data"]["total_requested"] == 2
        assert payload["data"]["total_found"] == 1
        item = payload["data"]["items"][0]
        assert item["id"] == ENTRY_ID, "the item must carry the requested id"
        assert item["content"] == "words of the entry", "the item must be the pass's content"

    def test_get_by_id_response_is_the_pass_read_not_a_reread(
        self, isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`run_journal_get(id=...)` must not re-read the matched file."""
        import tools.lib.entry_id_lookup as lookup_module
        from tools.journal.__main__ import run_journal_get

        _seed(
            isolated_data_dir, "life-index_2026-05-28_001.md", entry_id=ENTRY_ID, body="first read"
        )
        target = isolated_data_dir / "Journals" / "2026" / "05" / "life-index_2026-05-28_001.md"
        replacement = f"---\nid: {OTHER_ID}\n---\n\nSECOND READ"
        monkeypatch.setattr(
            lookup_module,
            "_read_bytes",
            self._read_then_replace(lookup_module, target, replacement),
        )

        payload = run_journal_get(id=f"  {ENTRY_ID}  ")

        assert payload["success"] is True, payload
        assert payload["data"]["id"] == ENTRY_ID
        assert payload["data"]["content"] == "first read"
        assert "SECOND READ" not in payload["data"]["content"]
