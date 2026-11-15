#!/usr/bin/env python3
"""Tests for ``migrate`` assigning the durable entry id (H1).

Covers: id assignment on current- and older-schema files in one rewrite, the
never-touch rules for malformed and duplicated ids, crash safety of the
single replace, and the dry-run/apply agreement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.lib import journal_rewrite
from tools.lib.entry_id import is_valid_entry_id, legacy_entry_id
from tools.lib.frontmatter import parse_frontmatter

V3 = 3  # tools.lib.schema.SCHEMA_VERSION, pinned here for readable fixtures


def _month(tmp_path: Path, year: str = "2026", month: str = "03") -> Path:
    month_dir = tmp_path / "Journals" / year / month
    month_dir.mkdir(parents=True, exist_ok=True)
    return month_dir


def _write_entry(
    month_dir: Path,
    name: str,
    frontmatter: str,
    body: str = "Body text.",
) -> Path:
    """Write one entry as LF bytes (no platform newline translation)."""
    path = month_dir / name
    path.write_bytes(f"---\n{frontmatter}\n---\n\n{body}\n".encode("utf-8"))
    return path


def _stored_id(path: Path) -> str | None:
    metadata, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
    value = metadata.get("id")
    return str(value) if value is not None else None


class TestAssignsMissingIds:
    def test_a_current_schema_file_without_an_id_gets_one_and_keeps_its_body(
        self, tmp_path: Path
    ) -> None:
        from tools.migrate import apply_migrations

        path = _write_entry(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            f"schema_version: {V3}\ntitle: T\ndate: 2026-03-07",
        )
        before = path.read_bytes()
        suffix_before = before.split(b"---\n", 2)[2]  # bytes after the block

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 1
        assert result["failed_count"] == 0
        assigned = _stored_id(path)
        assert is_valid_entry_id(assigned)
        assert result["assigned_ids"] == [{"path": str(path), "id": assigned}]
        # The id is the recipe applied to the pre-migration bytes at the
        # data-dir-relative path.
        assert assigned == legacy_entry_id("Journals/2026/03/life-index_2026-03-07_001.md", before)
        # Body bytes identical: everything after the frontmatter block is
        # byte-for-byte what it was.
        after = path.read_bytes()
        assert after.split(b"---\n", 2)[2] == suffix_before
        # The migration adds `id` and nothing else: no kind, no timestamps.
        metadata, _body = parse_frontmatter(after.decode("utf-8"))
        assert set(metadata) == {"schema_version", "title", "date", "id"}

    def test_an_older_schema_file_gets_chain_steps_and_id_in_one_replace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tools.migrate import apply_migrations

        path = _write_entry(
            _month(tmp_path, "2025", "06"),
            "life-index_2025-06-15_001.md",
            "schema_version: 1\ntitle: Old\ndate: 2025-06-15",
        )
        calls: list[Path] = []
        real_replace = journal_rewrite.replace_journal_bytes

        def counting_replace(journal_path: Path, new_bytes: bytes) -> None:
            calls.append(journal_path)
            real_replace(journal_path, new_bytes)

        monkeypatch.setattr("tools.migrate.replace_journal_bytes", counting_replace)

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 1
        assert calls == [path], "one file, exactly one replace"
        metadata, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
        assert metadata["schema_version"] == V3
        assert "entities" in metadata  # the chain steps ran in the same rewrite
        assert is_valid_entry_id(metadata.get("id"))
        assert "Body text." in path.read_text(encoding="utf-8")

    def test_a_second_run_rewrites_nothing(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations

        month = _month(tmp_path)
        _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f"schema_version: {V3}\ntitle: T\ndate: 2026-03-07",
        )
        _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            "schema_version: 1\ntitle: U\ndate: 2026-03-08",
        )

        first = apply_migrations(tmp_path / "Journals")
        assert first["migrated_count"] == 2
        snapshot = {p.name: p.read_bytes() for p in sorted(month.glob("life-index_*.md"))}

        second = apply_migrations(tmp_path / "Journals")
        assert second["migrated_count"] == 0
        assert second["already_current"] == 2
        assert second["failed_count"] == 0
        assert {p.name: p.read_bytes() for p in sorted(month.glob("life-index_*.md"))} == snapshot

    def test_a_file_with_a_valid_id_is_not_touched(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations

        path = _write_entry(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            f'schema_version: {V3}\ntitle: T\ndate: 2026-03-07\nid: "' + "a" * 32 + '"',
        )
        before = path.read_bytes()

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert result["already_current"] == 1
        assert path.read_bytes() == before


class TestNeverTouchRules:
    def test_a_malformed_id_is_left_byte_identical_and_reported(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations

        path = _write_entry(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            f'schema_version: {V3}\ntitle: T\ndate: 2026-03-07\nid: "not-an-id"',
        )
        before = path.read_bytes()

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert result["failed_count"] == 1
        assert result["failed_files"][0]["path"] == str(path)
        assert "malformed_id" in result["failed_files"][0]["error"]
        assert path.read_bytes() == before

    def test_a_malformed_id_blocks_even_an_outdated_schema_file(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations

        path = _write_entry(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            'schema_version: 1\ntitle: T\ndate: 2026-03-07\nid: "UPPERCASE"',
        )
        before = path.read_bytes()

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert "malformed_id" in result["failed_files"][0]["error"]
        assert path.read_bytes() == before

    def test_two_files_with_one_id_are_both_left_and_both_named(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations

        shared = "c" * 32
        month = _month(tmp_path)
        first = _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f'schema_version: {V3}\ntitle: T\ndate: 2026-03-07\nid: "{shared}"',
        )
        second = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            f'schema_version: {V3}\ntitle: U\ndate: 2026-03-08\nid: "{shared}"',
        )
        before = (first.read_bytes(), second.read_bytes())

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        reported = {item["path"] for item in result["failed_files"]}
        assert reported == {str(first), str(second)}
        assert all("duplicate_id" in item["error"] for item in result["failed_files"])
        assert (first.read_bytes(), second.read_bytes()) == before

    def test_a_duplicated_id_file_needing_a_schema_step_is_still_not_changed(
        self, tmp_path: Path
    ) -> None:
        from tools.migrate import apply_migrations

        shared = "e" * 32
        month = _month(tmp_path)
        current = _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f'schema_version: {V3}\ntitle: T\ndate: 2026-03-07\nid: "{shared}"',
        )
        outdated = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            f'schema_version: 1\ntitle: U\ndate: 2026-03-08\nid: "{shared}"',
        )
        before = (current.read_bytes(), outdated.read_bytes())

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert result["failed_count"] == 2
        assert (current.read_bytes(), outdated.read_bytes()) == before

    def test_a_duplicated_id_counts_even_when_one_schema_version_is_text(
        self, tmp_path: Path
    ) -> None:
        """Both carriers are refused as duplicate_id, the unreadable-version
        one included: the census counts stored ids whatever else is wrong."""
        from tools.migrate import apply_migrations

        shared = "f" * 32
        month = _month(tmp_path)
        text_version = _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f'schema_version: "3"\ntitle: T\ndate: 2026-03-07\nid: "{shared}"',
        )
        other = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            f'schema_version: {V3}\ntitle: U\ndate: 2026-03-08\nid: "{shared}"',
        )
        before = (text_version.read_bytes(), other.read_bytes())

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert result["failed_count"] == 2
        assert all("duplicate_id" in item["error"] for item in result["failed_files"])
        assert not any("invalid_schema_version" in item["error"] for item in result["failed_files"])
        assert (text_version.read_bytes(), other.read_bytes()) == before


class TestProspectiveIdCollisions:
    def test_a_prospective_id_already_stored_somewhere_is_refused(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations

        month = _month(tmp_path)
        victim = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            f"schema_version: {V3}\ntitle: U\ndate: 2026-03-08",
        )
        # Pre-compute the id the migration would assign to the victim and
        # plant it as another file's stored id.
        prospective = legacy_entry_id(
            "Journals/2026/03/life-index_2026-03-08_001.md", victim.read_bytes()
        )
        carrier = _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f'schema_version: {V3}\ntitle: T\ndate: 2026-03-07\nid: "{prospective}"',
        )
        before = (carrier.read_bytes(), victim.read_bytes())

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert result["failed_count"] == 1
        assert result["failed_files"][0]["path"] == str(victim)
        assert "duplicate_id" in result["failed_files"][0]["error"]
        assert prospective in result["failed_files"][0]["error"]
        # No two files end up carrying one id; nothing was written.
        assert (carrier.read_bytes(), victim.read_bytes()) == before

    def test_dry_run_reports_the_same_prospective_collision(self, tmp_path: Path) -> None:
        from tools.migrate import scan_journals

        month = _month(tmp_path)
        victim = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            f"schema_version: {V3}\ntitle: U\ndate: 2026-03-08",
        )
        prospective = legacy_entry_id(
            "Journals/2026/03/life-index_2026-03-08_001.md", victim.read_bytes()
        )
        _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f'schema_version: {V3}\ntitle: T\ndate: 2026-03-07\nid: "{prospective}"',
        )

        report = scan_journals(tmp_path / "Journals")

        refused = {item["path"]: item["reason"] for item in report["refused_files"]}
        assert refused[str(victim)] == "duplicate_id"

    def test_a_prospective_id_assigned_earlier_in_the_run_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two id-less files whose recipe ids would collide: the second is
        refused because the first was already assigned in this run."""
        from tools.migrate import apply_migrations

        month = _month(tmp_path)
        first = _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f"schema_version: {V3}\ntitle: T\ndate: 2026-03-07",
        )
        second = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            f"schema_version: {V3}\ntitle: U\ndate: 2026-03-08",
        )
        shared_prospective = "9" * 32
        # Both files' recipe yields the same id (a forced collision); the
        # files are planned in sorted order, so 03-07 is assigned first.
        monkeypatch.setattr("tools.migrate.legacy_entry_id", lambda rel, raw: shared_prospective)

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 1
        assert _stored_id(first) == shared_prospective
        assert result["failed_count"] == 1
        assert result["failed_files"][0]["path"] == str(second)
        assert "duplicate_id" in result["failed_files"][0]["error"]
        assert "already assigned" in result["failed_files"][0]["error"]
        assert _stored_id(second) is None, "the colliding file was left without an id"


