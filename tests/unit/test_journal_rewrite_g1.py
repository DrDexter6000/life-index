#!/usr/bin/env python3
"""G1: every rewrite of an existing journal file is lossless, atomic, locked.

Byte-level tests, in a temporary data directory (``isolated_data_dir`` /
``LIFE_INDEX_DATA_DIR``), for the shared rewrite primitive in
``tools/lib/journal_rewrite.py`` and its consumers (``edit``, ``migrate``,
the confirm path, and ``write``'s LF rule).
"""

import os
import stat
import threading
import time
from pathlib import Path

import pytest

from tools.edit_journal import edit_journal
from tools.lib.frontmatter import (
    _split_frontmatter_sections,
    frontmatter_opens_block,
    is_frontmatter_delimiter_line,
)
from tools.lib.journal_rewrite import (
    _is_windows_transient_replace_error,
    _unlink_temp,
    replace_journal_bytes,
    split_journal_bytes,
)
from tools.lib.revisions import list_revisions

DATE = "2026-03-14"


def _journal_path(data_dir: Path, name: str = f"life-index_{DATE}_001.md") -> Path:
    path = data_dir / "Journals" / "2026" / "03" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_journal(data_dir: Path, raw: bytes, name: str = f"life-index_{DATE}_001.md") -> Path:
    path = _journal_path(data_dir, name)
    path.write_bytes(raw)
    return path


def _temp_leftovers(month_dir: Path) -> list[str]:
    return sorted(
        entry.name
        for entry in month_dir.iterdir()
        if entry.name.startswith(".") and ".tmp-" in entry.name
    )


# ---------------------------------------------------------------------------
# 1. A metadata-only edit keeps the suffix byte-identical
# ---------------------------------------------------------------------------

