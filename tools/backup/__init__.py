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
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from ..lib.paths import get_journals_dir, get_by_topic_dir, get_attachments_dir, get_user_data_dir
from ..lib.logger import get_logger

logger = get_logger(__name__)

RECOVERY_MANIFEST_NAME = ".life-index-recovery-manifest.json"
RECOVERY_MANIFEST_SCHEMA = "life-index.backup-manifest.v1"


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
        if not dry_run:
            dest.mkdir(parents=True, exist_ok=True)

        # 创建带时间戳的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = dest / f"life-index-backup-{timestamp}"
        if not dry_run:
            backup_subdir.mkdir(parents=True, exist_ok=True)

        result["backup_path"] = str(backup_subdir)

        # 加载之前的备份清单（用于增量备份）
        manifest: Dict[str, Any] = load_backup_manifest(dest) if not full else {"files": {}}
        recovery_artifacts: List[Dict[str, Any]] = []

        # 默认排除模式
        exclude_patterns = exclude_patterns or []
        exclude_patterns.extend(
            [
                ".life-index-backup-manifest.json",
                "*.tmp",
                ".cache",
            ]
        )

        def should_exclude(file_path: Path) -> bool:
            """检查文件是否应该被排除"""
            for pattern in exclude_patterns:
                if pattern in str(file_path):
                    return True
            return False

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

                    except (IOError, OSError) as e:
                        error_msg = f"备份失败 {file_path}: {e}"
                        logger.error(error_msg)
                        result["errors"].append(error_msg)

        # 备份各个目录
        logger.info("备份日志文件...")
        backup_directory(
            get_journals_dir(),
            "Journals",
            default_classification="canonical_source",
        )

        logger.info("备份索引文件...")
        backup_directory(
            get_by_topic_dir(),
            "by-topic",
            default_classification="rebuildable_derived",
        )

        logger.info("备份附件文件...")
        backup_directory(
            get_attachments_dir(),
            "attachments",
            default_classification="canonical_source",
        )

        entity_graph = get_user_data_dir() / "entity_graph.yaml"
        if entity_graph.is_file() and not should_exclude(entity_graph):
            try:
                destination = backup_subdir / "entity_graph.yaml"
                if not dry_run:
                    shutil.copy2(entity_graph, destination)
                    recovery_artifacts.append(
                        _artifact_record(
                            path="entity_graph.yaml",
                            file_path=destination,
                            classification="canonical_source",
                            included=True,
                        )
                    )
                result["files_backed_up"] += 1
                manifest["files"]["entity_graph.yaml"] = {
                    "hash": calculate_file_hash(entity_graph),
                    "mtime": entity_graph.stat().st_mtime,
                    "size": entity_graph.stat().st_size,
                }
            except (IOError, OSError) as e:
                error_msg = f"备份失败 {entity_graph}: {e}"
                logger.error(error_msg)
                result["errors"].append(error_msg)

        index_dir = get_user_data_dir() / ".index"
        if index_dir.exists():
            for file_path in sorted(index_dir.rglob("*")):
                if file_path.is_file():
                    recovery_artifacts.append(
                        _artifact_record(
                            path=f".index/{file_path.relative_to(index_dir).as_posix()}",
                            file_path=file_path,
                            classification="rebuildable_derived",
                            included=False,
                        )
                    )

        # 保存备份清单
        if not dry_run and not result["errors"]:
            if full:
                try:
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
    }

    try:
        backup = Path(backup_path)
        dest = Path(dest_path) if dest_path else get_user_data_dir()

        if not backup.exists():
            cast(List[str], result["errors"]).append(f"备份目录不存在: {backup}")
            return result

        if dest.exists() and any(dest.iterdir()):
            cast(List[str], result["errors"]).append(
                f"Restore destination is nonempty; refusing overlay before mutation: {dest}"
            )
            return result

        recovery_manifest_path = backup / RECOVERY_MANIFEST_NAME
        restore_files: List[tuple[Path, Path]] = []
        if recovery_manifest_path.exists():
            try:
                recovery_manifest = json.loads(recovery_manifest_path.read_text(encoding="utf-8"))
                if recovery_manifest.get("schema_version") != RECOVERY_MANIFEST_SCHEMA:
                    raise ValueError("unsupported recovery manifest schema")
                if recovery_manifest.get("hash_algorithm") != "sha256":
                    raise ValueError("unsupported recovery manifest hash algorithm")
                if recovery_manifest.get("complete") is not True:
                    raise ValueError("recovery manifest is not complete")
                for artifact in recovery_manifest.get("artifacts", []):
                    if not artifact.get("included"):
                        continue
                    relative_path = Path(str(artifact["path"]))
                    if relative_path.is_absolute() or ".." in relative_path.parts:
                        raise ValueError(f"unsafe recovery artifact path: {relative_path}")
                    source_file = backup / relative_path
                    if not source_file.is_file():
                        raise ValueError(f"recovery artifact missing: {relative_path.as_posix()}")
                    actual_hash = _calculate_sha256(source_file)
                    if actual_hash != artifact.get("sha256"):
                        raise ValueError(
                            f"recovery artifact hash mismatch: {relative_path.as_posix()}"
                        )
                    restore_files.append((source_file, dest / relative_path))
            except (IOError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                cast(List[str], result["errors"]).append(
                    f"恢复清单验证失败 {recovery_manifest_path}: {e}"
                )
                return result
        else:
            for subdir in ["Journals", "by-topic", "attachments"]:
                src = backup / subdir
                if src.exists():
                    for file_path in src.rglob("*"):
                        if file_path.is_file():
                            restore_files.append(
                                (file_path, dest / subdir / file_path.relative_to(src))
                            )

        for file_path, dest_file in restore_files:
            try:
                if not dry_run:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest_file)
                result["files_restored"] += 1
            except (IOError, OSError) as e:
                error_msg = f"恢复失败 {file_path}: {e}"
                logger.error(error_msg)
                cast(List[str], result["errors"]).append(error_msg)

        result["success"] = len(cast(List[str], result["errors"])) == 0
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
