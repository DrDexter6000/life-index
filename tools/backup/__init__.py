#!/usr/bin/env python3
"""
Life Index - Backup Tool
数据备份工具（支持增量备份）

Usage:
    python -m tools.backup --dest /path/to/backup
    python -m tools.backup --dest /path/to/backup --full
    python -m tools.backup --dest /path/to/backup --dry-run

Public API:
    from tools.backup import create_backup
    result = create_backup(dest_path="/path/to/backup")
"""

import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, cast

from ..lib.paths import get_journals_dir, get_by_topic_dir, get_attachments_dir, get_user_data_dir
from ..lib.logger import get_logger

logger = get_logger(__name__)

RECOVERY_MANIFEST_NAME = ".life-index-recovery-manifest.json"
RECOVERY_MANIFEST_SCHEMA = "life-index.backup-manifest.v1"
RECOVERY_MANIFEST_FIELDS = frozenset({"schema_version", "hash_algorithm", "complete", "artifacts"})
RECOVERY_ARTIFACT_FIELDS = frozenset({"path", "classification", "included", "sha256", "size"})
CANONICAL_SOURCE = "canonical_source"
REBUILDABLE_DERIVED = "rebuildable_derived"
LEGACY_RESTORE_WARNING = (
    "Legacy backup has no verified recovery manifest; restored files are unverified."
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def calculate_file_hash(file_path: Path) -> str:
    """计算文件的 MD5 哈希值"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except (IOError, OSError) as e:
        logger.error(f"计算哈希失败 {file_path}: {e}")
        return ""


def load_backup_manifest(backup_dir: Path) -> Dict[str, Any]:
    """加载备份清单文件"""
    manifest_path = backup_dir / ".life-index-backup-manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"无法加载备份清单: {e}")
    return {"backups": [], "files": {}}


def save_backup_manifest(backup_dir: Path, manifest: Dict[str, Any]) -> bool:
    """保存备份清单文件"""
    manifest_path = backup_dir / ".life-index-backup-manifest.json"
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        logger.error(f"无法保存备份清单: {e}")
        return False


def _calculate_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_generated_journal_artifact(relative_path: Path) -> bool:
    return relative_path.name.startswith(("index_", "monthly_", "yearly_"))


def _create_backup_subdir(dest: Path, timestamp: str, *, dry_run: bool) -> Path:
    base_name = f"life-index-backup-{timestamp}"
    if dry_run:
        return dest / base_name

    counter = 0
    while True:
        suffix = "" if counter == 0 else f"-{counter:03d}"
        candidate = dest / f"{base_name}{suffix}"
        try:
            candidate.mkdir(parents=False, exist_ok=False)
            return candidate
        except FileExistsError:
            counter += 1


def _is_reparse_point(path: Path) -> bool:
    try:
        stat_result = path.lstat()
    except OSError:
        return False
    if path.is_symlink():
        return True
    return bool(getattr(stat_result, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)


def _assert_contained_without_reparse(root: Path, candidate: Path) -> None:
    root_resolved = root.resolve(strict=True)
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"artifact is outside recovery root: {candidate}") from exc

    current = root
    if _is_reparse_point(current):
        raise ValueError(f"reparse point is not allowed in recovery path: {current}")
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _is_reparse_point(current):
                raise ValueError(f"reparse point is not allowed in recovery path: {current}")

    candidate_resolved = candidate.resolve(strict=True)
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"artifact resolves outside recovery root: {candidate}") from exc


def _assert_destination_contained_without_reparse(root: Path, candidate: Path) -> None:
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"destination is outside requested root: {candidate}") from exc
    if root.exists() and _is_reparse_point(root):
        raise ValueError(f"restore destination root is a reparse point: {root}")
    root_resolved = root.resolve(strict=False)
    current = root
    for part in relative.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _is_reparse_point(current):
                raise ValueError(f"reparse point is not allowed in restore path: {current}")
    try:
        candidate.resolve(strict=False).relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"destination resolves outside requested root: {candidate}") from exc


def _normalize_manifest_path(raw_path: Any) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("artifact path must be a nonempty string")
    if "\\" in raw_path:
        raise ValueError(f"artifact path is not normalized: {raw_path}")
    pure_path = PurePosixPath(raw_path)
    if pure_path.is_absolute() or any(part in {"", ".", ".."} for part in pure_path.parts):
        raise ValueError(f"artifact path is unsafe: {raw_path}")
    normalized = pure_path.as_posix()
    if normalized != raw_path:
        raise ValueError(f"artifact path is not normalized: {raw_path}")
    return normalized


def _expected_artifact_mapping(path: str) -> tuple[str, bool]:
    parts = PurePosixPath(path).parts
    first = parts[0]
    if path == "entity_graph.yaml":
        return CANONICAL_SOURCE, True
    if first == "attachments" and len(parts) > 1:
        return CANONICAL_SOURCE, True
    if first == "Journals" and len(parts) > 1:
        if _is_generated_journal_artifact(Path(parts[-1])):
            return REBUILDABLE_DERIVED, True
        return CANONICAL_SOURCE, True
    if first == "by-topic" and len(parts) > 1:
        return REBUILDABLE_DERIVED, True
    if first == ".index" and len(parts) > 1:
        return REBUILDABLE_DERIVED, False
    raise ValueError(f"artifact path is outside the closed recovery schema: {path}")


def _validate_recovery_artifact(artifact: Any) -> tuple[str, bool]:
    if not isinstance(artifact, dict) or set(artifact) != RECOVERY_ARTIFACT_FIELDS:
        raise ValueError("artifact must contain exactly path/classification/included/sha256/size")
    path = _normalize_manifest_path(artifact["path"])
    expected_classification, expected_included = _expected_artifact_mapping(path)
    if artifact["classification"] != expected_classification:
        raise ValueError(
            f"artifact classification mismatch for {path}: expected {expected_classification}"
        )
    if not isinstance(artifact["included"], bool) or artifact["included"] != expected_included:
        raise ValueError(f"artifact inclusion mismatch for {path}: expected {expected_included}")
    if not isinstance(artifact["sha256"], str) or not _SHA256_PATTERN.fullmatch(artifact["sha256"]):
        raise ValueError(f"artifact sha256 is invalid: {path}")
    if (
        not isinstance(artifact["size"], int)
        or isinstance(artifact["size"], bool)
        or artifact["size"] < 0
    ):
        raise ValueError(f"artifact size is invalid: {path}")
    return path, expected_included


def _canonical_source_inventory(data_root: Path) -> Dict[str, Path]:
    inventory: Dict[str, Path] = {}
    journals = data_root / "Journals"
    if journals.exists():
        for file_path in sorted(journals.rglob("*")):
            if file_path.is_file() and not _is_generated_journal_artifact(file_path):
                relative = file_path.relative_to(data_root).as_posix()
                inventory[relative] = file_path
    attachments = data_root / "attachments"
    if attachments.exists():
        for file_path in sorted(attachments.rglob("*")):
            if file_path.is_file():
                relative = file_path.relative_to(data_root).as_posix()
                inventory[relative] = file_path
    entity_graph = data_root / "entity_graph.yaml"
    if entity_graph.is_file():
        inventory["entity_graph.yaml"] = entity_graph
    return dict(sorted(inventory.items()))


def _artifact_record(
    *,
    path: str,
    file_path: Path,
    classification: str,
    included: bool,
) -> Dict[str, Any]:
    return {
        "path": path.replace("\\", "/"),
        "classification": classification,
        "included": included,
        "sha256": _calculate_sha256(file_path),
        "size": file_path.stat().st_size,
    }


def _write_recovery_manifest(backup_subdir: Path, artifacts: List[Dict[str, Any]]) -> Path:
    manifest_path = backup_subdir / RECOVERY_MANIFEST_NAME
    temp_path = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    payload = {
        "schema_version": RECOVERY_MANIFEST_SCHEMA,
        "hash_algorithm": "sha256",
        "complete": True,
        "artifacts": sorted(artifacts, key=lambda item: cast(str, item["path"])),
    }
    try:
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(manifest_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return manifest_path


def _validate_recovery_manifest(
    recovery_manifest: Any,
    *,
    backup: Path,
    dest: Path,
) -> List[tuple[Path, Path]]:
    if (
        not isinstance(recovery_manifest, dict)
        or set(recovery_manifest) != RECOVERY_MANIFEST_FIELDS
    ):
        raise ValueError("recovery manifest contains unknown or missing fields")
    if recovery_manifest.get("schema_version") != RECOVERY_MANIFEST_SCHEMA:
        raise ValueError("unsupported recovery manifest schema")
    if recovery_manifest.get("hash_algorithm") != "sha256":
        raise ValueError("unsupported recovery manifest hash algorithm")
    if recovery_manifest.get("complete") is not True:
        raise ValueError("recovery manifest is not complete")
    artifacts = recovery_manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("recovery manifest artifacts must be a list")

    seen_paths: set[str] = set()
    restore_files: List[tuple[Path, Path]] = []
    backup_resolved = backup.resolve(strict=True)
    dest_resolved = dest.resolve(strict=False)
    for artifact in artifacts:
        path, included = _validate_recovery_artifact(artifact)
        identity = path.casefold()
        if identity in seen_paths:
            raise ValueError(f"duplicate recovery artifact path: {path}")
        seen_paths.add(identity)
        if not included:
            continue

        relative_path = Path(*PurePosixPath(path).parts)
        source_file = backup / relative_path
        if not source_file.is_file():
            raise ValueError(f"recovery artifact missing: {path}")
        _assert_contained_without_reparse(backup, source_file)
        try:
            source_file.resolve(strict=True).relative_to(backup_resolved)
        except ValueError as exc:
            raise ValueError(f"recovery artifact resolves outside backup: {path}") from exc
        if source_file.stat().st_size != artifact["size"]:
            raise ValueError(f"recovery artifact size mismatch: {path}")
        if _calculate_sha256(source_file) != artifact["sha256"]:
            raise ValueError(f"recovery artifact hash mismatch: {path}")

        destination_file = dest / relative_path
        try:
            destination_file.resolve(strict=False).relative_to(dest_resolved)
        except ValueError as exc:
            raise ValueError(f"recovery destination escapes requested root: {path}") from exc
        restore_files.append((source_file, destination_file))
    return restore_files


def create_backup(
    dest_path: str,
    full: bool = False,
    dry_run: bool = False,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    创建 Life Index 数据备份

    Args:
        dest_path: 备份目标路径
        full: 是否执行全量备份（默认增量）
        dry_run: 模拟运行，不实际复制文件
        exclude_patterns: 排除的文件模式列表

    Returns:
        {
            "success": bool,
            "backup_path": str,
            "files_backed_up": int,
            "files_skipped": int,
            "errors": List[str],
            "manifest_path": str,
            "recovery_manifest_path": str,
        }
    """
    result: Dict[str, Any] = {
        "success": False,
        "backup_path": "",
        "files_backed_up": 0,
        "files_skipped": 0,
        "errors": [],
        "manifest_path": "",
        "recovery_manifest_path": "",
    }

    try:
        dest = Path(dest_path)
        data_root = get_user_data_dir()
        if not dry_run:
            dest.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = _create_backup_subdir(dest, timestamp, dry_run=dry_run)
        result["backup_path"] = str(backup_subdir)

        # 加载之前的备份清单（用于增量备份）
        manifest: Dict[str, Any] = load_backup_manifest(dest)
        manifest.setdefault("files", {})
        recovery_artifacts: List[Dict[str, Any]] = []

        # 默认排除模式
        caller_exclude_patterns = list(exclude_patterns or [])
        active_exclude_patterns = caller_exclude_patterns + [
            ".life-index-backup-manifest.json",
            "*.tmp",
            ".cache",
        ]

        def should_exclude(file_path: Path) -> bool:
            """检查文件是否应该被排除"""
            for pattern in active_exclude_patterns:
                if pattern in str(file_path):
                    return True
            return False

        canonical_inventory = _canonical_source_inventory(data_root)
        if full:
            for relative_path, file_path in canonical_inventory.items():
                matched_pattern = next(
                    (
                        pattern
                        for pattern in caller_exclude_patterns
                        if pattern in str(file_path) or pattern in relative_path
                    ),
                    None,
                )
                if matched_pattern is not None:
                    result["errors"].append(
                        "Canonical source cannot be excluded from a full backup: "
                        f"{relative_path} (matched caller pattern {matched_pattern!r})"
                    )
            if result["errors"]:
                return result

        def backup_directory(
            src_dir: Path,
            dest_subdir: str,
            *,
            default_classification: str,
        ) -> None:
            """备份单个目录"""
            if not src_dir.exists():
                logger.warning(f"源目录不存在: {src_dir}")
                return

            backup_dest = backup_subdir / dest_subdir
            if not dry_run:
                backup_dest.mkdir(parents=True, exist_ok=True)

            for file_path in src_dir.rglob("*"):
                if file_path.is_file() and not should_exclude(file_path):
                    try:
                        _assert_contained_without_reparse(src_dir, file_path)
                        # 计算相对路径
                        rel_path = file_path.relative_to(src_dir)
                        dest_file = backup_dest / rel_path

                        # 增量备份：检查文件是否已更改
                        file_hash = calculate_file_hash(file_path)
                        file_key = f"{dest_subdir}/{rel_path}"

                        if not full and file_key in manifest.get("files", {}):
                            old_hash = manifest["files"][file_key].get("hash", "")
                            if old_hash == file_hash:
                                result["files_skipped"] += 1
                                continue

                        if not dry_run:
                            dest_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, dest_file)

                        result["files_backed_up"] += 1

                        # 更新清单
                        manifest["files"][file_key] = {
                            "hash": file_hash,
                            "mtime": file_path.stat().st_mtime,
                            "size": file_path.stat().st_size,
                        }
                        if not dry_run:
                            classification = default_classification
                            if dest_subdir == "Journals" and _is_generated_journal_artifact(
                                rel_path
                            ):
                                classification = "rebuildable_derived"
                            recovery_artifacts.append(
                                _artifact_record(
                                    path=file_key,
                                    file_path=dest_file,
                                    classification=classification,
                                    included=True,
                                )
                            )

                    except (IOError, OSError, ValueError) as e:
                        error_msg = f"备份失败 {file_path}: {e}"
                        logger.error(error_msg)
                        result["errors"].append(error_msg)

        # 备份各个目录
        logger.info("备份日志文件...")
        backup_directory(
            get_journals_dir(),
            "Journals",
            default_classification=CANONICAL_SOURCE,
        )

        logger.info("备份索引文件...")
        backup_directory(
            get_by_topic_dir(),
            "by-topic",
            default_classification=REBUILDABLE_DERIVED,
        )

        logger.info("备份附件文件...")
        backup_directory(
            get_attachments_dir(),
            "attachments",
            default_classification=CANONICAL_SOURCE,
        )

        entity_graph = get_user_data_dir() / "entity_graph.yaml"
        if entity_graph.is_file() and not should_exclude(entity_graph):
            try:
                _assert_contained_without_reparse(data_root, entity_graph)
                destination = backup_subdir / "entity_graph.yaml"
                if not dry_run:
                    shutil.copy2(entity_graph, destination)
                    recovery_artifacts.append(
                        _artifact_record(
                            path="entity_graph.yaml",
                            file_path=destination,
                            classification=CANONICAL_SOURCE,
                            included=True,
                        )
                    )
                result["files_backed_up"] += 1
                manifest["files"]["entity_graph.yaml"] = {
                    "hash": calculate_file_hash(entity_graph),
                    "mtime": entity_graph.stat().st_mtime,
                    "size": entity_graph.stat().st_size,
                }
            except (IOError, OSError, ValueError) as e:
                error_msg = f"备份失败 {entity_graph}: {e}"
                logger.error(error_msg)
                result["errors"].append(error_msg)

        index_dir = get_user_data_dir() / ".index"
        if index_dir.exists():
            for file_path in sorted(index_dir.rglob("*")):
                if file_path.is_file():
                    try:
                        _assert_contained_without_reparse(index_dir, file_path)
                        recovery_artifacts.append(
                            _artifact_record(
                                path=f".index/{file_path.relative_to(index_dir).as_posix()}",
                                file_path=file_path,
                                classification=REBUILDABLE_DERIVED,
                                included=False,
                            )
                        )
                    except (IOError, OSError, ValueError) as e:
                        error_msg = f"备份源路径校验失败 {file_path}: {e}"
                        logger.error(error_msg)
                        result["errors"].append(error_msg)

        # 保存备份清单
        if not dry_run and not result["errors"]:
            if full:
                try:
                    manifest_canonical_paths = {
                        cast(str, artifact["path"])
                        for artifact in recovery_artifacts
                        if artifact["classification"] == CANONICAL_SOURCE
                    }
                    expected_canonical_paths = set(canonical_inventory)
                    if manifest_canonical_paths != expected_canonical_paths:
                        missing = sorted(expected_canonical_paths - manifest_canonical_paths)
                        unexpected = sorted(manifest_canonical_paths - expected_canonical_paths)
                        raise RuntimeError(
                            "canonical source inventory mismatch: "
                            f"missing={missing}, unexpected={unexpected}"
                        )
                    recovery_manifest_path = _write_recovery_manifest(
                        backup_subdir, recovery_artifacts
                    )
                    result["recovery_manifest_path"] = str(recovery_manifest_path)
                except (IOError, OSError, RuntimeError) as e:
                    error_msg = f"无法保存恢复清单 {backup_subdir / RECOVERY_MANIFEST_NAME}: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)

        if not dry_run and not result["errors"]:
            backup_record: Dict[str, Any] = {
                "timestamp": timestamp,
                "type": "full" if full else "incremental",
                "path": str(backup_subdir),
                "files_backed_up": result["files_backed_up"],
                "files_skipped": result["files_skipped"],
            }
            if "backups" not in manifest:
                manifest["backups"] = []
            backups = cast(List[Dict[str, Any]], manifest["backups"])
            backups.append(backup_record)
            if save_backup_manifest(dest, manifest):
                result["manifest_path"] = str(dest / ".life-index-backup-manifest.json")
            else:
                result["errors"].append(
                    f"无法保存备份清单: {dest / '.life-index-backup-manifest.json'}"
                )

        result["success"] = len(result["errors"]) == 0

        logger.info(
            f"备份完成: {result['files_backed_up']} 个文件已备份, "
            f"{result['files_skipped']} 个文件已跳过"
        )

    except (OSError, IOError, RuntimeError) as e:
        error_msg = f"备份过程出错: {e}"
        logger.error(error_msg)
        result["errors"].append(error_msg)

    return result