SUFFIX_CASES = {
    "lf_trailing_newline": (b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody first\nbody second\n"),
    "crlf_file": (b"---\r\ntitle: T\r\ndate: 2026-03-14\r\n---\r\n\r\nbody line\r\nanother\r\n"),
    "mixed_no_final_newline": (
        b"---\ntitle: T\r\ndate: 2026-03-14\n---\r\n\n\n  leading  \r\ninner\nlast  \r\n"
    ),
    "dashes_in_body": (
        b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbefore\n---\nbetween\n---\nafter\n"
    ),
}


@pytest.mark.parametrize("raw", SUFFIX_CASES.values(), ids=SUFFIX_CASES)
def test_metadata_only_edit_keeps_the_suffix_byte_identical(isolated_data_dir, raw):
    journal = _write_journal(isolated_data_dir, raw)
    suffix_before = split_journal_bytes(journal.read_bytes()).suffix

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is True, result
    assert result["content_modified"] is False
    after = journal.read_bytes()
    split_after = split_journal_bytes(after)
    assert split_after.suffix == suffix_before
    # The newly formatted frontmatter block is LF and carries the new field.
    assert b"\r" not in split_after.frontmatter_block
    assert b'weather: "Sunny"\n' in split_after.frontmatter_block


def test_content_edit_rewrites_the_body_with_lf(isolated_data_dir):
    journal = _write_journal(
        isolated_data_dir,
        b"---\ntitle: T\r\ndate: 2026-03-14\n---\r\n\r\nold body\r\n",
    )

    result = edit_journal(
        journal_path=journal, frontmatter_updates={}, replace_content="new body\nline"
    )

    assert result["success"] is True, result
    assert result["content_modified"] is True
    raw = journal.read_bytes()
    assert raw.endswith(b"\n\nnew body\nline")
    assert b"\r" not in raw


# ---------------------------------------------------------------------------
# 2. Atomicity: a failing replace/fsync leaves the journal untouched
# ---------------------------------------------------------------------------


def test_replace_failure_leaves_bytes_and_no_temp(isolated_data_dir, monkeypatch):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    original = journal.read_bytes()

    def fail_replace(_temp: Path, _path: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("tools.lib.journal_rewrite.replace_with_retry", fail_replace)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    assert "replace failed" in result["error"]["message"]
    assert journal.read_bytes() == original
    assert _temp_leftovers(journal.parent) == []


def test_fsync_failure_leaves_bytes_and_no_temp(isolated_data_dir, monkeypatch):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    original = journal.read_bytes()

    def fail_fsync(_fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("tools.lib.journal_rewrite.os.fsync", fail_fsync)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    assert journal.read_bytes() == original
    assert _temp_leftovers(journal.parent) == []


def test_windows_transient_replace_retries_then_succeeds(isolated_data_dir, monkeypatch):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    real_replace = os.replace
    attempts = {"count": 0}

    def flaky_replace(temp: Path, path: Path) -> None:
        if Path(path) != journal:
            # Only the journal's own replace is flaky; post-commit side
            # effects replace other files and must keep working.
            return real_replace(temp, path)
        attempts["count"] += 1
        if attempts["count"] <= 2:
            exc = PermissionError("transient share violation")
            exc.winerror = 32
            raise exc
        real_replace(temp, path)

    monkeypatch.setattr(os, "replace", flaky_replace)
    # The retry loop is Windows-gated by the transient predicate; the loop
    # itself is exercised everywhere by widening the predicate in this test.
    monkeypatch.setattr(
        "tools.lib.journal_rewrite._is_windows_transient_replace_error",
        lambda exc: isinstance(exc, OSError),
    )

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is True, result
    assert attempts["count"] == 3
    assert b'weather: "Sunny"' in journal.read_bytes()
    assert _temp_leftovers(journal.parent) == []


def test_windows_transient_replace_exhaustion_fails_clean(isolated_data_dir, monkeypatch):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    original = journal.read_bytes()
    attempts = {"count": 0}

    def always_denied(temp: Path, path: Path) -> None:
        attempts["count"] += 1
        exc = PermissionError("locked by another process")
        exc.winerror = 5
        raise exc

    monkeypatch.setattr(os, "replace", always_denied)
    monkeypatch.setattr(
        "tools.lib.journal_rewrite._is_windows_transient_replace_error",
        lambda exc: isinstance(exc, OSError),
    )

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    assert attempts["count"] == 3
    assert journal.read_bytes() == original
    assert _temp_leftovers(journal.parent) == []


@pytest.mark.skipif(os.name != "nt", reason="winerror semantics are Windows-only")
def test_the_transient_predicate_matches_only_windows_5_and_32():
    def exc_with(winerror: int) -> OSError:
        exc = PermissionError("denied")
        exc.winerror = winerror
        return exc

    assert _is_windows_transient_replace_error(exc_with(5)) is True
    assert _is_windows_transient_replace_error(exc_with(32)) is True
    assert _is_windows_transient_replace_error(exc_with(13)) is False
    assert _is_windows_transient_replace_error(RuntimeError("no")) is False


# ---------------------------------------------------------------------------
# 3. Mode: the original file's permission bits survive the replace (POSIX)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission modes")
@pytest.mark.parametrize("umask", [0o022, 0o077])
@pytest.mark.parametrize("mode", [0o600, 0o644])
def test_edit_keeps_the_original_mode(isolated_data_dir, mode, umask):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    os.chmod(journal, mode)
    previous_umask = os.umask(umask)
    try:
        result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})
    finally:
        os.umask(previous_umask)

    assert result["success"] is True, result
    assert stat.S_IMODE(os.stat(journal).st_mode) == mode


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission modes")
def test_the_temp_gets_the_original_mode_not_mkstemp_0600(tmp_path):
    journal = tmp_path / "life-index_2026-03-14_001.md"
    journal.write_bytes(b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    os.chmod(journal, 0o644)
    previous_umask = os.umask(0o077)
    try:
        replace_journal_bytes(journal, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    finally:
        os.umask(previous_umask)
    assert stat.S_IMODE(os.stat(journal).st_mode) == 0o644


# ---------------------------------------------------------------------------
# 4. Revisions are byte-exact
# ---------------------------------------------------------------------------


def test_revision_is_byte_exact_for_a_mixed_endings_file(isolated_data_dir):
    raw = b"---\ntitle: T\r\ndate: 2026-03-14\n---\r\n\r\n  body  \r\nlast\nno final newline"
    journal = _write_journal(isolated_data_dir, raw)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is True, result
    revisions = list_revisions(journal)
    assert len(revisions) == 1
    assert revisions[0].read_bytes() == raw


def test_failed_revision_save_prevents_the_replace(isolated_data_dir, monkeypatch):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    original = journal.read_bytes()

    def fail_revision(_path: Path, _content: bytes) -> Path:
        raise OSError("revision destination unwritable")

    monkeypatch.setattr("tools.edit_journal.save_revision_bytes", fail_revision)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    assert journal.read_bytes() == original
    assert _temp_leftovers(journal.parent) == []


# ---------------------------------------------------------------------------
# 5. A physical ``content:`` key never silently disappears
# ---------------------------------------------------------------------------


def test_physical_content_key_in_frontmatter_is_refused(isolated_data_dir):
    raw = b'---\ntitle: T\ndate: 2026-03-14\ncontent: "irreplaceable words"\n---\n\nbody\n'
    journal = _write_journal(isolated_data_dir, raw)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0202"
    assert result["error"]["details"]["reason"] == "content_key_in_frontmatter"
    assert journal.read_bytes() == raw
    assert list_revisions(journal) == []


def test_content_update_through_frontmatter_updates_is_refused(isolated_data_dir):
    raw = b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n"
    journal = _write_journal(isolated_data_dir, raw)

    result = edit_journal(journal_path=journal, frontmatter_updates={"content": "smuggled body"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0001"
    assert journal.read_bytes() == raw


# ---------------------------------------------------------------------------
# 6. New-form fragments: the words are not editable through ``edit``
# ---------------------------------------------------------------------------

NEW_FORM_FRAGMENT = (
    b"---\n"
    b"kind: fragment\n"
    b"id: frag-2026-03-14-0001\n"
    b"date: 2026-03-14\n"
    b"expressed_at: 2026-03-14T10:00:00\n"
    b"ingested_at: 2026-03-14T10:00:05\n"
    b"schema_version: 3\n"
    b"---\n\n"
    b"the user's own words\n"
)

LEGACY_JOURNAL = b"---\ntitle: T\ndate: 2026-03-14\n---\n\nlegacy body\n"


def test_fragment_replace_and_append_are_refused(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, NEW_FORM_FRAGMENT)
    original = journal.read_bytes()

    for kwargs in ({"replace_content": "new words"}, {"append_content": "more words"}):
        result = edit_journal(journal_path=journal, frontmatter_updates={}, **kwargs)
        assert result["success"] is False
        assert result["error"]["code"] == "E0505"
        assert "fragment note" in result["error"]["message"]
        assert journal.read_bytes() == original


@pytest.mark.parametrize("field", ["id", "kind", "ingested_at", "schema_version", "content"])
def test_fragment_identity_fields_are_refused(isolated_data_dir, field):
    journal = _write_journal(isolated_data_dir, NEW_FORM_FRAGMENT)
    original = journal.read_bytes()

    result = edit_journal(journal_path=journal, frontmatter_updates={field: "something-else"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0505"
    assert result["error"]["details"]["field"] == field
    assert journal.read_bytes() == original


def test_fragment_identity_cannot_be_bypassed_in_one_call(isolated_data_dir):
    """Changing kind/id and the body in the same call still refuses."""
    journal = _write_journal(isolated_data_dir, NEW_FORM_FRAGMENT)
    original = journal.read_bytes()

    result = edit_journal(
        journal_path=journal,
        frontmatter_updates={"kind": "journal", "id": "other"},
        replace_content="rewritten words",
    )

    assert result["success"] is False
    assert result["error"]["code"] == "E0505"
    assert journal.read_bytes() == original


def test_fragment_location_does_not_require_weather(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, NEW_FORM_FRAGMENT)

    result = edit_journal(journal_path=journal, frontmatter_updates={"location": "Beijing, China"})

    assert result["success"] is True, result
    assert b'location: "Beijing, China"' in journal.read_bytes()


def test_fragment_other_metadata_stays_editable(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, NEW_FORM_FRAGMENT)

    result = edit_journal(
        journal_path=journal, frontmatter_updates={"weather": "Sunny", "place": "home"}
    )

    assert result["success"] is True, result
    raw = journal.read_bytes()
    assert b'weather: "Sunny"' in raw
    assert b'place: "home"' in raw
    # The fragment's own words are untouched, byte for byte.
    assert raw.endswith(b"\n\nthe user's own words\n")


def test_legacy_journal_keeps_the_location_weather_coupling(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, LEGACY_JOURNAL)

    refused = edit_journal(journal_path=journal, frontmatter_updates={"location": "Beijing, China"})
    assert refused["success"] is False
    assert refused["error"]["code"] == "E0504"

    accepted = edit_journal(
        journal_path=journal,
        frontmatter_updates={"location": "Beijing, China", "weather": "Sunny"},
    )
    assert accepted["success"] is True, accepted


def test_legacy_journal_still_allows_content_edits(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, LEGACY_JOURNAL)

    result = edit_journal(
        journal_path=journal, frontmatter_updates={}, append_content="added later"
    )

    assert result["success"] is True, result
    assert result["content_modified"] is True
    assert journal.read_bytes().endswith(b"legacy body\n\nadded later")


# ---------------------------------------------------------------------------
# 7. migrate: locked, re-read inside the lock, suffix verbatim
# ---------------------------------------------------------------------------

V1_JOURNAL = (
    b"---\nschema_version: 1\ntitle: T\ndate: 2026-03-14\n---\r\n"
    b"\r\n  body with CRLF  \r\nlast line\r\n"
)


def test_migrate_keeps_the_suffix_byte_identical(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, V1_JOURNAL)
    suffix_before = split_journal_bytes(journal.read_bytes()).suffix

    from tools.migrate import apply_migrations

    result = apply_migrations(isolated_data_dir / "Journals")

    assert result["migrated_count"] == 1
    assert result["failed_count"] == 0
    raw = journal.read_bytes()
    assert split_journal_bytes(raw).suffix == suffix_before
    assert b"\r" in split_journal_bytes(raw).suffix  # the suffix keeps its CRLF
    from tools.lib.schema import SCHEMA_VERSION

    assert f"schema_version: {SCHEMA_VERSION}".encode() in raw


def test_migrate_does_not_lose_a_concurrent_locked_edit(isolated_data_dir, monkeypatch):
    """A lock-respecting writer that commits while migrate runs is not clobbered.

    migrate's replace is gated so it happens while the journals lock is held;
    the concurrent ``edit`` (same lock protocol) can only apply after migrate
    releases it. Both changes must survive.
    """
    from tools.migrate import apply_migrations

    journal = _write_journal(isolated_data_dir, V1_JOURNAL)
    month_dir = journal.parent

    import tools.lib.journal_rewrite as journal_rewrite

    real_replace = journal_rewrite.replace_journal_bytes
    entered = threading.Event()
    gate = threading.Event()

    def slow_replace(path: Path, data: bytes) -> None:
        entered.set()
        gate.wait(timeout=10)
        real_replace(path, data)

    monkeypatch.setattr("tools.migrate.replace_journal_bytes", slow_replace)

    migrate_outcome: dict[str, object] = {}

    def run_migrate() -> None:
        migrate_outcome["report"] = apply_migrations(isolated_data_dir / "Journals")

    migrate_thread = threading.Thread(target=run_migrate)
    migrate_thread.start()
    assert entered.wait(10), "migrate never reached its replace step"

    edit_outcome: dict[str, object] = {}

    def run_edit() -> None:
        edit_outcome["result"] = edit_journal(
            journal_path=journal, frontmatter_updates={"weather": "Rain"}
        )

    edit_thread = threading.Thread(target=run_edit)
    edit_thread.start()
    # The edit blocks on the journals lock migrate holds; give it a moment to
    # get there, then let migrate finish.
    time.sleep(0.3)
    gate.set()
    migrate_thread.join(timeout=10)
    edit_thread.join(timeout=10)

    assert not migrate_thread.is_alive()
    assert not edit_thread.is_alive()
    assert edit_outcome["result"]["success"] is True, edit_outcome
    assert migrate_outcome["report"]["migrated_count"] == 1
    raw = journal.read_bytes()
    assert b'weather: "Rain"' in raw  # the concurrent edit survived the migration
    from tools.lib.schema import SCHEMA_VERSION

    assert f"schema_version: {SCHEMA_VERSION}".encode() in raw
    assert _temp_leftovers(month_dir) == []


def test_migrate_takes_the_journals_lock(isolated_data_dir, monkeypatch):
    from tools.lib.file_lock import FileLock, get_journals_lock_path

    journal = _write_journal(isolated_data_dir, V1_JOURNAL)
    original = journal.read_bytes()

    import tools.migrate as migrate_module

    monkeypatch.setattr(migrate_module, "FILE_LOCK_TIMEOUT_REBUILD", 0.01)
    with FileLock(get_journals_lock_path(), timeout=0.2):
        from tools.migrate import apply_migrations

        report = apply_migrations(isolated_data_dir / "Journals")

    assert report["success"] is False
    assert report["error"]["code"] == "E0005"
    assert report["migrated_count"] == 0
    assert report["failed_count"] == 0
    assert journal.read_bytes() == original


# ---------------------------------------------------------------------------
# 8. The other rewriters keep the suffix byte-identical too
# ---------------------------------------------------------------------------


def test_confirm_path_keeps_the_suffix(isolated_data_dir):
    from tools.write_journal.core import apply_confirmation_updates

    journal = _write_journal(isolated_data_dir, SUFFIX_CASES["crlf_file"])
    suffix_before = split_journal_bytes(journal.read_bytes()).suffix

    result = apply_confirmation_updates(journal_path=journal, weather="Cloudy")

    assert result["success"] is True, result
    raw = journal.read_bytes()
    assert split_journal_bytes(raw).suffix == suffix_before
    assert b'weather: "Cloudy"' in split_journal_bytes(raw).frontmatter_block


# ---------------------------------------------------------------------------
# 9. write produces LF-only journals on every platform
# ---------------------------------------------------------------------------


def test_write_journal_contains_no_cr(isolated_data_dir):
    from tools.write_journal import write_journal

    result = write_journal(
        data={
            "date": DATE,
            "title": "CRLF supplied title",
            "content": "line1\r\nline2\rline3\nplain",
            "location": "Test City",
            "weather": "Sunny",
            "topic": ["work"],
        }
    )

    assert result["success"] is True, result
    raw = Path(result["journal_path"]).read_bytes()
    assert b"\r" not in raw
    assert b"line1\nline2\nline3\nplain" in raw


# ---------------------------------------------------------------------------
# 10. One delimiter rule: the byte split and the parser never disagree
# ---------------------------------------------------------------------------

DELIMITER_LINE_VARIANTS = {
    "plain": "---",
    "trailing_space": "--- ",
    "trailing_tab": "---\t",
    "trailing_cr": "---\r",
    "ideographic_space": "---\u3000",
    "nbsp": "---\xa0",
    "file_separator": "---\x1c",
    "leading_space": " ---",
    "leading_tab": "\t---",
    "leading_ideographic_space": "\u3000---",
    "blank_line": "",
    "not_a_delimiter": "---junk",
}


def _c1_file(open_line: str, close_line: str) -> bytes:
    # A later whole-line ``---`` lives in the body, the exact shape of the
    # reported loss bug.
    return (
        f"{open_line}\ntitle: T\ndate: 2026-03-14\n{close_line}\n\n" "body one\n---\nafter\n"
    ).encode("utf-8")


def _parser_saw_a_whole_line_block(text: str) -> bool:
    lines = text.split("\n")
    return frontmatter_opens_block(text) and any(
        is_frontmatter_delimiter_line(line) for line in lines[1:]
    )


@pytest.mark.parametrize("variant", DELIMITER_LINE_VARIANTS.values(), ids=DELIMITER_LINE_VARIANTS)
@pytest.mark.parametrize("position", ["opening", "closing"])
def test_the_byte_split_suffix_is_the_parser_body_section(variant, position):
    if position == "opening":
        raw = _c1_file(variant, "---")
    else:
        raw = _c1_file("---", variant)
    text = raw.decode("utf-8")
    sections = _split_frontmatter_sections(text)
    split = split_journal_bytes(raw)

    if _parser_saw_a_whole_line_block(text):
        assert split is not None
        assert sections is not None
        # The byte suffix decodes to exactly the parser's body section,
        # before any stripping.
        assert split.suffix.decode("utf-8") == sections[1]
    else:
        assert split is None


@pytest.mark.parametrize("variant", DELIMITER_LINE_VARIANTS.values(), ids=DELIMITER_LINE_VARIANTS)
@pytest.mark.parametrize("position", ["opening", "closing"])
def test_every_delimiter_variant_is_safe_to_edit(isolated_data_dir, variant, position):
    if position == "opening":
        raw = _c1_file(variant, "---")
    else:
        raw = _c1_file("---", variant)
    journal = _write_journal(isolated_data_dir, raw)
    split_before = split_journal_bytes(journal.read_bytes())

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    if result["success"] is True:
        assert split_before is not None
        # The suffix after the edit is byte-identical to the bytes that
        # followed the block the parser saw (which the direct test above
        # proves is what split_journal_bytes returned before the edit).
        assert split_journal_bytes(journal.read_bytes()).suffix == split_before.suffix
        assert b"body one" in split_before.suffix  # the reported loss cannot recur
    else:
        assert journal.read_bytes() == raw
        assert result["error"]["code"] in ("E0202", "E0200")


# ---------------------------------------------------------------------------
# 11. Content edits write the body region with LF (no CR at all)
# ---------------------------------------------------------------------------


def test_append_content_writes_the_body_region_with_lf(isolated_data_dir):
    journal = _write_journal(
        isolated_data_dir,
        b"---\r\ntitle: T\r\ndate: 2026-03-14\r\n---\r\n\r\nline one\r\nline two\r\n",
    )

    result = edit_journal(
        journal_path=journal, frontmatter_updates={}, append_content="added\r\nmore"
    )

    assert result["success"] is True, result
    assert result["content_modified"] is True
    after_block = split_journal_bytes(journal.read_bytes()).suffix
    assert b"\r" not in after_block
    assert after_block == b"\n\nline one\nline two\n\nadded\nmore"


def test_replace_content_writes_the_body_region_with_lf(isolated_data_dir):
    journal = _write_journal(
        isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nold body\n"
    )

    result = edit_journal(journal_path=journal, frontmatter_updates={}, replace_content="a\r\nb\rc")

    assert result["success"] is True, result
    assert result["content_modified"] is True
    after_block = split_journal_bytes(journal.read_bytes()).suffix
    assert b"\r" not in after_block
    assert after_block == b"\n\na\nb\nc"


# ---------------------------------------------------------------------------
# 12. A journal the user cannot write is refused cleanly on both platforms
# ---------------------------------------------------------------------------


@pytest.mark.skipif(os.name != "nt", reason="Windows read-only attribute")
def test_windows_readonly_journal_is_refused_clean(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    os.chmod(journal, stat.S_IREAD)
    original = journal.read_bytes()

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    assert journal.read_bytes() == original
    assert stat.S_IMODE(os.stat(journal).st_mode) & stat.S_IWRITE == 0
    assert _temp_leftovers(journal.parent) == []
    assert list_revisions(journal) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission modes")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can write 0444")
def test_posix_0444_journal_is_refused_clean(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    os.chmod(journal, 0o444)
    original = journal.read_bytes()

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    assert journal.read_bytes() == original
    assert stat.S_IMODE(os.stat(journal).st_mode) == 0o444
    assert _temp_leftovers(journal.parent) == []
    assert list_revisions(journal) == []


def test_unlink_temp_removes_a_read_only_temp(tmp_path):
    temp = tmp_path / ".life-index_journal.md.tmp-abc"
    temp.write_bytes(b"x")
    os.chmod(temp, 0o444)

    _unlink_temp(temp)

    assert not temp.exists()


# ---------------------------------------------------------------------------
# 13. A metadata edit that changes nothing does not rewrite the file
# ---------------------------------------------------------------------------


def test_a_no_change_metadata_edit_does_not_rewrite(isolated_data_dir):
    raw = b"---\r\ntitle: T\r\nweather: sunny\r\ndate: 2026-03-14\r\n---\r\n\r\nbody\r\n"
    journal = _write_journal(isolated_data_dir, raw)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "sunny"})

    assert result["success"] is True, result
    assert result["changes"] == {}
    assert result["content_modified"] is False
    assert result["revision_path"] is None
    assert journal.read_bytes() == raw  # the header was not reformatted either
    assert list_revisions(journal) == []
    assert _temp_leftovers(journal.parent) == []


# ---------------------------------------------------------------------------
# 14. Round-2 reproductions: B (leading-whitespace opener), C (recoverable
# content shape), D (forged update keys). Each must be refused with the bytes
# unchanged whether the refusing layer is the outgoing-file check (E0202
# not_round_trippable) or the up-front validation (E0001 / blocker reason).
# ---------------------------------------------------------------------------

LEADING_WHITESPACE_OPENERS = {
    "space": " ",
    "tab": "\t",
    "ideographic_space": "\u3000",
}


@pytest.mark.parametrize(
    "padding", LEADING_WHITESPACE_OPENERS.values(), ids=LEADING_WHITESPACE_OPENERS
)
def test_a_leading_whitespace_opener_cannot_lose_the_metadata(isolated_data_dir, padding):
    raw = (f'{padding}---\ntitle: "T"\ndate: 2026-03-14\n---\n\nbody one\n---\nafter\n').encode(
        "utf-8"
    )
    journal = _write_journal(isolated_data_dir, raw)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "rain"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0202"
    assert journal.read_bytes() == raw
    assert list_revisions(journal) == []


def test_a_leading_blank_line_cannot_lose_the_metadata(isolated_data_dir):
    raw = '\ntitle: "T"\ndate: 2026-03-14\n---\n\nbody one\n'.encode("utf-8")
    journal = _write_journal(isolated_data_dir, raw)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "rain"})

    assert result["success"] is False
    assert journal.read_bytes() == raw


def test_a_leading_whitespace_opener_is_refused_through_confirm(isolated_data_dir):
    from tools.write_journal.core import apply_confirmation_updates

    raw = ' ---\ntitle: "T"\ndate: 2026-03-14\n---\n\nbody one\n'.encode("utf-8")
    journal = _write_journal(isolated_data_dir, raw)

    result = apply_confirmation_updates(journal_path=journal, weather="Cloudy")

    assert result["success"] is False
    assert journal.read_bytes() == raw


def test_a_leading_whitespace_opener_is_refused_by_migrate(isolated_data_dir):
    from tools.migrate import apply_migrations

    raw = ' ---\nschema_version: 1\ntitle: "T"\ndate: 2026-03-14\n---\n\nbody one\n'.encode("utf-8")
    journal = _write_journal(isolated_data_dir, raw)

    report = apply_migrations(isolated_data_dir / "Journals")

    assert report["migrated_count"] == 0
    assert report["failed_count"] == 1
    assert journal.read_bytes() == raw


RECOVERABLE_CONTENT_SHAPE = (
    '---\ntitle: "T"\ndate: 2026-03-14\ncontent:\n'
    '"irreplaceable "quoted" words"\n---\n\ntrailing body\n'
).encode("utf-8")


def test_the_recoverable_content_shape_is_refused_by_edit(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, RECOVERABLE_CONTENT_SHAPE)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "rain"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0202"
    assert journal.read_bytes() == RECOVERABLE_CONTENT_SHAPE
    assert list_revisions(journal) == []


def test_the_recoverable_content_shape_is_refused_by_migrate(isolated_data_dir):
    from tools.migrate import apply_migrations

    journal = _write_journal(isolated_data_dir, RECOVERABLE_CONTENT_SHAPE)

    report = apply_migrations(isolated_data_dir / "Journals")

    assert report["migrated_count"] == 0
    assert report["failed_count"] == 1
    assert journal.read_bytes() == RECOVERABLE_CONTENT_SHAPE


def _assert_forged_key_refused(result, journal, original):
    assert result["success"] is False
    assert result["error"]["code"] in ("E0001", "E0202")
    assert journal.read_bytes() == original
    assert list_revisions(journal) == []


def test_a_padded_kind_key_cannot_bypass_the_fragment_guard(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, NEW_FORM_FRAGMENT)
    original = journal.read_bytes()

    result = edit_journal(journal_path=journal, frontmatter_updates={"kind" + chr(32): "journal"})
    _assert_forged_key_refused(result, journal, original)

    # The fragment is still refused a content edit afterwards.
    after = edit_journal(
        journal_path=journal, frontmatter_updates={}, replace_content="rewritten words"
    )
    assert after["success"] is False
    assert after["error"]["code"] == "E0505"
    assert journal.read_bytes() == original


def test_a_padded_content_key_cannot_change_the_body(isolated_data_dir):
    from tools.lib.frontmatter import parse_frontmatter

    raw = b"---\ntitle: T\ndate: 2026-03-14\n---\n\nthe body words\n"
    journal = _write_journal(isolated_data_dir, raw)

    result = edit_journal(journal_path=journal, frontmatter_updates={"content" + chr(32): "FORGED"})
    _assert_forged_key_refused(result, journal, raw)

    _metadata, body = parse_frontmatter(journal.read_text(encoding="utf-8"))
    assert "the body words" in body
    assert "FORGED" not in body


def test_a_key_holding_a_delimiter_line_cannot_inject_body_bytes(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    original = journal.read_bytes()
    forged_key = "x: 1" + chr(10) + "---" + chr(10) + "BODY"

    result = edit_journal(journal_path=journal, frontmatter_updates={forged_key: "v"})
    _assert_forged_key_refused(result, journal, original)


def test_an_update_key_with_a_line_break_is_rejected(isolated_data_dir):
    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    original = journal.read_bytes()

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather" + chr(10): "sunny"})
    _assert_forged_key_refused(result, journal, original)


# ---------------------------------------------------------------------------
# 15. Round-2 roots: F (type-sensitive no-change), G (symlink), H (mutations)
# ---------------------------------------------------------------------------


def test_a_type_change_is_a_change_and_rewrites(isolated_data_dir):
    from tools.lib.frontmatter import parse_frontmatter

    journal = _write_journal(
        isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\ncustom: true\n---\n\nbody\n"
    )

    result = edit_journal(journal_path=journal, frontmatter_updates={"custom": 1})

    assert result["success"] is True, result
    metadata, _body = parse_frontmatter(journal.read_text(encoding="utf-8"))
    assert metadata["custom"] == 1
    assert not isinstance(metadata["custom"], bool)
    assert list_revisions(journal) != []  # a real rewrite kept a revision


def test_an_identical_int_is_not_a_change(isolated_data_dir):
    raw = b"---\ntitle: T\ndate: 2026-03-14\ncustom: 1\n---\n\nbody\n"
    journal = _write_journal(isolated_data_dir, raw)

    result = edit_journal(journal_path=journal, frontmatter_updates={"custom": 1})

    assert result["success"] is True, result
    assert result["content_modified"] is False
    assert result["revision_path"] is None
    assert journal.read_bytes() == raw
    assert list_revisions(journal) == []


def test_a_symlinked_journal_is_refused(isolated_data_dir, tmp_path):
    target = tmp_path / "elsewhere.md"
    raw = b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n"
    target.write_bytes(raw)
    journal = _journal_path(isolated_data_dir)
    try:
        journal.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("this platform or user cannot create a symbolic link")

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    assert journal.is_symlink()  # the link is still a link
    assert target.read_bytes() == raw  # the target keeps its old bytes
    assert list_revisions(journal) == []
    assert _temp_leftovers(journal.parent) == []


def test_an_identity_field_update_alone_is_refused(isolated_data_dir):
    """Only an identity field, no content operation: still E0505.

    Proves the identity-field check itself (the combined-call test would
    still pass with that check removed, via the content restriction).
    """
    journal = _write_journal(isolated_data_dir, NEW_FORM_FRAGMENT)
    original = journal.read_bytes()

    result = edit_journal(journal_path=journal, frontmatter_updates={"kind": "journal"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0505"
    assert journal.read_bytes() == original
    assert list_revisions(journal) == []

    after = edit_journal(
        journal_path=journal, frontmatter_updates={}, replace_content="rewritten words"
    )
    assert after["success"] is False
    assert after["error"]["code"] == "E0505"
    assert journal.read_bytes() == original


def test_a_failure_below_the_primitive_leaves_the_edit_intact(isolated_data_dir, monkeypatch):
    import errno as errno_module

    journal = _write_journal(isolated_data_dir, b"---\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n")
    original = journal.read_bytes()

    def fail_replace(src, dst):
        # A non-transient OSError below the primitive: not retried, not
        # absorbed; the primitive must clean its own temp up.
        raise OSError(errno_module.EIO, "non-transient replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    result = edit_journal(journal_path=journal, frontmatter_updates={"weather": "Sunny"})

    assert result["success"] is False
    assert result["error"]["code"] == "E0200"
    assert journal.read_bytes() == original
    assert _temp_leftovers(journal.parent) == []


def test_a_failure_below_the_primitive_fails_that_migrate_file(isolated_data_dir, monkeypatch):
    import errno as errno_module

    from tools.migrate import apply_migrations

    journal = _write_journal(
        isolated_data_dir,
        b"---\nschema_version: 1\ntitle: T\ndate: 2026-03-14\n---\n\nbody\n",
    )
    original = journal.read_bytes()

    def fail_replace(src, dst):
        raise OSError(errno_module.EIO, "non-transient replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    report = apply_migrations(isolated_data_dir / "Journals")

    assert report["migrated_count"] == 0
    assert report["failed_count"] == 1
    assert journal.read_bytes() == original
    assert _temp_leftovers(journal.parent) == []