class TestIdOnlyRewriteChangesNothingElse:
    def _current(self, month: Path, name: str, extra: str) -> Path:
        return _write_entry(
            month,
            name,
            f"schema_version: {V3}\ntitle: T\ndate: 2026-03-07\n{extra}",
        )

    def test_a_string_in_a_list_field_is_refused_and_named(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations, scan_journals

        path = self._current(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            'tags: "alpha, beta"',
        )
        before = path.read_bytes()

        report = scan_journals(tmp_path / "Journals")
        result = apply_migrations(tmp_path / "Journals")

        assert any(
            item["reason"] == "would_change_metadata" for item in report["refused_files"]
        ), report
        assert result["migrated_count"] == 0
        assert "would_change_metadata" in result["failed_files"][0]["error"]
        assert "tags" in result["failed_files"][0]["error"]
        assert path.read_bytes() == before

    def test_a_null_known_field_is_refused_and_named(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations

        path = self._current(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            "weather: null",
        )
        before = path.read_bytes()

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 0
        assert "would_change_metadata" in result["failed_files"][0]["error"]
        assert "weather" in result["failed_files"][0]["error"]
        assert path.read_bytes() == before

    def test_an_ordinary_current_schema_file_is_migrated(self, tmp_path: Path) -> None:
        from tools.migrate import apply_migrations

        path = _write_entry(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            f'schema_version: {V3}\ntitle: T\ndate: 2026-03-07\ntags: ["a", "b"]',
        )

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 1
        assert result["failed_count"] == 0
        assert is_valid_entry_id(_stored_id(path))

    def test_a_schema_step_file_keeps_the_normalisations(self, tmp_path: Path) -> None:
        """A file that needs the chain keeps today's behaviour: the
        serializer's normalisations apply, no would_change_metadata refusal."""
        from tools.migrate import apply_migrations

        path = _write_entry(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            'schema_version: 1\ntitle: T\ndate: 2026-03-07\ntags: "alpha, beta"',
        )

        result = apply_migrations(tmp_path / "Journals")

        assert result["migrated_count"] == 1
        assert result["failed_count"] == 0
        from tools.lib.frontmatter import parse_frontmatter as _pf

        metadata, _body = _pf(path.read_text(encoding="utf-8"))
        assert metadata["tags"] == ["alpha", "beta"]
        assert is_valid_entry_id(metadata.get("id"))


class TestEachFileReplacedBeforeTheNextIsRead:
    def test_an_edit_during_the_run_is_not_overwritten(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """File A is edited at the moment file B is planned; A's later words
        survive because A was already replaced before B was read."""
        from tools.migrate import _plan_one_file, apply_migrations

        month = _month(tmp_path)
        first = _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f"schema_version: {V3}\ntitle: T\ndate: 2026-03-07",
        )
        second = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            f"schema_version: {V3}\ntitle: U\ndate: 2026-03-08",
        )
        real_plan = _plan_one_file
        hooked: list[Path] = []

        def plan_with_editor(*args: Any, **kwargs: Any):
            md_file = args[0]
            if md_file == second:
                # The "editor" rewrites file A while file B is being planned.
                hooked.append(md_file)
                first.write_bytes(first.read_bytes().replace(b"Body text.", b"editor words"))
            return real_plan(*args, **kwargs)

        monkeypatch.setattr("tools.migrate._plan_one_file", plan_with_editor)

        result = apply_migrations(tmp_path / "Journals")

        assert hooked == [second], "the editor hook fired when file B was planned"
        assert result["migrated_count"] == 2
        assert result["failed_count"] == 0
        assert b"editor words" in first.read_bytes(), "A's later words must survive"
        assert is_valid_entry_id(_stored_id(first))
        assert is_valid_entry_id(_stored_id(second))


class TestCrashSafety:
    def test_a_failed_replace_leaves_the_file_unchanged_and_reproducible(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The failure is injected below the shared primitive: ``os.replace``
        as seen by ``tools.lib.journal_rewrite`` raises for one file. The
        original bytes stay, no temp file survives, and the next run assigns
        the same id — so a mutation that swaps the atomic replace for a
        direct in-place write is caught (the victim's bytes would change)."""
        import os as os_module

        from tools.migrate import apply_migrations

        month = _month(tmp_path)
        victim = _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f"schema_version: {V3}\ntitle: T\ndate: 2026-03-07",
        )
        other = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            f"schema_version: {V3}\ntitle: U\ndate: 2026-03-08",
        )
        victim_bytes = victim.read_bytes()
        real_os_replace = os_module.replace

        def failing_os_replace(src: Any, dst: Any, *args: Any, **kwargs: Any) -> None:
            if Path(dst) == victim:
                raise OSError("simulated crash inside os.replace")
            return real_os_replace(src, dst, *args, **kwargs)

        monkeypatch.setattr("tools.lib.journal_rewrite.os.replace", failing_os_replace)

        first = apply_migrations(tmp_path / "Journals")

        assert first["migrated_count"] == 1  # the other file is done
        assert first["failed_count"] == 1
        assert victim.read_bytes() == victim_bytes  # untouched
        assert is_valid_entry_id(_stored_id(other))
        leftovers = [p.name for p in month.iterdir() if p.name.startswith(".")]
        assert leftovers == [], "the failed replace must leave no temp file behind"

        monkeypatch.undo()
        second = apply_migrations(tmp_path / "Journals")

        assert second["migrated_count"] == 1
        assert second["failed_count"] == 0
        # The retried file gets the same id the failed attempt computed.
        assert _stored_id(victim) == legacy_entry_id(
            "Journals/2026/03/life-index_2026-03-07_001.md", victim_bytes
        )


class TestDryRun:
    def test_dry_run_names_every_refused_file_changes_no_byte_and_agrees_with_apply(
        self, tmp_path: Path
    ) -> None:
        from tools.migrate import apply_migrations, scan_journals

        month = _month(tmp_path)
        good = _write_entry(
            month,
            "life-index_2026-03-07_001.md",
            f"schema_version: {V3}\ntitle: T\ndate: 2026-03-07",
        )
        older = _write_entry(
            month,
            "life-index_2026-03-08_001.md",
            "schema_version: 1\ntitle: U\ndate: 2026-03-08",
        )
        malformed = _write_entry(
            month,
            "life-index_2026-03-09_001.md",
            f'schema_version: {V3}\ntitle: M\ndate: 2026-03-09\nid: "bad"',
        )
        shared = "d" * 32
        dup_a = _write_entry(
            month,
            "life-index_2026-03-10_001.md",
            f'schema_version: {V3}\ntitle: D\ndate: 2026-03-10\nid: "{shared}"',
        )
        dup_b = _write_entry(
            month,
            "life-index_2026-03-11_001.md",
            f'schema_version: {V3}\ntitle: E\ndate: 2026-03-11\nid: "{shared}"',
        )
        blocked = _write_entry(
            month,
            "life-index_2026-03-12_001.md",
            "schema_version: 1\ntitle: B\ndate: 2026-03-12\ncustom: !!pairs [a: b]",
        )
        no_block = month / "life-index_2026-03-13_001.md"
        no_block.write_bytes("no frontmatter here".encode("utf-8"))

        snapshot = {path: path.read_bytes() for path in month.glob("life-index_*.md")}

        report = scan_journals(tmp_path / "Journals")

        # No byte changed.
        assert {path: path.read_bytes() for path in month.glob("life-index_*.md")} == snapshot
        # Every file that will not be migrated is named with a reason.
        refused = {item["path"]: item["reason"] for item in report["refused_files"]}
        assert refused[str(malformed)] == "malformed_id"
        assert refused[str(dup_a)] == "duplicate_id"
        assert refused[str(dup_b)] == "duplicate_id"
        assert refused[str(blocked)] == "not_round_trippable"
        assert refused[str(no_block)] == "no_frontmatter_block"
        assert set(refused) == {
            str(malformed),
            str(dup_a),
            str(dup_b),
            str(blocked),
            str(no_block),
        }
        # Would be rewritten: good (id), older (schema+id), blocked (schema+id,
        # but refused) and no_block (counted as v1, but refused).
        assert report["needs_migration"] == 4
        assert report["needs_id"] == 4

        applied = apply_migrations(tmp_path / "Journals")

        # Apply does exactly what dry-run said: migrates the two writable
        # files, refuses the same five for the same reasons.
        assert applied["migrated_count"] == 2
        assert is_valid_entry_id(_stored_id(good))
        assert (
            _stored_id(older) is not None
            and "entities" in parse_frontmatter(older.read_text(encoding="utf-8"))[0]
        )
        applied_refused = {item["path"]: item["error"] for item in applied["failed_files"]}
        assert set(applied_refused) == set(refused)
        assert "malformed_id" in applied_refused[str(malformed)]
        assert "duplicate_id" in applied_refused[str(dup_a)]
        assert "not_round_trippable" in applied_refused[str(blocked)]
        assert "no_frontmatter_block" in applied_refused[str(no_block)]
        assert malformed.read_bytes() == snapshot[malformed]
        assert dup_a.read_bytes() == snapshot[dup_a]
        assert dup_b.read_bytes() == snapshot[dup_b]
        assert blocked.read_bytes() == snapshot[blocked]
        assert no_block.read_bytes() == snapshot[no_block]

    def test_dry_run_reports_a_not_replaceable_file(self, tmp_path: Path) -> None:
        from tools.migrate import scan_journals

        path = _write_entry(
            _month(tmp_path),
            "life-index_2026-03-07_001.md",
            f"schema_version: {V3}\ntitle: T\ndate: 2026-03-07",
        )
        # A read-only file cannot be replaced; dry-run names the precondition.
        path.chmod(0o444)
        try:
            report = scan_journals(tmp_path / "Journals")
        finally:
            path.chmod(0o644)
        refused = {item["path"]: item["reason"] for item in report["refused_files"]}
        assert refused[str(path)] == "not_replaceable"

    def test_dry_run_names_an_unreadable_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tools.migrate import scan_journals

        month = _month(tmp_path)
        path = month / "life-index_2026-03-07_001.md"
        path.write_bytes(b"---\n- a list root\n---\n\nbody\n")
        report = scan_journals(tmp_path / "Journals")
        refused = {item["path"]: item["reason"] for item in report["refused_files"]}
        assert refused[str(path)] == "unreadable"