def list_backups(backup_dir: Path) -> List[Dict[str, Any]]:
    """列出所有备份记录"""
    manifest = load_backup_manifest(backup_dir)
    return cast(List[Dict[str, Any]], manifest.get("backups", []))


def restore_backup(
    backup_path: str,
    dest_path: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    从备份恢复数据

    Args:
        backup_path: 备份目录路径
        dest_path: 恢复目标路径（默认 get_user_data_dir()）
        dry_run: 模拟运行

    Returns:
        恢复结果
    """
    result: Dict[str, Any] = {
        "success": False,
        "files_restored": 0,
        "errors": [],
        "restore_mode": "unknown",
        "recovery_manifest_verified": False,
        "warnings": [],
    }

    try:
        backup = Path(backup_path)
        dest = Path(dest_path) if dest_path else get_user_data_dir()

        if not backup.exists():
            cast(List[str], result["errors"]).append(f"备份目录不存在: {backup}")
            return result
        if not backup.is_dir() or _is_reparse_point(backup):
            cast(List[str], result["errors"]).append(
                f"Restore backup root must be a real directory, not a reparse point: {backup}"
            )
            return result

        if dest.exists():
            if not dest.is_dir() or _is_reparse_point(dest):
                cast(List[str], result["errors"]).append(
                    f"Restore destination must be a real directory, not a reparse point: {dest}"
                )
                return result
            if any(dest.iterdir()):
                cast(List[str], result["errors"]).append(
                    f"Restore destination is nonempty; refusing overlay before mutation: {dest}"
                )
                return result

        recovery_manifest_path = backup / RECOVERY_MANIFEST_NAME
        restore_files: List[tuple[Path, Path]] = []
        if recovery_manifest_path.exists():
            try:
                recovery_manifest = json.loads(recovery_manifest_path.read_text(encoding="utf-8"))
                restore_files = _validate_recovery_manifest(
                    recovery_manifest,
                    backup=backup,
                    dest=dest,
                )
                result["restore_mode"] = "manifest_verified"
                result["recovery_manifest_verified"] = True
            except (IOError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                cast(List[str], result["errors"]).append(
                    f"恢复清单验证失败 {recovery_manifest_path}: {e}"
                )
                return result
        else:
            result["restore_mode"] = "legacy_unverified"
            cast(List[str], result["warnings"]).append(LEGACY_RESTORE_WARNING)
            for subdir in ["Journals", "by-topic", "attachments"]:
                src = backup / subdir
                if src.exists():
                    if not src.is_dir() or _is_reparse_point(src):
                        cast(List[str], result["errors"]).append(
                            f"Legacy restore path is not a real directory: {src}"
                        )
                        return result
                    for file_path in src.rglob("*"):
                        if file_path.is_file():
                            try:
                                _assert_contained_without_reparse(backup, file_path)
                                destination_file = dest / subdir / file_path.relative_to(src)
                                _assert_destination_contained_without_reparse(
                                    dest, destination_file
                                )
                                restore_files.append((file_path, destination_file))
                            except (OSError, ValueError) as e:
                                cast(List[str], result["errors"]).append(
                                    f"Legacy restore path validation failed {file_path}: {e}"
                                )
                                return result

        if dry_run:
            result["files_restored"] = len(restore_files)
            result["success"] = True
            return result

        destination_existed = dest.exists()
        created_directories: List[Path] = []
        attempted_files: List[Path] = []

        def ensure_directory(directory: Path) -> None:
            missing: List[Path] = []
            current = directory
            while not current.exists():
                missing.append(current)
                if current == dest:
                    break
                current = current.parent
            _assert_destination_contained_without_reparse(dest, directory)
            directory.mkdir(parents=True, exist_ok=True)
            created_directories.extend(reversed(missing))

        for file_path, dest_file in restore_files:
            try:
                _assert_contained_without_reparse(backup, file_path)
                _assert_destination_contained_without_reparse(dest, dest_file)
                ensure_directory(dest_file.parent)
                attempted_files.append(dest_file)
                shutil.copy2(file_path, dest_file)
                result["files_restored"] += 1
            except (IOError, OSError, ValueError) as e:
                error_msg = f"恢复失败 {file_path}: {e}"
                logger.error(error_msg)
                cast(List[str], result["errors"]).append(error_msg)
                rollback_errors: List[str] = []
                for attempted_file in reversed(attempted_files):
                    try:
                        attempted_file.unlink(missing_ok=True)
                    except OSError as rollback_error:
                        rollback_errors.append(f"{attempted_file}: {rollback_error}")
                for created_directory in sorted(
                    set(created_directories), key=lambda path: len(path.parts), reverse=True
                ):
                    try:
                        created_directory.rmdir()
                    except FileNotFoundError:
                        pass
                    except OSError as rollback_error:
                        rollback_errors.append(f"{created_directory}: {rollback_error}")
                if not destination_existed and dest.exists():
                    try:
                        dest.rmdir()
                    except OSError as rollback_error:
                        rollback_errors.append(f"{dest}: {rollback_error}")
                result["files_restored"] = 0
                if rollback_errors:
                    cast(List[str], result["errors"]).append(
                        "Restore compensation failed: " + "; ".join(rollback_errors)
                    )
                return result

        result["success"] = True
        logger.info(f"恢复完成: {result['files_restored']} 个文件已恢复")

    except (OSError, IOError, RuntimeError) as e:
        error_msg = f"恢复过程出错: {e}"
        logger.error(error_msg)
        cast(List[str], result["errors"]).append(error_msg)

    return result


__all__ = [
    "create_backup",
    "restore_backup",
    "list_backups",
    "RECOVERY_MANIFEST_NAME",
    "RECOVERY_MANIFEST_SCHEMA",
]
