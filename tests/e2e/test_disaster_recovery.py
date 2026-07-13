"""Synthetic backup -> empty restore -> rebuild disaster-recovery proof."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.backup import create_backup, restore_backup
from tools.build_index import build_all
from tools.generate_index import rebuild_index_tree
from tools.lib.entity_graph import save_entity_graph
from tools.lib.paths import get_default_user_data_dir, is_default_user_data_dir
from tools.search_journals import hierarchical_search
from tools.verify.core import run_verify

RECOVERY_MANIFEST_NAME = ".life-index-recovery-manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_hashes(root: Path) -> dict[str, str]:
    source_paths = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and (
            path.name == "entity_graph.yaml"
            or "attachments" in path.relative_to(root).parts
            or (
                "Journals" in path.relative_to(root).parts
                and not path.name.startswith(("index_", "monthly_", "yearly_"))
            )
        )
    ]
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(source_paths, key=lambda item: item.relative_to(root).as_posix())
    }


def _assert_sandbox(root: Path, tmp_path: Path) -> None:
    assert root.is_relative_to(tmp_path)
    assert root.resolve() != get_default_user_data_dir().resolve()
    assert not is_default_user_data_dir(root)


def _activate_sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True)
    process_temp = tmp_path / f"{name}-process-temp"
    process_temp.mkdir()
    _assert_sandbox(root, tmp_path)
    monkeypatch.setenv("LIFE_INDEX_VALIDATION_MODE", "1")
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(root))
    monkeypatch.setenv("TEMP", str(process_temp))
    monkeypatch.setenv("TMP", str(process_temp))
    return root


def _write_synthetic_dataset(root: Path) -> dict[str, str]:
    journal_specs = [
        (
            "2025",
            "12",
            "life-index_2025-12-31_001.md",
            "Recovery Alpha",
            "recoveryquartzalpha",
            "",
        ),
        (
            "2026",
            "01",
            "life-index_2026-01-02_001.md",
            "Recovery Beta",
            "recoveryquartzbeta",
            "![evidence](attachments/2026/01/recovery-evidence.bin)",
        ),
    ]
    for year, month, filename, title, token, attachment_ref in journal_specs:
        target = root / "Journals" / year / month / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "\n".join(
                [
                    "---",
                    f'title: "{title}"',
                    f"date: {year}-{month}-02" if month == "01" else f"date: {year}-{month}-31",
                    'topic: ["life"]',
                    f'abstract: "Synthetic recovery token {token}"',
                    "---",
                    "",
                    f"# {title}",
                    "",
                    f"Known synthetic token: {token}.",
                    attachment_ref,
                    "",
                ]
            ),
            encoding="utf-8",
        )

    attachment = root / "attachments" / "2026" / "01" / "recovery-evidence.bin"
    attachment.parent.mkdir(parents=True)
    attachment.write_bytes(b"synthetic-attachment-evidence\x00\x01")

    save_entity_graph(
        [
            {
                "id": "actor-recovery-guide",
                "type": "actor",
                "primary_name": "Recovery Guide",
                "aliases": ["RecoveryGuideAlias"],
                "attributes": {"kind": "human"},
                "relationships": [],
            }
        ],
        root / "entity_graph.yaml",
    )

    derived = root / ".index" / "derived-sentinel.bin"
    derived.parent.mkdir(parents=True)
    derived.write_bytes(b"rebuildable-only")
    return _source_hashes(root)


def _load_recovery_manifest(result: dict[str, object]) -> tuple[Path, dict[str, object]]:
    manifest_path = Path(str(result["recovery_manifest_path"]))
    assert manifest_path.name == RECOVERY_MANIFEST_NAME
    return manifest_path, json.loads(manifest_path.read_text(encoding="utf-8"))


def test_backup_manifest_covers_all_required_source_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _activate_sandbox(monkeypatch, tmp_path, "source")
    expected_source_hashes = _write_synthetic_dataset(source)
    backup_root = tmp_path / "backups"
    backup_root.mkdir()

    first = create_backup(str(backup_root), full=True)

    assert first["success"] is True
    manifest_path, manifest = _load_recovery_manifest(first)
    artifacts = manifest["artifacts"]
    canonical = {
        item["path"]: item["sha256"]
        for item in artifacts
        if item["classification"] == "canonical_source"
    }
    derived = {
        item["path"]: item for item in artifacts if item["classification"] == "rebuildable_derived"
    }

    assert manifest["schema_version"] == "life-index.backup-manifest.v1"
    assert manifest["hash_algorithm"] == "sha256"
    assert manifest["complete"] is True
    assert canonical == expected_source_hashes
    assert derived[".index/derived-sentinel.bin"]["included"] is False
    assert not (manifest_path.parent / ".index" / "derived-sentinel.bin").exists()
    assert list(canonical) == sorted(canonical)

    second = create_backup(str(backup_root), full=True)
    _, second_manifest = _load_recovery_manifest(second)
    assert second_manifest == manifest


def test_backup_empty_restore_rebuild_search_verify_roundtrip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _activate_sandbox(monkeypatch, tmp_path, "source")
    source_hashes = _write_synthetic_dataset(source)
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    backup_result = create_backup(str(backup_root), full=True)
    assert backup_result["success"] is True

    restored = tmp_path / "restored"
    restored.mkdir()
    _assert_sandbox(restored, tmp_path)
    assert list(restored.iterdir()) == []

    restore_result = restore_backup(str(backup_result["backup_path"]), dest_path=str(restored))
    assert restore_result["success"] is True
    assert _source_hashes(restored) == source_hashes
    assert not (restored / ".index" / "derived-sentinel.bin").exists()

    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(restored))
    fts_result = build_all(incremental=False)
    legacy_result = rebuild_index_tree()
    assert fts_result["success"] is True
    assert legacy_result["success"] is True

    for token in ("recoveryquartzalpha", "recoveryquartzbeta"):
        search_result = hierarchical_search(query=token, level=3, limit=0)
        assert search_result["success"] is True
        assert any(token in item.get("content", "") for item in search_result["merged_results"])

    verify_result = run_verify()
    assert verify_result["success"] is True
    assert verify_result["issues_count"] == 0
    assert _source_hashes(restored) == source_hashes


def test_backup_copy_failure_names_artifact_and_does_not_publish_complete_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _activate_sandbox(monkeypatch, tmp_path, "source")
    _write_synthetic_dataset(source)
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    failed_name = "life-index_2026-01-02_001.md"

    from tools import backup as backup_module

    real_copy2 = backup_module.shutil.copy2

    def fail_selected_copy(source_path: Path, destination_path: Path) -> object:
        if Path(source_path).name == failed_name:
            raise OSError("injected backup copy failure")
        return real_copy2(source_path, destination_path)

    monkeypatch.setattr(backup_module.shutil, "copy2", fail_selected_copy)
    result = create_backup(str(backup_root), full=True)

    assert result["success"] is False
    assert any(failed_name in error for error in result["errors"])
    assert result.get("recovery_manifest_path", "") == ""
    assert not (Path(result["backup_path"]) / RECOVERY_MANIFEST_NAME).exists()
    catalog = backup_root / ".life-index-backup-manifest.json"
    if catalog.exists():
        records = json.loads(catalog.read_text(encoding="utf-8")).get("backups", [])
        assert all(record.get("path") != result["backup_path"] for record in records)


def test_restore_refuses_nonempty_destination_before_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _activate_sandbox(monkeypatch, tmp_path, "source")
    _write_synthetic_dataset(source)
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    backup_result = create_backup(str(backup_root), full=True)
    assert backup_result["success"] is True

    destination = tmp_path / "nonempty-destination"
    destination.mkdir()
    sentinel = destination / "owner-sentinel.txt"
    sentinel.write_text("must remain unchanged", encoding="utf-8")
    before = {path.name: path.read_bytes() for path in destination.iterdir()}

    result = restore_backup(str(backup_result["backup_path"]), dest_path=str(destination))

    assert result["success"] is False
    assert any("nonempty" in error.lower() for error in result["errors"])
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == before


def test_rebuild_failure_is_visible_and_preserves_source_hashes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _activate_sandbox(monkeypatch, tmp_path, "source")
    _write_synthetic_dataset(source)
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    backup_result = create_backup(str(backup_root), full=True)
    assert backup_result["success"] is True
    restored = tmp_path / "restored"
    restored.mkdir()
    assert restore_backup(str(backup_result["backup_path"]), dest_path=str(restored))["success"]
    before = _source_hashes(restored)
    monkeypatch.setenv("LIFE_INDEX_DATA_DIR", str(restored))

    monkeypatch.setattr(
        "tools.build_index.update_fts_index",
        lambda **_kwargs: {"success": False, "error": "injected rebuild failure"},
    )
    result = build_all(incremental=False)

    assert result["success"] is False
    assert result["fts"]["error"] == "injected rebuild failure"
    assert _source_hashes(restored) == before
